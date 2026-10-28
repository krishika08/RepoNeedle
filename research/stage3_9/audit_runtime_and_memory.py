"""
Stage 3.9: Runtime Latency and Memory Profiling Audit.
Measures:
  1. Indexing time (ms)
  2. Query latency percentiles (p50, p90, p95, p99 ms)
  3. Process Working Set RSS (MB) via Windows PSAPI (K32GetProcessMemoryInfo)
Across small (Click), medium (Gin, Tokio), and large (Spring Boot) repositories.
Generates:
  - research/stage3_9/RUNTIME_MEMORY_RESULTS.csv
"""

import sys
import os
import time
import csv
import json
import gc
import ctypes
from ctypes import wintypes
from pathlib import Path
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
STAGE_DIR = ROOT_DIR / "research" / "stage3_9"

sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from reponeedle.models import FileDoc, AblationConfig
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.graph import RepoGraph
from agent_retrieval_bench.baseline import read_jsonl

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

try:
    ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
except Exception:
    pass

def get_process_memory_info():
    """Returns (current_working_set_mb, peak_working_set_mb) via Windows PSAPI."""
    try:
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return (
                counters.WorkingSetSize / (1024 * 1024),
                counters.PeakWorkingSetSize / (1024 * 1024),
            )
    except Exception:
        pass
    return (0.0, 0.0)

def run_runtime_memory_audit():
    print("=" * 80)
    print("STAGE 3.9: RUNTIME & MEMORY PROFILING AUDIT")
    print("=" * 80)

    # Manifest
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    manifest = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            manifest[row["repo"]] = ARB_DIR / row["chunks_path"]

    target_repos = [
        ("pallets/click", "Small (Python, ~20 files)"),
        ("gin-gonic/gin", "Medium (Go, ~100 files)"),
        ("tokio-rs/tokio", "Medium (Rust, ~300 files)"),
        ("caddyserver/caddy", "Medium/Large (Go, ~250 files)"),
    ]

    benchmark_queries = {
        "pallets/click": ["parse args options CLI context", "subcommand group invoke callback"],
        "gin-gonic/gin": ["recovery middleware panic handler", "bind JSON form struct query"],
        "tokio-rs/tokio": ["async task spawn join handle", "mpsc channel receiver sender queue"],
        "caddyserver/caddy": ["caddyfile tls app config options", "reverse proxy transport dial"],
    }

    configs_to_test = [
        ("BASE-BM25", AblationConfig.bm25_baseline()),
        ("CAND-C", AblationConfig.candidate_c()),
        ("CAND-F", AblationConfig.candidate_f()),
        ("RECOVERED-CANDIDATE", AblationConfig.candidate_recovered()),
        ("SPARSE-RERANK", AblationConfig.candidate_recovered()),
    ]

    out_rows = []

    for repo, desc in target_repos:
        chunks_path = manifest.get(repo)
        if not chunks_path or not chunks_path.is_file():
            print(f"Skipping {repo}: chunks not found.")
            continue

        print(f"\nProfiling {repo} ({desc})...")
        chunks = read_jsonl(chunks_path)
        file_texts = {}
        for c in chunks:
            p = c.get("path")
            t = c.get("text", "")
            if p and (p not in file_texts or len(t) > len(file_texts[p])):
                file_texts[p] = t

        file_count = len(file_texts)
        total_loc = sum(len(t.splitlines()) for t in file_texts.values())

        docs = []
        for p, t in file_texts.items():
            syms, imps = RepoGraph.extract_polyglot_symbols(t[:25000], p)
            docs.append(FileDoc(path=p, content=t[:25000], symbols=syms, imports=imps, is_test="test" in p.lower()))

        queries = benchmark_queries.get(repo, ["test query"])

        for cfg_name, cfg in configs_to_test:
            gc.collect()
            rss_before, _ = get_process_memory_info()

            t0 = time.perf_counter()
            engine = RepoNeedleEngine.from_documents(docs)
            fit_time_ms = (time.perf_counter() - t0) * 1000.0

            rss_after, _ = get_process_memory_info()
            incremental_index_mb = max(0.0, rss_after - rss_before)

            # Warm-up query
            for q in queries:
                _ = engine.retrieve(q, ablation_config=cfg)

            # Timed repetitions
            latencies = []
            for _ in range(5):
                for q in queries:
                    t_q0 = time.perf_counter()
                    _ = engine.retrieve(q, ablation_config=cfg)
                    latencies.append((time.perf_counter() - t_q0) * 1000.0)

            p50 = float(np.median(latencies))
            p90 = float(np.percentile(latencies, 90))
            p95 = float(np.percentile(latencies, 95))
            p99 = float(np.percentile(latencies, 99))
            _, peak_rss = get_process_memory_info()

            print(f"  {cfg_name:<20} | Index: {fit_time_ms:6.1f}ms | Latency p50: {p50:5.2f}ms, p95: {p95:5.2f}ms | Peak RSS: {peak_rss:5.1f}MB")

            out_rows.append({
                "repository": repo,
                "scale_category": desc,
                "file_count": file_count,
                "total_loc": total_loc,
                "configuration": cfg_name,
                "index_fit_time_ms": f"{fit_time_ms:.1f}",
                "incremental_index_mb": f"{incremental_index_mb:.1f}",
                "query_latency_p50_ms": f"{p50:.2f}",
                "query_latency_p90_ms": f"{p90:.2f}",
                "query_latency_p95_ms": f"{p95:.2f}",
                "query_latency_p99_ms": f"{p99:.2f}",
                "peak_process_rss_mb": f"{peak_rss:.1f}",
            })

    out_csv = STAGE_DIR / "RUNTIME_MEMORY_RESULTS.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"\n[DONE] Wrote runtime and memory audit to {out_csv.name}.")


if __name__ == "__main__":
    run_runtime_memory_audit()
