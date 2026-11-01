import json
import sys
sys.path.insert(0, ".")
from research.v1_accuracy.m3_cud_pack.cud_pack_engine import CUDPackOptimizer, CUDPackConfig, ExactTokenizer
from reponeedle.core.tokenizer import CodeTokenizer
from pathlib import Path

ARB_DIR = Path("external/agent-retrieval-bench")
manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
manifest = {}
for line in open(manifest_path, encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        manifest[(r["repo"], r["base_commit"])] = ARB_DIR / r["chunks_path"]

with open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl", "r", encoding="utf-8") as f:
    q = json.loads(f.readline())

cpath = manifest[(q["repo"], q["commit"])]
file_chunks = {}
with open(cpath, "r", encoding="utf-8") as f:
    for line in f:
        c = json.loads(line)
        if c.get("kind") == "file":
            file_chunks[c["path"]] = c.get("text", "")

pool = []
for c in q["candidates"][:50]:
    c_copy = dict(c)
    c_copy["content"] = file_chunks.get(c["path"], "")
    pool.append(c_copy)

tok = CodeTokenizer()
exact_tok = ExactTokenizer()
optimizer = CUDPackOptimizer(exact_tok, CUDPackConfig(mode="complete", alpha=0.55))

selected = optimizer.pack(
    candidate_pool=pool,
    budget_tokens=8192,
    query_text=q["query_text"],
    query_terms=tok.tokenize_text(q["query_text"]),
    track=q["track"],
)

print(f"Selected {len(selected)} files in query {q['query_id']}:")
for s in selected:
    is_gold = s.path in q["gold_files"]
    print(f"  [{s.tier.value.upper()}] Rank {s.rank:>2} | {s.path:<45} | tokens: {s.packaged_tokens:>4} | density: {s.utility_density:.6f} | gold={is_gold} | reason: {s.reason}")

