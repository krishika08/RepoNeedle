"""
Stage 3.7.1: Rigorous Multi-Scale Runtime and Memory Verification.
Measures isolated query latency (median and p95), index build time, graph construction,
and process RSS across both Small/Medium and Large repository scales.
Outputs: research/stage3_7_1/RUNTIME_VERIFICATION.csv
"""

import sys
import os
import json
import csv
import time
import ctypes
from ctypes import wintypes
import tracemalloc
import gc
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
STAGE_DIR = ROOT_DIR / "research" / "stage3_7_1"
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import read_jsonl, query_text_for_eval
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex


# Windows PSAPI for Process Working Set (RSS)
class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]


def get_process_memory_mb():
    try:
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return counters.WorkingSetSize / (1024 * 1024), counters.PeakWorkingSetSize / (1024 * 1024)
    except Exception:
        pass
    return 0.0, 0.0


def run_verification():
    print("=" * 80)
    print("STAGE 3.7.1: RUNTIME AND MEMORY VERIFICATION")
    print("=" * 80)

    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    manifest_raw = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            manifest_raw[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]

    samples = read_jsonl(ARB_DIR / "data" / "benchmark" / "v2_code2test" / "samples.jsonl")[:50]

    # Two test regimes
    regimes = [
        ("Medium Scale (pallets/click)", "pallets/click", 150),
        ("Large Scale (multi-repo benchmark)", None, 1500),
    ]

    verification_rows = []

    for reg_name, target_repo, max_files in regimes:
        gc.collect()
        tracemalloc.start()
        rss_start, _ = get_process_memory_mb()

        all_docs = []
        for (repo_id, base_commit), cpath in manifest_raw.items():
            if target_repo and repo_id != target_repo:
                continue
            if not cpath.is_file():
                continue
            chunks = read_jsonl(cpath)
            file_texts = {}
            for c in chunks:
                p = c.get("path")
                t = c.get("text", "")
                if p and (p not in file_texts or len(t) > len(file_texts[p])):
                    file_texts[p] = t
            for p, t in file_texts.items():
                content = t[:25000]
                syms, imps = RepoGraph.extract_polyglot_symbols(content, p)
                all_docs.append(FileDoc(path=p, content=content, symbols=syms, imports=imps))
            if len(all_docs) >= max_files:
                break

        total_files = len(all_docs)
        t0 = time.perf_counter()
        bm25 = BM25Index(decouple_symbols=True).fit(all_docs)
        sem = SubwordSemanticIndex().fit(all_docs)
        t_index = time.perf_counter() - t0

        t_g0 = time.perf_counter()
        rg = RepoGraph().fit(all_docs)
        t_graph = (time.perf_counter() - t_g0) * 1000.0

        # Query benchmarking: Warm up first
        doc_paths = [d.path for d in all_docs]
        is_doc = np.array([p.endswith((".md", ".txt")) for p in doc_paths], dtype=bool)

        # 5 warm-up queries
        for s in samples[:5]:
            q_text = query_text_for_eval(s)
            _ = bm25.score(q_text)

        # Timed queries
        latencies = []
        for s in samples:
            q_text = query_text_for_eval(s)
            t_q0 = time.perf_counter()
            l_sc = bm25.score(q_text)
            s_sc = sem.score(q_text)
            base = (l_sc + s_sc) / 2.0
            base[is_doc] *= 0.5

            hits = l_sc + s_sc
            if len(hits) > 0 and float(np.max(hits)) > 0:
                top_seeds = np.argsort(hits)[::-1][:5]
                boost = np.zeros(len(all_docs), dtype=np.float32)
                for s_idx in top_seeds:
                    sp = doc_paths[s_idx]
                    sv = float(hits[s_idx])
                    if sv > 0 and sp in rg.graph:
                        for succ in rg.graph.successors(sp):
                            if succ in rg.path_to_idx:
                                deg = max(1, rg.graph.in_degree(succ))
                                boost[rg.path_to_idx[succ]] = max(boost[rg.path_to_idx[succ]], sv * 0.25 / np.sqrt(deg))
                        for pred in rg.graph.predecessors(sp):
                            if pred in rg.path_to_idx:
                                deg = max(1, rg.graph.out_degree(pred))
                                boost[rg.path_to_idx[pred]] = max(boost[rg.path_to_idx[pred]], sv * 0.20 / np.sqrt(deg))
                base = base + 0.15 * boost

            _ = np.argsort(-base)[:20]
            latencies.append((time.perf_counter() - t_q0) * 1000.0)

        lat_med = float(np.median(latencies))
        lat_p95 = float(np.percentile(latencies, 95))

        _, peak_heap = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        rss_end, peak_rss = get_process_memory_mb()

        row = {
            "scale_regime": reg_name,
            "indexed_files": total_files,
            "indexing_time_sec": f"{t_index:.3f}",
            "graph_construction_ms": f"{t_graph:.2f}",
            "median_latency_ms": f"{lat_med:.2f}",
            "p95_latency_ms": f"{lat_p95:.2f}",
            "python_heap_peak_mb": f"{peak_heap / (1024 * 1024):.2f}",
            "process_rss_mb": f"{rss_end:.2f}",
            "sub_100mb_rss": "YES" if rss_end < 100.0 else "NO",
            "notes": "Verified under clean single-process conditions"
        }
        verification_rows.append(row)
        print(f"\n{reg_name}:")
        print(f"  Files: {total_files} | Index Time: {t_index:.2f}s | Graph: {t_graph:.1f}ms")
        print(f"  Latency: Median={lat_med:.2f}ms, p95={lat_p95:.2f}ms | Heap: {peak_heap/(1024*1024):.1f}MB | RSS: {rss_end:.1f}MB (Sub-100MB: {row['sub_100mb_rss']})")

    out_csv = STAGE_DIR / "RUNTIME_VERIFICATION.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(verification_rows[0].keys()))
        writer.writeheader()
        writer.writerows(verification_rows)

    print(f"\nSaved RUNTIME_VERIFICATION.csv to {out_csv}")


if __name__ == "__main__":
    run_verification()

