import json
from pathlib import Path
from collections import defaultdict
import sys

sys.path.insert(0, ".")
from reponeedle.core.tokenizer import estimate_tokens

ARB_DIR = Path("external/agent-retrieval-bench")
manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
manifest = {}
if manifest_path.exists():
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            manifest[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]

queries = []
with open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        queries.append(json.loads(line))

print(f"Loaded {len(queries)} queries.")

# Build cache of chunks by (repo, commit)
chunks_cache = {}
gold_missing_as_file = []
gold_found = 0
total_gold_targets = 0

# Track per-query gold tokens
query_gold_data = []

# Group queries by (repo, commit) to read chunk files only once!
queries_by_corpus = defaultdict(list)
for q in queries:
    queries_by_corpus[(q["repo"], q["commit"])].append(q)

print(f"Unique corpus snapshots: {len(queries_by_corpus)}")

for (repo, commit), q_list in queries_by_corpus.items():
    chunks_path = manifest.get((repo, commit))
    if not chunks_path:
        repo_clean = repo.replace("/", "__")
        found = list(ARB_DIR.glob(f"data/corpus/*/{repo_clean}/{commit}.chunks.jsonl"))
        chunks_path = found[0]

    # Read chunks
    file_chunks = {}
    symbol_chunks = defaultdict(list)
    with open(chunks_path, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            p = c.get("path")
            if c.get("kind") == "file":
                file_chunks[p] = c.get("text", "")
            elif c.get("kind") == "symbol":
                symbol_chunks[p].append(c.get("text", ""))

    for q in q_list:
        qid = q["query_id"]
        golds = q["gold_files"]
        q_golds_info = []
        for g in golds:
            total_gold_targets += 1
            if g in file_chunks:
                gold_found += 1
                text = file_chunks[g]
                tok = estimate_tokens(text)
                q_golds_info.append({
                    "path": g,
                    "found": True,
                    "source": "file_chunk",
                    "char_count": len(text),
                    "line_count": len(text.splitlines()),
                    "token_count": tok,
                })
            elif g in symbol_chunks:
                # File not present as a whole file chunk, but present as symbol chunks
                combined_text = "\n\n".join(symbol_chunks[g])
                tok = estimate_tokens(combined_text)
                gold_found += 1
                q_golds_info.append({
                    "path": g,
                    "found": True,
                    "source": "symbol_chunks",
                    "char_count": len(combined_text),
                    "line_count": len(combined_text.splitlines()),
                    "token_count": tok,
                })
                print(f"Notice: Gold {g} in {qid} found via symbol chunks only ({len(symbol_chunks[g])} symbols)")
            else:
                gold_missing_as_file.append((qid, repo, commit, g))
                q_golds_info.append({
                    "path": g,
                    "found": False,
                    "source": "missing",
                    "char_count": 0,
                    "line_count": 0,
                    "token_count": 0,
                })

print(f"Total gold targets across 345 queries: {total_gold_targets}")
print(f"Gold targets successfully found: {gold_found}")
print(f"Gold targets missing: {len(gold_missing_as_file)}")
if gold_missing_as_file:
    for m in gold_missing_as_file[:10]:
        print(f"  Missing: {m}")

