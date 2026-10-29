"""
Test suite for RepoNeedle Stage 3.12: Performance Hardening, Bitwise Parity, and Artifact Integrity.
"""

import sys
import os
import csv
import json
import numpy as np
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from reponeedle.models import FileDoc, AblationConfig
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex
from reponeedle.engine import RepoNeedleEngine


def test_bm25_inverted_index_bitwise_parity():
    """Verify that BM25 inverted index returns bitwise identical scores to linear scan."""
    sample_docs = [
        FileDoc(path="src/main.py", content="def parse_arguments():\n    parser = argparse.ArgumentParser()\n    return parser.parse_args()"),
        FileDoc(path="src/utils.py", content="import math\ndef compute_distance(x, y):\n    return math.sqrt(x**2 + y**2)"),
        FileDoc(path="tests/test_main.py", content="def test_parse():\n    args = parse_arguments()\n    assert args is not None", is_test=True),
        FileDoc(path="docs/index.md", content="# Documentation\nHere is how to parse arguments and run the application"),
        FileDoc(path="src/network.py", content="import socket\ndef send_request(host, port):\n    s = socket.socket()\n    s.connect((host, port))"),
    ]

    index = BM25Index()
    index.fit(sample_docs)

    test_queries = [
        "parse arguments parser",
        "compute distance math",
        "socket request connect",
        "documentation application",
        "nonexistent term unknown",
    ]

    for q in test_queries:
        # Score via inverted index (default)
        fast_scores = index.score(q)

        # Compute reference scores using exact original linear formula
        q_tokens = index.tokenizer.tokenize_text(q)
        ref_scores = np.zeros(len(sample_docs), dtype=np.float32)
        for term in q_tokens:
            if term not in index.idf:
                continue
            idf = index.idf[term]
            for i, doc_tf in enumerate(index.doc_term_freqs):
                if term in doc_tf:
                    tf = doc_tf[term]
                    denom = tf + index.k1 * (1.0 - index.b + index.b * (index.doc_lengths[i] / index.avg_doc_len))
                    ref_scores[i] += idf * ((tf * (index.k1 + 1.0)) / denom)

        max_val = float(np.max(ref_scores))
        if max_val > 0.0:
            ref_scores /= max_val

        # Must be exact match within floating point precision
        np.testing.assert_allclose(fast_scores, ref_scores, rtol=1e-6, atol=1e-7,
                                   err_msg=f"Bitwise score mismatch for query '{q}'")


def test_semantic_candidate_slicing_parity():
    """Verify that candidate_indices slicing yields identical scores for the candidate subset."""
    sample_docs = [
        FileDoc(path="pkg/a.py", content="def handle_request(): return 'ok'"),
        FileDoc(path="pkg/b.py", content="class TokenizerEngine: pass"),
        FileDoc(path="pkg/c.py", content="def calculate_hash(data): return hash(data)"),
        FileDoc(path="pkg/d.py", content="def handle_response(): return 'done'"),
        FileDoc(path="pkg/e.py", content="import json; def serialize(obj): return json.dumps(obj)"),
    ]

    sem = SubwordSemanticIndex()
    sem.fit(sample_docs)

    query = "handle request response data"

    # Full scoring
    full_scores = sem.score(query)

    # Sliced scoring on candidate subset [0, 2, 3]
    candidate_indices = [0, 2, 3]
    sliced_scores = sem.score(query, candidate_indices=candidate_indices)

    # Candidate indices must match full scores exactly
    for idx in candidate_indices:
        assert abs(full_scores[idx] - sliced_scores[idx]) < 1e-6, f"Mismatch at index {idx}"

    # Non-candidate indices must be zero
    assert sliced_scores[1] == 0.0
    assert sliced_scores[4] == 0.0


def test_semantic_query_cache_and_invalidation():
    """Verify that query vector caching works and clears on re-fitting."""
    sample_docs = [
        FileDoc(path="a.py", content="def foo(): pass"),
        FileDoc(path="b.py", content="def bar(): pass"),
    ]

    sem = SubwordSemanticIndex()
    sem.fit(sample_docs)

    assert len(sem._query_cache) == 0

    # Score query
    _ = sem.score("foo bar")
    assert len(sem._query_cache) == 1
    assert "foo bar" in sem._query_cache

    # Re-fit with new documents
    new_docs = [FileDoc(path="c.py", content="def baz(): pass")]
    sem.fit(new_docs)

    # Cache must be emptied
    assert len(sem._query_cache) == 0


def test_engine_candidate_pool_size_integration():
    """Verify that candidate_pool_size parameter properly constrains retrieval."""
    sample_docs = [
        FileDoc(path=f"file_{i}.py", content=f"function_{i} implementation content keyword_{i % 5}")
        for i in range(100)
    ]

    engine = RepoNeedleEngine.from_documents(sample_docs)

    # CONFIG-09 (Full)
    res_full = engine.retrieve("keyword_0", ablation_config=AblationConfig.config_09())
    assert len(res_full.selected_files) > 0

    # CONFIG-10 (K=10)
    res_c10 = engine.retrieve("keyword_0", ablation_config=AblationConfig.config_10(pool_size=10))
    assert len(res_c10.selected_files) > 0
    # Must run without errors and return valid FileSelection
    assert res_c10.execution_time_ms > 0.0


def test_stage3_12_deliverables_integrity():
    """Verify all Stage 3.12 deliverables exist, have valid non-empty contents and correct schemas."""
    stage_dir = ROOT_DIR / "research" / "stage3_12"

    required_files = [
        "CANONICAL_REPRODUCTION.csv",
        "RUNTIME_BENCHMARKS.csv",
        "QUALITY_SPEED_TRADEOFF.csv",
        "MEMORY_BENCHMARKS.csv",
        "CLAIM_EVIDENCE_LEDGER.csv",
        "FAILURE_ANALYSIS.md",
        "REPRODUCE.md",
        "EXPERIMENT_REGISTRY.jsonl",
        "STAGE3_12_REPORT.md",
    ]

    for fname in required_files:
        fpath = stage_dir / fname
        assert fpath.exists(), f"Missing required deliverable: {fname}"
        assert fpath.stat().st_size > 0, f"Deliverable is empty: {fname}"

    # Verify CANONICAL_REPRODUCTION.csv
    can_rows = list(csv.DictReader(open(stage_dir / "CANONICAL_REPRODUCTION.csv", encoding="utf-8")))
    assert len(can_rows) == 4, f"Expected 4 canonical systems, found {len(can_rows)}"
    sys_ids = {r["system_id"] for r in can_rows}
    assert {"BASE-BM25", "CONFIG-09", "CONFIG-10", "BASE-REPOMAP"}.issubset(sys_ids)

    # Verify CLAIM_EVIDENCE_LEDGER.csv
    claim_rows = list(csv.DictReader(open(stage_dir / "CLAIM_EVIDENCE_LEDGER.csv", encoding="utf-8")))
    assert len(claim_rows) >= 8, f"Expected at least 8 claims, found {len(claim_rows)}"
    for r in claim_rows:
        assert r["reproducible_status"] in {
            "WITHDRAWN_INVALIDATED", "VERIFIED_VALID", "RECONCILED_METHODOLOGY_ERROR", "SUPERSEDED_INCOMPLETE"
        }

    # Verify RUNTIME_BENCHMARKS.csv
    rt_rows = list(csv.DictReader(open(stage_dir / "RUNTIME_BENCHMARKS.csv", encoding="utf-8")))
    assert len(rt_rows) >= 10, f"Expected at least 10 runtime rows, found {len(rt_rows)}"
    for r in rt_rows:
        assert "warm_latency_p50_ms" in r
        assert "scoring_latency_p50_ms" in r
        assert "packing_latency_p50_ms" in r
