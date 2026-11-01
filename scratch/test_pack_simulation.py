import json
import time
from pathlib import Path
from collections import defaultdict
import sys

sys.path.insert(0, ".")
from reponeedle.models import FileDoc, ContextTier, BudgetConfig
from reponeedle.core.budget import BudgetOptimizer
from reponeedle.core.tokenizer import estimate_tokens, CodeTokenizer

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

print(f"Loaded {len(queries)} queries.")

# Test on 3 queries from different repos
test_queries = queries[:3]
tok = CodeTokenizer()
optimizer = BudgetOptimizer(BudgetConfig())

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

    # Build candidates
    candidate_files = []
    for c in q["candidates"][:100]:
        p = c["path"]
        text = file_chunks.get(p, "")
        doc = FileDoc(path=p, content=text, token_count=estimate_tokens(text))
        candidate_files.append((doc, c["m1_score"], c["scores"]))

    for B in [2048, 4096, 8192]:
        t0 = time.perf_counter()
        selected = optimizer.pack_context(
            candidate_files=candidate_files,
            budget_tokens=B,
            query_terms=q_terms,
            allow_skeletons=True,
        )
        lat = (time.perf_counter() - t0) * 1000
        used = sum(s.token_count for s in selected)
        fulls = sum(1 for s in selected if s.tier == ContextTier.FULL)
        skels = sum(1 for s in selected if s.tier == ContextTier.SKELETON)
        print(f"Query {q['query_id']} | Budget {B} | {len(selected)} selected ({fulls} full, {skels} skel) | {used}/{B} tokens | Latency: {lat:.2f} ms")
        for s in selected:
            is_gold = s.path in q["gold_files"]
            print(f"  [{s.tier.value.upper()}] {s.path} (tokens: {s.token_count}, gold={is_gold})")

