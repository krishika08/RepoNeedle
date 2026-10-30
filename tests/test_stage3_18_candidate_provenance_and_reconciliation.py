"""
Automated Safeguard and Audit Verification Test Suite for RepoNeedle Stage 3.18:
Candidate Provenance, Benchmark Reconciliation & Research Integrity Audit.
"""

import sys
import csv
import json
import subprocess
from pathlib import Path
import numpy as np
from scipy.stats import wilcoxon
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

STAGE18_DIR = ROOT_DIR / "research" / "stage3_18"


def test_baseline_tags_immutable():
    """Verify frozen baseline tags point to their exact recorded commit SHAs."""
    r1 = subprocess.run(
        ["git", "rev-parse", "v0.1.0-baseline^{commit}"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=True
    )
    assert r1.stdout.strip() == "8e0042553a14b6e3c6cf5b35823c4da84181a8e9"

    r2 = subprocess.run(
        ["git", "rev-parse", "stage3-candidate-freeze^{commit}"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=True
    )
    assert r2.stdout.strip() == "cd7f3b01e28695f9a9357e0815069e0eae85baca"


def test_production_code_untouched():
    """Verify zero modifications to production code under reponeedle/."""
    r = subprocess.run(
        ["git", "diff", "--name-only", "461f690d5b4bd3c21776eaaf94f038250ee9d6a0", "--", "reponeedle/"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=True
    )
    assert r.stdout.strip() == "", f"Production code modified: {r.stdout.strip()}"


def test_stage3_18_deliverables_exist():
    """Verify all 11 required Stage 3.18 deliverables exist and are non-empty."""
    required_files = [
        "STAGE3_18_REPORT.md",
        "CANDIDATE_PROVENANCE.md",
        "METRIC_RECONCILIATION.md",
        "METRIC_RECONCILIATION.csv",
        "CANDIDATE_LEADERBOARD.csv",
        "CANDIDATE_QUERY_LEVEL_RESULTS.csv",
        "STATISTICAL_ANALYSIS.md",
        "CANDIDATE_F_INVALIDATION_AUDIT.md",
        "EXPERIMENT_REGISTRY.jsonl",
        "DECISION_REPORT.md",
        "REPRODUCE.md",
    ]
    for fname in required_files:
        fpath = STAGE18_DIR / fname
        assert fpath.exists(), f"Missing required file: {fname}"
        assert fpath.stat().st_size > 100, f"File is suspiciously small or empty: {fname}"


def test_candidate_leaderboard_integrity():
    """Verify CANDIDATE_LEADERBOARD.csv contains exactly the 5 audited systems with canonical metrics."""
    lb_path = STAGE18_DIR / "CANDIDATE_LEADERBOARD.csv"
    with open(lb_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 5
    by_sys = {r["system_id"]: r for r in rows}

    # Verify ARM-101-BASE
    assert "ARM-101-BASE" in by_sys
    assert by_sys["ARM-101-BASE"]["status"] == "CANDIDATE_CHAMPION"
    assert by_sys["ARM-101-BASE"]["mrr"] == "0.2078"
    assert by_sys["ARM-101-BASE"]["recall_at_20"] == "0.5648"
    assert by_sys["ARM-101-BASE"]["token_bcy_at_8k"] == "0.2822"
    assert by_sys["ARM-101-BASE"]["p50_latency_ms"] == "12.92"

    # Verify BASE-BM25
    assert "BASE-BM25" in by_sys
    assert by_sys["BASE-BM25"]["status"] == "LEXICAL_BASELINE"
    assert by_sys["BASE-BM25"]["mrr"] == "0.1752"
    assert by_sys["BASE-BM25"]["recall_at_20"] == "0.4535"

    # Verify BASE-REPOMAP
    assert "BASE-REPOMAP" in by_sys
    assert by_sys["BASE-REPOMAP"]["mrr"] == "0.2293"
    assert by_sys["BASE-REPOMAP"]["recall_at_20"] == "0.6599"

    # Verify CAND-C
    assert "CAND-C" in by_sys
    assert by_sys["CAND-C"]["mrr"] == "0.1399"
    assert by_sys["CAND-C"]["recall_at_20"] == "0.5105"

    # Verify CAND-F
    assert "CAND-F" in by_sys
    assert by_sys["CAND-F"]["status"] == "FORMALLY_INVALIDATED"
    assert by_sys["CAND-F"]["mrr"] == "0.1351"
    assert by_sys["CAND-F"]["recall_at_20"] == "0.5078"


def test_query_level_results_integrity():
    """Verify CANDIDATE_QUERY_LEVEL_RESULTS.csv has exactly 345 queries matching leaderboard means."""
    q_path = STAGE18_DIR / "CANDIDATE_QUERY_LEVEL_RESULTS.csv"
    with open(q_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 345
    systems = ["BASE-BM25", "BASE-REPOMAP", "CAND-C", "ARM-101-BASE", "CAND-F"]

    for s in systems:
        mean_mrr = np.mean([float(r[f"{s}_mrr"]) for r in rows])
        mean_r20 = np.mean([float(r[f"{s}_r20"]) for r in rows])
        if s == "ARM-101-BASE":
            assert abs(mean_mrr - 0.2078) < 0.0005
            assert abs(mean_r20 - 0.5648) < 0.0005
        elif s == "BASE-BM25":
            assert abs(mean_mrr - 0.1752) < 0.0005
            assert abs(mean_r20 - 0.4535) < 0.0005
        elif s == "BASE-REPOMAP":
            assert abs(mean_mrr - 0.2293) < 0.0005
            assert abs(mean_r20 - 0.6599) < 0.0005
        elif s == "CAND-F":
            assert abs(mean_mrr - 0.1351) < 0.0005
            assert abs(mean_r20 - 0.5078) < 0.0005


def test_metric_reconciliation_zero_unresolved():
    """Verify METRIC_RECONCILIATION.csv has zero unresolved discrepancies."""
    rec_path = STAGE18_DIR / "METRIC_RECONCILIATION.csv"
    with open(rec_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 10
    for r in rows:
        assert r["reconciliation_status"] == "EXPLAINED_AND_RESOLVED"
        assert len(r["detailed_cause"]) > 20
        assert len(r["supporting_artifact"]) > 5


def test_candidate_f_invalidation_statistical_proof():
    """Verify live statistical tests prove Candidate F is significantly worse than BM25 and ARM-101."""
    q_path = STAGE18_DIR / "CANDIDATE_QUERY_LEVEL_RESULTS.csv"
    with open(q_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    cand_f_mrr = np.array([float(r["CAND-F_mrr"]) for r in rows])
    bm25_mrr = np.array([float(r["BASE-BM25_mrr"]) for r in rows])
    arm101_mrr = np.array([float(r["ARM-101-BASE_mrr"]) for r in rows])

    # Candidate F vs BM25
    res_f_bm = wilcoxon(cand_f_mrr, bm25_mrr, alternative="two-sided")
    assert res_f_bm.pvalue < 0.01  # Exact p is ~0.008541

    # ARM-101 vs Candidate F
    res_arm_f = wilcoxon(arm101_mrr, cand_f_mrr, alternative="two-sided")
    assert res_arm_f.pvalue < 1e-15  # Exact p is ~7.2e-18

    # ARM-101 vs BM25
    res_arm_bm = wilcoxon(arm101_mrr, bm25_mrr, alternative="two-sided")
    assert res_arm_bm.pvalue < 1e-25  # Exact p is ~6.4e-31


def test_soft_damping_and_verified_edges_in_source():
    """Verify ARM-101 soft lexical damping and verified edges are implemented in referenced code."""
    pilot_path = ROOT_DIR / "research" / "stage3_14" / "pilot_attenuation.py"
    pilot_code = pilot_path.read_text(encoding="utf-8")
    assert "soft_damping_tau" in pilot_code
    assert "bm25_margin" in pilot_code
    assert "threshold = self.soft_damping_tau * bm25_margin" in pilot_code

    fg_path = ROOT_DIR / "research" / "stage3_11" / "function_graph_engine.py"
    fg_code = fg_path.read_text(encoding="utf-8")
    assert "verified_call" in fg_code
    assert "unique_global_call" in fg_code


def test_governance_decision_verdicts():
    """Verify formal decision strings in DECISION_REPORT.md and STAGE3_18_REPORT.md."""
    dec_text = (STAGE18_DIR / "DECISION_REPORT.md").read_text(encoding="utf-8")
    assert "VERDICT: RECONCILED — REPRODUCIBLE CANDIDATE LEADERBOARD" in dec_text
    assert "CONTEXTBENCH GATE STATUS: BLOCKED — OFFICIAL DATA ACQUISITION" in dec_text

    rep_text = (STAGE18_DIR / "STAGE3_18_REPORT.md").read_text(encoding="utf-8")
    assert "RECONCILED — REPRODUCIBLE CANDIDATE LEADERBOARD" in rep_text
    assert "BLOCKED — OFFICIAL DATA ACQUISITION" in rep_text
