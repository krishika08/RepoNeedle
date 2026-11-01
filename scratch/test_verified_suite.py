import json
from pathlib import Path
import re
import sys

sys.path.insert(0, ".")
from research.v1_accuracy.m3_cud_pack.cud_pack_engine import CUDPackOptimizer, ExactTokenizer, ContextTier
from reponeedle.core.tokenizer import CodeTokenizer

ARB_DIR = Path("external/agent-retrieval-bench")
manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
manifest = {}
for line in open(manifest_path, encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        manifest[(r["repo"], r["base_commit"])] = ARB_DIR / r["chunks_path"]

with open("research/v1_accuracy/m3_cud_pack/compact_context_acceptance_suite.json", "r", encoding="utf-8") as f:
    suite = json.load(f)

with open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl", "r", encoding="utf-8") as f:
    q_map = {json.loads(line)["query_id"]: json.loads(line) for line in f}

exact_tok = ExactTokenizer()
optimizer = CUDPackOptimizer(exact_tok)
tok = CodeTokenizer()

passed = 0
total = len(suite)

print(f"Testing CUD-Pack COMPACT MODE on {total}-query acceptance suite (Budget: 4,096 tokens)...")

for idx, item in enumerate(suite, 1):
    qid = item["query_id"]
    q = q_map[qid]
    repo = item["repo"]
    commit = item["commit"]
    track = item["track"]
    q_text = q["query_text"]
    q_terms = tok.tokenize_text(q_text)

    cpath = manifest[(repo, commit)]
    file_chunks = {}
    with open(cpath, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if c.get("kind") == "file":
                file_chunks[c["path"]] = c.get("text", "")

    pool = []
    for c in q["candidates"][:85]:
        c_copy = dict(c)
        c_copy["content"] = file_chunks.get(c["path"], "")
        pool.append(c_copy)

    selected = optimizer.pack_context(
        candidate_pool=pool,
        budget_tokens=4096,
        query_text=q_text,
        query_terms=q_terms,
        track=track,
        mode="compact",
    )

    tot_pkg = sum(s.packaged_tokens for s in selected)
    assert tot_pkg <= 4096, f"Overflow in query {qid}: {tot_pkg} > 4096"

    sel_map = {s.path: s for s in selected}

    all_spans_present = True
    for sp in item["annotated_spans"]:
        gp = sp["gold_path"]
        sym = sp["target_symbol"]
        if gp not in sel_map:
            all_spans_present = False
            print(f"  [FAIL] Q {idx} ({qid[:8]}): Gold file {gp} NOT selected! (Total selected: {len(selected)})")
            break
        sel_item = sel_map[gp]
        if sym != "module_level" and sym.lower() not in sel_item.rendered_content.lower():
            all_spans_present = False
            print(f"  [FAIL] Q {idx} ({qid[:8]}): Symbol {sym} NOT in rendered content of {gp} (Tier: {sel_item.tier.value})")
            break

    if all_spans_present:
        passed += 1
        tiers = [sel_map[sp["gold_path"]].tier.value for sp in item["annotated_spans"]]
        print(f"  [PASS] Q {idx:>2} ({qid[:8]}) | Repo: {repo:<25} | Tokens: {tot_pkg:>4}/4096 | Tiers: {tiers}")

print("\n" + "=" * 80)
print(f"COMPACT CONTEXT ACCEPTANCE SUITE RESULT: {passed}/{total} ({passed/total:.2%}) PASSED.")
print("=" * 80)

