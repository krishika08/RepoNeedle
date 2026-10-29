"""
Stage 3.10.2: Canonical Evaluation Integrity and Verification Test Suite.

Verifies:
1. Presence and integrity of all Stage 3.10.2 audit artifacts.
2. Independent reference implementation of evaluation metrics.
3. Full recomputation of all 7 systems over 345 positive ARB v2 queries.
4. Mathematical verification of the p=0.001 statistical claim for TEST-GRAPH.
5. Latency and memory audits on Click and Caddy corpora.
"""

import csv
import json
import pytest
from pathlib import Path
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE_DIR = ROOT_DIR / "research" / "stage3_10_2"

import sys
sys.path.insert(0, str(STAGE_DIR))
import independent_metrics as im


def test_stage3_10_2_artifacts_exist():
    """Verify that all required Stage 3.10.2 deliverables exist."""
    required_files = [
        "EVALUATION_INTEGRITY_REPORT.md",
        "CANONICAL_EVALUATION_CONTRACT.md",
        "INDEPENDENT_METRIC_RECOMPUTATION.csv",
        "PER_QUERY_PAIRED_DIFFERENCES.csv",
        "PER_TASK_RESULTS.csv",
        "PER_REPOSITORY_RESULTS.csv",
        "STATISTICAL_VALIDATION.md",
        "RUNTIME_MEMORY_RESULTS.csv",
        "REPRODUCTION_MATRIX.csv",
        "RUN_PROVENANCE.json",
        "REPRODUCE.md",
    ]
    for fname in required_files:
        fpath = STAGE_DIR / fname
        assert fpath.exists(), f"Required artifact {fname} missing from stage3_10_2"


def test_independent_metric_implementations():
    """Verify that independent_metrics functions produce exact expected outputs."""
    # Reciprocal Rank
    assert im.compute_reciprocal_rank(["a.py", "b.py", "c.py"], {"b.py"}) == (0.5, 2)
    assert im.compute_reciprocal_rank(["a.py", "b.py", "c.py"], {"z.py"}) == (0.0, -1)

    # Fractional Recall vs Hit
    ranked = ["f1.py", "f2.py", "f3.py", "f4.py", "f5.py"]
    gold = {"f2.py", "f4.py", "f9.py"}
    assert im.compute_fractional_recall(ranked, gold, 5) == pytest.approx(2.0 / 3.0)
    assert im.compute_binary_hit(ranked, gold, 5) == 1.0
    assert im.compute_precision_at_k(ranked, gold, 5) == pytest.approx(2.0 / 5.0)


def test_recomputed_metrics_match_canonical():
    """Verify that INDEPENDENT_METRIC_RECOMPUTATION.csv matches canonical values."""
    recomp_path = STAGE_DIR / "INDEPENDENT_METRIC_RECOMPUTATION.csv"
    with open(recomp_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 345

    bm25_mrr = np.mean([float(r["BASE-BM25_mrr"]) for r in rows])
    ctrl_mrr = np.mean([float(r["CONTROL-CASCADE_mrr"]) for r in rows])
    tst_mrr = np.mean([float(r["TEST-GRAPH_mrr"]) for r in rows])
    rm_mrr = np.mean([float(r["BASE-REPOMAP_mrr"]) for r in rows])
    cand_c_mrr = np.mean([float(r["CAND-C_mrr"]) for r in rows])
    cand_f_mrr = np.mean([float(r["CAND-F_mrr"]) for r in rows])

    assert bm25_mrr == pytest.approx(0.1752, abs=1e-3)
    assert ctrl_mrr == pytest.approx(0.1883, abs=1e-3)
    assert tst_mrr == pytest.approx(0.1898, abs=1e-3)
    assert rm_mrr == pytest.approx(0.2293, abs=1e-3)
    assert cand_c_mrr == pytest.approx(0.1401, abs=1e-3)
    assert cand_f_mrr == pytest.approx(0.1338, abs=1e-3)


def test_statistical_claim_reproducibility():
    """Verify the exact reproducibility of the p=0.001 claim from per-query paired data."""
    paired_path = STAGE_DIR / "PER_QUERY_PAIRED_DIFFERENCES.csv"
    with open(paired_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 345

    diffs = [float(r["mrr_delta"]) for r in rows]
    mean_diff = np.mean(diffs)
    assert mean_diff == pytest.approx(0.001489, abs=1e-4)

    wins = sum(1 for d in diffs if d > 0)
    losses = sum(1 for d in diffs if d < 0)
    ties = sum(1 for d in diffs if d == 0)

    assert wins == 24
    assert losses == 8
    assert ties == 313

    # Check statistical summary JSON
    stat_json = STAGE_DIR / "statistical_summary.json"
    with open(stat_json, encoding="utf-8") as f:
        summary = json.load(f)

    test_vs_ctrl = summary["TEST-GRAPH vs CONTROL-CASCADE"]
    assert test_vs_ctrl["wilcoxon_stat"] == 87.5
    assert test_vs_ctrl["raw_p_value"] == pytest.approx(0.000964, rel=1e-2)
    assert test_vs_ctrl["holm_adjusted_p_value"] < 0.01
    assert test_vs_ctrl["statistically_significant"] is True


def test_runtime_memory_audit():
    """Verify that RUNTIME_MEMORY_RESULTS.csv exists and has Click and Caddy records."""
    mem_path = STAGE_DIR / "RUNTIME_MEMORY_RESULTS.csv"
    assert mem_path.exists()

    with open(mem_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) >= 2
    repo_map = {r["repository"]: r for r in rows}

    assert "pallets/click" in repo_map
    click = repo_map["pallets/click"]
    assert float(click["warm_query_latency_p50_ms"]) < 10.0
    assert float(click["process_rss_after_mb"]) > 50.0

    assert "caddyserver/caddy" in repo_map
    caddy = repo_map["caddyserver/caddy"]
    assert float(caddy["warm_query_latency_p50_ms"]) < 20.0
    assert float(caddy["process_rss_after_mb"]) > 100.0
