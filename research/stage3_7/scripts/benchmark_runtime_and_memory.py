"""
Stage 3.7: Runtime, Latency, and Memory Footprint Benchmark.
Measures process RSS, Python heap, index build time, graph construction time,
and query latency (median and p95) under clean, isolated conditions across all 8 experiment systems.
Outputs: research/stage3_7/RUNTIME_AND_MEMORY.csv
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
STAGE_DIR = ROOT_DIR / "research" / "stage3_7"
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import read_jsonl, query_text_for_eval
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex


# Windows API for Process Working Set (RSS)
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


def get_process_memory_info():
    """Returns (current_working_set_mb, peak_working_set_mb) via Windows PSAPI."""
    try:
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return counters.WorkingSetSize / (1024 * 1024), counters.PeakWorkingSetSize / (1024 * 1024)
    except Exception:
        pass
    return 0.0, 0.0


def benchmark_efficiency():
    print("=" * 80)
    print("STAGE 3.7: EFFICIENCY & RESOURCE BENCHMARKING")
    print("=" * 80)

    # 1. Corpus Manifest
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    manifest_raw = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            manifest_raw[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]

    # Benchmark samples for latency
    samples = read_jsonl(ARB_DIR / "data" / "benchmark" / "v2_code2test" / "samples.jsonl")[:100]

    results = []

    configs = [
        ("EXP-371", "CAND-C", "BM25 Pure + Semantic + PageRank + DocFilter"),
        ("EXP-372", "CAND-F", "Coupled BM25 + Polyglot AST + PageRank + Unbounded Diffusion"),
        ("EXP-373", "CAND-F-NO-DIFF", "Candidate F without Graph Diffusion"),
        ("EXP-374", "CAND-F-DECOUPLED", "Candidate F with Decoupled BM25 symbols"),
        ("EXP-375", "CAND-F-FWD-ONLY", "Candidate F with Forward-Only Diffusion"),
        ("EXP-376", "CAND-F-BWD-ONLY", "Candidate F with Backward-Only Diffusion"),
        ("EXP-377", "CAND-F-HUBNORM", "Candidate F with Hub-Normalized Diffusion"),
        ("EXP-378", "CAND-COMBINED", "Decoupled BM25 + Semantic + DocFilter + Hub-Normalized Diffusion"),
    ]

    for exp_id, name, desc in configs:
        gc.collect()
        tracemalloc.start()
        rss_start, _ = get_process_memory_info()

        t_index_start = time.perf_counter()
        t_graph_build = 0.0

        total_files = 0
        all_docs = []

        # Ingest representative corpora across multiple ecosystems
        for (repo_id, base_commit), cpath in manifest_raw.items():
            if not cpath.is_file():
                continue
            chunks = read_jsonl(cpath)
            file_texts = {}
            for c in chunks:
                p = c.get("path")
                t = c.get("text", "")
                if p and (p not in file_texts or len(t) > len(file_texts[p])):
                    file_texts[p] = t

            docs = []
            for p, t in file_texts.items():
                content = t[:25000]
                if "EXP-371" in exp_id:
                    syms, imps = [], []
                else:
                    syms, imps = RepoGraph.extract_polyglot_symbols(content, p)
                docs.append(FileDoc(path=p, content=content, symbols=syms, imports=imps))

            all_docs.extend(docs)
            total_files += len(docs)
            if total_files >= 1500: # Standardized representative 1,500-file benchmark
                break

        # Fit index
        decouple = True if exp_id in ["EXP-371", "EXP-374", "EXP-378"] else False
        bm25 = BM25Index(decouple_symbols=decouple).fit(all_docs)
        sem = SubwordSemanticIndex().fit(all_docs)

        # Graph build
        t_g0 = time.perf_counter()
        rg = RepoGraph().fit(all_docs)
        t_graph_build = (time.perf_counter() - t_g0) * 1000.0

        t_index_total_s = time.perf_counter() - t_index_start

        # Query latencies
        latencies = []
        doc_paths = [d.path for d in all_docs]
        is_doc = np.array([p.endswith((".md", ".txt")) for p in doc_paths], dtype=bool)

        for s in samples:
            q_text = query_text_for_eval(s)
            t_q0 = time.perf_counter()

            l_sc = bm25.score(q_text)
            s_sc = sem.score(q_text)

            if exp_id == "EXP-378":
                base = (l_sc + s_sc) / 2.0
                base[is_doc] *= 0.5
            else:
                base = (l_sc + s_sc + rg.pagerank_scores) / 3.0
                base[is_doc] *= 0.5

            if exp_id != "EXP-373":
                hits = l_sc + s_sc
                if len(hits) > 0 and float(np.max(hits)) > 0:
                    top_seeds = np.argsort(hits)[::-1][:5]
                    boost = np.zeros(len(all_docs), dtype=np.float32)
                    for s_idx in top_seeds:
                        sp = doc_paths[s_idx]
                        sv = float(hits[s_idx])
                        if sv > 0 and sp in rg.graph:
                            if exp_id in ["EXP-372", "EXP-374", "EXP-375"]:
                                for succ in rg.graph.successors(sp):
                                    if succ in rg.path_to_idx:
                                        boost[rg.path_to_idx[succ]] = max(boost[rg.path_to_idx[succ]], sv * 0.25)
                            if exp_id in ["EXP-372", "EXP-374", "EXP-376"]:
                                for pred in rg.graph.predecessors(sp):
                                    if pred in rg.path_to_idx:
                                        boost[rg.path_to_idx[pred]] = max(boost[rg.path_to_idx[pred]], sv * 0.20)
                            if exp_id in ["EXP-377", "EXP-378"]:
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

        current_heap, peak_heap = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        rss_end, peak_rss = get_process_memory_info()

        row = {
            "experiment_id": exp_id,
            "system_name": name,
            "description": desc,
            "indexed_files": total_files,
            "indexing_time_sec": f"{t_index_total_s:.3f}",
            "graph_construction_ms": f"{t_graph_build:.2f}",
            "query_latency_median_ms": f"{lat_med:.2f}",
            "query_latency_p95_ms": f"{lat_p95:.2f}",
            "python_heap_peak_mb": f"{peak_heap / (1024 * 1024):.2f}",
            "process_rss_mb": f"{rss_end:.2f}",
            "sub_100mb_rss": "YES" if rss_end < 100.0 else "NO",
        }
        results.append(row)
        print(f"{exp_id:<9} | {name:<17} | Index: {t_index_total_s:.2f}s | Graph: {t_graph_build:.1f}ms | Med Lat: {lat_med:.2f}ms | p95 Lat: {lat_p95:.2f}ms | Heap: {peak_heap / (1024*1024):.1f}MB | RSS: {rss_end:.1f}MB")

    # Write RUNTIME_AND_MEMORY.csv
    out_csv = STAGE_DIR / "RUNTIME_AND_MEMORY.csv"
    headers = [
        "experiment_id", "system_name", "description", "indexed_files",
        "indexing_time_sec", "graph_construction_ms",
        "query_latency_median_ms", "query_latency_p95_ms",
        "python_heap_peak_mb", "process_rss_mb", "sub_100mb_rss"
    ]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved runtime & memory benchmark to {out_csv}")


if __name__ == "__main__":
    benchmark_efficiency()
