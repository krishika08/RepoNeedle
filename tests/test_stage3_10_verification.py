"""
Unit and regression test suite for Stage 3.10: Canonical Ranking Recovery Verification.
Verifies dataset integrity, metric point estimates, statistical conclusions,
and code leakage checks.
"""

import csv
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE_DIR = ROOT_DIR / "research" / "stage3_10"


def test_canonical_results_integrity_and_values():
    """Verify CANONICAL_RESULTS.csv exists, has 7 systems, and matches verified point estimates."""
    can_csv = STAGE_DIR / "CANONICAL_RESULTS.csv"
    assert can_csv.exists(), "CANONICAL_RESULTS.csv missing"

    with open(can_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 7, f"Expected 7 systems, found {len(rows)}"
    sys_map = {r["system_id"]: r for r in rows}

    expected_systems = [
        "BASE-BM25",
        "CONFIG-09",
        "CONFIG-10",
        "CONFIG-11",
        "CAND-C",
        "CAND-F",
        "BASE-REPOMAP",
    ]
    for s in expected_systems:
        assert s in sys_map, f"System {s} missing from canonical results"
        assert int(sys_map[s]["query_count"]) == 345

    # Check primary MRR figures
    assert float(sys_map["BASE-BM25"]["mrr"]) == pytest.approx(0.1759, abs=1e-3)
    assert float(sys_map["CONFIG-09"]["mrr"]) == pytest.approx(0.2061, abs=1e-3)
    assert float(sys_map["CONFIG-10"]["mrr"]) == pytest.approx(0.2019, abs=1e-3)
    assert float(sys_map["CONFIG-11"]["mrr"]) == pytest.approx(0.2063, abs=1e-3)
    assert float(sys_map["CAND-C"]["mrr"]) == pytest.approx(0.1394, abs=1e-3)
    assert float(sys_map["CAND-F"]["mrr"]) == pytest.approx(0.1334, abs=1e-3)
    assert float(sys_map["BASE-REPOMAP"]["mrr"]) == pytest.approx(0.2293, abs=1e-3)

    # Check Recall@20 figures
    assert float(sys_map["CONFIG-09"]["recall_at_20"]) == pytest.approx(0.5576, abs=1e-3)
    assert float(sys_map["BASE-BM25"]["recall_at_20"]) == pytest.approx(0.4622, abs=1e-3)
    assert float(sys_map["BASE-REPOMAP"]["recall_at_20"]) == pytest.approx(0.6599, abs=1e-3)


def test_per_query_dataset_integrity():
    """Verify PER_QUERY_RESULTS.csv covers exactly 345 queries without nulls."""
    pq_csv = STAGE_DIR / "PER_QUERY_RESULTS.csv"
    assert pq_csv.exists(), "PER_QUERY_RESULTS.csv missing"

    with open(pq_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 345
    for r in rows:
        assert r["query_id"].strip() != ""
        assert r["repo"].strip() != ""
        assert float(r["CONFIG-09_mrr"]) >= 0.0
        assert float(r["BASE-BM25_mrr"]) >= 0.0
        assert float(r["BASE-REPOMAP_mrr"]) >= 0.0


def test_paired_statistical_test_significance():
    """Verify statistical conclusions with Holm's correction."""
    stat_csv = STAGE_DIR / "PAIRED_STATISTICAL_TESTS.csv"
    assert stat_csv.exists(), "PAIRED_STATISTICAL_TESTS.csv missing"

    with open(stat_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Lookup test rows
    tests = {(r["comparison"], r["metric"]): r for r in rows}

    # 1. Primary: CONFIG-09 vs BASE-BM25 on MRR is significant
    prim_mrr = tests[("Primary: CONFIG-09 vs. BASE-BM25", "MRR")]
    assert prim_mrr["statistically_significant"] == "YES"
    assert float(prim_mrr["mean_difference"]) > 0.025
    assert float(prim_mrr["holm_adjusted_p_value"]) < 0.001

    # 2. Diffusion value: CONFIG-11 vs CONFIG-09 on Recall@20 is NOT significant
    diff_r20 = tests[("Secondary: CONFIG-11 vs. CONFIG-09", "Recall@20")]
    assert diff_r20["statistically_significant"] == "NO"
    assert float(diff_r20["holm_adjusted_p_value"]) > 0.05

    # 3. RepoMap superiority on Recall@20 is significant
    repo_r20 = tests[("Secondary: CONFIG-09 vs. BASE-REPOMAP", "Recall@20")]
    assert repo_r20["statistically_significant"] == "YES"
    assert float(repo_r20["mean_difference"]) < -0.05


def test_codebase_leakage_absence():
    """Verify zero benchmark query or repo leakage in reponeedle/."""
    from research.stage3_10.run_leakage_audit import audit_leakage

    hits = audit_leakage()
    assert len(hits) == 0, f"Found leakage hits in reponeedle/: {hits}"
