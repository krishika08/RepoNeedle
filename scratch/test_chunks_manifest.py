import json
from pathlib import Path

ARB_DIR = Path("external/agent-retrieval-bench")
manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
manifest = {}
if manifest_path.exists():
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            manifest[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]

print(f"Loaded manifest entries: {len(manifest)}")

queries = []
with open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        queries.append(json.loads(line))

print(f"Loaded queries: {len(queries)}")

missing_chunks = 0
for q in queries:
    repo = q["repo"]
    commit = q["commit"]
    key = (repo, commit)
    if key not in manifest:
        repo_clean = repo.replace("/", "__")
        found = list(ARB_DIR.glob(f"data/corpus/*/{repo_clean}/{commit}.chunks.jsonl"))
        if not found:
            found = list(ARB_DIR.glob(f"data/corpus/**/{commit}.chunks.jsonl"))
        if found:
            manifest[key] = found[0]
        else:
            missing_chunks += 1

print(f"Total resolved chunks files: {len(manifest)}, missing: {missing_chunks}")

