import json
from pathlib import Path
from collections import defaultdict
import numpy as np
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

# Group queries by corpus
queries_by_corpus = defaultdict(list)
for q in queries:
    queries_by_corpus[(q["repo"], q["commit"])].append(q)

BUDGETS = [2048, 4096, 8192, 16384, 32768]

per_query_results = []
all_gold_file_stats = []

for (repo, commit), q_list in queries_by_corpus.items():
    chunks_path = manifest.get((repo, commit))
    if not chunks_path:
        repo_clean = repo.replace("/", "__")
        found = list(ARB_DIR.glob(f"data/corpus/*/{repo_clean}/{commit}.chunks.jsonl"))
        chunks_path = found[0]

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
        repo = q["repo"]
        commit = q["commit"]
        track = q["track"]
        golds = q["gold_files"]

        gold_files_info = []
        tot_raw_tokens = 0
        tot_packaged_tokens = 0
        tot_chars = 0
        tot_lines = 0

        for g in golds:
            if g in file_chunks:
                text = file_chunks[g]
            elif g in symbol_chunks:
                text = "\n\n".join(symbol_chunks[g])
            else:
                text = ""

            raw_tok = estimate_tokens(text)
            char_c = len(text)
            line_c = len(text.splitlines())

            # Packaging overhead:
            # File header: "# File: {path}\n"
            # Markdown block: "```{ext}\n{content}\n```\n\n"
            ext = g.split(".")[-1] if "." in g else "text"
            packaged_text = f"# File: {g}\n```{ext}\n{text}\n```\n\n"
            packaged_tok = estimate_tokens(packaged_text)
            overhead_tok = packaged_tok - raw_tok

            g_stat = {
                "path": g,
                "char_count": char_c,
                "line_count": line_c,
                "raw_tokens": raw_tok,
                "packaging_overhead_tokens": overhead_tok,
                "packaged_tokens": packaged_tok,
            }
            gold_files_info.append(g_stat)
            all_gold_file_stats.append(g_stat)

            tot_raw_tokens += raw_tok
            tot_packaged_tokens += packaged_tok
            tot_chars += char_c
            tot_lines += line_c

        # Knapsack oracle calculation for both raw and packaged tokens
        # Knapsack on few items (max ~15 items): exact subsets or DP
        # We want to find subset S subseteq golds maximizing len(S) such that sum(weight) <= B
        # Since all items have value 1, this is simply sorting by ascending weight!
        raw_weights_sorted = sorted([g["raw_tokens"] for g in gold_files_info])
        pkg_weights_sorted = sorted([g["packaged_tokens"] for g in gold_files_info])

        budget_feasibility = {}
        for B in BUDGETS:
            # Raw tokens
            fits_all_raw = (tot_raw_tokens <= B)
            cum_w_raw = 0
            k_raw = 0
            for w in raw_weights_sorted:
                if cum_w_raw + w <= B:
                    cum_w_raw += w
                    k_raw += 1
                else:
                    break

            # Packaged tokens
            fits_all_pkg = (tot_packaged_tokens <= B)
            cum_w_pkg = 0
            k_pkg = 0
            for w in pkg_weights_sorted:
                if cum_w_pkg + w <= B:
                    cum_w_pkg += w
                    k_pkg += 1
                else:
                    break

            budget_feasibility[str(B)] = {
                "fits_all_raw": fits_all_raw,
                "fits_all_packaged": fits_all_pkg,
                "oracle_max_gold_raw": k_raw,
                "oracle_max_gold_packaged": k_pkg,
                "oracle_recall_raw": k_raw / len(golds),
                "oracle_recall_packaged": k_pkg / len(golds),
                "all_impossible": (k_pkg == 0),
            }

        q_res = {
            "query_id": qid,
            "repo": repo,
            "commit": commit,
            "track": track,
            "num_gold_files": len(golds),
            "total_chars": tot_chars,
            "total_lines": tot_lines,
            "total_gold_raw_tokens": tot_raw_tokens,
            "total_gold_packaging_overhead": tot_packaged_tokens - tot_raw_tokens,
            "total_gold_packaged_tokens": tot_packaged_tokens,
            "gold_files": gold_files_info,
            "feasibility": budget_feasibility,
        }
        per_query_results.append(q_res)

# Sort by query_id to keep deterministic
per_query_results.sort(key=lambda x: x["query_id"])

print(f"Processed {len(per_query_results)} queries.")

# Compute summary statistics
oracle_ceiling = {
    "evaluation_scope": {
        "benchmark": "Agent-Retrieval-Bench v2 (Complete 345-Query Scope)",
        "total_queries": len(per_query_results),
        "total_gold_files": len(all_gold_file_stats),
        "mean_gold_files_per_query": float(np.mean([q["num_gold_files"] for q in per_query_results])),
        "max_gold_files_per_query": int(np.max([q["num_gold_files"] for q in per_query_results])),
        "single_gold_queries": sum(1 for q in per_query_results if q["num_gold_files"] == 1),
        "multi_gold_queries": sum(1 for q in per_query_results if q["num_gold_files"] > 1),
    },
    "gold_file_token_distribution": {
        "mean_raw_tokens": float(np.mean([g["raw_tokens"] for g in all_gold_file_stats])),
        "median_raw_tokens": float(np.median([g["raw_tokens"] for g in all_gold_file_stats])),
        "p25_raw_tokens": float(np.percentile([g["raw_tokens"] for g in all_gold_file_stats], 25)),
        "p75_raw_tokens": float(np.percentile([g["raw_tokens"] for g in all_gold_file_stats], 75)),
        "p90_raw_tokens": float(np.percentile([g["raw_tokens"] for g in all_gold_file_stats], 90)),
        "p95_raw_tokens": float(np.percentile([g["raw_tokens"] for g in all_gold_file_stats], 95)),
        "max_raw_tokens": int(np.max([g["raw_tokens"] for g in all_gold_file_stats])),
        "min_raw_tokens": int(np.min([g["raw_tokens"] for g in all_gold_file_stats])),
        "mean_packaging_overhead_tokens": float(np.mean([g["packaging_overhead_tokens"] for g in all_gold_file_stats])),
    },
    "per_query_total_token_distribution": {
        "mean_total_packaged_tokens": float(np.mean([q["total_gold_packaged_tokens"] for q in per_query_results])),
        "median_total_packaged_tokens": float(np.median([q["total_gold_packaged_tokens"] for q in per_query_results])),
        "p25_packaged_tokens": float(np.percentile([q["total_gold_packaged_tokens"] for q in per_query_results], 25)),
        "p75_packaged_tokens": float(np.percentile([q["total_gold_packaged_tokens"] for q in per_query_results], 75)),
        "p90_packaged_tokens": float(np.percentile([q["total_gold_packaged_tokens"] for q in per_query_results], 90)),
        "p95_packaged_tokens": float(np.percentile([q["total_gold_packaged_tokens"] for q in per_query_results], 95)),
        "max_packaged_tokens": int(np.max([q["total_gold_packaged_tokens"] for q in per_query_results])),
        "min_packaged_tokens": int(np.min([q["total_gold_packaged_tokens"] for q in per_query_results])),
    },
    "budget_ceilings": {},
}

for B in BUDGETS:
    b_str = str(B)
    complete_raw_count = sum(1 for q in per_query_results if q["feasibility"][b_str]["fits_all_raw"])
    complete_pkg_count = sum(1 for q in per_query_results if q["feasibility"][b_str]["fits_all_packaged"])
    
    total_golds = 514
    n_queries = 345

    oracle_retrieved_pkg = sum(q["feasibility"][b_str]["oracle_max_gold_packaged"] for q in per_query_results)
    macro_rec_pkg = np.mean([q["feasibility"][b_str]["oracle_recall_packaged"] for q in per_query_results])
    micro_rec_pkg = oracle_retrieved_pkg / total_golds

    oracle_retrieved_raw = sum(q["feasibility"][b_str]["oracle_max_gold_raw"] for q in per_query_results)
    macro_rec_raw = np.mean([q["feasibility"][b_str]["oracle_recall_raw"] for q in per_query_results])
    micro_rec_raw = oracle_retrieved_raw / total_golds

    impossible_complete_queries = [
        q["query_id"] for q in per_query_results if not q["feasibility"][b_str]["fits_all_packaged"]
    ]
    zero_gold_queries = [
        q["query_id"] for q in per_query_results if q["feasibility"][b_str]["all_impossible"]
    ]

    oracle_ceiling["budget_ceilings"][f"{B // 1024}k_budget_{B}_tokens"] = {
        "budget_tokens": B,
        "complete_gold_coverage_ceiling_count": complete_pkg_count,
        "complete_gold_coverage_ceiling_pct": float(complete_pkg_count / n_queries),
        "complete_gold_coverage_raw_pct": float(complete_raw_count / n_queries),
        "impossible_complete_gold_queries_count": len(impossible_complete_queries),
        "impossible_complete_gold_queries_pct": float(len(impossible_complete_queries) / n_queries),
        "zero_gold_feasible_queries_count": len(zero_gold_queries),
        "oracle_macro_recall_ceiling": float(macro_rec_pkg),
        "oracle_micro_recall_ceiling": float(micro_rec_pkg),
        "oracle_macro_recall_raw_ceiling": float(macro_rec_raw),
        "oracle_micro_recall_raw_ceiling": float(micro_rec_raw),
        "impossible_query_ids": impossible_complete_queries,
        "zero_gold_query_ids": zero_gold_queries,
    }

print("\n" + "=" * 80)
print("ORACLE CEILING SUMMARY ACROSS TOKEN BUDGETS:")
print("=" * 80)
for B in BUDGETS:
    key = f"{B // 1024}k_budget_{B}_tokens"
    c = oracle_ceiling["budget_ceilings"][key]
    print(f"Budget {B // 1024:>2}k ({B} tokens):")
    print(f"  Complete-Gold Coverage Ceiling: {c['complete_gold_coverage_ceiling_count']}/345 = {c['complete_gold_coverage_ceiling_pct']:.2%}")
    print(f"  Mathematically Impossible Queries: {c['impossible_complete_gold_queries_count']}/345 = {c['impossible_complete_gold_queries_pct']:.2%}")
    print(f"  Zero-Gold Feasible Queries: {c['zero_gold_feasible_queries_count']}")
    print(f"  Oracle Micro Recall Ceiling: {c['oracle_micro_recall_ceiling']:.4f}")
    print(f"  Oracle Macro Recall Ceiling: {c['oracle_macro_recall_ceiling']:.4f}")
print("=" * 80)

# Save intermediate summary for verification
with open("scratch/summary_preview.json", "w", encoding="utf-8") as f:
    json.dump(oracle_ceiling, f, indent=2)

