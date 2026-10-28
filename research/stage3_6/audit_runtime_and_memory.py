"""
Stage 3.6: Rigorous Runtime, Latency, and Memory Footprint Audit.
Measures:
  1. Index Build Time (s)
  2. Retained Index Heap Delta (MB via tracemalloc)
  3. Peak Traced Python Heap (MB via tracemalloc)
  4. Process RSS & Peak RSS (MB via Windows API K32GetProcessMemoryInfo)
  5. Cold Start Query Latency (ms)
  6. Warm Query Median (p50) & p95 Latency (ms)
  7. Query Throughput (queries/s)
Across 4 Systems:
  - BASE-BM25
  - CAND-C
  - CAND-F
  - BASE-REPOMAP
Across 3 Repository Scales:
  - Micro: Synthetic Django (5 files, 70 lines)
  - Medium: pallets/click (133 files, 14,670 lines)
  - Large: caddyserver/caddy (250 files, 22,995 lines)

Outputs:
  - research/stage3_6/RUNTIME_MEMORY_RESULTS.csv
"""

import sys
import os
import time
import ctypes
from ctypes import wintypes
import tracemalloc
import gc
import json
from pathlib import Path
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import read_jsonl
from reponeedle.models import FileDoc, AblationConfig
from reponeedle.engine import RepoNeedleEngine
from benchmarks.baselines import BM25Baseline, RepoMapBaseline
from research.stage3.build_independent_benchmark import create_benchmark_instances


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
            rss_mb = counters.WorkingSetSize / (1024 * 1024)
            peak_mb = counters.PeakWorkingSetSize / (1024 * 1024)
            return rss_mb, peak_mb
    except Exception:
        pass
    return 0.0, 0.0


def load_arb_docs(repo_name: str, max_files: int = 500):
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    chunks_path = None
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            if row.get("repo") == repo_name:
                chunks_path = ARB_DIR / row["chunks_path"]
                break
    if not chunks_path or not chunks_path.is_file():
        return []

    chunks = read_jsonl(chunks_path)
    file_texts = {}
    for c in chunks:
        p = c.get("path")
        t = c.get("text", "")
        if p and (p not in file_texts or len(t) > len(file_texts[p])):
            file_texts[p] = t

    docs = [
        FileDoc(path=p, content=t[:25000], is_test="test" in p.lower())
        for p, t in list(file_texts.items())[:max_files]
    ]
    return docs


def run_runtime_and_memory_audit():
    print("=" * 80)
    print("STAGE 3.6: RIGOROUS RUNTIME & PROCESS MEMORY AUDIT")
    print("=" * 80)

    # 1. Load scale fixtures
    django_instances = create_benchmark_instances()
    django_micro = next(i for i in django_instances if i["repo"] == "django/django")["docs"]
    click_docs = load_arb_docs("pallets/click", max_files=133)
    caddy_docs = load_arb_docs("caddyserver/caddy", max_files=250)

    scales = [
        ("Micro (Synthetic Django)", django_micro, "QuerySet Q filter expressions"),
        ("Medium (pallets/click)", click_docs, "Custom click ParamType parser conversion error"),
        ("Large (caddyserver/caddy)", caddy_docs, "TLS automated certificate renewal manager error"),
    ]

    systems = [
        ("BASE-BM25", "Pure BM25"),
        ("CAND-C", "Candidate C (Hybrid + Doc Filter)"),
        ("CAND-F", "Candidate F (Polyglot Graph Diffusion)"),
        ("BASE-REPOMAP", "RepoMap (AST PageRank)"),
    ]

    csv_rows = [
        "Repository Scale,System ID,Total Files,Total Lines,Index Build Time (s),Retained Index Delta (MB),"
        "Peak Traced Heap (MB),Process Baseline RSS (MB),Process Retained RSS (MB),Process Peak RSS (MB),"
        "Cold Start Latency (ms),Warm Query Median p50 (ms),Warm Query p95 (ms),Query Throughput (qps),Under 100MB Ceiling"
    ]

    for scale_name, docs, query in scales:
        num_files = len(docs)
        num_lines = sum(len(d.content.splitlines()) for d in docs)
        print(f"\n--- Scale: {scale_name} ({num_files} files, {num_lines} lines) ---")

        for sys_id, sys_name in systems:
            gc.collect()
            time.sleep(0.1)
            base_rss, _ = get_process_memory_info()

            tracemalloc.start()
            t0 = time.perf_counter()

            # Initialize system
            if sys_id == "BASE-BM25":
                sys_obj = BM25Baseline(docs)
            elif sys_id == "CAND-C":
                sys_obj = RepoNeedleEngine.from_documents(docs, ablation_config=AblationConfig.candidate_c())
            elif sys_id == "CAND-F":
                sys_obj = RepoNeedleEngine.from_documents(docs, ablation_config=AblationConfig.candidate_e())
            elif sys_id == "BASE-REPOMAP":
                sys_obj = RepoMapBaseline(docs)

            build_time = time.perf_counter() - t0
            cur_traced, peak_traced = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            retained_rss, peak_rss = get_process_memory_info()

            # Cold latency
            t_c0 = time.perf_counter()
            _ = sys_obj.retrieve(query, budget_tokens=8000)
            cold_ms = (time.perf_counter() - t_c0) * 1000.0

            # Warm latencies (25 repetitions)
            warm_times = []
            for _ in range(25):
                t_w0 = time.perf_counter()
                _ = sys_obj.retrieve(query, budget_tokens=8000)
                warm_times.append((time.perf_counter() - t_w0) * 1000.0)

            p50 = float(np.median(warm_times))
            p95 = float(np.percentile(warm_times, 95))
            qps = 1000.0 / p50 if p50 > 0 else 0.0

            index_delta_mb = cur_traced / (1024 * 1024)
            peak_heap_mb = peak_traced / (1024 * 1024)
            under_100 = "PASSED" if retained_rss <= 100.0 else f"FAILED (+{retained_rss - 100.0:.1f} MB)"

            print(f"  {sys_id:14} | Build: {build_time:.2f}s | Retained RSS: {retained_rss:.1f} MB | Heap Delta: {index_delta_mb:.2f} MB | p50: {p50:.2f}ms | Ceiling: {under_100}")

            csv_rows.append(
                f'"{scale_name}",{sys_id},{num_files},{num_lines},{build_time:.3f},{index_delta_mb:.2f},'
                f'{peak_heap_mb:.2f},{base_rss:.1f},{retained_rss:.1f},{peak_rss:.1f},'
                f'{cold_ms:.2f},{p50:.2f},{p95:.2f},{qps:.1f},{under_100}'
            )

            del sys_obj
            gc.collect()

    out_csv = ROOT_DIR / "research" / "stage3_6" / "RUNTIME_MEMORY_RESULTS.csv"
    out_csv.write_text("\n".join(csv_rows), encoding="utf-8")
    print(f"\nWrote RUNTIME_MEMORY_RESULTS.csv to {out_csv}")


if __name__ == "__main__":
    run_runtime_and_memory_audit()
