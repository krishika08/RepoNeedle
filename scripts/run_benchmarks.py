"""
Script to execute RepoNeedle benchmarks and dump verified results to JSON.
"""

import json
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from benchmarks.runner import BenchmarkRunner


def main():
    runner = BenchmarkRunner()
    print("Running benchmark suite across all baselines and repositories...")
    summary = runner.run_all()
    runner.print_summary_table(summary)

    # Save verified results
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "benchmarks", "results"))
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "benchmark_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nBenchmark results successfully recorded to: {out_file}")


if __name__ == "__main__":
    main()

