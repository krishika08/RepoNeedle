"""
Stage 3.8: Isolated Runtime and Memory Benchmark.

Measures:
  - Repository index construction time (BM25 + Subword Semantic + RepoGraph).
  - Graph construction time.
  - Query latency (median, p95, p99).
  - Retained index size in memory (tracemalloc / sys.getsizeof).
  - Process RSS memory (psutil).

Outputs:
  - research/stage3_8/RUNTIME_AND_MEMORY.csv
"""

import sys
import os
import json
import csv
import time
import tracemalloc
import ctypes
from ctypes import wintypes
from pathlib import Path
from collections import defaultdict
import numpy as np

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

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
STAGE_DIR = ROOT_DIR / "research" / "stage3_8"
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import read_jsonl, query_text_for_eval
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex


def benchmark_runtime_and_memory():
    print("=" * 80)
    print("STAGE 3.8: RUNTIME & MEMORY PROFILING")
    print("=" * 80)

    rss_start_mb, _ = get_process_memory_info()
    print(f"Initial process RSS: {rss_start_mb:.2f} MB")

    # Select representative repositories
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    manifest_raw = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            manifest_raw[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]

    subsets_def = [
        ("code2test", ARB_DIR / "data" / "benchmark" / "v2_code2test" / "samples.jsonl"),
        ("comment2context", ARB_DIR / "data" / "benchmark" / "v2_comment2context" / "samples.jsonl"),
        ("trace2code", ARB_DIR / "data" / "benchmark" / "v2_trace2code" / "samples.jsonl"),
        ("edit2ripple", ARB_DIR / "data" / "benchmark" / "v2_edit2ripple" / "samples.jsonl"),
    ]

    all_samples = []
    for _, spath in subsets_def:
        for r in read_jsonl(spath):
            all_samples.append(r)

    by_repo = defaultdict(list)
    for s in all_samples:
        by_repo[s["repo"]].append(s)

    # Select top 5 diverse repos
    target_repos = ["pallets/click", "clap-rs/clap", "psf/requests", "expressjs/express", "gin-gonic/gin"]
    benchmark_results = []

    for r_name in target_repos:
        samples = by_repo.get(r_name, [])
        if not samples:
            continue
        first_sample = samples[0]
        base_commit = first_sample["base_commit"]
        chunks_path = manifest_raw.get((r_name, base_commit))
        if not chunks_path or not chunks_path.is_file():
            continue

        chunks = read_jsonl(chunks_path)
        file_texts = {}
        for c in chunks:
            p = c.get("path")
            t = c.get("text", "")
            if p and (p not in file_texts or len(t) > len(file_texts[p])):
                file_texts[p] = t

        num_files = len(file_texts)
        total_chars = sum(len(t) for t in file_texts.values())

        tracemalloc.start()
        t0 = time.perf_counter()

        # Build Docs
        docs = []
        for p, t in file_texts.items():
            content = t[:25000]
            syms, imps = RepoGraph.extract_polyglot_symbols(content, p)
            docs.append(FileDoc(path=p, content=content, symbols=syms, imports=imps))

        # Build Indices
        t_bm25_start = time.perf_counter()
        bm25 = BM25Index(decouple_symbols=True).fit(docs)
        t_bm25 = (time.perf_counter() - t_bm25_start) * 1000.0

        t_subword_start = time.perf_counter()
        subword = SubwordSemanticIndex().fit(docs)
        t_subword = (time.perf_counter() - t_subword_start) * 1000.0

        t_graph_start = time.perf_counter()
        rg = RepoGraph().fit(docs)
        t_graph = (time.perf_counter() - t_graph_start) * 1000.0

        t_index_total = (time.perf_counter() - t0) * 1000.0
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        retained_index_mb = current_mem / (1024 * 1024)
        peak_index_mb = peak_mem / (1024 * 1024)
        rss_repo_mb, _ = get_process_memory_info()

        G = rg.graph
        num_nodes = G.number_of_nodes()
        num_edges = G.number_of_edges()

        # Query Latency Benchmarking
        doc_paths = [d.path for d in docs]
        path_to_idx = {d.path: i for i, d in enumerate(docs)}
        doc_paths_lower = [p.lower() for p in doc_paths]
        is_doc_file = np.array([
            any(seg in p for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or
            p.endswith((".md", ".rst", ".txt", ".adoc", ".html"))
            for p in doc_paths_lower
        ], dtype=bool)
        is_test_file = np.array(["test" in p or "spec" in p or p.startswith("tests/") for p in doc_paths_lower], dtype=bool)
        is_manifest_file = np.array([p.endswith(("cargo.toml", "pyproject.toml", "package.json", "go.mod", "setup.py")) for p in doc_paths_lower], dtype=bool)

        latencies_384 = []
        latencies_386 = []
        latencies_388 = []

        for s in samples:
            q_text = query_text_for_eval(s)
            q_lower = q_text.lower()
            t_type = s.get("_subset_name", "")
            query_is_test_seeking = ("test" in q_lower or "assert" in q_lower or "spec" in q_lower) and t_type != "trace2code"

            # Benchmark EXP-384
            t_q0 = time.perf_counter()
            lex = bm25.score(q_text)
            sm = subword.score(q_text)
            base = (lex + sm) / 2.0
            base[is_doc_file] *= 0.5
            hits = lex + sm
            boost_384 = np.zeros(len(docs), dtype=np.float32)
            if G.number_of_edges() > 0 and len(hits) > 0 and float(np.max(hits)) > 0:
                top_seeds = np.argsort(hits)[::-1][:5]
                for s_idx in top_seeds:
                    sp = doc_paths[s_idx]
                    sv = float(hits[s_idx])
                    if sv <= 0 or sp not in G:
                        continue
                    for succ in G.successors(sp):
                        if succ in path_to_idx:
                            n_idx = path_to_idx[succ]
                            in_deg = max(1, G.in_degree(succ))
                            boost_384[n_idx] = max(boost_384[n_idx], float(sv * 0.25 / np.sqrt(in_deg)))
                    for pred in G.predecessors(sp):
                        if pred in path_to_idx:
                            n_idx = path_to_idx[pred]
                            out_deg = max(1, G.out_degree(pred))
                            boost_384[n_idx] = max(boost_384[n_idx], float(sv * 0.20 / np.sqrt(out_deg)))
            sc_384 = base + 0.15 * boost_384
            _ = np.argsort(-sc_384)
            latencies_384.append((time.perf_counter() - t_q0) * 1000.0)

            # Benchmark EXP-386 (Edge-Gated)
            t_q1 = time.perf_counter()
            lex = bm25.score(q_text)
            sm = subword.score(q_text)
            base = (lex + sm) / 2.0
            base[is_doc_file] *= 0.5
            hits = lex + sm
            boost_386 = np.zeros(len(docs), dtype=np.float32)
            if G.number_of_edges() > 0 and len(hits) > 0 and float(np.max(hits)) > 0:
                top_seeds = np.argsort(hits)[::-1][:5]
                for s_idx in top_seeds:
                    sp = doc_paths[s_idx]
                    sv = float(hits[s_idx])
                    if sv <= 0 or sp not in G:
                        continue
                    for succ in G.successors(sp):
                        if succ in path_to_idx:
                            n_idx = path_to_idx[succ]
                            in_deg = max(1, G.in_degree(succ))
                            boost_386[n_idx] = max(boost_386[n_idx], float(sv * 0.25 / np.sqrt(in_deg)))
                    for pred in G.predecessors(sp):
                        if pred in path_to_idx:
                            n_idx = path_to_idx[pred]
                            out_deg = max(1, G.out_degree(pred))
                            bwd_raw = float(sv * 0.20 / np.sqrt(out_deg))
                            edge_mult = 1.0
                            if is_manifest_file[n_idx]:
                                edge_mult = 0.05
                            elif not query_is_test_seeking and is_test_file[n_idx] and not is_test_file[s_idx]:
                                edge_mult = 0.15
                            elif query_is_test_seeking and is_test_file[n_idx]:
                                edge_mult = 1.25
                            boost_386[n_idx] = max(boost_386[n_idx], bwd_raw * edge_mult)
            sc_386 = base + 0.15 * boost_386
            _ = np.argsort(-sc_386)
            latencies_386.append((time.perf_counter() - t_q1) * 1000.0)

        benchmark_results.append({
            "repo": r_name,
            "num_files": num_files,
            "total_chars": total_chars,
            "graph_nodes": num_nodes,
            "graph_edges": num_edges,
            "index_time_total_ms": f"{t_index_total:.2f}",
            "index_time_bm25_ms": f"{t_bm25:.2f}",
            "index_time_subword_ms": f"{t_subword:.2f}",
            "index_time_graph_ms": f"{t_graph:.2f}",
            "retained_index_mb": f"{retained_index_mb:.2f}",
            "peak_index_mb": f"{peak_index_mb:.2f}",
            "process_rss_mb": f"{rss_repo_mb:.2f}",
            "query_count": len(samples),
            "exp384_latency_median_ms": f"{np.median(latencies_384):.2f}",
            "exp384_latency_p95_ms": f"{np.percentile(latencies_384, 95):.2f}",
            "exp386_latency_median_ms": f"{np.median(latencies_386):.2f}",
            "exp386_latency_p95_ms": f"{np.percentile(latencies_386, 95):.2f}",
        })

    # Summary across all measured repos
    all_lats_384 = [float(row["exp384_latency_median_ms"]) for row in benchmark_results]
    all_lats_386 = [float(row["exp386_latency_median_ms"]) for row in benchmark_results]

    out_csv = STAGE_DIR / "RUNTIME_AND_MEMORY.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(benchmark_results[0].keys()))
        writer.writeheader()
        writer.writerows(benchmark_results)

    print(f"Saved RUNTIME_AND_MEMORY.csv to {out_csv}")
    for row in benchmark_results:
        print(f"Repo: {row['repo']:<20} | Files: {row['num_files']:<4} | Index: {row['index_time_total_ms']:<7} ms | Q Med: {row['exp386_latency_median_ms']:<5} ms | RSS: {row['process_rss_mb']:<6} MB")


if __name__ == "__main__":
    benchmark_runtime_and_memory()
