"""
Stage 3.2 Candidate Evaluation Suite.
Evaluates the 7 frozen systems under strictly matched conditions:
  - BASE-BM25
  - BASE-REPOMAP
  - CAND-A (Static Hybrid Full)
  - CAND-B (Candidate A + Skeletons)
  - CAND-C (Candidate B + Doc Filter 0.5x)
  - CAND-D (Candidate C + Graph Diffusion)
  - CAND-E (Candidate D + Polyglot Symbols)

Generates:
  - research/stage3_2/CANDIDATE_EVALUATION.csv
  - research/stage3_2/PER_REPOSITORY_RESULTS.csv
  - research/stage3_2/PER_SAMPLE_RESULTS.jsonl
"""

import sys
import time
import json
import csv
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from reponeedle.models import FileDoc, Query, BudgetConfig, AblationConfig, ContextTier
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.tokenizer import estimate_tokens
from benchmarks.baselines import BM25Baseline, RepoMapBaseline
from research.stage3.build_independent_benchmark import create_benchmark_instances

STAGE3_2_DIR = Path(__file__).resolve().parent


def evaluate_system(
    sys_id: str,
    ablation: AblationConfig,
    inst: dict,
    budget_tokens: int = 8000,
) -> dict:
    docs = inst["docs"]
    gold_files = set(inst["gold_files"])
    query_text = inst["problem_statement"]

    t0 = time.perf_counter()

    if sys_id == "BASE-BM25":
        engine = RepoNeedleEngine.from_documents(docs, ablation_config=ablation)
        res = engine.retrieve(query_text, budget_tokens=budget_tokens, ablation_config=ablation)
        ranked_paths = [f.path for f in res.selected_files]
        selected_files = res.selected_files
    elif sys_id == "BASE-REPOMAP":
        repo_map = RepoMapBaseline(docs)
        res = repo_map.retrieve(query_text, budget_tokens=budget_tokens)
        ranked_paths = [f.path for f in res.selected_files]
        selected_files = res.selected_files
    else:
        engine = RepoNeedleEngine.from_documents(docs, ablation_config=ablation)
        res = engine.retrieve(query_text, budget_tokens=budget_tokens, ablation_config=ablation)
        ranked_paths = [f.path for f in res.selected_files]
        selected_files = res.selected_files

    lat_ms = (time.perf_counter() - t0) * 1000

    # 1. Ranking Metric: MRR (Explicitly defined as separate first-hit reciprocal rank)
    mrr = 0.0
    for r_idx, p in enumerate(ranked_paths):
        if p in gold_files:
            mrr = 1.0 / (r_idx + 1)
            break

    r20_hit = any(p in gold_files for p in ranked_paths[:20])
    recall_at_20 = 1.0 if r20_hit else 0.0

    # 2. Context Metrics
    retrieved_paths = set(ranked_paths)
    intersect = retrieved_paths.intersection(gold_files)

    context_recall = len(intersect) / max(1, len(gold_files))
    context_precision = len(intersect) / max(1, len(retrieved_paths))
    if context_recall + context_precision > 0:
        context_f1 = (2.0 * context_recall * context_precision) / (context_recall + context_precision)
    else:
        context_f1 = 0.0

    # 3. Token-Budget Efficiency (BCY@8k)
    total_tokens_used = 0
    gold_tokens_retrieved = 0
    total_gold_tokens = 0
    for d in docs:
        d_tok = d.token_count if d.token_count > 0 else estimate_tokens(d.content)
        if d.path in gold_files:
            total_gold_tokens += d_tok

    for sf in selected_files:
        toks = sf.token_count if getattr(sf, 'token_count', 0) > 0 else estimate_tokens(getattr(sf, 'rendered_content', getattr(sf, 'content', '')))
        total_tokens_used += toks
        sf_path = sf.path if hasattr(sf, 'path') else sf[0].path
        if sf_path in gold_files:
            gold_tokens_retrieved += toks

    bcy_denom = max(1, min(budget_tokens, total_gold_tokens))
    bcy_8k = min(1.0, gold_tokens_retrieved / bcy_denom)
    token_efficiency = gold_tokens_retrieved / max(1, total_tokens_used)

    return {
        "mrr": mrr,
        "recall@20": recall_at_20,
        "context_recall": context_recall,
        "context_precision": context_precision,
        "context_f1": context_f1,
        "bcy@8k": bcy_8k,
        "token_efficiency": token_efficiency,
        "latency_ms": lat_ms,
        "total_tokens_used": total_tokens_used,
        "files_retrieved": len(ranked_paths),
    }


def run_stage3_2_eval():
    instances = create_benchmark_instances()
    systems = [
        ("BASE-BM25", "Pure BM25 Baseline", AblationConfig.bm25_baseline()),
        ("BASE-REPOMAP", "Aider-Style RepoMap Reference", None),
        ("CAND-A", "Static Hybrid Full Files", AblationConfig.candidate_a()),
        ("CAND-B", "Candidate A + Skeletons", AblationConfig.candidate_b()),
        ("CAND-C", "Candidate B + Doc Filter 0.5x", AblationConfig.candidate_c()),
        ("CAND-D", "Candidate C + Graph Diffusion", AblationConfig.candidate_d()),
        ("CAND-E", "Candidate D + Polyglot Symbols", AblationConfig.candidate_e()),
    ]

    all_records = []
    agg = {s[0]: {"held_out": defaultdict(list), "replication": defaultdict(list)} for s in systems}
    repo_breakdown = defaultdict(lambda: {s[0]: defaultdict(list) for s in systems})

    for inst in instances:
        inst_id = inst["instance_id"]
        repo = inst["repo"]
        part = inst["partition"]
        lang = inst["language"]

        for sys_id, sys_name, ablation in systems:
            m = evaluate_system(sys_id, ablation, inst)
            rec = {
                "instance_id": inst_id,
                "repo": repo,
                "partition": part,
                "language": lang,
                "system_id": sys_id,
                **m,
            }
            all_records.append(rec)
            for k, v in m.items():
                agg[sys_id][part][k].append(v)
                repo_breakdown[repo][sys_id][k].append(v)

    # 1. Output CANDIDATE_EVALUATION.csv
    eval_csv = STAGE3_2_DIR / "CANDIDATE_EVALUATION.csv"
    with open(eval_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "System ID",
            "System Name",
            "Partition",
            "Sample Count",
            "Context Recall@8k",
            "Context Precision@8k",
            "Context F1",
            "BCY@8k",
            "Token Efficiency",
            "Separate MRR",
            "Recall@20",
            "Mean Latency (ms)",
        ])
        for sys_id, sys_name, _ in systems:
            for part in ["held_out", "replication"]:
                p = agg[sys_id][part]
                writer.writerow([
                    sys_id,
                    sys_name,
                    part.upper(),
                    len(p["context_recall"]),
                    f"{np.mean(p['context_recall']):.4f}",
                    f"{np.mean(p['context_precision']):.4f}",
                    f"{np.mean(p['context_f1']):.4f}",
                    f"{np.mean(p['bcy@8k']):.4f}",
                    f"{np.mean(p['token_efficiency']):.4f}",
                    f"{np.mean(p['mrr']):.4f}",
                    f"{np.mean(p['recall@20']):.4f}",
                    f"{np.mean(p['latency_ms']):.2f}",
                ])

    # 2. Output PER_REPOSITORY_RESULTS.csv
    repo_csv = STAGE3_2_DIR / "PER_REPOSITORY_RESULTS.csv"
    with open(repo_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Repository",
            "Partition",
            "Language",
            "System ID",
            "Context Recall@8k",
            "Context Precision@8k",
            "Context F1",
            "BCY@8k",
            "Separate MRR",
            "Mean Latency (ms)",
        ])
        for repo in sorted(repo_breakdown.keys()):
            ex = next(i for i in instances if i["repo"] == repo)
            part = ex["partition"].upper()
            lang = ex["language"]
            for sys_id, _, _ in systems:
                m = repo_breakdown[repo][sys_id]
                writer.writerow([
                    repo,
                    part,
                    lang,
                    sys_id,
                    f"{np.mean(m['context_recall']):.4f}",
                    f"{np.mean(m['context_precision']):.4f}",
                    f"{np.mean(m['context_f1']):.4f}",
                    f"{np.mean(m['bcy@8k']):.4f}",
                    f"{np.mean(m['mrr']):.4f}",
                    f"{np.mean(m['latency_ms']):.2f}",
                ])

    # 3. Output PER_SAMPLE_RESULTS.jsonl
    jsonl_file = STAGE3_2_DIR / "PER_SAMPLE_RESULTS.jsonl"
    with open(jsonl_file, "w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r) + "\n")

    print(f"Generated {eval_csv}")
    print(f"Generated {repo_csv}")
    print(f"Generated {jsonl_file}")


if __name__ == "__main__":
    run_stage3_2_eval()
