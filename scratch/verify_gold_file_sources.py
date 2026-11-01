import json
from pathlib import Path
from collections import defaultdict
import sys

ARB_DIR = Path("external/agent-retrieval-bench")
manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
manifest = {}
for line in open(manifest_path, encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        manifest[(r["repo"], r["base_commit"])] = ARB_DIR / r["chunks_path"]

queries = []
with open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        queries.append(json.loads(line))

queries_by_corpus = defaultdict(list)
for q in queries:
    queries_by_corpus[(q["repo"], q["commit"])].append(q)

gold_from_file_chunk = 0
gold_from_symbol_chunk = 0
gold_missing = 0

for (repo, commit), q_list in queries_by_corpus.items():
    chunks_path = manifest[(repo, commit)]
    file_chunks = {}
    symbol_chunks = defaultdict(list)
    with open(chunks_path, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            p = c.get("path")
            if c.get("kind") == "file":
                file_chunks[p] = c
            elif c.get("kind") == "symbol":
                symbol_chunks[p].append(c)

    for q in q_list:
        for g in q["gold_files"]:
            if g in file_chunks:
                gold_from_file_chunk += 1
            elif g in symbol_chunks:
                gold_from_symbol_chunk += 1
                print(f"SYMBOL CHUNK ONLY: qid={q['query_id']}, repo={repo}, commit={commit}, path={g}")
            else:
                gold_missing += 1
                print(f"MISSING: qid={q['query_id']}, repo={repo}, commit={commit}, path={g}")

print(f"Total gold targets: {gold_from_file_chunk + gold_from_symbol_chunk + gold_missing}")
print(f"From file chunk (kind=='file'): {gold_from_file_chunk}")
print(f"From symbol chunk (kind=='symbol'): {gold_from_symbol_chunk}")
print(f"Missing: {gold_missing}")

