"""
Explore available benchmarks and repositories in external/agent-retrieval-bench.
"""
import json
import os
from collections import defaultdict, Counter

def explore_benchmarks():
    arb_dir = "external/agent-retrieval-bench"
    print("=== EXPLORING external/agent-retrieval-bench ===")
    
    # 1. Check repo manifest
    manifest_path = os.path.join(arb_dir, "data", "repo_manifest.jsonl")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_repos = [json.loads(line) for line in f if line.strip()]
        print(f"repo_manifest.jsonl has {len(manifest_repos)} repository entries:")
        for r in manifest_repos[:10]:
            print(f"  {r.get('repo') or r.get('name')}: {r.get('url')} ({r.get('language')})")

    # 2. Check benchmarks in data/benchmark/
    bench_dir = os.path.join(arb_dir, "data", "benchmark")
    benchmark_repos = defaultdict(set)
    benchmark_counts = defaultdict(int)

    for root, dirs, files in os.walk(bench_dir):
        for f in files:
            if f in ["samples.jsonl", "code2test.jsonl", "comment2context.jsonl", "edit2ripple.jsonl", "trace2code.jsonl"]:
                p = os.path.join(root, f)
                rel_suite = os.path.relpath(root, bench_dir)
                try:
                    with open(p, "r", encoding="utf-8") as fp:
                        for line in fp:
                            if line.strip():
                                rec = json.loads(line)
                                repo = rec.get("repo")
                                if repo:
                                    benchmark_repos[rel_suite].add(repo)
                                    benchmark_counts[rel_suite] += 1
                except Exception as e:
                    print(f"Error reading {p}: {e}")

    print("\nBenchmark suites in data/benchmark/:")
    for suite, repos in sorted(benchmark_repos.items()):
        print(f"  Suite '{suite}': {benchmark_counts[suite]} samples across {len(repos)} repos")

    # Compare against our 25 repositories
    import sys
    sys.path.insert(0, "research/v1_accuracy/ranking_0_80/r2/src")
    from split import TRAIN_REPOS, VAL_REPOS, HELD_OUT_REPOS
    existing_25 = TRAIN_REPOS | VAL_REPOS | HELD_OUT_REPOS
    print(f"\nExisting 25 Repositories: {sorted(list(existing_25))}")

    all_found_repos = set()
    for suite, repos in benchmark_repos.items():
        all_found_repos |= repos

    new_repos = all_found_repos - existing_25
    print(f"\nNew Repositories found in benchmark files ({len(new_repos)} repos):")
    for nr in sorted(list(new_repos)):
        print(f"  {nr}")

    # Check corpus availability for new repos
    corpus_dir = os.path.join(arb_dir, "data", "corpus")
    print(f"\nChecking corpus availability in {corpus_dir}:")
    for root, dirs, files in os.walk(corpus_dir):
        for d in dirs:
            print(f"  Corpus dir: {d}")
        break

if __name__ == "__main__":
    explore_benchmarks()
