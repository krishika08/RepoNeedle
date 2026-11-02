"""
Automated unit and integration regression tests for Phase R4.
Covers:
1. DenseSemanticEngine:
   - Subword & identifier extraction
   - SVD low-rank latent projection (k=8)
   - Pre-computed document embeddings
   - Query projection and cosine similarity scoring in [0.0, 1.0]
2. MultiHopGraphEngine:
   - 1-hop and 2-hop BFS path expansion
   - Distance attenuation (gamma = 0.5)
   - Cycle detection and prevention (A <-> B)
   - Hub dampening on high-degree nodes
   - Intent-conditioned edge routing (test vs implementation)
3. R4Ranker & Fusion:
   - Treatments A through H execution
   - Treatment D multiplicative semantic gating
   - Treatment H calibrated tri-modal hybrid fusion
   - Candidate pool preservation (100% recall retention)
"""
import os
import sys
import math
import pytest
import numpy as np
import networkx as nx

# Ensure r4/src, r3/src, and r2/src are on python path
r4_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "research", "v1_accuracy", "ranking_0_80", "r4", "src"))
r3_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "research", "v1_accuracy", "ranking_0_80", "r3", "src"))
r2_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "research", "v1_accuracy", "ranking_0_80", "r2", "src"))

for p in [r4_src, r3_src, r2_src]:
    if p not in sys.path:
        sys.path.insert(0, p)

from reponeedle.models import FileDoc
from dense_engine import DenseSemanticEngine
from multihop_graph import MultiHopGraphEngine
from ranker_r4 import R4Ranker, TREATMENTS


def test_dense_engine_fit_and_query():
    docs = [
        FileDoc(path="src/parser.py", content="class ArgumentParser: def parse_args(self): pass", symbols=["ArgumentParser", "parse_args"]),
        FileDoc(path="src/builder.py", content="class CommandBuilder: def build_command(self): pass", symbols=["CommandBuilder", "build_command"]),
        FileDoc(path="tests/test_parser.py", content="def test_argument_parser(): parser = ArgumentParser()", symbols=["test_argument_parser"]),
        FileDoc(path="utils/helpers.py", content="def log_message(msg): print(msg)", symbols=["log_message"]),
    ]
    engine = DenseSemanticEngine(dimension=8, max_features=500, metric="cosine")
    engine.fit(docs)

    assert engine.num_docs == 4
    assert len(engine.doc_paths) == 4
    assert engine.doc_embeddings.shape == (4, 8)

    query = "argument parser options"
    q_emb = engine.embed_query(query)
    assert q_emb.shape == (8,)
    assert pytest.approx(np.linalg.norm(q_emb), rel=1e-3) == 1.0

    scores = engine.score(query)
    assert len(scores) == 4
    for score in scores:
        assert 0.0 <= score <= 1.0

    # parser.py (index 0) should score higher than helpers.py (index 3)
    assert scores[0] > scores[3]


def test_dense_engine_empty_query():
    docs = [
        FileDoc(path="a.py", content="content here", symbols=[]),
        FileDoc(path="b.py", content="other content", symbols=[]),
        FileDoc(path="c.py", content="third file", symbols=[]),
    ]
    engine = DenseSemanticEngine(dimension=4, max_features=500, metric="cosine")
    engine.fit(docs)
    q_emb = engine.embed_query("")
    assert np.all(q_emb == 0.0)

    scores = engine.score("")
    assert np.all(scores == 0.5) or np.all(scores == 0.0)  # Normalized cosine neutral


def test_multihop_graph_expansion():
    # Mock FunctionGraphEngine
    class MockGraphEngine:
        def __init__(self):
            self.graph = nx.DiGraph()
            self.graph.add_edge("a.py", "b.py")
            self.graph.add_edge("b.py", "c.py")
            self.graph.add_node("d.py")

            self.callees_map = {
                "a.py": {"b.py": 0.8},
                "b.py": {"c.py": 0.8},
                "c.py": {},
                "d.py": {}
            }
            self.callers_map = {
                "a.py": {},
                "b.py": {"a.py": 0.8},
                "c.py": {"b.py": 0.8},
                "d.py": {}
            }

    mock_base = MockGraphEngine()
    engine = MultiHopGraphEngine(function_graph=mock_base, hop_decay=0.5, hub_degree_threshold=10)

    # Reference seeking traverses forward callees
    scores = engine.expand_multihop({"a.py": 1.0}, max_hops=2, intent="reference_seeking")
    assert "b.py" in scores
    # b.py is 1-hop away: score(1.0) * conf(0.8) * decay(0.5^1) = 0.4
    assert scores["b.py"] == pytest.approx(0.4, rel=1e-2)
    # c.py is 2-hops away: score(0.4) * conf(0.8) * decay(0.5^2) = 0.08
    assert "c.py" in scores
    assert scores["c.py"] == pytest.approx(0.08, rel=1e-2)
    # d.py is disconnected
    assert "d.py" not in scores


def test_multihop_graph_cycle_prevention():
    # Cyclic graph: A <-> B
    class MockCyclicEngine:
        def __init__(self):
            self.graph = nx.DiGraph()
            self.graph.add_edge("a.py", "b.py")
            self.graph.add_edge("b.py", "a.py")
            self.callees_map = {"a.py": {"b.py": 0.8}, "b.py": {"a.py": 0.8}}
            self.callers_map = {"a.py": {"b.py": 0.8}, "b.py": {"a.py": 0.8}}

    mock_base = MockCyclicEngine()
    engine = MultiHopGraphEngine(function_graph=mock_base, hop_decay=0.5)
    # Should terminate cleanly without recursion or loop error
    scores = engine.expand_multihop({"a.py": 1.0}, max_hops=4, intent="reference_seeking")
    assert "b.py" in scores


def test_multihop_graph_hub_dampening():
    # Node H has high degree (connected to 16 nodes)
    class MockHubEngine:
        def __init__(self):
            self.graph = nx.Graph()
            self.graph.add_node("hub.py")
            for i in range(16):
                self.graph.add_edge("hub.py", f"worker_{i}.py")
            self.callees_map = {"hub.py": {f"worker_{i}.py": 0.8 for i in range(16)}}
            self.callers_map = {}

    mock_base = MockHubEngine()
    engine = MultiHopGraphEngine(function_graph=mock_base, hub_degree_threshold=10)

    # Degree of hub.py is 16 (> 10)
    assert mock_base.graph.degree("hub.py") == 16
    damping = engine._get_hub_damping("hub.py")
    assert damping == pytest.approx(1.0 / math.sqrt(16), rel=1e-3)
    assert damping == 0.25


def test_multihop_intent_conditioning():
    class MockIntentEngine:
        def __init__(self):
            self.graph = nx.DiGraph()
            self.graph.add_edge("src/lib.py", "src/util.py")
            self.graph.add_edge("tests/test_lib.py", "src/lib.py")
            self.callees_map = {
                "src/lib.py": {"src/util.py": 0.9},
                "tests/test_lib.py": {"src/lib.py": 0.9}
            }
            self.callers_map = {
                "src/lib.py": {"tests/test_lib.py": 0.9},
                "src/util.py": {"src/lib.py": 0.9}
            }

    mock_base = MockIntentEngine()
    engine = MultiHopGraphEngine(function_graph=mock_base)

    # Test seeking from seed 'src/lib.py' routes towards test files
    test_scores = engine.expand_multihop({"src/lib.py": 1.0}, max_hops=1, intent="test_seeking")
    assert "tests/test_lib.py" in test_scores

    # Implementation seeking routes towards callers / references
    impl_scores = engine.expand_multihop({"src/util.py": 1.0}, max_hops=1, intent="implementation_seeking")
    assert "src/lib.py" in impl_scores


def test_r4_ranker_all_treatments():
    mock_candidates = [
        {"path": "src/parser.py", "m1_score": 12.5, "m1_rank": 1, "scores": {"subwords": 0.85, "structural_expansion": 0.5}},
        {"path": "src/builder.py", "m1_score": 8.0, "m1_rank": 2, "scores": {"subwords": 0.40, "structural_expansion": 0.2}},
        {"path": "tests/test_parser.py", "m1_score": 10.0, "m1_rank": 3, "scores": {"subwords": 0.75, "structural_expansion": 0.1}},
        {"path": "utils/helpers.py", "m1_score": 3.0, "m1_rank": 4, "scores": {"subwords": 0.10, "structural_expansion": 0.0}}
    ]

    query_text = "fix argument parser bug in cli"
    ranker = R4Ranker()

    for treatment in TREATMENTS:
        reranked, telemetry = ranker.rank(
            candidates=mock_candidates,
            query_text=query_text,
            treatment=treatment
        )
        assert len(reranked) == len(mock_candidates)
        paths = [c["path"] for c in reranked]
        assert set(paths) == {c["path"] for c in mock_candidates}
        for c in reranked:
            assert c["final_score"] >= 0.0
            assert "rank" in c
        assert telemetry["treatment"] == treatment
        assert telemetry["latency_ms"] >= 0.0


def test_treatment_d_multiplicative_gating():
    mock_candidates = [
        {"path": "src/parser.py", "m1_score": 10.0, "m1_rank": 1, "scores": {"subwords": 0.90}},
        {"path": "src/unrelated.py", "m1_score": 0.0, "m1_rank": 2, "scores": {"subwords": 0.80}}
    ]
    query_text = "parser"
    ranker = R4Ranker()
    reranked, _ = ranker.rank(mock_candidates, query_text, treatment="D")

    scores_by_path = {c["path"]: c["final_score"] for c in reranked}
    # Unrelated with 0 base score must remain exactly 0.0
    assert scores_by_path["src/unrelated.py"] == 0.0
    # Relevant parser should receive non-zero score with multiplicative boost
    assert scores_by_path["src/parser.py"] > 10.0
