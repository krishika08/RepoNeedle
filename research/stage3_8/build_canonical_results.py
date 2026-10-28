"""
Builds the authoritative canonical benchmark results for Stage 3.8.
Reads the verified predictions from research/stage3_6/PER_QUERY_RESULTS.csv,
augments each record with the repository snapshot base_commit,
computes canonical token-budgeted BCY@8k using bcy_curve.pack_files,
and writes research/stage3_8/CANONICAL_PER_QUERY_RESULTS.csv.
"""

import sys
import csv
import json
import time
from pathlib import Path
from collections import defaultdict

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import read_jsonl
from agent_retrieval_bench.bcy_curve import pack_files, CorpusFileCache


def build_canonical_results():
    t0 = time.time()
    print("=" * 80)
    print("STAGE 3.8: GENERATING CANONICAL PER-QUERY RESULTS (N=345, 4 SYSTEMS)")
    print("=" * 80)

    # 1. Load corpus manifest
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    manifest = {}
    for row in read_jsonl(manifest_path):
        if row.get("status") and row.get("status") != "ok":
            continue
        repo = str(row.get("repo") or "")
        base_commit = str(row.get("base_commit") or "")
        chunks_path = row.get("chunks_path")
        if repo and base_commit and chunks_path:
            manifest[(repo, base_commit)] = ARB_DIR / str(chunks_path)

    cache = CorpusFileCache(manifest)

    # 2. Load benchmark sample metadata
    samples_by_id = {}
    tracks = ["v2_code2test", "v2_comment2context", "v2_trace2code", "v2_edit2ripple"]
    for track in tracks:
        p = ARB_DIR / "data" / "benchmark" / track / "samples.jsonl"
        for s in read_jsonl(p):
            samples_by_id[s["id"]] = s

    print(f"Loaded {len(samples_by_id)} benchmark samples across 4 tracks.")

    # 3. Read stage 3.6 predictions
    in_csv = ROOT_DIR / "research" / "stage3_6" / "PER_QUERY_RESULTS.csv"
    reader = csv.DictReader(open(in_csv, encoding="utf-8"))
    rows = list(reader)
    print(f"Loaded {len(rows)} raw prediction rows from {in_csv.name}.")

    config_map = {
        "BASE-BM25": "EXP-016-OKAPI",
        "CAND-C": "EXP-CAND-C-DOC05",
        "CAND-F": "EXP-CAND-F-POLYGLOT-DIFF",
        "BASE-REPOMAP": "AIDER-REPOMAP-CALLGRAPH",
    }

    out_rows = []
    header = [
        "query_id", "repo", "base_commit", "task_type", "language", "system_id", "candidate_config_id",
        "mrr", "recall_at_1", "recall_at_5", "recall_at_10", "recall_at_20",
        "precision_at_5", "precision_at_10", "precision_at_20",
        "char_cov_at_4k", "char_cov_at_8k", "char_cov_at_16k", "token_bcy_at_8k",
        "first_relevant_rank", "retrieved_token_count", "selected_file_count",
        "latency_ms", "abstained", "execution_status", "gold_files", "top_ranked_paths"
    ]

    for idx, r in enumerate(rows):
        qid = r["query_id"]
        s = samples_by_id[qid]
        repo = s["repo"]
        commit = s["base_commit"]
        sys_id = r["system_id"]
        cfg_id = config_map.get(sys_id, sys_id)

        gold = [p for p in r["gold_files"].split(";") if p]
        top_files = [p for p in r["top_ranked_paths"].split(";") if p]

        # Compute canonical token BCY@8k
        packed = pack_files(repo, commit, top_files, set(gold), cache, budget=8000)
        token_bcy = packed["bcy"]

        out_row = {
            "query_id": qid,
            "repo": repo,
            "base_commit": commit,
            "task_type": r["task_type"],
            "language": r["language"],
            "system_id": sys_id,
            "candidate_config_id": cfg_id,
            "mrr": f"{float(r['mrr']):.6f}",
            "recall_at_1": f"{float(r['recall_at_1']):.6f}",
            "recall_at_5": f"{float(r['recall_at_5']):.6f}",
            "recall_at_10": f"{float(r['recall_at_10']):.6f}",
            "recall_at_20": f"{float(r['recall_at_20']):.6f}",
            "precision_at_5": f"{float(r['precision_at_5']):.6f}",
            "precision_at_10": f"{float(r['precision_at_10']):.6f}",
            "precision_at_20": f"{float(r['precision_at_20']):.6f}",
            "char_cov_at_4k": f"{float(r['bcy_at_4k']):.6f}",
            "char_cov_at_8k": f"{float(r['bcy_at_8k']):.6f}",
            "char_cov_at_16k": f"{float(r['bcy_at_16k']):.6f}",
            "token_bcy_at_8k": f"{token_bcy:.6f}",
            "first_relevant_rank": r["first_relevant_rank"],
            "retrieved_token_count": r["retrieved_token_count"],
            "selected_file_count": r["selected_file_count"],
            "latency_ms": f"{float(r['latency_ms']):.2f}",
            "abstained": r["abstained"],
            "execution_status": "SUCCESS_NO_EXCLUSION",
            "gold_files": r["gold_files"],
            "top_ranked_paths": r["top_ranked_paths"],
        }
        out_rows.append(out_row)

        if (idx + 1) % 200 == 0 or (idx + 1) == len(rows):
            print(f"Processed {idx + 1}/{len(rows)} records...", flush=True)

    out_csv = ROOT_DIR / "research" / "stage3_8" / "CANONICAL_PER_QUERY_RESULTS.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(out_rows)

    t1 = time.time()
    print(f"\n[DONE] Wrote {len(out_rows)} canonical records to {out_csv} in {t1 - t0:.2f}s.")


if __name__ == "__main__":
    build_canonical_results()

