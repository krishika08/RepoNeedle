import json
import time
import re
import csv
from pathlib import Path
from collections import defaultdict
import numpy as np
import sys

sys.path.insert(0, ".")
from research.v1_accuracy.m3_cud_pack.cud_pack_engine import (
    CUDPackOptimizer,
    ExactTokenizer,
    ContextTier,
    TOKEN_RE,
)
from reponeedle.core.tokenizer import CodeTokenizer

ARB_DIR = Path("external/agent-retrieval-bench")
OUT_DIR = Path("research/v1_accuracy/m3_cud_pack")
OUT_DIR.mkdir(parents=True, exist_ok=True)

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

# Load independent compact-context acceptance suite
with open(OUT_DIR / "compact_context_acceptance_suite.json", "r", encoding="utf-8") as f:
    compact_suite = json.load(f)
compact_suite_qids = {s["query_id"]: s for s in compact_suite}

# Group queries by corpus
queries_by_corpus = defaultdict(list)
for q in queries:
    queries_by_corpus[(q["repo"], q["commit"])].append(q)

exact_tok = ExactTokenizer()
optimizer = CUDPackOptimizer(exact_tok)
tok = CodeTokenizer()

BUDGETS = [2048, 4096, 8192, 16384, 32768]

per_query_results = []
budget_aggregate_records = defaultdict(list)
acceptance_suite_eval = []

start_total_time = time.perf_counter()

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
        track = q["track"]
        golds = set(q["gold_files"])
        num_golds = len(golds)
        q_text = q["query_text"]
        q_terms = tok.tokenize_text(q_text)

        # Build candidate pool with content
        pool = []
        for c in q["candidates"][:85]:
            c_copy = dict(c)
            c_copy["content"] = file_chunks.get(c["path"], "")
            pool.append(c_copy)

        q_budget_outputs = {}

        for B in BUDGETS:
            # Select mode: 2k & 4k compact mode option, >= 8k complete mode
            mode = "compact" if B <= 4096 else "complete"
            
            t0 = time.perf_counter()
            selected = optimizer.pack_context(
                candidate_pool=pool,
                budget_tokens=B,
                query_text=q_text,
                query_terms=q_terms,
                track=track,
                mode=mode,
            )
            pack_lat_ms = (time.perf_counter() - t0) * 1000

            tot_pkg_tok = sum(s.packaged_tokens for s in selected)
            tot_content_tok = sum(s.content_tokens for s in selected)
            tot_overhead = tot_pkg_tok - tot_content_tok

            # Hard invariant verification
            assert tot_pkg_tok <= B, f"CRITICAL OVERFLOW: {tot_pkg_tok} > {B}"

            # Gold target accounting
            selected_paths = {s.path: s for s in selected}
            full_golds = {s.path for s in selected if s.path in golds and s.tier == ContextTier.FULL}
            span_golds = {s.path for s in selected if s.path in golds and s.tier == ContextTier.FOCUS_SPAN}
            skel_golds = {s.path for s in selected if s.path in golds and s.tier == ContextTier.SKELETON}
            any_golds = full_golds | span_golds | skel_golds
            impl_golds = full_golds | span_golds  # implementation preserved

            gold_full_c = len(full_golds)
            gold_span_c = len(span_golds)
            gold_skel_c = len(skel_golds)
            gold_any_c = len(any_golds)
            gold_impl_c = len(impl_golds)
            gold_excl_c = num_golds - gold_any_c

            complete_gold_full = (gold_full_c == num_golds)
            complete_gold_impl = (gold_impl_c == num_golds)
            complete_gold_any = (gold_any_c == num_golds)

            micro_rec_full = gold_full_c / num_golds
            micro_rec_impl = gold_impl_c / num_golds
            micro_rec_any = gold_any_c / num_golds

            # Token yield
            gold_tokens = sum(s.packaged_tokens for s in selected if s.path in golds)
            dist_tokens = tot_pkg_tok - gold_tokens
            yield_pct = gold_tokens / tot_pkg_tok if tot_pkg_tok > 0 else 0.0

            # Redundancy check (same directory count)
            dirs_seen = set()
            dup_dir_count = 0
            for s in selected:
                d = "/".join(s.path.split("/")[:-1])
                if d in dirs_seen:
                    dup_dir_count += 1
                else:
                    dirs_seen.add(d)
            redundancy_ratio = dup_dir_count / len(selected) if selected else 0.0

            # Acceptance suite span verification
            span_success = False
            if qid in compact_suite_qids and B == 4096:
                suite_item = compact_suite_qids[qid]
                all_spans_found = True
                for span_req in suite_item["annotated_spans"]:
                    req_path = span_req["gold_path"]
                    req_sym = span_req["target_symbol"]
                    if req_path not in selected_paths:
                        all_spans_found = False
                        break
                    sel_item = selected_paths[req_path]
                    # If full, symbol is definitely present; if focus span, check if symbol name is in rendered_content
                    if req_sym != "module_level" and req_sym.lower() not in sel_item.rendered_content.lower():
                        all_spans_found = False
                        break
                span_success = all_spans_found
                acceptance_suite_eval.append({
                    "query_id": qid,
                    "all_spans_found": all_spans_found,
                    "selected_tiers": [selected_paths[g].tier.value for g in suite_item["gold_files"] if g in selected_paths],
                })

            b_record = {
                "budget_tokens": B,
                "mode": mode,
                "packing_latency_ms": pack_lat_ms,
                "selected_files_count": len(selected),
                "full_files_count": sum(1 for s in selected if s.tier == ContextTier.FULL),
                "focus_span_count": sum(1 for s in selected if s.tier == ContextTier.FOCUS_SPAN),
                "skeleton_count": sum(1 for s in selected if s.tier == ContextTier.SKELETON),
                "packaged_tokens": tot_pkg_tok,
                "content_tokens": tot_content_tok,
                "packaging_overhead": tot_overhead,
                "remaining_budget": B - tot_pkg_tok,
                "budget_utilization": tot_pkg_tok / B,
                "is_overflow": False,
                "gold_metrics": {
                    "num_golds": num_golds,
                    "gold_full_count": gold_full_c,
                    "gold_focus_span_count": gold_span_c,
                    "gold_skeleton_count": gold_skel_c,
                    "gold_any_count": gold_any_c,
                    "gold_impl_count": gold_impl_c,
                    "gold_excluded_count": gold_excl_c,
                    "complete_gold_full": complete_gold_full,
                    "complete_gold_impl": complete_gold_impl,
                    "complete_gold_any": complete_gold_any,
                    "micro_recall_full": micro_rec_full,
                    "micro_recall_impl": micro_rec_impl,
                    "micro_recall_any": micro_rec_any,
                    "gold_packaged_tokens": gold_tokens,
                    "distractor_packaged_tokens": dist_tokens,
                    "relevant_token_yield": yield_pct,
                },
                "redundancy_ratio": redundancy_ratio,
                "selected_files": [
                    {
                        "path": s.path,
                        "tier": s.tier.value,
                        "rank": s.rank,
                        "score": s.score,
                        "packaged_tokens": s.packaged_tokens,
                        "is_gold": s.path in golds,
                        "reason": s.reason,
                    }
                    for s in selected
                ],
            }

            q_budget_outputs[str(B)] = b_record
            budget_aggregate_records[B].append(b_record)

        per_query_results.append({
            "query_id": qid,
            "repo": repo,
            "commit": commit,
            "track": track,
            "gold_files": list(golds),
            "num_gold_files": num_golds,
            "budgets": q_budget_outputs,
        })

per_query_results.sort(key=lambda x: x["query_id"])

# Write PER_QUERY_PACKING_RESULTS.jsonl
jsonl_path = OUT_DIR / "PER_QUERY_PACKING_RESULTS.jsonl"
with open(jsonl_path, "w", encoding="utf-8") as f:
    for r in per_query_results:
        f.write(json.dumps(r) + "\n")
print(f"Written {len(per_query_results)} query records to {jsonl_path}")

total_eval_time = time.perf_counter() - start_total_time

# Build CSV Comparison
csv_path = OUT_DIR / "TOKEN_BUDGET_COMPARISON.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Budget", "Mode", "Complete_Full_Coverage", "Complete_Impl_Coverage", "Complete_Any_Coverage",
        "Micro_Recall_Full", "Micro_Recall_Impl", "Micro_Recall_Any",
        "Macro_Recall_Full", "Macro_Recall_Impl", "Macro_Recall_Any",
        "Gold_Impl_Preservation_Rate", "Skeletonization_Rate", "Exclusion_Rate",
        "Mean_Utilization", "Relevant_Token_Yield", "Redundancy_Ratio",
        "Exact_Overflow_Count", "Exact_Overflow_Rate", "Median_Latency_ms", "P95_Latency_ms"
    ])

    summary_data = {
        "metadata": {
            "mission": "RepoNeedle V1.0.0 — Milestone 3.3 Zero-Loss Context Packing Engine (CUD-Pack)",
            "benchmark_scope": "Agent-Retrieval-Bench v2 (345 Queries, 25 Repositories, 514 Gold Targets)",
            "exact_tokenizer": "regex_code_tokenizer_v1",
            "total_evaluation_time_seconds": total_eval_time,
        },
        "compact_acceptance_suite": {
            "total_annotated_queries": len(acceptance_suite_eval),
            "successful_span_coverage_count": sum(1 for a in acceptance_suite_eval if a["all_spans_found"]),
            "span_coverage_rate": sum(1 for a in acceptance_suite_eval if a["all_spans_found"]) / len(acceptance_suite_eval) if acceptance_suite_eval else 1.0,
        },
        "budget_summaries": {},
    }

    for B in BUDGETS:
        records = budget_aggregate_records[B]
        n_queries = len(records)
        total_golds = 514

        comp_full = sum(1 for r in records if r["gold_metrics"]["complete_gold_full"])
        comp_impl = sum(1 for r in records if r["gold_metrics"]["complete_gold_impl"])
        comp_any = sum(1 for r in records if r["gold_metrics"]["complete_gold_any"])

        tot_g_full = sum(r["gold_metrics"]["gold_full_count"] for r in records)
        tot_g_span = sum(r["gold_metrics"]["gold_focus_span_count"] for r in records)
        tot_g_skel = sum(r["gold_metrics"]["gold_skeleton_count"] for r in records)
        tot_g_impl = tot_g_full + tot_g_span
        tot_g_any = sum(r["gold_metrics"]["gold_any_count"] for r in records)
        tot_g_excl = sum(r["gold_metrics"]["gold_excluded_count"] for r in records)

        micro_full = tot_g_full / total_golds
        micro_impl = tot_g_impl / total_golds
        micro_any = tot_g_any / total_golds

        macro_full = float(np.mean([r["gold_metrics"]["micro_recall_full"] for r in records]))
        macro_impl = float(np.mean([r["gold_metrics"]["micro_recall_impl"] for r in records]))
        macro_any = float(np.mean([r["gold_metrics"]["micro_recall_any"] for r in records]))

        impl_pres_rate = tot_g_impl / total_golds
        skel_rate = tot_g_skel / total_golds
        excl_rate = tot_g_excl / total_golds

        utils = [r["budget_utilization"] for r in records]
        yields = [r["gold_metrics"]["relevant_token_yield"] for r in records]
        reduns = [r["redundancy_ratio"] for r in records]
        lats = [r["packing_latency_ms"] for r in records]

        overflow_c = sum(1 for r in records if r["is_overflow"])

        mode_str = records[0]["mode"]

        writer.writerow([
            f"{B // 1024}k", mode_str, f"{comp_full/n_queries:.4f}", f"{comp_impl/n_queries:.4f}", f"{comp_any/n_queries:.4f}",
            f"{micro_full:.4f}", f"{micro_impl:.4f}", f"{micro_any:.4f}",
            f"{macro_full:.4f}", f"{macro_impl:.4f}", f"{macro_any:.4f}",
            f"{impl_pres_rate:.4f}", f"{skel_rate:.4f}", f"{excl_rate:.4f}",
            f"{np.mean(utils):.4f}", f"{np.mean(yields):.4f}", f"{np.mean(reduns):.4f}",
            overflow_c, f"{overflow_c/n_queries:.4f}",
            f"{np.median(lats):.2f}", f"{np.percentile(lats, 95):.2f}"
        ])

        summary_data["budget_summaries"][str(B)] = {
            "budget": B,
            "mode": mode_str,
            "complete_gold_full_pct": comp_full / n_queries,
            "complete_gold_impl_pct": comp_impl / n_queries,
            "complete_gold_any_pct": comp_any / n_queries,
            "micro_recall_full": micro_full,
            "micro_recall_impl": micro_impl,
            "micro_recall_any": micro_any,
            "macro_recall_full": macro_full,
            "macro_recall_impl": macro_impl,
            "macro_recall_any": macro_any,
            "implementation_preservation_rate": impl_pres_rate,
            "skeletonization_rate": skel_rate,
            "exclusion_rate": excl_rate,
            "mean_utilization": float(np.mean(utils)),
            "mean_yield": float(np.mean(yields)),
            "mean_redundancy": float(np.mean(reduns)),
            "overflow_count": overflow_c,
            "overflow_rate": 0.0,
            "median_latency_ms": float(np.median(lats)),
            "p95_latency_ms": float(np.percentile(lats, 95)),
        }

# Write summary JSON
sum_path = OUT_DIR / "cud_pack_metrics_summary.json"
with open(sum_path, "w", encoding="utf-8") as f:
    json.dump(summary_data, f, indent=2)

print(f"Written CSV comparison to {csv_path}")
print(f"Written summary metrics to {sum_path}")

print("\n" + "=" * 80)
print("CUD-PACK FULL BENCHMARK EVALUATION RESULTS (N=345):")
print("=" * 80)
for B in BUDGETS:
    s = summary_data["budget_summaries"][str(B)]
    print(f"Budget {B // 1024:>2}k ({s['mode']:8}): Complete(Full)={s['complete_gold_full_pct']:.2%} | Complete(Impl)={s['complete_gold_impl_pct']:.2%} | Complete(Any)={s['complete_gold_any_pct']:.2%} | Micro(Any)={s['micro_recall_any']:.4f} | Yield={s['mean_yield']:.2%} | Overflows={s['overflow_count']} | Latency(P50)={s['median_latency_ms']:.1f}ms | Latency(P95)={s['p95_latency_ms']:.1f}ms")
print("=" * 80)
print(f"Compact Acceptance Suite (N=20): {summary_data['compact_acceptance_suite']['successful_span_coverage_count']}/{summary_data['compact_acceptance_suite']['total_annotated_queries']} ({summary_data['compact_acceptance_suite']['span_coverage_rate']:.2%}) spans covered.")

