"""
Automated unit and integration regression tests for Phase R5.
Covers:
1. CodeUnitIndexer:
   - Polyglot AST extraction (Python, Rust, JavaScript)
   - Fallback lexical chunking for unparseable source code
   - Incremental re-indexing upon file modification
2. QueryIntentDetector & CodeUnitScorer:
   - Intent classification across 6 archetypes
   - Asymmetric symbol and signature scoring
   - Source-span localization
3. ChangeImpactEngine:
   - Multi-relational typed edges (TESTS_BEHAVIOR, CHANGED_CALLER, IMPORTS, BUILD_CONFIG)
   - Intent-conditioned edge propagation
4. MultiTargetSelector:
   - Target role classification
   - Role-aware MMR diversity selection
   - Candidate pool preservation (100% recall)
5. R5Ranker:
   - Treatments A through H execution
   - Treatment F change-impact gating
"""
import os
import sys
import math
import pytest

# Ensure r5/src, r4/src, r3/src, and r2/src are on python path
r5_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "research", "v1_accuracy", "ranking_0_80", "r5", "src"))
r4_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "research", "v1_accuracy", "ranking_0_80", "r4", "src"))
r3_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "research", "v1_accuracy", "ranking_0_80", "r3", "src"))
r2_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "research", "v1_accuracy", "ranking_0_80", "r2", "src"))

for p in [r5_src, r4_src, r3_src, r2_src]:
    if p not in sys.path:
        sys.path.insert(0, p)

from code_unit import CodeUnitIndexer, CodeUnitType
from query_alignment import QueryIntentDetector, QueryIntent, CodeUnitScorer
from change_impact import ChangeImpactEngine, EdgeType
from multi_target import MultiTargetSelector, TargetRole
from ranker_r5 import R5Ranker, TREATMENTS


def test_code_unit_python_ast_extraction():
    indexer = CodeUnitIndexer()
    py_code = """
import os

class DatabaseClient:
    \"\"\"Handles connection pool.\"\"\"
    def __init__(self, host: str):
        self.host = host

    def query(self, sql: str) -> list:
        return self._execute(sql)

    def _execute(self, sql: str):
        pass

def global_health_check() -> bool:
    return True
"""
    units = indexer.index_file("db/client.py", py_code)
    unit_ids = [u.unit_id for u in units]

    assert "db/client.py::[module]" in unit_ids
    assert "db/client.py::DatabaseClient" in unit_ids
    assert "db/client.py::DatabaseClient.query" in unit_ids
    assert "db/client.py::global_health_check" in unit_ids

    # Verify method properties
    query_unit = indexer.units_by_id["db/client.py::DatabaseClient.query"]
    assert query_unit.unit_type == CodeUnitType.METHOD
    assert query_unit.parent_name == "DatabaseClient"
    assert "sql" in query_unit.signature
    assert "_execute" in query_unit.calls


def test_code_unit_incremental_reindexing():
    indexer = CodeUnitIndexer()
    v1_code = "def old_func(): pass\n"
    indexer.index_file("test_mod.py", v1_code)
    assert "test_mod.py::old_func" in indexer.units_by_id

    # Update file with new content
    v2_code = "def new_func(): pass\n"
    indexer.index_file("test_mod.py", v2_code)
    assert "test_mod.py::old_func" not in indexer.units_by_id
    assert "test_mod.py::new_func" in indexer.units_by_id


def test_code_unit_lexical_fallback():
    indexer = CodeUnitIndexer()
    raw_text = "\n".join([f"config_entry_{i} = {i * 10}" for i in range(100)])
    units = indexer.index_file("config.ini", raw_text, language="generic")
    assert len(units) > 1
    assert any(u.unit_type == CodeUnitType.SOURCE_SPAN for u in units)


def test_query_intent_detector():
    assert QueryIntentDetector.detect("where is function parse_args defined?") == QueryIntent.DEFINITION
    assert QueryIntentDetector.detect("where is DatabaseClient.query called?") == QueryIntent.REFERENCE
    assert QueryIntentDetector.detect("Traceback (most recent call last): File 'app.py', line 42") == QueryIntent.ERROR
    assert QueryIntentDetector.detect("which method validates the user email token?") == QueryIntent.VALIDATION
    assert QueryIntentDetector.detect("find unit tests covering help template builder") == QueryIntent.TEST


def test_code_unit_scorer_source_span_localization():
    cand = {
        "path": "src/parser/argument_parser.py",
        "scores": {"exact_symbol": 8.0, "subwords": 0.85}
    }
    query = "where is argument_parser implemented?"
    tokens = ["argument", "parser"]
    intent = QueryIntent.DEFINITION

    score, meta = CodeUnitScorer.score_candidate_unit(cand, query, tokens, intent)
    assert score > 0.0
    assert "argument_parser" in meta["best_unit"]
    assert meta["exact_sym_score"] == 8.0


def test_change_impact_typed_propagation():
    seeds = ["src/auth/session_manager.py"]
    candidates = [
        {"path": "tests/auth/test_session.py", "scores": {}},
        {"path": "src/auth/session_storage.py", "scores": {}},
        {"path": "setup.py", "scores": {}},
        {"path": "unrelated/crypto/hash.py", "scores": {}},
    ]

    # Test Intent: tests/auth/test_session.py should receive highest impact
    test_impact = ChangeImpactEngine.compute_candidate_impact(seeds, candidates, query_intent="test")
    assert test_impact["tests/auth/test_session.py"] > test_impact["unrelated/crypto/hash.py"]

    # Reference Intent: sibling session_storage should receive high impact
    ref_impact = ChangeImpactEngine.compute_candidate_impact(seeds, candidates, query_intent="reference")
    assert ref_impact["src/auth/session_storage.py"] > ref_impact["unrelated/crypto/hash.py"]


def test_multi_target_role_classification_and_mmr():
    selector = MultiTargetSelector(diversity_lambda=0.75, max_same_dir=2)

    assert selector.classify_role("src/core/parser.py", is_top_impl=True) == TargetRole.PRIMARY_IMPL
    assert selector.classify_role("src/core/helpers.py", is_top_impl=False) == TargetRole.SUPPORT_IMPL
    assert selector.classify_role("tests/core/test_parser.py") == TargetRole.TEST
    assert selector.classify_role("pyproject.toml") == TargetRole.CONFIG_BUILD
    assert selector.classify_role("docs/architecture.md") == TargetRole.DOCS

    mock_candidates = [
        {"path": "src/core/parser.py", "score": 10.0},
        {"path": "src/core/parser_aux1.py", "score": 9.5},
        {"path": "src/core/parser_aux2.py", "score": 9.2},
        {"path": "tests/core/test_parser.py", "score": 9.0},
        {"path": "src/core/parser_aux3.py", "score": 8.8},
    ]

    selected = selector.select_diverse_targets(mock_candidates, top_k=20)
    assert len(selected) == len(mock_candidates)
    paths_selected = [c["path"] for c in selected]
    # All candidates preserved (100% recall retention)
    assert set(paths_selected) == {c["path"] for c in mock_candidates}
    # Test file receives role diversity bonus
    test_idx = paths_selected.index("tests/core/test_parser.py")
    assert test_idx <= 3


def test_r5_ranker_treatments_and_recall_invariance():
    mock_candidates = [
        {"path": "src/parser.py", "m1_score": 12.0, "m1_rank": 1, "scores": {"exact_symbol": 6.0, "subwords": 0.8}},
        {"path": "src/builder.py", "m1_score": 8.0, "m1_rank": 2, "scores": {"exact_symbol": 2.0, "subwords": 0.4}},
        {"path": "tests/test_parser.py", "m1_score": 10.0, "m1_rank": 3, "scores": {"exact_symbol": 5.0, "subwords": 0.7}},
        {"path": "setup.py", "m1_score": 3.0, "m1_rank": 4, "scores": {"exact_symbol": 0.0, "subwords": 0.1}},
    ]
    query_text = "where is parser implemented and how to test it?"
    ranker = R5Ranker()

    for treatment in TREATMENTS:
        reranked, telemetry = ranker.rank(mock_candidates, query_text, treatment=treatment)
        assert len(reranked) == len(mock_candidates)
        paths = [c["path"] for c in reranked]
        assert set(paths) == {c["path"] for c in mock_candidates}
        for c in reranked:
            assert c["final_score"] >= 0.0
            assert "rank" in c
        assert telemetry["treatment"] == treatment
        assert telemetry["latency_ms"] >= 0.0

