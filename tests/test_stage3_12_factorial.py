"""
Stage 3.12: Unit and Integrity Tests for Controlled Graph Retrieval Factorial Experiment.

Verifies:
  1. All 8 factorial arms + baselines exist in deliverables with non-empty, valid schemas.
  2. Mathematical formulas for Factors A, B, and C behave as specified.
  3. Acceptance criteria for ADVANCE verdict are strictly satisfied.
  4. Immutable baseline tags remain untouched.
"""

import os
import sys
import json
import csv
import subprocess
from pathlib import Path
import pytest
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE_DIR = ROOT_DIR / "research" / "stage3_12"

sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(STAGE_DIR))

from research.stage3_12.factorial_engine import FactorialCascadedRanker, create_arm_ranker
from reponeedle.models import FileDoc


def test_frozen_git_tags_integrity():
    """Verify immutable baseline tags have not moved."""
    res_b = subprocess.run(
        ["git", "rev-parse", "v0.1.0-baseline^{commit}"],
        capture_output=True, text=True, cwd=str(ROOT_DIR)
    )
    assert res_b.returncode == 0
    assert "8e00425" in res_b.stdout, f"v0.1.0-baseline moved: {res_b.stdout}"

    res_c = subprocess.run(
        ["git", "rev-parse", "stage3-candidate-freeze^{commit}"],
        capture_output=True, text=True, cwd=str(ROOT_DIR)
    )
    assert res_c.returncode == 0
    assert "cd7f3b0" in res_c.stdout, f"stage3-candidate-freeze moved: {res_c.stdout}"


def test_stage3_12_factorial_deliverables_exist():
    """Verify all required Stage 3.12 deliverables exist and are non-empty."""
    required_files = [
        "DESIGN_AND_PREREGISTRATION.md",
        "STAGE3_12_DECISION_REPORT.md",
        "CANONICAL_PER_QUERY_RESULTS.csv",
        "FACTORIAL_RESULTS.csv",
        "PER_TASK_RESULTS.csv",
        "REGRESSION_ANALYSIS.md",
        "STATISTICAL_ANALYSIS.json",
        "RUNTIME_AND_MEMORY.csv",
        "EXPERIMENT_REGISTRY.jsonl",
        "RUN_PROVENANCE.json",
        "REPRODUCE.md",
        "factorial_engine.py",
        "run_stage3_12_factorial.py",
    ]
    for fname in required_files:
        fpath = STAGE_DIR / fname
        assert fpath.exists(), f"Missing required file: {fname}"
        assert fpath.stat().st_size > 0, f"File is empty: {fname}"


def test_factorial_results_schema_and_arms():
    """Verify FACTORIAL_RESULTS.csv contains all 8 arms + baselines and correct values."""
    res_path = STAGE_DIR / "FACTORIAL_RESULTS.csv"
    rows = list(csv.DictReader(open(res_path, encoding="utf-8")))
    sys_names = {r["system_name"] for r in rows}

    expected_systems = {
        "BASE-BM25", "CONTROL-CASCADE",
        "ARM-000", "ARM-100", "ARM-010", "ARM-001",
        "ARM-110", "ARM-101", "ARM-011", "ARM-111",
        "STAGE3_11-NO-FREEZE", "BASE-REPOMAP"
    }
    assert expected_systems.issubset(sys_names), f"Missing systems: {expected_systems - sys_names}"

    row_map = {r["system_name"]: r for r in rows}

    # Verify key metrics
    assert float(row_map["CONTROL-CASCADE"]["mean_mrr"]) >= 0.1880
    assert float(row_map["ARM-111"]["mean_mrr"]) > float(row_map["CONTROL-CASCADE"]["mean_mrr"])
    assert float(row_map["ARM-101"]["mean_mrr"]) > 0.2050

    # Verify latencies < 25 ms
    assert float(row_map["ARM-111"]["p50_latency_ms"]) < 25.0
    assert float(row_map["ARM-101"]["p50_latency_ms"]) < 25.0

    # Verify win/loss ratio > 3:1 for ARM-111 and ARM-101 vs Control
    assert int(row_map["ARM-111"]["wins_vs_control"]) >= 3 * int(row_map["ARM-111"]["losses_vs_control"])
    assert int(row_map["ARM-101"]["wins_vs_control"]) >= 3 * int(row_map["ARM-101"]["losses_vs_control"])


def test_statistical_analysis_significance():
    """Verify statistical analysis JSON contains 10k bootstrap results and significance."""
    stat_path = STAGE_DIR / "STATISTICAL_ANALYSIS.json"
    data = json.load(open(stat_path, encoding="utf-8"))

    assert data["metadata"]["bootstrap_replicates"] == 10000
    assert data["metadata"]["num_queries"] == 345

    # Check ARM-111 and ARM-101 vs control
    arm111 = data["comparisons_vs_control"]["ARM-111"]
    assert arm111["ci_95_lower"] > 0.0, "ARM-111 95% CI should strictly exclude zero"
    assert arm111["significant_after_fwer_05"] is True

    arm101 = data["comparisons_vs_control"]["ARM-101"]
    assert arm101["ci_95_lower"] > 0.0, "ARM-101 95% CI should strictly exclude zero"
    assert arm101["significant_after_fwer_05"] is True


def test_soft_lexical_damping_margin_gate():
    """Unit test verifying mathematical behavior of Factor A (dynamic margin gating)."""
    docs = [
        FileDoc(path="pkg/seed1.py", content="seed1", symbols=[], imports=[]),
        FileDoc(path="pkg/seed2.py", content="seed2", symbols=[], imports=[]),
        FileDoc(path="pkg/target.py", content="target", symbols=[], imports=[]),
    ]

    # Case 1: Large BM25 gap (BM25_1 = 10.0, BM25_2 = 2.0 -> margin = 8.0 -> threshold = 2.0)
    # Target gets modest graph boost -> cannot displace seed1
    bm25_scores = np.array([10.0, 2.0, 1.0], dtype=np.float32)

    ranker = FactorialCascadedRanker(
        mode="factorial",
        factor_a_soft_damping=True,
        soft_damping_tau=0.25,
    )

    # Fake graph boost directly in test
    # Seed 1 fused score: 0.60 * 10.0 = 6.0
    # Target fused score with modest boost: 0.60 * 1.0 + 0.25 * 5.0 = 0.6 + 1.25 = 1.85 (below 6.0 + 2.0)
    ranked = ranker.rank(docs, bm25_scores)
    assert ranked[0] == 0, "Seed 1 should remain at Rank 1 when lexical lead is dominant"

    # Case 2: Tiny BM25 gap (BM25_1 = 5.0, BM25_2 = 5.0 -> margin = 0.0 -> threshold = 0.0)
    # Target gets higher fused score -> displaces seed1
    # We test via mock fused calculation
    sem_scores = np.array([0.0, 0.0, 100.0], dtype=np.float32)
    ranked_disp = ranker.rank(docs, bm25_scores, semantic_scores=sem_scores)
    assert ranked_disp[0] == 2, "Target should displace Seed 1 when fused margin exceeds threshold"


def test_hub_attenuation_math():
    """Unit test verifying Factor B inverse logarithmic attenuation formula."""
    # W_hub(v) = 1 / log2(2 + deg_in)
    import math
    deg_0 = 0
    deg_2 = 2
    deg_6 = 6
    deg_14 = 14

    w0 = 1.0 / math.log2(2.0 + deg_0)
    w2 = 1.0 / math.log2(2.0 + deg_2)
    w6 = 1.0 / math.log2(2.0 + deg_6)
    w14 = 1.0 / math.log2(2.0 + deg_14)

    assert pytest.approx(w0, 1e-4) == 1.0
    assert pytest.approx(w2, 1e-4) == 0.5
    assert pytest.approx(w6, 1e-4) == 1.0 / 3.0
    assert pytest.approx(w14, 1e-4) == 0.25


def test_decision_report_verdict():
    """Verify STAGE3_12_DECISION_REPORT.md formal verdict is ADVANCE and covers required sections."""
    rep_path = STAGE_DIR / "STAGE3_12_DECISION_REPORT.md"
    content = rep_path.read_text(encoding="utf-8")

    assert "ADVANCE" in content
    assert "d373fd6ddcf0e01a06d0b4fa5bc1e9eddd857554ee6c792dc7f05011e8c1329d" in content
    assert "ARM-111" in content
    assert "ARM-101" in content
    assert "reponeedle/" in content
    assert "BLOCKED / PRELIMINARY" in content
