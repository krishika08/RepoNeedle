"""
Stage 3.12A: Canonical Evaluation Reconciliation Test Suite.
Verifies cross-stage reconciliation, artifact integrity, exact query alignment,
and numerical correctness of the canonical evaluation summary.
"""

import csv
import json
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE_DIR = ROOT_DIR / "research" / "stage3_12a"


def test_stage3_12a_deliverables_exist():
    """Verify that all required Stage 3.12A deliverables exist."""
    required = [
        "GIT_AND_ARTIFACT_PROVENANCE.md",
        "EVALUATOR_DIFFERENCES.md",
        "CANONICAL_PER_QUERY_RESULTS.csv",
        "CANONICAL_METRIC_SUMMARY.csv",
        "RECONCILIATION_DECISION.md",
        "STAGE3_12_DESIGN_SPEC.md",
        "statistical_reconciliation.json",
        "RUN_PROVENANCE.json",
        "REPRODUCE.md",
    ]
    for fname in required:
        fpath = STAGE_DIR / fname
        assert fpath.exists(), f"Required Stage 3.12A deliverable {fname} is missing"


def test_canonical_per_query_results_properties():
    """Verify CANONICAL_PER_QUERY_RESULTS.csv row count, schema, and alignment."""
    pq_path = STAGE_DIR / "CANONICAL_PER_QUERY_RESULTS.csv"
    assert pq_path.exists()

    with open(pq_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 345, f"Expected 345 queries, got {len(rows)}"

    for r in rows:
        assert r["query_id"].strip() != ""
        assert r["repository"].strip() != ""
        assert float(r["BASE-BM25_mrr"]) >= 0.0
        assert float(r["CONTROL-CASCADE_mrr"]) >= 0.0
        assert float(r["FUNCTION-GRAPH_mrr"]) >= 0.0
        assert float(r["FUNCTION-GRAPH-NO-FREEZE_mrr"]) >= 0.0
        assert float(r["CAND-F_mrr"]) >= 0.0
        assert float(r["BASE-REPOMAP_mrr"]) >= 0.0


def test_canonical_metric_summary_values():
    """Verify that CANONICAL_METRIC_SUMMARY.csv contains exact reconciled values."""
    summary_path = STAGE_DIR / "CANONICAL_METRIC_SUMMARY.csv"
    assert summary_path.exists()

    with open(summary_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 7
    sys_map = {r["system_name"]: r for r in rows}

    assert float(sys_map["BASE-BM25"]["mean_mrr"]) == pytest.approx(0.1752, abs=1e-3)
    assert float(sys_map["CAND-F (Stage 3.5 Unconstrained)"]["mean_mrr"]) == pytest.approx(0.1338, abs=1e-3)
    assert float(sys_map["CONTROL-CASCADE"]["mean_mrr"]) == pytest.approx(0.1882, abs=1e-3)
    assert float(sys_map["TEST-GRAPH"]["mean_mrr"]) == pytest.approx(0.1897, abs=1e-3)
    assert float(sys_map["FUNCTION-GRAPH (Stage 3.11 Primary)"]["mean_mrr"]) == pytest.approx(0.1901, abs=1e-3)
    assert float(sys_map["FUNCTION-GRAPH-NO-FREEZE (Stage 3.11 Exploratory)"]["mean_mrr"]) == pytest.approx(0.2082, abs=1e-3)
    assert float(sys_map["BASE-REPOMAP (Pinned 9e4d689)"]["mean_mrr"]) == pytest.approx(0.2293, abs=1e-3)


def test_statistical_reconciliation_integrity():
    """Verify statistical tests and candidate collapse."""
    stat_path = STAGE_DIR / "statistical_reconciliation.json"
    assert stat_path.exists()

    with open(stat_path, encoding="utf-8") as f:
        stats_data = json.load(f)

    # Candidate F collapses significantly below Control Cascade
    cand_f = stats_data["CAND-F vs. CONTROL-CASCADE"]
    assert cand_f["mean_delta"] < -0.05
    assert cand_f["losses"] > 200
    assert cand_f["p_value"] < 1e-10

    # Function Graph No Freeze achieves large significant gain
    no_freeze = stats_data["FUNCTION-GRAPH-NO-FREEZE vs. CONTROL-CASCADE"]
    assert no_freeze["mean_delta"] > 0.015
    assert no_freeze["wins"] > 130
    assert no_freeze["losses"] < 30
    assert no_freeze["p_value"] < 1e-15
