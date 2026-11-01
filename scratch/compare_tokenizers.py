import json
from pathlib import Path
from collections import defaultdict
import numpy as np
import re
import sys

sys.path.insert(0, ".")
from reponeedle.core.tokenizer import estimate_tokens

# ARB's official regex tokenizer:
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+|[^A-Za-z0-9_\s]", re.UNICODE)
def arb_count_tokens(text: str) -> int:
    return len(TOKEN_RE.findall(text))

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

gold_comparisons = []

for (repo, commit), q_list in queries_by_corpus.items():
    chunks_path = manifest[(repo, commit)]
    file_chunks = {}
    with open(chunks_path, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if c.get("kind") == "file":
                file_chunks[c["path"]] = c.get("text", "")

    for q in q_list:
        for g in q["gold_files"]:
            text = file_chunks.get(g, "")
            reponeedle_est = estimate_tokens(text)
            arb_exact = arb_count_tokens(text)
            char_count = len(text)
            word_count = len(text.split())
            ratio = reponeedle_est / arb_exact if arb_exact > 0 else 1.0

            # Also check packaging overhead under both
            pkg_text_rep = f"# File: {g}\n```\n{text}\n```\n\n"
            pkg_text_arb = f"### {g}\n{text}\n"

            rep_overhead = estimate_tokens(pkg_text_rep) - reponeedle_est
            arb_overhead = arb_count_tokens(pkg_text_arb) - arb_exact

            gold_comparisons.append({
                "path": g,
                "repo": repo,
                "reponeedle_est": reponeedle_est,
                "arb_regex_exact": arb_exact,
                "diff": reponeedle_est - arb_exact,
                "ratio": ratio,
                "char_count": char_count,
                "chars_per_arb_token": char_count / arb_exact if arb_exact > 0 else 0,
                "rep_overhead": rep_overhead,
                "arb_overhead": arb_overhead,
            })

print(f"Total compared gold files: {len(gold_comparisons)}")
rep_vals = [c["reponeedle_est"] for c in gold_comparisons]
arb_vals = [c["arb_regex_exact"] for c in gold_comparisons]
ratios = [c["ratio"] for c in gold_comparisons]
diffs = [c["diff"] for c in gold_comparisons]
chars_per_tok = [c["chars_per_arb_token"] for c in gold_comparisons]

print("=== TOKENIZER COMPARISON ACROSS 514 GOLD FILES ===")
print(f"Mean RepoNeedle Estimate: {np.mean(rep_vals):.2f} (std={np.std(rep_vals):.2f})")
print(f"Mean ARB Regex Tokenizer: {np.mean(arb_vals):.2f} (std={np.std(arb_vals):.2f})")
print(f"Mean Difference (Rep - ARB): {np.mean(diffs):.2f} tokens (std={np.std(diffs):.2f})")
print(f"Mean Ratio (Rep / ARB):   {np.mean(ratios):.4f} (median={np.median(ratios):.4f})")
print(f"Mean Chars / ARB Token:   {np.mean(chars_per_tok):.2f} chars/token")
print(f"Overcount instances (Rep > ARB): {sum(1 for d in diffs if d > 0)} ({sum(1 for d in diffs if d > 0)/len(diffs):.2%})")
print(f"Undercount instances (Rep < ARB): {sum(1 for d in diffs if d < 0)} ({sum(1 for d in diffs if d < 0)/len(diffs):.2%})")
print(f"Exact match instances:          {sum(1 for d in diffs if d == 0)} ({sum(1 for d in diffs if d == 0)/len(diffs):.2%})")

# Mean packaging overhead:
print(f"Mean Packaging Overhead: RepoNeedle template={np.mean([c['rep_overhead'] for c in gold_comparisons]):.2f} tokens, ARB template={np.mean([c['arb_overhead'] for c in gold_comparisons]):.2f} tokens")

