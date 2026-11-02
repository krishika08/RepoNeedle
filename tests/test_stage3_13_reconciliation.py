"""
Test suite for RepoNeedle Stage 3.13: Canonical Evidence Reconciliation, End-to-End Performance, and Independent Validation.
"""

import sys
import os
import csv
import subprocess
import numpy as np
import scipy.stats as stats
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE_DIR = ROOT_DIR / "research" / "stage3_13"
sys.path.insert(0, str(ROOT_DIR))


def test_stage3_13_deliverables_exist():
    """Verify all Stage 3.13 deliverables exist and are non-empty."""
    required_files = [
        "CANONICAL_LINEAGE_AUDIT.md",
        "CANONICAL_METRIC_RECONCILIATION.csv",
        "UNRESOLVED_CLAIMS.md",
        "END_TO_END_PERFORMANCE_AUDIT.csv",
        "PERFORMANCE_METHODS.md",
        "INDEPENDENT_VALIDATION_READINESS.md",
        "validate_contextbench.py",
        "STAGE3_13_REPORT.md",
    ]
    for fname in required_files:
        fpath = STAGE_DIR / fname
        assert fpath.exists(), f"Missing deliverable: {fname}"
        assert fpath.stat().st_size > 0, f"Deliverable is empty: {fname}"


def test_frozen_tags_unmodified():
    """Verify that frozen tags v0.1.0-baseline and stage3-candidate-freeze remain unchanged."""
    expected_baseline = "8e0042553a14b6e3c6cf5b35823c4da84181a8e9"
    expected_freeze = "cd7f3b01e28695f9a9357e0815069e0eae85baca"

    baseline_commit = subprocess.check_output(
        ["git", "rev-parse", "v0.1.0-baseline^{commit}"], text=True
    ).strip()
    freeze_commit = subprocess.check_output(
        ["git", "rev-parse", "stage3-candidate-freeze^{commit}"], text=True
    ).strip()

    assert baseline_commit == expected_baseline, f"Baseline tag moved: {baseline_commit}"
    assert freeze_commit == expected_freeze, f"Candidate freeze tag moved: {freeze_commit}"


def test_tost_statistical_equivalence():
    """Verify that Two One-Sided Tests (TOST) confirm equivalence between CONFIG-09 and CONFIG-10 within delta = 0.015."""
    s10_csv = ROOT_DIR / "research" / "stage3_10" / "PER_QUERY_RESULTS.csv"
    assert s10_csv.exists(), "PER_QUERY_RESULTS.csv missing"

    rows = list(csv.DictReader(open(s10_csv, encoding="utf-8")))
    m9 = np.array([float(r["CONFIG-09_mrr"]) for r in rows])
    m10 = np.array([float(r["CONFIG-10_mrr"]) for r in rows])
    d = m10 - m9
    n = len(d)
    assert n == 345, f"Expected 345 queries, got {n}"

    mean_d = float(np.mean(d))
    se_d = float(np.std(d, ddof=1) / np.sqrt(n))
    delta = 0.015

    # TOST
    t1 = (mean_d - (-delta)) / se_d
    p1 = 1 - stats.t.cdf(t1, df=n - 1)

    t2 = (mean_d - delta) / se_d
    p2 = stats.t.cdf(t2, df=n - 1)

    p_tost = max(p1, p2)
    assert p_tost < 0.05, f"TOST equivalence failed: p = {p_tost}"
    assert abs(mean_d) < delta, f"Mean difference {mean_d} exceeds delta {delta}"


def test_performance_audit_table_invariants():
    """Verify the empirical observations and invariants in END_TO_END_PERFORMANCE_AUDIT.csv."""
    audit_csv = STAGE_DIR / "END_TO_END_PERFORMANCE_AUDIT.csv"
    rows = list(csv.DictReader(open(audit_csv, encoding="utf-8")))
    assert len(rows) == 10, f"Expected 10 rows (5 repos x 2 configs), got {len(rows)}"

    for r in rows:
        assert float(r["warm_e2e_p50_ms"]) > 0
        assert float(r["scoring_latency_p50_ms"]) > 0
        assert float(r["packing_latency_p50_ms"]) > 0
        assert int(r["sample_count"]) == 20

    # Group by repo
    by_repo = {}
    for r in rows:
        repo = r["repository"]
        cfg = r["configuration"]
        if repo not in by_repo:
            by_repo[repo] = {}
        by_repo[repo][cfg] = r

    # Click & Gin: CONFIG-10 scoring should be slower or near-equal due to CSR slicing overhead
    click_c09_sc = float(by_repo["pallets/click"]["CONFIG-09"]["scoring_latency_p50_ms"])
    click_c10_sc = float(by_repo["pallets/click"]["CONFIG-10"]["scoring_latency_p50_ms"])
    assert click_c10_sc >= click_c09_sc * 0.9, "Click candidate slicing should have overhead on tiny repo"

    # Etcd: CONFIG-10 scoring must be substantially faster (> 1.5x)
    etcd_c09_sc = float(by_repo["etcd-io/etcd"]["CONFIG-09"]["scoring_latency_p50_ms"])
    etcd_c10_sc = float(by_repo["etcd-io/etcd"]["CONFIG-10"]["scoring_latency_p50_ms"])
    assert etcd_c09_sc / etcd_c10_sc >= 1.5, f"Expected >= 1.5x speedup on etcd, got {etcd_c09_sc / etcd_c10_sc}"


def test_contextbench_validator_script():
    """Verify that validate_contextbench.py executes and reports BLOCKED cleanly in sandbox or ONLINE in CI."""
    val_script = STAGE_DIR / "validate_contextbench.py"
    res = subprocess.run([sys.executable, str(val_script)], capture_output=True, text=True)
    # Inside sandbox exit code is 2 (BLOCKED); in online CI runner exit code is 0 (ONLINE)
    assert res.returncode in (0, 2), f"Unexpected returncode {res.returncode}: {res.stdout}\n{res.stderr}"
    if res.returncode == 2:
        assert "[STATUS: BLOCKED]" in res.stdout
    else:
        assert "[STATUS: ONLINE]" in res.stdout
