"""
Focused tests for the supplemental product-aligned evaluator
(benchmarks/run_arb_product_aligned_eval.py). Pure helpers only; the ARB-dependent check is skipped
when the external Agent Retrieval Bench checkout is not present (e.g. in clean CI).
"""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))

import run_arb_product_aligned_eval as E  # noqa: E402
from run_arb_evaluator_audit import reconstruct_file  # noqa: E402

ARB_SRC = ROOT / "external" / "agent-retrieval-bench" / "src"


class TestProtocolHelpers:

    def test_tie_rule_score_desc_then_path_asc(self):
        scored = [("b.py", 1.0), ("a.py", 1.0), ("c.py", 2.0), ("d.py", 0.0)]
        assert E.rank_files(scored) == ["c.py", "a.py", "b.py", "d.py"]

    def test_chunk_to_file_rule_is_max(self):
        chunks = [("a.py", 0.2), ("b.py", 0.9), ("a.py", 0.7), ("b.py", 0.1)]
        assert dict(E.collapse_chunks_max(chunks)) == {"a.py": 0.7, "b.py": 0.9}

    def test_file_metrics_hand_computed(self):
        ranked = [f"f{i}.py" for i in range(1, 31)]
        m = E.file_metrics(["f3.py", "f12.py", "missing.py"], ranked)
        assert m["mrr"] == pytest.approx(1 / 3)
        assert m["recall@5"] == pytest.approx(1 / 3)
        assert m["recall@10"] == pytest.approx(1 / 3)
        assert m["recall@20"] == pytest.approx(2 / 3)

    def test_file_metrics_no_hit(self):
        assert E.file_metrics(["x.py"], ["a.py", "b.py"]) == {"mrr": 0.0, "recall@5": 0.0, "recall@10": 0.0, "recall@20": 0.0}

    def test_unranked_gold_gets_no_position(self):
        """Unselected / unranked files must never receive an artificial position."""
        assert E.gold_positions(["a.py", "z.py"], ["b.py", "a.py"]) == {"a.py": 2, "z.py": None}

    def test_bootstrap_is_deterministic_and_brackets_mean(self):
        rng = np.random.default_rng(1)
        diffs = list(rng.normal(0.1, 0.05, size=60))
        clusters = [f"repo{i % 6}" for i in range(60)]
        a = E.clustered_bootstrap_ci(diffs, clusters, n_boot=2000)
        b = E.clustered_bootstrap_ci(diffs, clusters, n_boot=2000)
        assert a == b
        assert a[0] <= float(np.mean(diffs)) <= a[1]

    def test_bootstrap_resamples_clusters_not_queries(self):
        # One cluster: every resample is the same cluster, so the interval collapses to its mean.
        ci = E.clustered_bootstrap_ci([0.1, 0.3, 0.5], ["r", "r", "r"], n_boot=500)
        assert ci[0] == pytest.approx(0.3) and ci[1] == pytest.approx(0.3)

    def test_protocol_constants_fixed(self):
        assert E.BOOT_SEED == 20261109 and E.BOOT_N == 10_000
        assert E.CONFIG["tie_rule"] == "score desc, path asc"
        assert E.CONFIG["chunk_to_file_rule"].startswith("max")
        for a, b, _ in E.COMPARISONS:
            assert a in E.SYSTEMS and b in E.SYSTEMS
        assert "NOT an official ARB score" in E.CONFIG["evaluation"]


class TestWholeFileReconstruction:

    def test_header_then_symbols_in_line_order(self):
        chunks = [
            {"kind": "symbol", "start_line": 10, "text": "def b():\n    return 2"},
            {"kind": "file", "start_line": 1, "text": "import os\nX = 1\n\ndef a():\n...[truncated]"},
            {"kind": "symbol", "start_line": 4, "text": "def a():\n    return 1"},
        ]
        text = reconstruct_file(chunks)
        assert text.splitlines()[:3] == ["import os", "X = 1", ""]
        assert text.index("def a()") < text.index("def b()")
        assert "[truncated]" not in text

    def test_no_symbols_falls_back_to_longest_chunk(self):
        assert reconstruct_file([{"kind": "file", "text": "short"}, {"kind": "file", "text": "much longer"}]) == "much longer"


@pytest.mark.skipif(not ARB_SRC.exists(), reason="Agent Retrieval Bench checkout not present")
class TestBM25Exactness:

    def test_precomputed_bm25_equals_arb_reference(self):
        sys.path.insert(0, str(ARB_SRC))
        from agent_retrieval_bench.baseline import (rank_chunks_bm25_with_scores, tokenize, chunk_text,
                                                    BM25_K1, BM25_B)
        chunks = [
            {"path": "src/session.py", "chunk_id": "1", "kind": "symbol", "symbol": "SessionManager",
             "text": "class SessionManager:\n    timeout = 3600\n    def refresh_token(self): pass"},
            {"path": "src/auth.py", "chunk_id": "2", "kind": "file", "text": "def login(user): return token"},
            {"path": "docs/guide.md", "chunk_id": "3", "kind": "file", "text": "Session timeout configuration guide"},
            {"path": "src/auth.py", "chunk_id": "4", "kind": "symbol", "symbol": "logout", "text": "def logout(): pass"},
        ]
        idx = E.PrecomputedBM25(chunks, tokenize, chunk_text, BM25_K1, BM25_B)
        for q in ["session timeout refresh token", "login logout", "", "nothing matches here"]:
            ref = rank_chunks_bm25_with_scores(q, chunks)
            got = idx.rank(q)
            assert [(s, c["chunk_id"]) for s, c in ref] == [(s, c["chunk_id"]) for s, c in got]
