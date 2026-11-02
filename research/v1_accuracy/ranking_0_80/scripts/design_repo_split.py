"""
Generate repository-clustered split for Mission 0.80+ experiment plan.
"""
import json
from collections import defaultdict, Counter

def design_repo_split():
    with open("reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl", "r", encoding="utf-8") as f:
        baseline_records = [json.loads(l) for l in f if l.strip()]

    repo_stats = defaultdict(lambda: {"queries": 0, "snapshots": set(), "gold_targets": 0, "tracks": Counter()})
    for r in baseline_records:
        repo = r["repo"]
        repo_stats[repo]["queries"] += 1
        repo_stats[repo]["snapshots"].add((repo, r["base_commit"]))
        repo_stats[repo]["gold_targets"] += len(r["gold_files"])
        repo_stats[repo]["tracks"][r["task_type"]] += 1

    print(f"Total Repositories: {len(repo_stats)}")
    
    # We want:
    # 15 Train repos (~60% of queries/snapshots)
    # 5 Val repos (~20% of queries/snapshots)
    # 5 Test repos (~20% of queries/snapshots)
    # Strata across Go, Python, Rust, TypeScript, Java.
    
    # Sorted by queries descending:
    sorted_repos = sorted(repo_stats.items(), key=lambda x: -x[1]["queries"])
    for repo, data in sorted_repos:
        print(f"  {repo:<30}: {data['queries']} queries, {len(data['snapshots'])} snapshots, tracks: {dict(data['tracks'])}")

if __name__ == "__main__":
    design_repo_split()

