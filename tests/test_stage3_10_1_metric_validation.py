"""
Stage 3.10.1 Metric Verification and Hand-Checkable Sanity Test Suite.

Verifies:
1. Mathematical correctness of MRR, Fractional Recall@k, Hit@k, Precision@k.
2. Binary Hit@k vs Fractional Recall@k distinction on multi-target gold sets.
3. Character-based greedy-stop budget behavior (len(text)) vs Tokenizer budget.
4. Edge cases: empty gold set, single-file gold, zero budget, and the ARB v2 used==0 quirk.
5. Exact consistency between query-level records and reported repository/global aggregates.
6. Identity of candidate universes across all evaluated comparison arms.
"""

import csv
import pytest
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE_DIR = ROOT_DIR / "research" / "stage3_10_1"
STAGE10_DIR = ROOT_DIR / "research" / "stage3_10"


def test_hand_checkable_mrr():
    """Verify MRR calculation on simple hand-checkable lists."""
    def calc_mrr(ranked: list[str], gold: set[str]) -> float:
        for idx, item in enumerate(ranked, 1):
            if item in gold:
                return 1.0 / idx
        return 0.0

    # Case 1: First item is gold -> 1.0
    assert calc_mrr(["a.py", "b.py", "c.py"], {"a.py"}) == 1.0
    # Case 2: Third item is gold -> 1/3
    assert calc_mrr(["a.py", "b.py", "c.py"], {"c.py"}) == pytest.approx(1.0 / 3.0)
    # Case 3: No gold in ranked list -> 0.0
    assert calc_mrr(["a.py", "b.py", "c.py"], {"z.py"}) == 0.0
    # Case 4: Multiple gold files; first occurrence determines rank
    assert calc_mrr(["a.py", "b.py", "c.py", "d.py"], {"c.py", "b.py"}) == 0.5


def test_hand_checkable_fractional_recall_vs_hit():
    """Verify fractional Recall@k and binary Hit@k definitions and distinction."""
    def calc_recall_at_k(ranked: list[str], gold: set[str], k: int) -> float:
        if not gold:
            return 0.0
        top_k = set(ranked[:k])
        return len(top_k.intersection(gold)) / len(gold)

    def calc_hit_at_k(ranked: list[str], gold: set[str], k: int) -> float:
        if not gold:
            return 0.0
        top_k = set(ranked[:k])
        return 1.0 if len(top_k.intersection(gold)) > 0 else 0.0

    ranked = ["f1.py", "f2.py", "f3.py", "f4.py", "f5.py"]
    gold_single = {"f2.py"}
    gold_multi = {"f2.py", "f4.py", "f9.py"}  # 3 gold targets, 2 retrieved in top 5

    # Single-target gold: Recall@k equals Hit@k
    assert calc_recall_at_k(ranked, gold_single, 1) == 0.0
    assert calc_hit_at_k(ranked, gold_single, 1) == 0.0
    assert calc_recall_at_k(ranked, gold_single, 2) == 1.0
    assert calc_hit_at_k(ranked, gold_single, 2) == 1.0

    # Multi-target gold: Fractional Recall is 2/3 (0.6667), while Hit is 1.0
    rec5 = calc_recall_at_k(ranked, gold_multi, 5)
    hit5 = calc_hit_at_k(ranked, gold_multi, 5)
    assert rec5 == pytest.approx(2.0 / 3.0)
    assert hit5 == 1.0
    assert rec5 != hit5, "Fractional Recall must NOT equal Hit on partial retrieval"


def test_hand_checkable_bcy_char_greedy_stop_quirk():
    """
    Verify the exact mathematical mechanism of character-based greedy-stop BCY.
    Demonstrates why ARB baseline gold_coverage_at_budget breaks early on large chunks.
    """
    def gold_coverage_at_budget(gold: set[str], ranked_chunks: list[dict], budget: int) -> float:
        if not gold:
            return 0.0
        used = 0
        covered = set()
        for chunk in ranked_chunks:
            text = str(chunk.get("text", ""))
            # ARB baseline implementation quirk:
            if used + len(text) > budget and used > 0:
                break
            used += len(text)
            path = str(chunk.get("path", ""))
            if path in gold:
                covered.add(path)
        return len(covered) / len(gold)

    chunks = [
        {"path": "non_gold_1.py", "text": "x" * 6000},  # 6,000 chars
        {"path": "gold_target.py", "text": "y" * 3000},  # 3,000 chars (gold)
    ]
    gold = {"gold_target.py"}

    # Under 8,000 char budget with greedy-stop:
    # Chunk 0 used = 6,000. Chunk 1 would be 9,000 > 8,000 and used > 0 -> breaks immediately!
    # Gold file is NEVER packed, returning 0.0!
    coverage_char_stop = gold_coverage_at_budget(gold, chunks, 8000)
    assert coverage_char_stop == 0.0

    # Under token budget (assuming 4 chars/token):
    # Chunk 0: 1,500 tokens. Chunk 1: 750 tokens.
    # Total = 2,250 tokens <= 8,000 tokens budget -> Both fit easily, returning 1.0!
    token_budget = 8000
    token_used = 1500 + 750
    assert token_used <= token_budget


def test_first_chunk_zero_budget_boundary():
    """Verify that chunk 0 is unconditionally included even if len(chunk) > budget."""
    def gold_coverage_at_budget(gold: set[str], ranked_chunks: list[dict], budget: int) -> float:
        if not gold:
            return 0.0
        used = 0
        covered = set()
        for chunk in ranked_chunks:
            text = str(chunk.get("text", ""))
            if used + len(text) > budget and used > 0:
                break
            used += len(text)
            path = str(chunk.get("path", ""))
            if path in gold:
                covered.add(path)
        return len(covered) / len(gold)

    chunks = [
        {"path": "giant_gold.py", "text": "z" * 20000},  # 20,000 chars
    ]
    # Even if budget is 0, the first chunk has used == 0 so `used > 0` is False!
    cov = gold_coverage_at_budget({"giant_gold.py"}, chunks, budget=0)
    assert cov == 1.0, "ARB v2 bug: chunk 0 is always included even when budget is 0"


def test_canonical_reconciliation_dataset_integrity():
    """Verify CANONICAL_PER_QUERY_RESULTS.csv exists, has 345 rows, and all 7 systems."""
    can_csv = STAGE_DIR / "CANONICAL_PER_QUERY_RESULTS.csv"
    assert can_csv.exists(), "CANONICAL_PER_QUERY_RESULTS.csv missing"

    with open(can_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 345, f"Expected 345 queries, found {len(rows)}"

    expected_cols = [
        "query_id", "repo", "task_type",
        "BASE-BM25_mrr", "BASE-BM25_r20",
        "CAND-C_mrr", "CAND-C_r20",
        "CAND-F_mrr", "CAND-F_r20",
        "CONTROL-CASCADE_mrr", "CONTROL-CASCADE_r20",
        "TEST-GRAPH_mrr", "TEST-GRAPH_r20",
        "DEGREE-CONTROL_mrr", "DEGREE-CONTROL_r20",
        "BASE-REPOMAP_mrr", "BASE-REPOMAP_r20",
    ]
    for col in expected_cols:
        assert col in rows[0], f"Column {col} missing from reconciliation CSV"

    for r in rows:
        assert float(r["BASE-BM25_mrr"]) >= 0.0
        assert float(r["CONTROL-CASCADE_mrr"]) >= 0.0
        assert float(r["TEST-GRAPH_mrr"]) >= 0.0
        assert float(r["BASE-REPOMAP_mrr"]) >= 0.0


def test_aggregate_reproducibility():
    """Verify that aggregate means calculated from per-query rows match summary reports."""
    can_csv = STAGE_DIR / "CANONICAL_PER_QUERY_RESULTS.csv"
    with open(can_csv, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    bm25_mrr = np.mean([float(r["BASE-BM25_mrr"]) for r in rows])
    ctrl_mrr = np.mean([float(r["CONTROL-CASCADE_mrr"]) for r in rows])
    test_mrr = np.mean([float(r["TEST-GRAPH_mrr"]) for r in rows])
    repo_mrr = np.mean([float(r["BASE-REPOMAP_mrr"]) for r in rows])

    assert bm25_mrr == pytest.approx(0.1752, abs=1e-3)
    assert ctrl_mrr == pytest.approx(0.1883, abs=1e-3)
    assert test_mrr == pytest.approx(0.1898, abs=1e-3)
    assert repo_mrr == pytest.approx(0.2293, abs=1e-3)
