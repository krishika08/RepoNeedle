"""
Unit tests for Stage 3.8: Metric definitions, sample alignment, and result reconciliation.
Verifies:
  1. Hand-calculated metric fixtures for MRR, Fractional Recall, and Character/Token budgets.
  2. Dataset alignment and query-set equality across all 4 evaluated systems in CANONICAL_PER_QUERY_RESULTS.csv.
  3. Reconciled point estimates and statistical difference calculations.
"""

import sys
import csv
from pathlib import Path
import pytest
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
ARB_SRC = ROOT_DIR / "external" / "agent-retrieval-bench" / "src"
if str(ARB_SRC) not in sys.path:
    sys.path.insert(0, str(ARB_SRC))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import (
    reciprocal_rank,
    recall_at,
    precision_at,
    gold_coverage_at_budget,
)


class TestHandCalculatedMetricFixtures:
    """Verifies canonical metrics against deterministic hand-calculated edge cases."""

    def test_mrr_first_target_ranking(self):
        # Target at rank 1 -> 1.0
        assert reciprocal_rank({"fileA.py"}, ["fileA.py", "fileB.py"]) == 1.0
        # Target at rank 4 -> 0.25
        assert reciprocal_rank({"fileD.py"}, ["fileA.py", "fileB.py", "fileC.py", "fileD.py"]) == 0.25
        # Multi-target: first target at rank 2 -> 0.50
        assert reciprocal_rank({"fileB.py", "fileD.py"}, ["fileA.py", "fileB.py", "fileC.py", "fileD.py"]) == 0.50
        # Zero target in list -> 0.0
        assert reciprocal_rank({"fileZ.py"}, ["fileA.py", "fileB.py"]) == 0.0

    def test_fractional_recall_multi_target(self):
        gold = {"f1.rs", "f2.rs", "f3.rs"}
        # Ranked top-5 has 2 of 3 gold files -> 2/3 = 0.666667
        ranked = ["f1.rs", "noise1.rs", "f2.rs", "noise2.rs", "noise3.rs", "f3.rs"]
        r5 = recall_at(gold, ranked, 5)
        assert pytest.approx(r5, 1e-5) == 2.0 / 3.0
        # Ranked top-6 has all 3 -> 1.0
        r6 = recall_at(gold, ranked, 6)
        assert pytest.approx(r6, 1e-5) == 1.0

    def test_character_budget_boundary(self):
        # 3 chunks of text lengths: 2500, 3000, 3500 characters
        # Budget = 8000 characters
        # Chunk 1: 2500 <= 8000 (accumulated = 2500)
        # Chunk 2: 2500 + 3000 = 5500 <= 8000 (accumulated = 5500)
        # Chunk 3: 5500 + 3500 = 9000 > 8000 -> STOPPED!
        c1 = {"path": "a.go", "text": "X" * 2500}
        c2 = {"path": "b.go", "text": "Y" * 3000}
        c3 = {"path": "c.go", "text": "Z" * 3500}
        chunks = [c1, c2, c3]
        gold = {"a.go", "b.go", "c.go"}
        # Only a.go and b.go are covered -> 2/3 = 0.666667
        cov = gold_coverage_at_budget(gold, chunks, 8000)
        assert pytest.approx(cov, 1e-5) == 2.0 / 3.0


class TestCanonicalDatasetAlignment:
    """Verifies the integrity, sample count, and alignment of CANONICAL_PER_QUERY_RESULTS.csv."""

    @pytest.fixture(scope="class")
    @classmethod
    def canonical_data(cls):
        csv_path = ROOT_DIR / "research" / "stage3_8" / "CANONICAL_PER_QUERY_RESULTS.csv"
        assert csv_path.exists(), f"Missing canonical file: {csv_path}"
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        return rows

    def test_row_count_and_systems(self, canonical_data):
        assert len(canonical_data) == 1380
        systems = {r["system_id"] for r in canonical_data}
        assert systems == {"BASE-BM25", "CAND-C", "CAND-F", "BASE-REPOMAP"}

    def test_exact_query_set_equality(self, canonical_data):
        queries_by_sys = {}
        for s in ["BASE-BM25", "CAND-C", "CAND-F", "BASE-REPOMAP"]:
            queries_by_sys[s] = [r["query_id"] for r in canonical_data if r["system_id"] == s]
            assert len(queries_by_sys[s]) == 345
            assert len(set(queries_by_sys[s])) == 345

        # All systems must evaluate the exact same queries in identical sequence
        assert queries_by_sys["BASE-BM25"] == queries_by_sys["CAND-C"]
        assert queries_by_sys["BASE-BM25"] == queries_by_sys["CAND-F"]
        assert queries_by_sys["BASE-BM25"] == queries_by_sys["BASE-REPOMAP"]

    def test_no_null_or_empty_critical_fields(self, canonical_data):
        for r in canonical_data:
            assert r["query_id"].strip() != ""
            assert r["repo"].strip() != ""
            assert r["base_commit"].strip() != ""
            assert r["system_id"].strip() != ""
            assert r["mrr"].strip() != ""
            assert r["recall_at_20"].strip() != ""
            assert r["char_cov_at_8k"].strip() != ""
            assert r["token_bcy_at_8k"].strip() != ""
            assert r["execution_status"] == "SUCCESS_NO_EXCLUSION"


class TestReconciledPointEstimates:
    """Verifies that the canonical per-query outputs reproduce the reconciled benchmark metrics."""

    @pytest.fixture(scope="class")
    @classmethod
    def canonical_data(cls):
        csv_path = ROOT_DIR / "research" / "stage3_8" / "CANONICAL_PER_QUERY_RESULTS.csv"
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def test_system_point_estimates(self, canonical_data):
        mrr = {}
        r20 = {}
        for s in ["BASE-BM25", "CAND-C", "CAND-F", "BASE-REPOMAP"]:
            sys_rows = [r for r in canonical_data if r["system_id"] == s]
            mrr[s] = np.mean([float(r["mrr"]) for r in sys_rows])
            r20[s] = np.mean([float(r["recall_at_20"]) for r in sys_rows])

        # BASE-BM25: MRR 0.1735, R@20 0.4549
        assert pytest.approx(mrr["BASE-BM25"], abs=0.001) == 0.1735
        assert pytest.approx(r20["BASE-BM25"], abs=0.001) == 0.4549

        # CAND-C: MRR 0.1399, R@20 0.5105
        assert pytest.approx(mrr["CAND-C"], abs=0.001) == 0.1399
        assert pytest.approx(r20["CAND-C"], abs=0.001) == 0.5105

        # CAND-F: MRR 0.1351, R@20 0.5078
        assert pytest.approx(mrr["CAND-F"], abs=0.001) == 0.1351
        assert pytest.approx(r20["CAND-F"], abs=0.001) == 0.5078

        # BASE-REPOMAP: MRR 0.2293, R@20 0.6599
        assert pytest.approx(mrr["BASE-REPOMAP"], abs=0.001) == 0.2293
        assert pytest.approx(r20["BASE-REPOMAP"], abs=0.001) == 0.6599

    def test_recall20_delta_point_estimate(self, canonical_data):
        bm25_r20 = np.array([float(r["recall_at_20"]) for r in canonical_data if r["system_id"] == "BASE-BM25"])
        candf_r20 = np.array([float(r["recall_at_20"]) for r in canonical_data if r["system_id"] == "CAND-F"])
        delta_r20 = candf_r20 - bm25_r20
        # Point estimate must equal +0.0529
        assert pytest.approx(np.mean(delta_r20), abs=0.001) == 0.0529
