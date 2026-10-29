"""
Stage 3.10.2: Performance, Latency, and Memory Audit Script
Benchmarks:
  - Cold index construction time (ms)
  - Warm query latency (median p50, p95, mean across repetitions)
  - Process RSS before/after indexing, peak working set (MB)
  - Document counts, source bytes, symbol counts, base edges, invocation edges
Evaluates on:
  - pallets/click (small python repository)
  - caddyserver/caddy (medium go repository)
  - gin-gonic/gin (go repository with heavy test invocations)
"""

import sys
import os
import time
import json
import csv
import ctypes
from ctypes import wintypes
from pathlib import Path
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
STAGE_DIR = ROOT_DIR / "research" / "stage3_10_2"

sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import read_jsonl
from reponeedle.models import FileDoc
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.cascade import CascadedRanker


class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('PageFaultCount', wintypes.DWORD),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
        ('PrivateUsage', ctypes.c_size_t),
    ]

def get_process_memory():
    pid = os.getpid()
    h = ctypes.windll.kernel32.OpenProcess(0x0410, False, pid)
    c = PROCESS_MEMORY_COUNTERS_EX()
    c.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
    ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb)
    ctypes.windll.kernel32.CloseHandle(h)
    rss_mb = c.WorkingSetSize / (1024.0 * 1024.0)
    peak_mb = c.PeakWorkingSetSize / (1024.0 * 1024.0)
    return rss_mb, peak_mb


def run_performance_audit():
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    lines = [json.loads(l) for l in open(manifest_path, encoding="utf-8") if l.strip()]

    target_repos = [
        "pallets/click",
        "caddyserver/caddy",
        "gin-gonic/gin",
    ]

    records = []
    print("=" * 80)
    print("STAGE 3.10.2: PERFORMANCE & MEMORY MEASUREMENT AUDIT")
    print("=" * 80)

    for target_repo in target_repos:
        matching = [r for r in lines if r["repo"] == target_repo]
        if not matching:
            continue
        row = matching[0]
        chunks = read_jsonl(arb_dir_chunks := ARB_DIR / row["chunks_path"])
        file_texts = {}
        for c in chunks:
            p, t = c.get("path"), c.get("text", "")
            if p and (p not in file_texts or len(t) > len(file_texts[p])):
                file_texts[p] = t

        docs = [FileDoc(path=p, content=t[:25000], is_test="test" in p.lower()) for p, t in file_texts.items()]
        total_source_bytes = sum(len(d.content.encode("utf-8")) for d in docs)

        rss_before, _ = get_process_memory()
        t0 = time.perf_counter()
        engine = RepoNeedleEngine.from_documents(docs)
        cold_index_ms = (time.perf_counter() - t0) * 1000.0
        rss_after, peak_ws = get_process_memory()

        g = engine.repo_graph
        sym_count = sum(len(d.symbols) for d in docs)
        base_edges = g.graph.number_of_edges()
        inv_edges = len(g.invocation_edges)
        unres_refs = len(g.unresolved_diagnostics)

        ranker = CascadedRanker(
            top_k_preserve=3,
            enable_graph_expansion=True,
            degree_normalized=True,
            package_fencing=True,
            test_discovery=True,
            enable_class_to_test=True,
            class_to_test_weight=0.35,
        )

        q_sample = "context route execution request response parameter"
        # Warmup
        for _ in range(5):
            l = engine.lexical_index.score(q_sample)
            s = engine.semantic_index.score(q_sample)
            ranker.rank(docs, l, s, g)

        # Timed repetitions (25 trials)
        query_lats = []
        for _ in range(25):
            t_q = time.perf_counter()
            l = engine.lexical_index.score(q_sample)
            s = engine.semantic_index.score(q_sample)
            ranker.rank(docs, l, s, g)
            query_lats.append((time.perf_counter() - t_q) * 1000.0)

        p50 = float(np.median(query_lats))
        p95 = float(np.percentile(query_lats, 95))
        mean_lat = float(np.mean(query_lats))

        record = {
            "repository": target_repo,
            "file_count": len(docs),
            "source_size_kb": round(total_source_bytes / 1024.0, 1),
            "symbol_count": sym_count,
            "base_edges": base_edges,
            "invocation_edges": inv_edges,
            "unresolved_diagnostics": unres_refs,
            "cold_index_time_ms": round(cold_index_ms, 2),
            "warm_query_latency_p50_ms": round(p50, 2),
            "warm_query_latency_p95_ms": round(p95, 2),
            "warm_query_latency_mean_ms": round(mean_lat, 2),
            "process_rss_before_mb": round(rss_before, 2),
            "process_rss_after_mb": round(rss_after, 2),
            "process_rss_delta_mb": round(rss_after - rss_before, 2),
            "peak_working_set_mb": round(peak_ws, 2),
        }
        records.append(record)
        print(f"[{target_repo}] {len(docs)} files, Index: {cold_index_ms:.1f}ms, Query p50: {p50:.2f}ms, RSS delta: {rss_after - rss_before:.2f}MB, Peak: {peak_ws:.1f}MB")

    # Write RUNTIME_MEMORY_RESULTS.csv
    out_csv = STAGE_DIR / "RUNTIME_MEMORY_RESULTS.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    print(f"Saved performance audit to {out_csv}")
    return records


if __name__ == "__main__":
    run_performance_audit()
