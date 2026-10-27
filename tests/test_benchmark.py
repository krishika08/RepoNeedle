"""
Tests for benchmark evaluation metrics.
"""

import pytest
from benchmarks.evaluator import RetrievalEvaluator
from reponeedle.models import ScoredFile


def test_recall_at_k():
    ranked = ["a.py", "b.py", "c.py"]
    gold = {"b.py", "d.py"}
    assert RetrievalEvaluator.recall_at_k(ranked, gold, 1) == 0.0
    assert RetrievalEvaluator.recall_at_k(ranked, gold, 2) == 0.5
    assert RetrievalEvaluator.recall_at_k(ranked, gold, 3) == 0.5


def test_reciprocal_rank():
    ranked = ["a.py", "b.py", "c.py"]
    assert RetrievalEvaluator.reciprocal_rank(ranked, {"a.py"}) == 1.0
    assert RetrievalEvaluator.reciprocal_rank(ranked, {"b.py"}) == 0.5
    assert RetrievalEvaluator.reciprocal_rank(ranked, {"z.py"}) == 0.0


def test_ndcg_at_k():
    ranked = ["a.py", "b.py"]
    gold = {"a.py"}
    assert RetrievalEvaluator.ndcg_at_k(ranked, gold, 1) == 1.0


def test_evaluate_budgeted_packing():
    files = [
        ScoredFile(path="a.py", score=0.9, token_count=100),
        ScoredFile(path="b.py", score=0.8, token_count=150),
    ]
    res = RetrievalEvaluator.evaluate_budgeted_packing(files, {"a.py"}, 500)
    assert res["coverage"] == 1.0
    assert res["irrelevant_tokens"] == 150.0
    assert res["tokens_used"] == 250.0

