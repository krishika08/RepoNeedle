"""
Official Agent Retrieval Bench evaluation runner for RepoNeedle and baselines.
Uses the exact official ARB evaluation methodology, metric definitions, and sample data.
"""

import sys
import os
import json
import time
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any

# Add ARB source to sys.path
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

from reponeedle.models import FileDoc, Query, TaskType, BudgetConfig
from reponeedle.engine import RepoNeedleEngine


def run_reponeedle_on_arb(
    sample_paths: List[Path],
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Evaluates RepoNeedle on official Agent Retrieval Bench samples using ARB's exact evaluator.
    """
    samples = []
    for p in sample_paths:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    samples.append(json.loads(line))

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

        # Convert ARB candidate chunks into FileDocs for RepoNeedle
        docs = []
        for c in chunks:
            path = c.get("path", "")
            text = c.get("text", "") or path.replace("/", " ")
            is_test = "test" in path.lower()
            docs.append(
                FileDoc(
                    path=path,
                    content=text,
                    is_test=is_test,
                )
            )

        engine = RepoNeedleEngine.from_documents(docs)
        
        # Determine task type
        raw_task = sample.get("task_type", "auto")
        if raw_task == "code2test":
            t_type = TaskType.CODE2TEST
        elif raw_task == "trace2code":
            t_type = TaskType.TRACE2CODE
        elif raw_task == "edit2ripple":
            t_type = TaskType.EDIT2RIPPLE
        else:
            t_type = TaskType.COMMENT2CONTEXT

        # Retrieve with RepoNeedle
        res = engine.retrieve(query=q_text, budget_tokens=8000, task_type=t_type)

        # Map ranked paths back to chunks in ranked order
        path_to_chunk = {c.get("path"): c for c in chunks}
        ranked_chunks = []
        seen = set()
        
        # 1. First add files selected by RepoNeedle
        for sf in res.selected_files:
            if sf.path in path_to_chunk and sf.path not in seen:
                ranked_chunks.append(path_to_chunk[sf.path])
                seen.add(sf.path)

        # 2. Append any remaining unselected chunks
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
            "ranker": "reponeedle",
            "gold_files": gold,
            "gold_spans": span_rows,
            "gold_blocks": block_rows,
            "hard_negative_files": hard_neg,
            "gold_ranks": gold_file_ranks(gold, ranked_chunks),
            "top_files": unique_ranked_paths(ranked_chunks)[:20],
            "metrics": metrics,
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
        "ranker": "reponeedle",
        "evaluated": len(details),
        "skipped": dict(skipped),
        "metrics": summary,
        "runtime_seconds": time.monotonic() - t0,
    }


def main():
    arb_sample_path = Path("external/agent-retrieval-bench/data/benchmark/v0_1/samples.jsonl")
    if not arb_sample_path.is_file():
        print(f"Error: {arb_sample_path} not found.")
        return

    print("=================================================================")
    print("Evaluating Official Agent Retrieval Bench (v0.1 - 35 samples)")
    print("=================================================================")

    # 1. Run ARB Official BM25 Baseline
    res_bm25 = evaluate_bm25_baseline(
        sample_paths=[arb_sample_path],
        corpus_dir=Path("external/agent-retrieval-bench/data"),
        dry_run=True,
    )

    # 2. Run ARB Official Lexical Baseline
    res_lex = evaluate_lexical_baseline(
        sample_paths=[arb_sample_path],
        corpus_dir=Path("external/agent-retrieval-bench/data"),
        dry_run=True,
    )

    # 3. Run RepoNeedle through the exact same ARB Evaluator
    res_rn = run_reponeedle_on_arb(
        sample_paths=[arb_sample_path],
        dry_run=True,
    )

    print("\n--- Summary of Results on ARB v0.1 (Evaluated: 35 samples across 12 repos) ---")
    keys_to_show = ["MRR", "Recall@5", "Recall@10", "Recall@20", "gold_coverage@8k", "context_pollution_tokens@8k"]

    for track in ["overall", "code2test", "comment2context", "trace2code"]:
        print(f"\n[Track: {track.upper()}]")
        print(f"{'Metric':<28} | {'Lexical':<10} | {'BM25':<10} | {'RepoNeedle':<10}")
        print("-" * 65)
        for k in keys_to_show:
            val_lex = res_lex["metrics"].get(track, {}).get(k, 0.0)
            val_bm25 = res_bm25["metrics"].get(track, {}).get(k, 0.0)
            val_rn = res_rn["metrics"].get(track, {}).get(k, 0.0)
            print(f"{k:<28} | {val_lex:<10.3f} | {val_bm25:<10.3f} | {val_rn:<10.3f}")

    # Save to disk
    out_dir = Path("benchmarks/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "arb_official_comparison.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "bm25": res_bm25,
                "lexical": res_lex,
                "reponeedle": res_rn,
            },
            f,
            indent=2,
        )
    print(f"\nSaved official comparison to: {out_dir / 'arb_official_comparison.json'}")


if __name__ == "__main__":
    main()

