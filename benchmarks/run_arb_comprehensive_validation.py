"""
Comprehensive Independent Validation Runner on Official Agent Retrieval Bench (ARB).

This script performs:
1. Exact evaluation of RepoNeedle and official baselines (BM25, RepoMap, Lexical) on identical
   frozen ARB v0.1 samples (N=35 across 12 repos) using the official ARB evaluator.
2. Full component ablations (w/o WorkflowRouter, w/o AST Graph, w/o Semantic, w/o Lexical).
3. Sample-level paired difference statistical testing (paired t-test, Wilcoxon signed-rank,
   10,000 bootstrap CI of the difference).
4. Repository-grouped and task-grouped evaluations.
5. Individual query failure analysis.
6. Official ARB Selective Abstention Pilot evaluation (N=82: 50 natural no-gold, 32 counterfactual).
"""

import os
import sys
import json
import time
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Tuple
import numpy as np
from scipy import stats

# Add paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "external", "agent-retrieval-bench", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent_retrieval_bench.baseline import (
    evaluate_bm25_baseline,
    evaluate_lexical_baseline,
    sample_metrics,
    summarize_details,
    target_gold_files,
    hard_negative_files,
    query_text_for_eval,
    query_has_leakage,
    synthetic_chunks,
    gold_spans,
    gold_blocks,
    gold_file_ranks,
    unique_ranked_paths,
    line_metrics_at_budget,
    block_metrics_at_budget,
    span_metrics_from_line_metrics,
)
from agent_retrieval_bench.repomap_eval import build_repomap_index, rank_files_for_sample
from agent_retrieval_bench.selective_eval import threshold_metrics, threshold_sweep

from reponeedle.models import FileDoc, Query, TaskType, BudgetConfig
from reponeedle.engine import RepoNeedleEngine


def run_official_repomap_on_arb(samples: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Evaluates official ARB RepoMap baseline on the given samples.
    """
    details = []
    skipped = defaultdict(int)
    t0 = time.monotonic()

    for sample_index, sample in enumerate(samples):
        gold = target_gold_files(sample)
        if not gold:
            skipped["no_gold"] += 1
            continue
        q_text = query_text_for_eval(sample)
        if query_has_leakage(sample, q_text):
            skipped["leakage"] += 1
            continue
        chunks = synthetic_chunks(sample)
        if not chunks:
            skipped["empty_corpus"] += 1
            continue

        index = build_repomap_index(chunks)
        candidate_paths = {c["path"] for c in chunks}
        ranked = rank_files_for_sample(
            sample=sample,
            query_text=q_text,
            index=index,
            candidate_paths=candidate_paths,
            query_weight=0.65,
            pagerank_weight=0.25,
            affinity_weight=0.10,
        )
        ranked_chunks = [{"path": p} for p, score, _ in ranked]
        hard_neg = hard_negative_files(sample)
        metrics = sample_metrics(gold, ranked_chunks, hard_negative_files=hard_neg)

        detail = {
            "_sample_index": sample_index,
            "sample_id": sample.get("id"),
            "task_type": sample.get("task_type"),
            "repo": sample.get("repo"),
            "base_commit": sample.get("base_commit"),
            "candidate_filter": "all_files",
            "ranker": "repomap",
            "gold_files": gold,
            "hard_negative_files": hard_neg,
            "gold_ranks": gold_file_ranks(gold, ranked_chunks),
            "top_files": unique_ranked_paths(ranked_chunks)[:20],
            "metrics": metrics,
        }
        details.append(detail)

    summary = summarize_details(details)
    return {
        "mode": "arb_evaluator",
        "ranker": "repomap",
        "evaluated": len(details),
        "skipped": dict(skipped),
        "metrics": summary,
        "runtime_seconds": time.monotonic() - t0,
    }, details


def run_reponeedle_variant(
    samples: List[Dict[str, Any]],
    variant_name: str = "full",
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Runs RepoNeedle or an ablation variant through the official ARB evaluator.
    Variants:
    - 'full': full RepoNeedle engine
    - 'no_router': disables workflow router, forces generic COMMENT2CONTEXT
    - 'no_graph': clears AST dependency graph and inverted test links
    - 'no_semantic': zeroes out subword semantic scores (lexical-only)
    - 'no_lexical': zeroes out BM25 lexical scores (semantic-only)
    """
    details = []
    skipped = defaultdict(int)
    t0 = time.monotonic()

    for sample_index, sample in enumerate(samples):
        gold = target_gold_files(sample)
        if not gold:
            skipped["no_gold"] += 1
            continue
        q_text = query_text_for_eval(sample)
        if query_has_leakage(sample, q_text):
            skipped["leakage"] += 1
            continue
        chunks = synthetic_chunks(sample)
        if not chunks:
            skipped["empty_corpus"] += 1
            continue

        docs = []
        for c in chunks:
            path = c.get("path", "")
            text = c.get("text", "") or path.replace("/", " ")
            is_test = "test" in path.lower()
            docs.append(FileDoc(path=path, content=text, is_test=is_test))

        # Explicit opt-in (1.2.0+) preserves the historical evaluation semantics.
        engine = RepoNeedleEngine.from_documents(
            docs, budget_config=BudgetConfig(enable_experimental_abstention=True)
        )

        # Apply ablation modifications
        raw_task = sample.get("task_type", "auto")
        if variant_name == "no_router":
            t_type = TaskType.COMMENT2CONTEXT
        else:
            if raw_task == "code2test":
                t_type = TaskType.CODE2TEST
            elif raw_task == "trace2code":
                t_type = TaskType.TRACE2CODE
            elif raw_task == "edit2ripple":
                t_type = TaskType.EDIT2RIPPLE
            else:
                t_type = TaskType.COMMENT2CONTEXT

        if variant_name == "no_graph":
            engine.repo_graph.pagerank_scores = np.zeros(len(docs), dtype=np.float32)
            engine.repo_graph.test_to_target_map.clear()
            engine.repo_graph.target_to_test_map.clear()
            engine.repo_graph.graph.clear()

        # Retrieve
        if variant_name == "no_semantic":
            # Override semantic index score to zeros
            orig_score = engine.semantic_index.score
            engine.semantic_index.score = lambda q: np.zeros(len(docs), dtype=np.float32)
            res = engine.retrieve(query=q_text, budget_tokens=8000, task_type=t_type)
            engine.semantic_index.score = orig_score
        elif variant_name == "no_lexical":
            # Override lexical index score to zeros
            orig_score = engine.lexical_index.score
            engine.lexical_index.score = lambda q: np.zeros(len(docs), dtype=np.float32)
            res = engine.retrieve(query=q_text, budget_tokens=8000, task_type=t_type)
            engine.lexical_index.score = orig_score
        else:
            res = engine.retrieve(query=q_text, budget_tokens=8000, task_type=t_type)

        path_to_chunk = {c.get("path"): c for c in chunks}
        ranked_chunks = []
        seen = set()
        for sf in res.selected_files:
            if sf.path in path_to_chunk and sf.path not in seen:
                ranked_chunks.append(path_to_chunk[sf.path])
                seen.add(sf.path)
        for c in chunks:
            p = c.get("path")
            if p not in seen:
                ranked_chunks.append(c)
                seen.add(p)

        hard_neg = hard_negative_files(sample)
        span_rows = gold_spans(sample)
        block_rows = gold_blocks(sample)
        metrics = sample_metrics(gold, ranked_chunks, hard_negative_files=hard_neg)

        detail = {
            "_sample_index": sample_index,
            "sample_id": sample.get("id"),
            "task_type": sample.get("task_type"),
            "repo": sample.get("repo"),
            "base_commit": sample.get("base_commit"),
            "candidate_filter": "all_files",
            "ranker": f"reponeedle_{variant_name}",
            "gold_files": gold,
            "hard_negative_files": hard_neg,
            "gold_ranks": gold_file_ranks(gold, ranked_chunks),
            "top_files": unique_ranked_paths(ranked_chunks)[:20],
            "metrics": metrics,
            "confidence": res.confidence_score,
            "abstained": res.abstained,
        }
        if span_rows:
            lm = line_metrics_at_budget(span_rows, ranked_chunks)
            metrics.update(span_metrics_from_line_metrics(lm))
        if block_rows:
            bm = block_metrics_at_budget(block_rows, ranked_chunks)
            metrics.update(bm)
        details.append(detail)

    summary = summarize_details(details)
    return {
        "mode": "arb_evaluator",
        "ranker": f"reponeedle_{variant_name}",
        "evaluated": len(details),
        "skipped": dict(skipped),
        "metrics": summary,
        "runtime_seconds": time.monotonic() - t0,
    }, details


def run_arb_details_for_baseline(
    samples: List[Dict[str, Any]],
    ranker_name: str = "bm25",
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Runs official BM25 or Lexical baseline and retains per-sample details.
    """
    from agent_retrieval_bench.baseline import (
        rank_chunks_bm25_with_scores,
        rank_chunks_with_scores,
    )
    details = []
    skipped = defaultdict(int)
    t0 = time.monotonic()

    for sample_index, sample in enumerate(samples):
        gold = target_gold_files(sample)
        if not gold:
            skipped["no_gold"] += 1
            continue
        q_text = query_text_for_eval(sample)
        if query_has_leakage(sample, q_text):
            skipped["leakage"] += 1
            continue
        chunks = synthetic_chunks(sample)
        if not chunks:
            skipped["empty_corpus"] += 1
            continue

        if ranker_name == "bm25":
            scored = rank_chunks_bm25_with_scores(q_text, chunks)
        else:
            scored = rank_chunks_with_scores(q_text, chunks)

        ranked_chunks = [chunk for _, chunk in scored]
        hard_neg = hard_negative_files(sample)
        span_rows = gold_spans(sample)
        block_rows = gold_blocks(sample)
        metrics = sample_metrics(gold, ranked_chunks, hard_negative_files=hard_neg)

        detail = {
            "_sample_index": sample_index,
            "sample_id": sample.get("id"),
            "task_type": sample.get("task_type"),
            "repo": sample.get("repo"),
            "base_commit": sample.get("base_commit"),
            "candidate_filter": "all_files",
            "ranker": ranker_name,
            "gold_files": gold,
            "hard_negative_files": hard_neg,
            "gold_ranks": gold_file_ranks(gold, ranked_chunks),
            "top_files": unique_ranked_paths(ranked_chunks)[:20],
            "metrics": metrics,
            "confidence": float(scored[0][0]) if scored else 0.0,
        }
        if span_rows:
            lm = line_metrics_at_budget(span_rows, ranked_chunks)
            metrics.update(span_metrics_from_line_metrics(lm))
        if block_rows:
            bm = block_metrics_at_budget(block_rows, ranked_chunks)
            metrics.update(bm)
        details.append(detail)

    summary = summarize_details(details)
    return {
        "mode": "arb_evaluator",
        "ranker": ranker_name,
        "evaluated": len(details),
        "skipped": dict(skipped),
        "metrics": summary,
        "runtime_seconds": time.monotonic() - t0,
    }, details


def paired_statistical_test(
    a_scores: List[float],
    b_scores: List[float],
    n_resamples: int = 10000,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """
    Computes paired difference statistics:
    - Delta = a - b
    - Mean Delta, standard error
    - 95% bootstrap CI on the paired difference
    - Paired t-test (two-sided)
    - Wilcoxon signed-rank test (two-sided)
    - Wins / Ties / Losses
    """
    diffs = np.array(a_scores) - np.array(b_scores)
    n = len(diffs)
    mean_diff = float(np.mean(diffs))
    std_diff = float(np.std(diffs, ddof=1)) if n > 1 else 0.0
    se_diff = std_diff / np.sqrt(n) if n > 0 else 0.0

    # 10,000 bootstrap resamples of the paired difference
    rng = np.random.default_rng(random_seed)
    boot_means = np.empty(n_resamples, dtype=np.float64)
    for i in range(n_resamples):
        sample = rng.choice(diffs, size=n, replace=True)
        boot_means[i] = np.mean(sample)
    ci_lower = float(np.percentile(boot_means, 2.5))
    ci_upper = float(np.percentile(boot_means, 97.5))

    # Paired t-test
    if np.all(diffs == 0):
        t_stat, p_ttest = 0.0, 1.0
    else:
        ttest_res = stats.ttest_rel(a_scores, b_scores)
        t_stat, p_ttest = float(ttest_res.statistic), float(ttest_res.pvalue)

    # Wilcoxon signed-rank test
    non_zero = diffs[diffs != 0]
    if len(non_zero) == 0:
        w_stat, p_wilcoxon = 0.0, 1.0
    else:
        try:
            wilc_res = stats.wilcoxon(a_scores, b_scores)
            w_stat, p_wilcoxon = float(wilc_res.statistic), float(wilc_res.pvalue)
        except Exception:
            w_stat, p_wilcoxon = 0.0, 1.0

    wins = int(np.sum(diffs > 1e-6))
    ties = int(np.sum(np.abs(diffs) <= 1e-6))
    losses = int(np.sum(diffs < -1e-6))

    return {
        "n_samples": n,
        "mean_difference": mean_diff,
        "std_difference": std_diff,
        "se_difference": se_diff,
        "bootstrap_ci_95": [ci_lower, ci_upper],
        "paired_t_statistic": t_stat,
        "paired_t_pvalue": p_ttest,
        "wilcoxon_statistic": w_stat,
        "wilcoxon_pvalue": p_wilcoxon,
        "statistically_significant_05": p_ttest < 0.05,
        "wins": wins,
        "ties": ties,
        "losses": losses,
    }


def evaluate_abstention_pilot() -> Dict[str, Any]:
    """
    Evaluates RepoNeedle's SelectiveAbstainer on the official ARB Abstention Pilot
    (data/benchmark/v2_abstention_pilot/abstention.jsonl).
    Contains 82 samples: 50 natural / organic no-gold, 32 counterfactual wrong-repo.
    """
    abs_path = Path("external/agent-retrieval-bench/data/benchmark/v2_abstention_pilot/abstention.jsonl")
    if not abs_path.is_file():
        return {"error": "abstention.jsonl not found"}

    samples = [json.loads(l) for l in abs_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    # Collect corpus chunks by repo from v0_1 samples
    v0_path = Path("external/agent-retrieval-bench/data/benchmark/v0_1/samples.jsonl")
    v0_samples = [json.loads(l) for l in v0_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    repo_to_chunks = defaultdict(list)
    for s in v0_samples:
        r = s.get("repo")
        chs = synthetic_chunks(s)
        repo_to_chunks[r].extend(chs)

    # De-duplicate chunks per repo
    repo_to_unique_docs = {}
    for r, chs in repo_to_chunks.items():
        seen = set()
        docs = []
        for c in chs:
            p = c.get("path")
            if p not in seen:
                seen.add(p)
                docs.append(FileDoc(path=p, content=c.get("text", "") or p.replace("/", " ")))
        repo_to_unique_docs[r] = docs

    results = []
    by_reason = defaultdict(lambda: {"total": 0, "abstained": 0, "returned": 0})

    for s in samples:
        q_dict = s.get("query") or {}
        q_text = q_dict.get("text") or q_dict.get("issue_title") or q_dict.get("pr_title") or ""
        reason = (s.get("gold") or {}).get("reason", "unknown")
        repo = s.get("repo")

        docs = repo_to_unique_docs.get(repo, [])
        if not docs:
            # Fallback: synthesize dummy candidate from repo name
            docs = [FileDoc(path=f"{repo}/src/main.py", content=f"# {repo} main module")]

        # Explicit opt-in (1.2.0+): this selective evaluation measures the experimental heuristic.
        engine = RepoNeedleEngine.from_documents(
            docs, budget_config=BudgetConfig(enable_experimental_abstention=True)
        )
        res = engine.retrieve(query=q_text, budget_tokens=8000)

        should_abstain = res.abstained
        by_reason[reason]["total"] += 1
        if should_abstain:
            by_reason[reason]["abstained"] += 1
        else:
            by_reason[reason]["returned"] += 1

        results.append({
            "id": s.get("id"),
            "repo": repo,
            "reason": reason,
            "is_organic": (s.get("metadata") or {}).get("organic", False),
            "abstained": should_abstain,
            "confidence": res.confidence_score,
            "explanation": res.explanation,
        })

    total = len(samples)
    total_abstained = sum(1 for r in results if r["abstained"])
    total_returned = total - total_abstained
    abstain_recall = total_abstained / total if total > 0 else 0.0

    return {
        "total_evaluated": total,
        "total_abstained": total_abstained,
        "total_returned": total_returned,
        "abstention_rate_on_no_gold": abstain_recall,
        "by_reason": dict(by_reason),
        "sample_breakdown_preview": results[:5],
    }


def main():
    print("=" * 80)
    print("REPONEEDLE INDEPENDENT VALIDATION GATE: OFFICIAL ARB BENCHMARK SUITE")
    print("=" * 80)

    arb_sample_path = Path("external/agent-retrieval-bench/data/benchmark/v0_1/samples.jsonl")
    if not arb_sample_path.is_file():
        print(f"Error: {arb_sample_path} not found.")
        return

    samples = [json.loads(line) for line in arb_sample_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"Loaded {len(samples)} frozen benchmark samples across 12 repositories.")

    # 1. Official Baselines
    print("\n[1/4] Running Official ARB Baselines (BM25, RepoMap, Lexical)...")
    res_bm25, details_bm25 = run_arb_details_for_baseline(samples, "bm25")
    res_repomap, details_repomap = run_official_repomap_on_arb(samples)
    res_lexical, details_lexical = run_arb_details_for_baseline(samples, "lexical")

    print(f"  Official BM25:    MRR = {res_bm25['metrics']['overall']['MRR']:.4f}")
    print(f"  Official RepoMap: MRR = {res_repomap['metrics']['overall']['MRR']:.4f}")
    print(f"  Official Lexical: MRR = {res_lexical['metrics']['overall']['MRR']:.4f}")

    # 2. RepoNeedle Full & Component Ablations
    print("\n[2/4] Running RepoNeedle (Full) and Component Ablations...")
    variants = ["full", "no_router", "no_graph", "no_semantic", "no_lexical"]
    variant_results = {}
    variant_details = {}

    for var in variants:
        t_start = time.perf_counter()
        summary, details = run_reponeedle_variant(samples, var)
        variant_results[var] = summary
        variant_details[var] = details
        dur = (time.perf_counter() - t_start) * 1000
        print(f"  RepoNeedle ({var:<12}): MRR = {summary['metrics']['overall']['MRR']:.4f}  (in {dur:.1f}ms)")

    # 3. Paired Statistical Analysis against each baseline on identical queries
    print("\n[3/4] Performing Paired Difference Statistical Testing (N=35)...")
    full_details = variant_details["full"]
    sample_ids = [d["sample_id"] for d in full_details]

    mrr_full = [d["metrics"]["MRR"] for d in full_details]
    mrr_bm25 = [d["metrics"]["MRR"] for d in details_bm25]
    mrr_repomap = [d["metrics"]["MRR"] for d in details_repomap]
    mrr_lexical = [d["metrics"]["MRR"] for d in details_lexical]

    stat_vs_bm25 = paired_statistical_test(mrr_full, mrr_bm25)
    stat_vs_repomap = paired_statistical_test(mrr_full, mrr_repomap)
    stat_vs_lexical = paired_statistical_test(mrr_full, mrr_lexical)

    # Ablation paired differences against full RepoNeedle
    ablation_stats = {}
    for var in ["no_router", "no_graph", "no_semantic", "no_lexical"]:
        mrr_ab = [d["metrics"]["MRR"] for d in variant_details[var]]
        ablation_stats[var] = paired_statistical_test(mrr_full, mrr_ab)

    print(f"  RepoNeedle vs BM25:    Mean Delta = +{stat_vs_bm25['mean_difference']:.4f} [95% CI: {stat_vs_bm25['bootstrap_ci_95'][0]:.4f}, {stat_vs_bm25['bootstrap_ci_95'][1]:.4f}], p={stat_vs_bm25['paired_t_pvalue']:.4f} (Wins: {stat_vs_bm25['wins']}, Ties: {stat_vs_bm25['ties']}, Losses: {stat_vs_bm25['losses']})")
    print(f"  RepoNeedle vs RepoMap: Mean Delta = +{stat_vs_repomap['mean_difference']:.4f} [95% CI: {stat_vs_repomap['bootstrap_ci_95'][0]:.4f}, {stat_vs_repomap['bootstrap_ci_95'][1]:.4f}], p={stat_vs_repomap['paired_t_pvalue']:.4f} (Wins: {stat_vs_repomap['wins']}, Ties: {stat_vs_repomap['ties']}, Losses: {stat_vs_repomap['losses']})")
    print(f"  RepoNeedle vs Lexical: Mean Delta = +{stat_vs_lexical['mean_difference']:.4f} [95% CI: {stat_vs_lexical['bootstrap_ci_95'][0]:.4f}, {stat_vs_lexical['bootstrap_ci_95'][1]:.4f}], p={stat_vs_lexical['paired_t_pvalue']:.4f} (Wins: {stat_vs_lexical['wins']}, Ties: {stat_vs_lexical['ties']}, Losses: {stat_vs_lexical['losses']})")

    # 4. Repository-grouped breakdown
    repo_grouped = defaultdict(lambda: {"count": 0, "reponeedle_mrr": [], "bm25_mrr": [], "repomap_mrr": []})
    for i in range(len(full_details)):
        r = full_details[i]["repo"]
        repo_grouped[r]["count"] += 1
        repo_grouped[r]["reponeedle_mrr"].append(mrr_full[i])
        repo_grouped[r]["bm25_mrr"].append(mrr_bm25[i])
        repo_grouped[r]["repomap_mrr"].append(mrr_repomap[i])

    repo_summary = {}
    for r, data in repo_grouped.items():
        repo_summary[r] = {
            "samples": data["count"],
            "reponeedle_mrr": float(np.mean(data["reponeedle_mrr"])),
            "bm25_mrr": float(np.mean(data["bm25_mrr"])),
            "repomap_mrr": float(np.mean(data["repomap_mrr"])),
        }

    # 5. Failure Case Inspection
    failures = []
    for i, d in enumerate(full_details):
        rn_mrr = d["metrics"]["MRR"]
        b25_mrr = details_bm25[i]["metrics"]["MRR"]
        rmap_mrr = details_repomap[i]["metrics"]["MRR"]
        if rn_mrr < 1.0 or rn_mrr < b25_mrr or rn_mrr < rmap_mrr:
            failures.append({
                "sample_id": d["sample_id"],
                "repo": d["repo"],
                "task_type": d["task_type"],
                "gold_files": d["gold_files"],
                "reponeedle_mrr": rn_mrr,
                "reponeedle_top_files": d["top_files"][:5],
                "bm25_mrr": b25_mrr,
                "repomap_mrr": rmap_mrr,
                "gold_ranks": d["gold_ranks"],
            })

    print(f"\n  Identified {len(failures)} non-perfect / edge queries for individual failure analysis.")

    # 6. Official ARB Abstention Pilot Evaluation (N=82)
    print("\n[4/4] Evaluating Official ARB Abstention Pilot (N=82)...")
    abstention_results = evaluate_abstention_pilot()
    print(f"  Abstention Pilot Evaluated: {abstention_results.get('total_evaluated')} samples")
    print(f"  Abstention Rate on No-Gold: {abstention_results.get('abstention_rate_on_no_gold')*100:.1f}%")
    for rk, rv in abstention_results.get("by_reason", {}).items():
        print(f"    - {rk}: {rv['abstained']}/{rv['total']} abstained ({rv['abstained']/rv['total']*100:.1f}%)")

    # Save complete evaluation output
    out_dir = Path("benchmarks/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "arb_comprehensive_validation.json"

    validation_payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset_release": "Agent Retrieval Bench v0.1 (Frozen 35-sample benchmark across 12 repos) & v2_abstention_pilot (82 samples)",
        "hardware_environment": {
            "os": "Windows 11",
            "cpu_architecture": "AMD64 / x86_64",
            "gpu_acceleration": "None (CPU Native)",
            "pytorch_installed": False,
            "sentence_transformers_installed": False,
            "onnxruntime_installed": True,
        },
        "overall_metrics": {
            "reponeedle_full": variant_results["full"]["metrics"]["overall"],
            "reponeedle_no_router": variant_results["no_router"]["metrics"]["overall"],
            "reponeedle_no_graph": variant_results["no_graph"]["metrics"]["overall"],
            "reponeedle_no_semantic": variant_results["no_semantic"]["metrics"]["overall"],
            "reponeedle_no_lexical": variant_results["no_lexical"]["metrics"]["overall"],
            "bm25_official": res_bm25["metrics"]["overall"],
            "repomap_official": res_repomap["metrics"]["overall"],
            "lexical_official": res_lexical["metrics"]["overall"],
        },
        "task_breakdown": {
            "code2test": {
                "samples": 17,
                "reponeedle": variant_results["full"]["metrics"]["code2test"],
                "bm25": res_bm25["metrics"]["code2test"],
                "repomap": res_repomap["metrics"]["code2test"],
                "lexical": res_lexical["metrics"]["code2test"],
            },
            "comment2context": {
                "samples": 16,
                "reponeedle": variant_results["full"]["metrics"]["comment2context"],
                "bm25": res_bm25["metrics"]["comment2context"],
                "repomap": res_repomap["metrics"]["comment2context"],
                "lexical": res_lexical["metrics"]["comment2context"],
            },
            "trace2code": {
                "samples": 2,
                "reponeedle": variant_results["full"]["metrics"]["trace2code"],
                "bm25": res_bm25["metrics"]["trace2code"],
                "repomap": res_repomap["metrics"]["trace2code"],
                "lexical": res_lexical["metrics"]["trace2code"],
            },
        },
        "paired_statistical_tests": {
            "vs_bm25": stat_vs_bm25,
            "vs_repomap": stat_vs_repomap,
            "vs_lexical": stat_vs_lexical,
        },
        "component_ablation_paired_stats": ablation_stats,
        "repository_grouped_metrics": repo_summary,
        "abstention_pilot_evaluation": abstention_results,
        "failure_analysis": failures,
    }

    out_path.write_text(json.dumps(validation_payload, indent=2), encoding="utf-8")
    print(f"\nSuccessfully wrote consolidated ARB validation report to: {out_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
