import json
from pathlib import Path
from collections import defaultdict
import numpy as np
import sys

sys.path.insert(0, ".")
from reponeedle.core.tokenizer import estimate_tokens

ARB_DIR = Path("external/agent-retrieval-bench")
OUT_DIR = Path("research/v1_accuracy/m3_token_feasibility")
OUT_DIR.mkdir(parents=True, exist_ok=True)

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

        raw_weights_sorted = sorted([g["raw_tokens"] for g in gold_files_info])
        pkg_weights_sorted = sorted([g["packaged_tokens"] for g in gold_files_info])

        budget_feasibility = {}
        for B in BUDGETS:
            fits_all_raw = (tot_raw_tokens <= B)
            cum_w_raw = 0
            k_raw = 0
            for w in raw_weights_sorted:
                if cum_w_raw + w <= B:
                    cum_w_raw += w
                    k_raw += 1
                else:
                    break

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
                "budget_tokens": B,
                "fits_all_packaged": fits_all_pkg,
                "fits_all_raw": fits_all_raw,
                "token_margin_packaged": B - tot_packaged_tokens,
                "oracle_knapsack_max_files": k_pkg,
                "oracle_recall": k_pkg / len(golds),
                "is_mathematically_impossible": not fits_all_pkg,
                "is_zero_gold_feasible": (k_pkg == 0),
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
            "total_packaging_overhead": tot_packaged_tokens - tot_raw_tokens,
            "total_gold_packaged_tokens": tot_packaged_tokens,
            "gold_files": gold_files_info,
            "feasibility_by_budget": budget_feasibility,
        }
        per_query_results.append(q_res)

per_query_results.sort(key=lambda x: x["query_id"])

# Write JSONL
jsonl_path = OUT_DIR / "M3_PER_QUERY_BUDGET_RESULTS.jsonl"
with open(jsonl_path, "w", encoding="utf-8") as f:
    for q in per_query_results:
        f.write(json.dumps(q) + "\n")

print(f"Written {len(per_query_results)} records to {jsonl_path}")

# Build comprehensive oracle ceiling JSON
all_raw_tokens = [g["raw_tokens"] for g in all_gold_file_stats]
all_pkg_tokens = [g["packaged_tokens"] for g in all_gold_file_stats]
all_overhead = [g["packaging_overhead_tokens"] for g in all_gold_file_stats]
all_q_pkg = [q["total_gold_packaged_tokens"] for q in per_query_results]
all_q_raw = [q["total_gold_raw_tokens"] for q in per_query_results]

oracle_ceiling = {
    "metadata": {
        "mission": "RepoNeedle V1.0.0 — Milestone 3 Token-Budget Feasibility Audit",
        "authoritative_baseline": "M1 Frozen Multi-Channel Candidate Snapshot",
        "benchmark_scope": "Agent-Retrieval-Bench v2 (345 Queries, 25 Repositories, 514 Gold Targets)",
        "source_data_path": "external/agent-retrieval-bench/data/corpus/",
        "calibrated_tokenizer": "reponeedle.core.tokenizer.estimate_tokens (Code-Aware BPE Heuristic)",
        "packaging_template": "# File: {path}\\n```{ext}\\n{content}\\n```\\n\\n",
        "audit_policy": "Theoretical Oracle Ceiling Audit (No production packing implemented, gold labels used exclusively for bound calculation)",
    },
    "corpus_summary": {
        "total_queries": len(per_query_results),
        "total_repositories": len(set(q["repo"] for q in per_query_results)),
        "total_corpus_snapshots": len(queries_by_corpus),
        "total_gold_files": len(all_gold_file_stats),
        "single_gold_queries": sum(1 for q in per_query_results if q["num_gold_files"] == 1),
        "multi_gold_queries": sum(1 for q in per_query_results if q["num_gold_files"] > 1),
        "gold_files_per_query_distribution": dict(defaultdict(int, {
            str(k): sum(1 for q in per_query_results if q["num_gold_files"] == k)
            for k in range(1, 6)
        })),
    },
    "token_distributions": {
        "gold_file_level": {
            "mean_raw_tokens": float(np.mean(all_raw_tokens)),
            "std_raw_tokens": float(np.std(all_raw_tokens)),
            "median_raw_tokens": float(np.median(all_raw_tokens)),
            "p25_raw_tokens": float(np.percentile(all_raw_tokens, 25)),
            "p75_raw_tokens": float(np.percentile(all_raw_tokens, 75)),
            "p90_raw_tokens": float(np.percentile(all_raw_tokens, 90)),
            "p95_raw_tokens": float(np.percentile(all_raw_tokens, 95)),
            "min_raw_tokens": int(np.min(all_raw_tokens)),
            "max_raw_tokens": int(np.max(all_raw_tokens)),
            "mean_packaging_overhead_tokens": float(np.mean(all_overhead)),
            "mean_packaged_tokens": float(np.mean(all_pkg_tokens)),
        },
        "query_level_total_gold_tokens": {
            "mean_packaged_tokens": float(np.mean(all_q_pkg)),
            "std_packaged_tokens": float(np.std(all_q_pkg)),
            "median_packaged_tokens": float(np.median(all_q_pkg)),
            "p25_packaged_tokens": float(np.percentile(all_q_pkg, 25)),
            "p75_packaged_tokens": float(np.percentile(all_q_pkg, 75)),
            "p90_packaged_tokens": float(np.percentile(all_q_pkg, 90)),
            "p95_packaged_tokens": float(np.percentile(all_q_pkg, 95)),
            "min_packaged_tokens": int(np.min(all_q_pkg)),
            "max_packaged_tokens": int(np.max(all_q_pkg)),
        },
    },
    "budget_feasibility_analysis": {},
}

for B in BUDGETS:
    b_str = str(B)
    b_label = f"{B // 1024}k"
    
    complete_pkg = [q for q in per_query_results if q["feasibility_by_budget"][b_str]["fits_all_packaged"]]
    complete_raw = [q for q in per_query_results if q["feasibility_by_budget"][b_str]["fits_all_raw"]]
    impossible_pkg = [q for q in per_query_results if not q["feasibility_by_budget"][b_str]["fits_all_packaged"]]
    zero_gold_pkg = [q for q in per_query_results if q["feasibility_by_budget"][b_str]["is_zero_gold_feasible"]]

    oracle_retrieved_pkg = sum(q["feasibility_by_budget"][b_str]["oracle_knapsack_max_files"] for q in per_query_results)
    oracle_macro_pkg = float(np.mean([q["feasibility_by_budget"][b_str]["oracle_recall"] for q in per_query_results]))
    oracle_micro_pkg = float(oracle_retrieved_pkg / 514)

    # Multi-gold vs single-gold breakdown
    single_complete = sum(1 for q in complete_pkg if q["num_gold_files"] == 1)
    multi_complete = sum(1 for q in complete_pkg if q["num_gold_files"] > 1)

    # Track breakdown of impossible queries
    track_impossible = defaultdict(int)
    for q in impossible_pkg:
        track_impossible[q["track"]] += 1

    # Repo breakdown of impossible queries
    repo_impossible = defaultdict(int)
    for q in impossible_pkg:
        repo_impossible[q["repo"]] += 1

    # Detailed impossible queries info
    impossible_ledger = []
    for q in impossible_pkg:
        impossible_ledger.append({
            "query_id": q["query_id"],
            "repo": q["repo"],
            "track": q["track"],
            "num_gold_files": q["num_gold_files"],
            "total_packaged_tokens": q["total_gold_packaged_tokens"],
            "budget_overflow_tokens": q["total_gold_packaged_tokens"] - B,
            "oracle_max_gold_retrievable": q["feasibility_by_budget"][b_str]["oracle_knapsack_max_files"],
            "oracle_recall_ceiling": q["feasibility_by_budget"][b_str]["oracle_recall"],
        })

    oracle_ceiling["budget_feasibility_analysis"][b_label] = {
        "budget_tokens": B,
        "complete_gold_coverage_ceiling": {
            "feasible_queries_count": len(complete_pkg),
            "feasible_queries_pct": float(len(complete_pkg) / 345),
            "single_gold_feasible_count": single_complete,
            "single_gold_feasible_pct": float(single_complete / 227),
            "multi_gold_feasible_count": multi_complete,
            "multi_gold_feasible_pct": float(multi_complete / 118),
        },
        "raw_tokens_comparison": {
            "raw_feasible_queries_count": len(complete_raw),
            "raw_feasible_queries_pct": float(len(complete_raw) / 345),
            "packaging_overhead_penalty_queries": len(complete_raw) - len(complete_pkg),
        },
        "impossibility_metrics": {
            "impossible_queries_count": len(impossible_pkg),
            "impossible_queries_pct": float(len(impossible_pkg) / 345),
            "zero_gold_feasible_queries_count": len(zero_gold_pkg),
            "impossible_by_track": dict(track_impossible),
            "impossible_by_repo": dict(repo_impossible),
        },
        "oracle_recall_ceilings": {
            "knapsack_micro_recall_ceiling": oracle_micro_pkg,
            "knapsack_macro_recall_ceiling": oracle_macro_pkg,
            "oracle_gold_files_retrieved": oracle_retrieved_pkg,
            "total_gold_files": 514,
        },
        "impossible_queries_ledger": impossible_ledger,
    }

json_path = OUT_DIR / "M3_ORACLE_CEILING.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(oracle_ceiling, f, indent=2)

print(f"Written comprehensive ceiling analysis to {json_path}")

