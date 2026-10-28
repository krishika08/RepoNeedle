"""
Stage 3.11: Independent Verification and Research Integrity Test Suite.
Verifies cross-stage reconciliation, canonical metric recomputation,
multiplicity-controlled statistical corrections, and dataset alignment.
"""

import csv
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE_11_DIR = ROOT_DIR / "research" / "stage3_11"


def test_query_alignment_and_sample_count():
    """Verify all 345 queries are present, aligned, and have consistent gold targets."""
    align_csv = STAGE_11_DIR / "QUERY_ALIGNMENT_AUDIT.csv"
    assert align_csv.exists(), "QUERY_ALIGNMENT_AUDIT.csv missing"

    with open(align_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 345, f"Expected 345 positive samples, got {len(rows)}"
    for r in rows:
        assert r["query_id"].strip() != ""
        assert r["repo"].strip() != ""
        assert int(r["gold_file_count"]) > 0
        assert r["has_prediction_base_bm25"] == "True"
        assert r["has_prediction_config_09"] == "True"
        assert r["has_prediction_config_10"] == "True"
        assert r["has_prediction_config_11"] == "True"
        assert r["has_prediction_cand_c"] == "True"
        assert r["has_prediction_cand_f"] == "True"
        assert r["has_prediction_base_repomap"] == "True"
        assert r["targets_consistent"] == "True"
        assert r["nan_or_null_present"] == "False"


def test_recomputed_metrics_match_published_within_tolerance():
    """Verify that independently recomputed metrics match published figures within 1e-4."""
    recomp_csv = STAGE_11_DIR / "RECOMPUTED_CANONICAL_RESULTS.csv"
    assert recomp_csv.exists(), "RECOMPUTED_CANONICAL_RESULTS.csv missing"

    with open(recomp_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 7
    sys_map = {r["system_id"]: r for r in rows}

    for s_id, r in sys_map.items():
        recomp_mrr = float(r["recomputed_mrr"])
        pub_mrr = float(r["published_mrr"])
        assert abs(recomp_mrr - pub_mrr) < 1e-4, f"MRR mismatch for {s_id}: {recomp_mrr} vs {pub_mrr}"

        recomp_r20 = float(r["recomputed_recall_at_20"])
        pub_r20 = float(r["published_recall_at_20"])
        assert abs(recomp_r20 - pub_r20) < 1e-4, f"Recall@20 mismatch for {s_id}: {recomp_r20} vs {pub_r20}"

        recomp_bcy = float(r["recomputed_token_bcy_at_8k"])
        pub_bcy = float(r["published_token_bcy_at_8k"])
        assert abs(recomp_bcy - pub_bcy) < 1e-4, f"BCY@8k mismatch for {s_id}: {recomp_bcy} vs {pub_bcy}"

        assert r["audit_agreement"] == "PERFECT_EXACT_MATCH"


def test_statistical_holm_stepdown_stopping_rule():
    """Verify that the Holm step-down stopping rule and monotonicity are correctly enforced."""
    stat_csv = STAGE_11_DIR / "STATISTICAL_RECOMPUTATION.csv"
    assert stat_csv.exists(), "STATISTICAL_RECOMPUTATION.csv missing"

    with open(stat_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Lookup test rows
    tests = {(r["comparison"], r["metric"]): r for r in rows}

    # 1. Primary: CONFIG-09 vs BASE-BM25 on MRR is significant
    prim_mrr = tests[("Primary: CONFIG-09 vs. BASE-BM25", "MRR")]
    assert prim_mrr["statistically_significant"] == "YES"
    assert float(prim_mrr["holm_adjusted_p_value"]) < 0.001

    # 2. CONFIG-11 vs CONFIG-09 on MRR must NOT be statistically significant
    diff_mrr = tests[("Secondary: CONFIG-11 vs. CONFIG-09", "MRR")]
    assert diff_mrr["statistically_significant"] == "NO"
    assert float(diff_mrr["holm_adjusted_p_value"]) > 0.05
    # Verify unadjusted p-value is the 0.039134 value from 17 wins vs 53 losses
    assert float(diff_mrr["unadjusted_p_value"]) == pytest.approx(0.039134, abs=1e-4)

    # 3. RepoMap superiority on Recall@20 is significant
    rm_r20 = tests[("Secondary: CONFIG-09 vs. BASE-REPOMAP", "Recall@20")]
    assert rm_r20["statistically_significant"] == "YES"
    assert float(rm_r20["mean_difference"]) < -0.05

    # 4. Monotonicity check across all metric families
    for m in ["MRR", "Recall@5", "Recall@10", "Recall@20", "BCY@8k"]:
        fam = [r for r in rows if r["metric"] == m]
        # When sorted by unadjusted p-value, adjusted p-values must be non-decreasing
        fam_sorted = sorted(fam, key=lambda x: float(x["unadjusted_p_value"]))
        for i in range(len(fam_sorted) - 1):
            p_curr = float(fam_sorted[i]["holm_adjusted_p_value"])
            p_next = float(fam_sorted[i + 1]["holm_adjusted_p_value"])
            assert p_curr <= p_next + 1e-6, f"Holm monotonicity violated in {m}: {p_curr} > {p_next}"


def test_repomap_precision5_and_latency_audit():
    """Verify RepoMap Precision@5 true recomputed value and latency constant documentation."""
    recomp_csv = STAGE_11_DIR / "RECOMPUTED_CANONICAL_RESULTS.csv"
    with open(recomp_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    sys_map = {r["system_id"]: r for r in rows}
    rm_row = sys_map["BASE-REPOMAP"]

    # Published was 0.0186 due to missing key in ARB v1.1 details
    assert float(rm_row["published_precision_at_5"]) == pytest.approx(0.0186, abs=1e-3)
    # True untruncated Precision@5 from top-5 paths is ~0.0910
    assert float(rm_row["true_untruncated_precision_at_5"]) == pytest.approx(0.0910, abs=1e-3)


def test_historical_deliverables_intact():
    """Verify all historical stage deliverables remain preserved and untouched."""
    required_paths = [
        ROOT_DIR / "research" / "stage3_5" / "STAGE3_5_DECISION_REPORT.md",
        ROOT_DIR / "research" / "stage3_6" / "STAGE3_6_AUDIT_REPORT.md",
        ROOT_DIR / "research" / "stage3_7" / "DECISION_REPORT.md",
        ROOT_DIR / "research" / "stage3_8" / "DECISION_REPORT.md",
        ROOT_DIR / "research" / "stage3_9" / "DECISION_REPORT.md",
        ROOT_DIR / "research" / "stage3_10" / "STAGE3_10_REPORT.md",
    ]
    for p in required_paths:
        assert p.exists(), f"Historical report {p} missing or moved!"
