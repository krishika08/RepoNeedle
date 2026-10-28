"""
Stage 2 Runtime and Resource Cost Profiler.
Measures index build time, memory footprint, query latency distributions,
and packing throughput across core ablation configurations.
Outputs:
  - research/STAGE2_RUNTIME_COSTS.csv
"""

import os
import sys
import json
import time
import tracemalloc
import csv
from pathlib import Path
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import read_jsonl, query_text_for_eval
from reponeedle.models import FileDoc, Query, AblationConfig
from reponeedle.engine import RepoNeedleEngine


def measure_runtime_profile():
    print("=" * 80)
    print("MEASURING STAGE 2 RUNTIME AND RESOURCE PROFILES")
    print("=" * 80)

    # Use gin-gonic/gin or pallets/click as a representative benchmark repository
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    manifest_raw = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            manifest_raw[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]

    # Select representative repos: click (Python, ~150 files), gin (Go, ~50 files), tokio (Rust, ~300 files)
    sample_subsets = [
        ARB_DIR / "data" / "benchmark" / "v2_code2test" / "samples.jsonl",
        ARB_DIR / "data" / "benchmark" / "v2_trace2code" / "samples.jsonl",
    ]
    test_samples = []
    for p in sample_subsets:
        for s in read_jsonl(p):
            if s.get("repo") in ("pallets/click", "tokio-rs/tokio", "gin-gonic/gin"):
                test_samples.append(s)

    test_samples = test_samples[:30]
    print(f"Loaded {len(test_samples)} representative test queries.")

    # Configurations to profile
    profile_configs = [
        ("EXP-016", "Pure BM25 Baseline", AblationConfig(enable_lexical=True, enable_semantic=False, enable_graph=False, enable_router=False, allow_skeletons=False)),
        ("EXP-024", "Pure Semantic Baseline", AblationConfig(enable_lexical=False, enable_semantic=True, enable_graph=False, enable_router=False, allow_skeletons=False)),
        ("EXP-028", "Pure Graph Baseline", AblationConfig(enable_lexical=False, enable_semantic=False, enable_graph=True, enable_router=False, allow_skeletons=False)),
        ("EXP-008", "Lexical + Semantic Static", AblationConfig(enable_lexical=True, enable_semantic=True, enable_graph=False, enable_router=False, allow_skeletons=False)),
        ("EXP-004", "Static Hybrid (A+B+C)", AblationConfig(enable_lexical=True, enable_semantic=True, enable_graph=True, enable_router=False, allow_skeletons=False)),
        ("EXP-002", "Full RepoNeedle w/o Skel", AblationConfig(enable_lexical=True, enable_semantic=True, enable_graph=True, enable_router=True, allow_skeletons=False)),
        ("EXP-001", "Full RepoNeedle Anchor (All)", AblationConfig(enable_lexical=True, enable_semantic=True, enable_graph=True, enable_router=True, allow_skeletons=True)),
    ]

    # Load corpus files for pallets/click
    target_repo = "pallets/click"
    matching_commit = next(base_commit for (repo, base_commit) in manifest_raw if repo == target_repo)
    chunks = read_jsonl(manifest_raw[(target_repo, matching_commit)])
    file_texts = {}
    for c in chunks:
        p = c.get("path")
        t = c.get("text", "")
        if p and (p not in file_texts or len(t) > len(file_texts[p])):
            file_texts[p] = t

    docs = [FileDoc(path=p, content=t[:25000], is_test="test" in p.lower()) for p, t in file_texts.items()]
    print(f"Loaded {len(docs)} documents for {target_repo}.")

    results = []

    for exp_id, name, ab_cfg in profile_configs:
        print(f"Profiling {exp_id}: {name}...")

        # Measure index build time and memory peak
        tracemalloc.start()
        t0 = time.perf_counter()
        engine = RepoNeedleEngine.from_documents(docs, ablation_config=ab_cfg)
        t_build = time.perf_counter() - t0
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        build_time_ms = t_build * 1000.0
        peak_mem_mb = peak_mem / (1024 * 1024)

        # Measure query latencies
        latencies_ms = []
        pack_times_ms = []
        tokens_packed_list = []

        for s in test_samples:
            q_text = query_text_for_eval(s)
            q_obj = Query(text=q_text, budget_tokens=8000)

            t_q0 = time.perf_counter()
            retrieved = engine.retrieve(q_obj)
            t_q1 = time.perf_counter()

            latencies_ms.append((t_q1 - t_q0) * 1000.0)
            tokens_packed = retrieved.total_tokens
            tokens_packed_list.append(tokens_packed)

        mean_lat = float(np.mean(latencies_ms))
        median_lat = float(np.median(latencies_ms))
        p95_lat = float(np.percentile(latencies_ms, 95))
        mean_tokens_packed = float(np.mean(tokens_packed_list))

        results.append({
            "experiment_id": exp_id,
            "name": name,
            "index_build_ms": round(build_time_ms, 2),
            "peak_memory_mb": round(peak_mem_mb, 2),
            "mean_latency_ms": round(mean_lat, 2),
            "median_latency_ms": round(median_lat, 2),
            "p95_latency_ms": round(p95_lat, 2),
            "mean_packed_tokens": round(mean_tokens_packed, 1),
            "allow_skeletons": ab_cfg.allow_skeletons,
        })

    # Write CSV
    out_csv = ROOT_DIR / "research" / "STAGE2_RUNTIME_COSTS.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "experiment_id", "name", "index_build_ms", "peak_memory_mb",
            "mean_latency_ms", "median_latency_ms", "p95_latency_ms",
            "mean_packed_tokens", "allow_skeletons",
        ])
        writer.writeheader()
        writer.writerows(results)

    print(f"Wrote STAGE2_RUNTIME_COSTS.csv to {out_csv}")
    return results


if __name__ == "__main__":
    measure_runtime_profile()

