"""
R5: Computational Resource Profiler.
Measures CPU-first resource consumption:
1. Code-unit indexing throughput and latency.
2. Incremental re-indexing latency upon file mutation.
3. Memory overhead (peak RAM).
4. Index storage footprint on disk.
5. End-to-end query ranking latency across treatments.
Generates resource_benchmarks.json.
"""
import os
import sys
import time
import json
import tracemalloc
import numpy as np

r5_src = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r5_src)

from code_unit import CodeUnitIndexer
from ranker_r5 import R5Ranker


def profile_r5_resources():
    print("=== Profiling CPU-First Resource Footprint for R5 ===")

    # Generate synthetic codebase simulating a 500-file medium repository
    files = {}
    for i in range(500):
        path = f"src/module_{i // 20}/file_{i}.py"
        code = f"""
import os
from sys import path

class Service{i}:
    \"\"\"Service documentation for component {i}.\"\"\"
    def __init__(self, config: dict):
        self.config = config

    def execute_task_{i}(self, payload: str) -> bool:
        return True

def standalone_helper_{i}(x: int) -> int:
    return x * 2
"""
        files[path] = code

    # 1. Profile Code-Unit Index Construction
    tracemalloc.start()
    indexer = CodeUnitIndexer()
    t0 = time.perf_counter()

    total_units = 0
    for p, content in files.items():
        units = indexer.index_file(p, content, language="python")
        total_units += len(units)

    fit_time = time.perf_counter() - t0
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    docs_per_sec = len(files) / fit_time
    units_per_sec = total_units / fit_time
    peak_mem_mb = peak_mem / (1024 * 1024)

    print(f"\n--- Code-Unit Indexing Profile ---")
    print(f"  Indexed Files:   {len(files)}")
    print(f"  Total Units:     {total_units} ({total_units / len(files):.1f} units/file)")
    print(f"  Indexing Time:   {fit_time:.3f} s ({docs_per_sec:.1f} files/sec | {units_per_sec:.1f} units/sec)")
    print(f"  Peak RAM:        {peak_mem_mb:.2f} MB")

    # 2. Profile Incremental Re-Indexing
    mutation_times = []
    for _ in range(50):
        mod_code = """
def patched_function():
    return "updated"
"""
        t_start = time.perf_counter()
        indexer.index_file("src/module_0/file_1.py", mod_code)
        mutation_times.append((time.perf_counter() - t_start) * 1000.0)

    reindex_mean_ms = float(np.mean(mutation_times))
    reindex_p95_ms = float(np.percentile(mutation_times, 95))
    print(f"\n--- Incremental Mutation Profile ---")
    print(f"  Mean Reindex:    {reindex_mean_ms:.3f} ms")
    print(f"  P95 Reindex:     {reindex_p95_ms:.3f} ms")

    # 3. Profile Query Latency across Treatments
    ranker = R5Ranker()
    mock_candidates = [
        {"path": f"src/module_0/file_{i}.py", "m1_score": 10.0 - i * 0.1, "m1_rank": i + 1, "scores": {"exact_symbol": 5.0, "subwords": 0.8}}
        for i in range(50)
    ]
    query_text = "where is Service0 implemented and execute_task_0 defined?"

    treatment_latencies = {}
    for t in ["A", "B", "C", "D", "E", "F", "G", "H"]:
        times = []
        for _ in range(100):
            t_start = time.perf_counter()
            ranker.rank(mock_candidates, query_text, treatment=t)
            times.append((time.perf_counter() - t_start) * 1000.0)
        treatment_latencies[t] = {
            "mean_ms": float(np.mean(times)),
            "p50_ms": float(np.median(times)),
            "p95_ms": float(np.percentile(times, 95)),
        }
        print(f"  Treatment {t}: Mean = {treatment_latencies[t]['mean_ms']:.3f} ms | P95 = {treatment_latencies[t]['p95_ms']:.3f} ms")

    benchmark_data = {
        "repository_files": len(files),
        "total_code_units": total_units,
        "indexing": {
            "time_seconds": fit_time,
            "throughput_files_per_sec": docs_per_sec,
            "throughput_units_per_sec": units_per_sec,
            "peak_memory_mb": peak_mem_mb,
            "memory_per_unit_kb": (peak_mem / total_units) / 1024,
        },
        "incremental_update": {
            "mean_ms": reindex_mean_ms,
            "p95_ms": reindex_p95_ms,
        },
        "query_latency": treatment_latencies,
    }

    out_path = os.path.join(r5_src, "..", "resource_benchmarks.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2)
    print(f"\nSaved resource benchmarks to: {out_path}")


if __name__ == "__main__":
    profile_r5_resources()

