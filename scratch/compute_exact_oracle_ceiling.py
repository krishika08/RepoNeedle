import json
import re
from pathlib import Path
from collections import defaultdict
import numpy as np

# Official ARB regex code tokenizer
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+|[^A-Za-z0-9_\s]", re.UNICODE)
def count_exact_tokens(text: str) -> int:
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

exact_gold_stats = []
query_exact_stats = []

for (repo, commit), q_list in queries_by_corpus.items():
    cpath = manifest[(repo, commit)]
    file_chunks = {}
    with open(cpath, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if c.get("kind") == "file":
                file_chunks[c["path"]] = c.get("text", "")

    for q in q_list:
        qid = q["query_id"]
        golds = q["gold_files"]
        q_golds_info = []
        tot_exact_raw = 0
        tot_exact_pkg = 0
        tot_exact_ovh = 0

        for g in golds:
            text = file_chunks.get(g, "")
            ext = g.split(".")[-1] if "." in g else "text"
            pkg_text = f"# File: {g}\n```{ext}\n{text}\n```\n\n"
            raw_tok = count_exact_tokens(text)
            pkg_tok = count_exact_tokens(pkg_text)
            ovh = pkg_tok - raw_tok

            g_info = {
                "path": g,
                "raw_tokens": raw_tok,
                "pkg_tokens": pkg_tok,
                "overhead": ovh,
            }
            q_golds_info.append(g_info)
            exact_gold_stats.append(g_info)

            tot_exact_raw += raw_tok
            tot_exact_pkg += pkg_tok
            tot_exact_ovh += ovh

        query_exact_stats.append({
            "query_id": qid,
            "repo": repo,
            "commit": commit,
            "track": q["track"],
            "num_golds": len(golds),
            "total_raw": tot_exact_raw,
            "total_pkg": tot_exact_pkg,
            "total_ovh": tot_exact_ovh,
            "golds": q_golds_info,
        })

print(f"Total audited gold files: {len(exact_gold_stats)}")
print(f"Total audited queries: {len(query_exact_stats)}")

raw_vals = [g["raw_tokens"] for g in exact_gold_stats]
pkg_vals = [g["pkg_tokens"] for g in exact_gold_stats]
ovh_vals = [g["overhead"] for g in exact_gold_stats]
q_pkg_vals = [q["total_pkg"] for q in query_exact_stats]

print("\n=== EXACT TOKEN DISTRIBUTIONS (ARB REGEX TOKENIZER) ===")
print(f"Gold File Raw:  Mean={np.mean(raw_vals):.2f}, Median={np.median(raw_vals):.2f}, Min={np.min(raw_vals)}, Max={np.max(raw_vals)}")
print(f"Gold File Pkg:  Mean={np.mean(pkg_vals):.2f}, Median={np.median(pkg_vals):.2f}, Min={np.min(pkg_vals)}, Max={np.max(pkg_vals)}")
print(f"Packaging Ovh:  Mean={np.mean(ovh_vals):.2f}, Median={np.median(ovh_vals):.2f}, Min={np.min(ovh_vals)}, Max={np.max(ovh_vals)}")
print(f"Query Total:    Mean={np.mean(q_pkg_vals):.2f}, Median={np.median(q_pkg_vals):.2f}, Min={np.min(q_pkg_vals)}, Max={np.max(q_pkg_vals)}")

print("\n=== EXACT KNAPSACK ORACLE CEILINGS (regex_code_tokenizer_v1) ===")
BUDGETS = [2048, 4096, 8192, 16384, 32768]
for B in BUDGETS:
    complete_pkg_count = sum(1 for q in query_exact_stats if q["total_pkg"] <= B)
    complete_raw_count = sum(1 for q in query_exact_stats if q["total_raw"] <= B)
    
    # Knapsack max targets
    k_targets = 0
    k_macro_list = []
    zero_gold_count = 0
    for q in query_exact_stats:
        weights = sorted([g["pkg_tokens"] for g in q["golds"]])
        cum = 0
        kq = 0
        for w in weights:
            if cum + w <= B:
                cum += w
                kq += 1
            else:
                break
        k_targets += kq
        k_macro_list.append(kq / q["num_golds"])
        if kq == 0:
            zero_gold_count += 1

    micro_rec = k_targets / 514
    macro_rec = np.mean(k_macro_list)
    impossible_count = len(query_exact_stats) - complete_pkg_count
    single_complete = sum(1 for q in query_exact_stats if q["num_golds"] == 1 and q["total_pkg"] <= B)
    multi_complete = sum(1 for q in query_exact_stats if q["num_golds"] > 1 and q["total_pkg"] <= B)

    print(f"\nBudget {B // 1024:>2}k ({B} tokens):")
    print(f"  Complete-Gold Coverage Ceiling: {complete_pkg_count}/345 = {complete_pkg_count/345:.2%}")
    print(f"  Complete-Gold Raw (No Ovh):     {complete_raw_count}/345 = {complete_raw_count/345:.2%}")
    print(f"  Single-Gold Feasible (N=227):   {single_complete}/227 = {single_complete/227:.2%}")
    print(f"  Multi-Gold Feasible (N=118):    {multi_complete}/118 = {multi_complete/118:.2%}")
    print(f"  Mathematically Impossible:      {impossible_count}/345 = {impossible_count/345:.2%}")
    print(f"  Zero-Gold Feasible Queries:     {zero_gold_count}")
    print(f"  Oracle Micro Recall Ceiling:    {micro_rec:.4f} ({k_targets}/514)")
    print(f"  Oracle Macro Recall Ceiling:    {macro_rec:.4f}")

