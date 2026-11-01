import json
import sys
sys.path.insert(0, ".")
from research.v1_accuracy.m3_cud_pack.cud_pack_engine import CUDPackOptimizer, ExactTokenizer, ContextTier
from pathlib import Path

ARB_DIR = Path("external/agent-retrieval-bench")
manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
manifest = {}
for line in open(manifest_path, encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        manifest[(r["repo"], r["base_commit"])] = ARB_DIR / r["chunks_path"]

with open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        q = json.loads(line)
        if q["query_id"] == "0265037c6c534b98289fe815":
            break

cpath = manifest[(q["repo"], q["commit"])]
file_chunks = {}
with open(cpath, "r", encoding="utf-8") as f:
    for line in f:
        c = json.loads(line)
        if c.get("kind") == "file":
            file_chunks[c["path"]] = c.get("text", "")

pool = []
for c in q["candidates"][:20]:
    c_copy = dict(c)
    c_copy["content"] = file_chunks.get(c["path"], "")
    pool.append(c_copy)

opt = CUDPackOptimizer(ExactTokenizer())
selected = opt.pack_context(pool, budget_tokens=4096, mode="compact")
print(f"Total selected in Q3: {len(selected)}")
for s in selected:
    print(f"  [{s.tier.value}] {s.path} (rank {s.rank}, tokens {s.packaged_tokens})")

print("\nCandidate 1:")
print("Path:", pool[0]["path"])
print("Tokens:", opt.tok.package_file(pool[0]["path"], pool[0]["content"])[1])

