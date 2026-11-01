import json
import time
from pathlib import Path
from collections import defaultdict
import sys

sys.path.insert(0, ".")
from research.v1_accuracy.m3_cud_pack.cud_pack_engine import (
    CUDPackOptimizer,
    CUDPackConfig,
    ExactTokenizer,
    ContextTier,
)
from reponeedle.core.tokenizer import CodeTokenizer

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

test_queries = queries[:10]
tok = CodeTokenizer()
exact_tok = ExactTokenizer()
optimizer = CUDPackOptimizer(exact_tok, CUDPackConfig(mode="complete", alpha=0.55))

print(f"Testing CUD-Pack on {len(test_queries)} queries...")

for q in test_queries:
    repo = q["repo"]
    commit = q["commit"]
    cpath = manifest[(repo, commit)]
    file_chunks = {}
    with open(cpath, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if c.get("kind") == "file":
                file_chunks[c["path"]] = c.get("text", "")

    q_text = q["query_text"]
    q_terms = tok.tokenize_text(q_text)

    # Attach content to top 50 candidates
    pool = []
    for c in q["candidates"][:50]:
        c_copy = dict(c)
        c_copy["content"] = file_chunks.get(c["path"], "")
        pool.append(c_copy)

    golds = set(q["gold_files"])

    for B in [2048, 4096, 8192]:
        t0 = time.perf_counter()
        selected = optimizer.pack(
            candidate_pool=pool,
            budget_tokens=B,
            query_text=q_text,
            query_terms=q_terms,
            track=q["track"],
        )
        lat = (time.perf_counter() - t0) * 1000
        tot_pkg = sum(s.packaged_tokens for s in selected)
        sel_golds = [s for s in selected if s.path in golds]
        full_golds = [s for s in sel_golds if s.tier == ContextTier.FULL]

        # Verify hard constraint:
        assert tot_pkg <= B, f"OVERFLOW DETECTED! {tot_pkg} > {B}"

        print(f"Q: {q['query_id'][:8]} | B: {B} | Pkg: {tot_pkg}/{B} | Sel: {len(selected)} | Golds Sel: {len(sel_golds)}/{len(golds)} ({len(full_golds)} full) | Lat: {lat:.1f}ms")

