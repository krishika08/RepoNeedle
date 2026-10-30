"""
Safeguard tests for RepoNeedle Stage 3.15:
Champion Reconciliation, Historical Reproduction, and Benchmark Integrity Audit.
"""

import csv
import json
import subprocess
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE15_DIR = ROOT_DIR / "research" / "stage3_15"


def test_frozen_baseline_tags_unmodified():
    """Verify that immutable tags point to their exact documented commit SHAs."""
    res_b = subprocess.run(
        ["git", "rev-parse", "v0.1.0-baseline^{commit}"],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT_DIR,
    )
    assert res_b.stdout.strip() == "8e0042553a14b6e3c6cf5b35823c4da84181a8e9"

    res_c = subprocess.run(
        ["git", "rev-parse", "stage3-candidate-freeze^{commit}"],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT_DIR,
    )
    assert res_c.stdout.strip() == "cd7f3b01e28695f9a9357e0815069e0eae85baca"


def test_stage3_15_deliverables_exist():
    """Verify all 11 required Stage 3.15 deliverables exist and are non-empty."""
    required_files = [
        "STAGE3_15_RECONCILIATION_REPORT.md",
        "COMMIT_AND_IMPLEMENTATION_MAP.md",
        "METRIC_CONTRACT.md",
        "BASELINE_DISCREPANCIES.csv",
        "REPRODUCED_PER_QUERY_RESULTS.csv",
        "CANONICAL_SCOREBOARD.csv",
        "CLAIM_VERIFICATION.csv",
        "TEST_AND_REPRODUCTION_LOG.md",
        "EXPERIMENT_REGISTRY.jsonl",
        "REPRODUCE.md",
        "DECISION_REPORT.md",
    ]
    for filename in required_files:
        filepath = STAGE15_DIR / filename
        assert filepath.exists(), f"Missing required deliverable: {filename}"
        assert filepath.stat().st_size > 100, f"Deliverable is suspiciously small: {filename}"


def test_reproduced_per_query_results_schema_and_counts():
    """Verify REPRODUCED_PER_QUERY_RESULTS.csv contains exactly 345 queries with aligned systems."""
    csv_path = STAGE15_DIR / "REPRODUCED_PER_QUERY_RESULTS.csv"
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 345, f"Expected 345 queries, got {len(rows)}"

    expected_cols = [
        "query_id", "repository", "base_commit", "task_type", "language", "gold_count",
        "BASE-BM25_mrr", "BASE-BM25_r20",
        "CAND-C_mrr", "CAND-C_r20",
        "CAND-F_mrr", "CAND-F_r20",
        "CONTROL-CASCADE_mrr", "CONTROL-CASCADE_r20",
        "ARM-101-BASE_mrr", "ARM-101-BASE_r20",
        "ARM-111-UNIFORM_mrr", "ARM-111-UNIFORM_r20",
        "BASE-REPOMAP_mrr", "BASE-REPOMAP_r20",
    ]
    for col in expected_cols:
        assert col in rows[0], f"Missing expected column {col}"

    # Verify score ranges
    for r in rows:
        for sys_id in ["BASE-BM25", "CAND-C", "CAND-F", "CONTROL-CASCADE", "ARM-101-BASE", "ARM-111-UNIFORM", "BASE-REPOMAP"]:
            mrr_val = float(r[f"{sys_id}_mrr"])
            assert 0.0 <= mrr_val <= 1.0


def test_canonical_scoreboard_values():
    """Verify CANONICAL_SCOREBOARD.csv contains all 7 systems and accurate MRR numbers."""
    csv_path = STAGE15_DIR / "CANONICAL_SCOREBOARD.csv"
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = {r["system_id"]: r for r in csv.DictReader(f)}

    assert "ARM-101-BASE" in rows
    assert "CAND-F" in rows
    assert "BASE-REPOMAP" in rows

    assert pytest.approx(float(rows["ARM-101-BASE"]["mrr"]), abs=1e-3) == 0.2078
    assert pytest.approx(float(rows["CAND-F"]["mrr"]), abs=1e-3) == 0.1351
    assert pytest.approx(float(rows["BASE-REPOMAP"]["mrr"]), abs=1e-3) == 0.2293
    assert pytest.approx(float(rows["BASE-BM25"]["mrr"]), abs=1e-3) == 0.1752

    assert rows["ARM-101-BASE"]["status"] == "CANONICAL_CHAMPION"
    assert rows["CAND-F"]["status"] == "FORMALLY_INVALIDATED"
    assert rows["BASE-REPOMAP"]["status"] == "EXTERNAL_BENCHMARK_LEADER"


def test_claim_verification_coverage():
    """Verify CLAIM_VERIFICATION.csv audits all Claims A through F."""
    csv_path = STAGE15_DIR / "CLAIM_VERIFICATION.csv"
    with open(csv_path, "r", encoding="utf-8") as f:
        claims = {r["claim_id"]: r for r in csv.DictReader(f)}

    for cid in ["CLAIM-A", "CLAIM-B", "CLAIM-C", "CLAIM-D", "CLAIM-E", "CLAIM-F"]:
        assert cid in claims
        assert "status" in claims[cid]
        assert "scientific_verdict" in claims[cid]


def test_decision_report_verdict():
    """Verify DECISION_REPORT.md records the formal verdict REPRODUCED WITH CORRECTIONS."""
    report_path = STAGE15_DIR / "DECISION_REPORT.md"
    content = report_path.read_text(encoding="utf-8")
    assert "[REPRODUCED WITH CORRECTIONS]" in content
    assert "ARM-101" in content
    assert "0.2078" in content
    assert "0.1351" in content


def test_production_code_untouched():
    """Ensure no production code in reponeedle/ has been modified."""
    res = subprocess.run(
        ["git", "status", "--porcelain", "reponeedle/"],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT_DIR,
    )
    assert res.stdout.strip() == "", f"Production files were modified: {res.stdout}"
