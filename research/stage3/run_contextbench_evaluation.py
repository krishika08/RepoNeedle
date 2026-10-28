"""
Stage 3 Independent ContextBench Evaluation Runner.
Evaluates 7 systems:
  - BASE-BM25: Pure BM25 Baseline
  - BASE-REPOMAP: Aider-Style RepoMap Baseline
  - CAND-A: Static Hybrid Full Files Only
  - CAND-B: Static Hybrid w/ Skeleton Compression
  - CAND-C: Candidate B + Documentation Distractor Filtering
  - CAND-D: Candidate C + Relevance-Aware Graph Diffusion
  - CAND-E: Candidate D + Multilingual Polyglot Symbol Extraction

Across both:
  1. PARTITION_HELD_OUT (14 repos, 14 instances)
  2. PARTITION_REPLICATION (5 repos, 5 instances)

Computes Context Recall, Context Precision, Context F1, BCY@8k, MRR, R@5, R@10, R@20,
Block-Level Retention, Latency, and Memory.
"""

import sys
import time
import json
import csv
import tracemalloc
from typing import Dict, Any, List, Optional
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from reponeedle.models import FileDoc, Query, BudgetConfig, AblationConfig, ContextTier
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.tokenizer import CodeTokenizer, estimate_tokens
from benchmarks.baselines import BM25Baseline, RepoMapBaseline
from research.stage3.build_independent_benchmark import create_benchmark_instances

STAGE3_DIR = Path(__file__).resolve().parent


def evaluate_system_on_instance(
    system_id: str,
    ablation: AblationConfig,
    inst: Dict[str, Any],
    budget_tokens: int = 8000,
) -> Dict[str, Any]:
    """
    Executes a single system retrieval on an instance and computes all official IR metrics.
    """
    docs = inst["docs"]
    gold_files = inst["gold_files"]
    gold_blocks = inst["gold_blocks"]
    query_text = inst["problem_statement"]

    t0 = time.perf_counter()

    if system_id == "BASE-BM25":
        engine = RepoNeedleEngine.from_documents(docs, ablation_config=ablation)
        res = engine.retrieve(query_text, budget_tokens=budget_tokens, ablation_config=ablation)
        ranked_paths = [f.path for f in res.selected_files]
        selected_files = res.selected_files
    elif system_id == "BASE-REPOMAP":
        # Aider-style RepoMap baseline: AST PageRank + call graph
        repo_map = RepoMapBaseline(docs)
        res = repo_map.retrieve(query_text, budget_tokens=budget_tokens)
        ranked_paths = [f.path for f in res.selected_files]
        selected_files = res.selected_files
    else:
        # RepoNeedle Candidates A, B, C, D, E
        engine = RepoNeedleEngine.from_documents(docs, ablation_config=ablation)
        res = engine.retrieve(query_text, budget_tokens=budget_tokens, ablation_config=ablation)
        ranked_paths = [f.path for f in res.selected_files]
        selected_files = res.selected_files

    latency_ms = (time.perf_counter() - t0) * 1000

    # 1. Ranking Metrics (MRR, Recall@k)
    mrr = 0.0
    for r_idx, p in enumerate(ranked_paths):
        if p in gold_files:
            mrr = 1.0 / (r_idx + 1)
            break

    r5_hit = any(p in gold_files for p in ranked_paths[:5])
    r10_hit = any(p in gold_files for p in ranked_paths[:10])
    r20_hit = any(p in gold_files for p in ranked_paths[:20])

    recall_at_5 = 1.0 if r5_hit else 0.0
    recall_at_10 = 1.0 if r10_hit else 0.0
    recall_at_20 = 1.0 if r20_hit else 0.0

    # 2. Context Metrics (Context Recall, Context Precision, F1, BCY)
    retrieved_paths_set = set(ranked_paths)
    gold_set = set(gold_files)
    intersect = retrieved_paths_set.intersection(gold_set)

    context_recall = len(intersect) / max(1, len(gold_set))
    context_precision = len(intersect) / max(1, len(retrieved_paths_set))
    if context_recall + context_precision > 0:
        context_f1 = (2.0 * context_recall * context_precision) / (context_recall + context_precision)
    else:
        context_f1 = 0.0

    # Token-level BCY
    total_tokens_used = 0
    gold_tokens_retrieved = 0
    total_gold_tokens = 0
    for d in docs:
        d_tok = d.token_count if d.token_count > 0 else estimate_tokens(d.content)
        if d.path in gold_set:
            total_gold_tokens += d_tok

    for sf in selected_files:
        toks = sf.token_count if getattr(sf, 'token_count', 0) > 0 else estimate_tokens(getattr(sf, 'rendered_content', getattr(sf, 'content', '')))
        total_tokens_used += toks
        sf_path = sf.path if hasattr(sf, 'path') else sf[0].path
        if sf_path in gold_set:
            gold_tokens_retrieved += toks

    bcy_denom = max(1, min(budget_tokens, total_gold_tokens))
    bcy_8k = min(1.0, gold_tokens_retrieved / bcy_denom)
    token_efficiency = gold_tokens_retrieved / max(1, total_tokens_used)

    # 3. Block-Level Retrieval Quality
    # Check if gold block name appears in retrieved content/symbols
    blocks_found = 0
    for gb in gold_blocks:
        b_name = gb.split(".")[-1]
        for sf in selected_files:
            sf_content = getattr(sf, 'rendered_content', getattr(sf, 'content', ''))
            sf_syms = getattr(sf, 'symbols', [])
            if b_name in sf_content or b_name in sf_syms:
                blocks_found += 1
                break
    block_recall = blocks_found / max(1, len(gold_blocks))

    return {
        "mrr": mrr,
        "recall@5": recall_at_5,
        "recall@10": recall_at_10,
        "recall@20": recall_at_20,
        "context_recall": context_recall,
        "context_precision": context_precision,
        "context_f1": context_f1,
        "bcy@8k": bcy_8k,
        "token_efficiency": token_efficiency,
        "block_recall": block_recall,
        "latency_ms": latency_ms,
        "tokens_used": total_tokens_used,
        "files_retrieved": len(ranked_paths),
    }


def run_full_contextbench_suite():
    print("=" * 80)
    print("STAGE 3 CONTEXTBENCH INDEPENDENT EVALUATION")
    print("=" * 80)

    instances = create_benchmark_instances()
    systems = [
        ("BASE-BM25", "Pure BM25 Baseline", AblationConfig.bm25_baseline()),
        ("BASE-REPOMAP", "Aider-Style RepoMap Reference", None),
        ("CAND-A", "Static Hybrid Full Files Only", AblationConfig.candidate_a()),
        ("CAND-B", "Candidate A + Structural Skeletons", AblationConfig.candidate_b()),
        ("CAND-C", "Candidate B + Doc Distractor Filtering", AblationConfig.candidate_c()),
        ("CAND-D", "Candidate C + Relevance Graph Diffusion", AblationConfig.candidate_d()),
        ("CAND-E", "Candidate D + Polyglot Symbol Extraction", AblationConfig.candidate_e()),
    ]

    all_sample_results = []
    # system_id -> partition -> list of dicts
    agg_results = {s[0]: {"held_out": defaultdict(list), "replication": defaultdict(list)} for s in systems}
    repo_results = defaultdict(lambda: {s[0]: defaultdict(list) for s in systems})

    for inst in instances:
        inst_id = inst["instance_id"]
        repo = inst["repo"]
        part = inst["partition"]
        lang = inst["language"]

        for sys_id, sys_name, ablation in systems:
            metrics = evaluate_system_on_instance(sys_id, ablation, inst)
            rec = {
                "instance_id": inst_id,
                "repo": repo,
                "partition": part,
                "language": lang,
                "system_id": sys_id,
                **metrics,
            }
            all_sample_results.append(rec)
            for k, v in metrics.items():
                agg_results[sys_id][part][k].append(v)
                repo_results[repo][sys_id][k].append(v)

    # 1. Output CONTEXTBENCH_RESULTS.csv (Partition-Level Aggregates)
    cb_results_file = STAGE3_DIR / "CONTEXTBENCH_RESULTS.csv"
    with open(cb_results_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "System ID",
            "System Name",
            "Partition",
            "Instance Count",
            "Context Recall@8k",
            "Context Precision@8k",
            "Context F1",
            "BCY@8k",
            "Token Efficiency",
            "Block Recall",
            "MRR",
            "Recall@20",
            "Mean Latency (ms)",
        ])

        for sys_id, sys_name, _ in systems:
            for part in ["held_out", "replication"]:
                p_metrics = agg_results[sys_id][part]
                cnt = len(p_metrics["mrr"])
                writer.writerow([
                    sys_id,
                    sys_name,
                    part.upper(),
                    cnt,
                    f"{np.mean(p_metrics['context_recall']):.4f}",
                    f"{np.mean(p_metrics['context_precision']):.4f}",
                    f"{np.mean(p_metrics['context_f1']):.4f}",
                    f"{np.mean(p_metrics['bcy@8k']):.4f}",
                    f"{np.mean(p_metrics['token_efficiency']):.4f}",
                    f"{np.mean(p_metrics['block_recall']):.4f}",
                    f"{np.mean(p_metrics['mrr']):.4f}",
                    f"{np.mean(p_metrics['recall@20']):.4f}",
                    f"{np.mean(p_metrics['latency_ms']):.2f}",
                ])

    print(f"Generated {cb_results_file}")

    # 2. Output PER_REPOSITORY_RESULTS.csv
    repo_results_file = STAGE3_DIR / "PER_REPOSITORY_RESULTS.csv"
    with open(repo_results_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Repository",
            "Partition",
            "Language",
            "System ID",
            "Context Recall@8k",
            "Context F1",
            "BCY@8k",
            "MRR",
            "Recall@20",
            "Mean Latency (ms)",
        ])
        for repo in sorted(repo_results.keys()):
            # Find partition and lang for this repo
            ex = next(i for i in instances if i["repo"] == repo)
            part = ex["partition"].upper()
            lang = ex["language"]
            for sys_id, _, _ in systems:
                m = repo_results[repo][sys_id]
                writer.writerow([
                    repo,
                    part,
                    lang,
                    sys_id,
                    f"{np.mean(m['context_recall']):.4f}",
                    f"{np.mean(m['context_f1']):.4f}",
                    f"{np.mean(m['bcy@8k']):.4f}",
                    f"{np.mean(m['mrr']):.4f}",
                    f"{np.mean(m['recall@20']):.4f}",
                    f"{np.mean(m['latency_ms']):.2f}",
                ])

    print(f"Generated {repo_results_file}")

    # 3. Output PER_SAMPLE_RESULTS.jsonl
    sample_jsonl_file = STAGE3_DIR / "PER_SAMPLE_RESULTS.jsonl"
    with open(sample_jsonl_file, "w", encoding="utf-8") as f:
        for r in all_sample_results:
            f.write(json.dumps(r) + "\n")

    print(f"Generated {sample_jsonl_file}")

    return agg_results


if __name__ == "__main__":
    run_full_contextbench_suite()
