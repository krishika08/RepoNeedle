import json
from pathlib import Path
from collections import Counter

ARB_DIR = Path("external/agent-retrieval-bench")
manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
manifest = []
commits = Counter()
repos = Counter()
pairs = set()

for line in open(manifest_path, encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        manifest.append(r)
        commits[r["base_commit"]] += 1
        repos[r["repo"]] += 1
        pairs.add((r["repo"], r["base_commit"]))

print(f"Total manifest rows: {len(manifest)}")
print(f"Unique (repo, commit) pairs in manifest: {len(pairs)}")
print(f"Unique base_commits in manifest: {len(commits)}")
print(f"Unique repos in manifest: {len(repos)}")

# Check in benchmark queries
queries = []
with open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        queries.append(json.loads(line))

q_commits = Counter(q["commit"] for q in queries)
q_pairs = set((q["repo"], q["commit"]) for q in queries)
q_repos = set(q["repo"] for q in queries)

print(f"In 345 benchmark queries:")
print(f"  Unique (repo, commit) pairs: {len(q_pairs)}")
print(f"  Unique commits: {len(q_commits)}")
print(f"  Unique repos: {len(q_repos)}")

# What are the 271 entries in manifest?
# Let's see if the manifest contains snapshots for all 4 tracks or multiple commits
print(f"Manifest minus queries: {len(pairs - q_pairs)} pairs in manifest not in queries")
print(f"Queries minus manifest: {len(q_pairs - pairs)} pairs in queries not in manifest")

