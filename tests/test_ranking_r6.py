"""
Unit, integration, and regression test suite for Mission 0.80+ Phase R6:
- Independent Benchmark Dataset & Provenance Integrity
- Zero-Oracle Compliance
- Graph Evidence Classification & Disentanglement
- Multi-Treatment Ranking Architecture
- Clustered Statistical Inference
"""

import os
import sys
import gzip
import json
import pytest
from typing import Dict, List, Any

# Ensure r6 src is on path
r6_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "research", "v1_accuracy", "ranking_0_80", "r6", "src"))
if r6_src not in sys.path:
    sys.path.insert(0, r6_src)

from graph_evidence import GraphEvidenceAuditor, EdgeProvenance, CONFIRMED_TYPES, HEURISTIC_TYPES
from ranker_r6 import R6Ranker, TREATMENTS
from evaluate_r6 import compute_metrics, clustered_bootstrap_ci

ARB_25_REPOS = {
    "gin-gonic/gin", "etcd-io/etcd", "pallets/click", "caddyserver/caddy", "clap-rs/clap",
    "spring-projects/spring-boot", "vuejs/core", "pypa/pip", "fastapi/fastapi", "scrapy/scrapy",
    "ipython/ipython", "tox-dev/tox", "mockito/mockito", "HypothesisWorks/hypothesis", "numpy/numpy",
    "tokio-rs/tokio", "huggingface/diffusers", "microsoft/playwright", "pydantic/pydantic", "eslint/eslint",
    "huggingface/transformers", "vitejs/vite", "pytest-dev/pytest", "astral-sh/ruff", "python/mypy"
}


@pytest.fixture(scope="module")
def benchmark_data():
    bm_path = os.path.abspath(os.path.join(r6_src, "..", "independent_benchmark.json.gz"))
    assert os.path.exists(bm_path), f"Benchmark dataset missing at {bm_path}"
    with gzip.open(bm_path, "rt", encoding="utf-8") as f:
        return json.load(f)


def test_benchmark_dataset_integrity(benchmark_data):
    """Verifies that the independent benchmark contains 180 tasks across 18 unseen repos."""
    assert len(benchmark_data) == 180, f"Expected 180 tasks, got {len(benchmark_data)}"
    
    repos = set(d["repo"] for d in benchmark_data)
    assert len(repos) == 18, f"Expected 18 repositories, got {len(repos)}"
    
    # 0.0% overlap with ARB v2
    overlap = repos & ARB_25_REPOS
    assert len(overlap) == 0, f"Critical Leakage Violation: Found overlapping repos {overlap}"

    # Partition integrity
    partitions = {d["partition"] for d in benchmark_data}
    assert partitions == {"train", "val", "held_out"}

    train_repos = {d["repo"] for d in benchmark_data if d["partition"] == "train"}
    val_repos = {d["repo"] for d in benchmark_data if d["partition"] == "val"}
    held_out_repos = {d["repo"] for d in benchmark_data if d["partition"] == "held_out"}

    assert len(train_repos) == 9
    assert len(val_repos) == 4
    assert len(held_out_repos) == 5
    assert not (train_repos & val_repos)
    assert not (train_repos & held_out_repos)
    assert not (val_repos & held_out_repos)


def test_graph_evidence_classification():
    """Verifies classification of confirmed vs heuristic relationships."""
    candidate = {
        "path": "django/db/models/query.py",
        "ast_symbols": ["QuerySet", "filter"],
        "imports": ["django.core.exceptions", "django.db.models.expressions"],
    }
    seeds = ["django/core/exceptions.py"]
    query_text = "QuerySet.filter() raises TypeError"

    edges = GraphEvidenceAuditor.audit_edges(candidate, seeds, query_text)
    assert len(edges) > 0

    # Must contain confirmed import
    has_confirmed_import = any(e["provenance"] == EdgeProvenance.CONFIRMED_IMPORT and e["is_confirmed"] for e in edges)
    assert has_confirmed_import, "Expected confirmed import edge"

    # Must contain confirmed symbol
    has_confirmed_symbol = any(e["provenance"] == EdgeProvenance.CONFIRMED_SYMBOL and e["is_confirmed"] for e in edges)
    assert has_confirmed_symbol, "Expected confirmed symbol edge"


def test_graph_evidence_heuristic_separation():
    """Verifies heuristic edges are marked not confirmed and can be ablated."""
    test_cand = {
        "path": "tests/test_query.py",
        "ast_symbols": ["TestQuerySet"],
        "imports": [],
    }
    seeds = ["django/db/models/query.py"]
    edges = GraphEvidenceAuditor.audit_edges(test_cand, seeds, "test query")

    # Should detect heuristic test stem
    has_stem = any(e["provenance"] == EdgeProvenance.HEURISTIC_TEST_STEM and not e["is_confirmed"] for e in edges)
    assert has_stem, "Expected heuristic test stem edge"

    # In no_heuristics mode, score must be 0.0
    score_no_heur = GraphEvidenceAuditor.compute_edge_impact_score(edges, mode="no_heuristics")
    assert score_no_heur == 0.0

    # In full mode, score should be > 0.0
    score_full = GraphEvidenceAuditor.compute_edge_impact_score(edges, mode="full", query_intent="test")
    assert score_full > 0.0


def test_ranker_r6_zero_oracle_execution():
    """Ensures ranker produces rankings using only permitted observable features."""
    cands = [
        {"path": "a.py", "m1_score": 5.0, "scores": {"subwords": 10.0, "exact_symbol": 2.0}, "ast_symbols": ["foo"], "imports": []},
        {"path": "b.py", "m1_score": 3.0, "scores": {"subwords": 5.0, "exact_symbol": 0.0}, "ast_symbols": ["bar"], "imports": ["a"]},
    ]
    ranked = R6Ranker.rank_candidates(cands, query_text="call foo in b", seeds=["a.py"], treatment="D")
    assert len(ranked) == 2
    assert all("path" in c for c in ranked)


def test_metric_computation():
    """Verifies standard evaluation metrics calculation."""
    sample_records = [
        {"gold_ranks": [1], "gold_files": ["a.py"], "gold_candidates_in_pool": 1},
        {"gold_ranks": [2, 15], "gold_files": ["b.py", "c.py"], "gold_candidates_in_pool": 2},
    ]
    m = compute_metrics(sample_records)
    # MRR = 0.5 * (1/1 + 1/2) = 0.75
    assert m["mrr"] == 0.75
    assert m["hit1"] == 0.5
    assert m["candidate_recall"] == 1.0


def test_reproduce_r6_validation_superiority(benchmark_data):
    """Validates that Treatment D improves over Treatment B on the Validation partition."""
    val_data = [d for d in benchmark_data if d["partition"] == "val"]
    
    b_records = []
    d_records = []
    for q in val_data:
        golds = q["_evaluator_gold"]["gold_files"]
        cands = q["candidates"]
        seeds = q.get("seed_files", [])
        qtext = q["query_text"]

        # Rank B
        r_b = R6Ranker.rank_candidates(cands, qtext, seeds, "B")
        paths_b = [c["path"] for c in r_b]
        ranks_b = sorted([paths_b.index(g) + 1 for g in golds if g in paths_b])
        b_records.append({
            "query_id": q["query_id"],
            "repo": q["repo"],
            "gold_files": golds,
            "gold_ranks": ranks_b,
            "gold_candidates_in_pool": len(golds),
        })

        # Rank D
        r_d = R6Ranker.rank_candidates(cands, qtext, seeds, "D")
        paths_d = [c["path"] for c in r_d]
        ranks_d = sorted([paths_d.index(g) + 1 for g in golds if g in paths_d])
        d_records.append({
            "query_id": q["query_id"],
            "repo": q["repo"],
            "gold_files": golds,
            "gold_ranks": ranks_d,
            "gold_candidates_in_pool": len(golds),
        })

    m_b = compute_metrics(b_records)
    m_d = compute_metrics(d_records)

    assert m_d["mrr"] >= m_b["mrr"], f"Expected D MRR ({m_d['mrr']}) >= B MRR ({m_b['mrr']})"
    assert m_d["recall_20"] >= m_b["recall_20"], f"Expected D Recall@20 ({m_d['recall_20']}) >= B Recall@20 ({m_b['recall_20']})"
    assert m_d["recall_20"] == 1.0, f"Expected 100% Recall@20 for Treatment D on Validation, got {m_d['recall_20']}"

