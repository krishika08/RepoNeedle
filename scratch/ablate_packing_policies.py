import json
import re
from pathlib import Path
from collections import defaultdict
import numpy as np
import sys

# Official ARB regex code tokenizer
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+|[^A-Za-z0-9_\s]", re.UNICODE)
def count_exact_tokens(text: str) -> int:
    return len(TOKEN_RE.findall(text))

def package_file(path: str, content: str) -> tuple[str, int]:
    ext = path.split(".")[-1] if "." in path else "text"
    wrapped = f"# File: {path}\n```{ext}\n{content}\n```\n\n"
    return wrapped, count_exact_tokens(wrapped)

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

# Select a balanced development set of 50 queries (across all 4 tracks, 10 repos)
dev_queries = queries[::7][:50]
print(f"Development split: {len(dev_queries)} queries.")

# Cache chunk texts for dev queries
corpus_cache = {}
for q in dev_queries:
    key = (q["repo"], q["commit"])
    if key not in corpus_cache:
        cpath = manifest[key]
        file_chunks = {}
        with open(cpath, "r", encoding="utf-8") as f:
            for line in f:
                c = json.loads(line)
                if c.get("kind") == "file":
                    file_chunks[c["path"]] = c.get("text", "")
        corpus_cache[key] = file_chunks

print(f"Cached {len(corpus_cache)} corpus snapshots.")

# Define packing policies to evaluate at 4,096 and 8,192 tokens:
# 1. Baseline Score-First Greedy (with exact token accounting to prevent overflows)
# 2. Pure Token-Density (Utility / Tokens^1.0)
# 3. Fractional Knapsack with alpha in [0.15, 0.30, 0.50, 0.65]
# 4. Rank-Tiered Capacity Allocation (Rank 1 full, ranks 2-10 capacity-gated, residual backfill)
# 5. Combined CUD-Pack: Score priority with soft token-cost dampening + dynamic representation

BUDGETS = [4096, 8192]

def evaluate_policy(policy_fn, policy_name):
    results = {}
    for B in BUDGETS:
        complete_count = 0
        gold_retrieved = 0
        total_golds = sum(len(q["gold_files"]) for q in dev_queries)
        overflows = 0
        total_packed_tok = 0
        gold_tok = 0

        for q in dev_queries:
            golds = set(q["gold_files"])
            file_chunks = corpus_cache[(q["repo"], q["commit"])]
            
            selected = policy_fn(q, file_chunks, B)
            
            tot_pkg = sum(s["pkg_tokens"] for s in selected)
            if tot_pkg > B:
                overflows += 1
            
            selected_paths = {s["path"] for s in selected}
            matched_golds = golds.intersection(selected_paths)
            if len(matched_golds) == len(golds):
                complete_count += 1
            gold_retrieved += len(matched_golds)
            
            total_packed_tok += tot_pkg
            for s in selected:
                if s["path"] in golds:
                    gold_tok += s["pkg_tokens"]

        micro_rec = gold_retrieved / total_golds
        complete_pct = complete_count / len(dev_queries)
        yield_pct = gold_tok / total_packed_tok if total_packed_tok > 0 else 0

        results[B] = {
            "complete_pct": complete_pct,
            "micro_rec": micro_rec,
            "overflows": overflows,
            "yield_pct": yield_pct,
        }
    return results

# Policy 1: Score-first Greedy (Exact Accounting)
def policy_score_first(q, file_chunks, B):
    selected = []
    used = 0
    for c in q["candidates"]:
        p = c["path"]
        text = file_chunks.get(p, "")
        if not text: continue
        _, pkg_tok = package_file(p, text)
        if used + pkg_tok <= B:
            selected.append({"path": p, "pkg_tokens": pkg_tok, "tier": "full"})
            used += pkg_tok
    return selected

# Policy 2: Pure Density (Score / Tokens)
def policy_pure_density(q, file_chunks, B):
    cands = []
    for c in q["candidates"][:60]:
        p = c["path"]
        text = file_chunks.get(p, "")
        if not text: continue
        _, pkg_tok = package_file(p, text)
        density = c["m1_score"] / (pkg_tok + 1)
        cands.append({"path": p, "pkg_tokens": pkg_tok, "density": density})
    cands.sort(key=lambda x: -x["density"])
    selected = []
    used = 0
    for c in cands:
        if used + c["pkg_tokens"] <= B:
            selected.append(c)
            used += c["pkg_tokens"]
    return selected

# Policy 3: Alpha-dampened density
def make_alpha_policy(alpha):
    def policy_alpha(q, file_chunks, B):
        cands = []
        for c in q["candidates"][:60]:
            p = c["path"]
            text = file_chunks.get(p, "")
            if not text: continue
            _, pkg_tok = package_file(p, text)
            priority = c["m1_score"] / ((pkg_tok + 1) ** alpha)
            cands.append({"path": p, "pkg_tokens": pkg_tok, "priority": priority})
        cands.sort(key=lambda x: -x["priority"])
        selected = []
        used = 0
        for c in cands:
            if used + c["pkg_tokens"] <= B:
                selected.append(c)
                used += c["pkg_tokens"]
        return selected
    return policy_alpha

# Policy 4: CUD-Pack (Capacity-Sensitive Utility-Density with Rank-Aware Dynamic Sizing)
def policy_cud_pack(alpha=0.20, div_discount=0.85):
    def policy_fn(q, file_chunks, B):
        selected = []
        selected_paths = set()
        selected_dirs = defaultdict(int)
        used = 0

        def get_dir(p):
            parts = p.split("/")
            return "/".join(parts[:-1]) if len(parts) > 1 else ""

        # Candidates with production evidence
        scored = []
        for rank, c in enumerate(q["candidates"][:80], 1):
            p = c["path"]
            text = file_chunks.get(p, "")
            if not text: continue
            _, pkg_tok = package_file(p, text)
            
            # Evidence bonus
            score = c["m1_score"]
            channels = set(c.get("channels", []))
            sym_bonus = 0.35 if "exact_symbol" in channels else 0.0
            
            # Directory / module diversity
            d_key = get_dir(p)
            d_count = selected_dirs[d_key]
            div = div_discount ** d_count
            
            utility = score * (1.0 + sym_bonus) * div
            
            # Rank dampening (prevent rank 40 from jumping ahead of rank 3 purely on size)
            rank_factor = 1.0 / (1.0 + 0.05 * (rank - 1))
            priority = (utility * rank_factor) / ((pkg_tok + 1) ** alpha)
            
            scored.append({
                "path": p,
                "pkg_tokens": pkg_tok,
                "score": score,
                "priority": priority,
                "rank": rank,
            })

        # Rank 1 priority
        if scored:
            top = scored[0]
            if top["pkg_tokens"] <= B * 0.70:
                selected.append(top)
                selected_paths.add(top["path"])
                selected_dirs[get_dir(top["path"])] += 1
                used += top["pkg_tokens"]

        # Sort remaining by priority
        rem = [c for c in scored if c["path"] not in selected_paths]
        rem.sort(key=lambda x: -x["priority"])

        for c in rem:
            if used + c["pkg_tokens"] <= B:
                selected.append(c)
                selected_paths.add(c["path"])
                selected_dirs[get_dir(c["path"])] += 1
                used += c["pkg_tokens"]

        return selected
    return policy_fn

# Run ablation
policies = [
    ("Score-First Greedy", policy_score_first),
    ("Pure Density (alpha=1.0)", policy_pure_density),
    ("Alpha=0.65 Density", make_alpha_policy(0.65)),
    ("Alpha=0.35 Density", make_alpha_policy(0.35)),
    ("Alpha=0.15 Density", make_alpha_policy(0.15)),
    ("CUD-Pack (alpha=0.15)", policy_cud_pack(alpha=0.15)),
    ("CUD-Pack (alpha=0.25)", policy_cud_pack(alpha=0.25)),
]

print("\n" + "=" * 80)
print("CONTROLLED ABLATION OF PACKING POLICIES ON DEVELOPMENT SET (N=50)")
print("=" * 80)
for name, p_fn in policies:
    res = evaluate_policy(p_fn, name)
    print(f"\nPolicy: {name}")
    for B in BUDGETS:
        r = res[B]
        print(f"  Budget {B:>4}: Complete={r['complete_pct']:6.2%} | MicroRec={r['micro_rec']:6.2%} | Yield={r['yield_pct']:6.2%} | Overflows={r['overflows']}")
print("=" * 80)

