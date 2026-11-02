"""
Automated unit and integration regression tests for Phase R3.
Covers:
1. IdentifierTokenizer (CamelCase, snake_case, qualified names, backticks).
2. ASTIntentClassifier (test, implementation, definition, reference, general).
3. ASTSymbolMatcher (intent-conditioned asymmetric boosts).
4. BM25 Variants (Okapi, BM25L, BM25+, FieldWeightedBM25).
5. R3Ranker pipeline across Treatments A through I.
"""
import os
import sys
import pytest

# Ensure r3/src and r2/src are on python path
r3_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "research", "v1_accuracy", "ranking_0_80", "r3", "src"))
r2_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "research", "v1_accuracy", "ranking_0_80", "r2", "src"))
for p in [r3_src, r2_src]:
    if p not in sys.path:
        sys.path.insert(0, p)

from ast_symbol import IdentifierTokenizer, ASTIntentClassifier, ASTSymbolMatcher
from bm25_variants import BM25Okapi, BM25L, BM25Plus, FieldWeightedBM25
from ranker_r3 import R3Ranker, TREATMENTS


def test_identifier_tokenizer_camel_and_snake():
    # CamelCase
    subwords = IdentifierTokenizer.split_identifier("SecureCookieSessionInterface")
    assert subwords == ["secure", "cookie", "session", "interface"]

    # snake_case
    subwords_snake = IdentifierTokenizer.split_identifier("parse_query_args_v2")
    assert "parse" in subwords_snake
    assert "query" in subwords_snake
    assert "args" in subwords_snake


def test_identifier_tokenizer_extraction():
    text = "Please check `SessionManager` in module os.path.join and handle invalid_token_error."
    symbols = IdentifierTokenizer.extract_symbols(text)
    assert "SessionManager" in symbols["backticked"]
    assert "os.path.join" in symbols["qualified"]
    assert "session" in symbols["subwords"]
    assert "manager" in symbols["subwords"]


def test_ast_intent_classifier():
    # Test seeking
    assert ASTIntentClassifier.classify("where is the unit test for parser?", test_prob=0.85) == "test_seeking"

    # Implementation seeking (Traceback)
    trace_query = '{"command": "go test ./cache", "failure_excerpt": "FAIL go.etcd.io/etcd/cache/v3 [build failed]"}'
    assert ASTIntentClassifier.classify(trace_query, test_prob=0.0) == "implementation_seeking"

    # Definition seeking
    def_query = "Where is class DatabaseRouter defined in django/db?"
    assert ASTIntentClassifier.classify(def_query, test_prob=0.0) == "definition_seeking"

    # Reference seeking
    ref_query = '{"anchor_diff": "@@ -1,5 +1,6 @@\\n- old_call()\\n+ new_call()"}'
    assert ASTIntentClassifier.classify(ref_query, test_prob=0.0) == "reference_seeking"

    # General search
    gen_query = "Optimize memory allocation during streaming compression"
    assert ASTIntentClassifier.classify(gen_query, test_prob=0.0) == "general_search"


def test_ast_symbol_matcher():
    matcher = ASTSymbolMatcher(def_boost=1.0, impl_boost=0.5, trace_test_penalty=0.05)

    # In implementation seeking: test file demoted, implementation file with symbol boosted
    test_mult = matcher.score_candidate("tests/core_test.py", exact_symbol_score=5.0, is_test_path=True, intent="implementation_seeking")
    assert test_mult == 0.05

    impl_mult = matcher.score_candidate("src/core.py", exact_symbol_score=5.0, is_test_path=False, intent="implementation_seeking")
    assert impl_mult > 1.0

    # In definition seeking: implementation file with symbol boosted
    def_mult = matcher.score_candidate("src/router.py", exact_symbol_score=10.0, is_test_path=False, intent="definition_seeking")
    assert def_mult > 1.5


def test_bm25_variants_length_normalization():
    # Synthetic docs: one short, one long
    docs = [
        ["token", "token", "foo", "bar"], # len = 4
        ["token", "token"] + [f"noise_{i}" for i in range(98)], # len = 100
    ]

    okapi = BM25Okapi().fit(docs)
    bm25l = BM25L(delta=0.5).fit(docs)
    bm25plus = BM25Plus(delta=0.5).fit(docs)

    scores_okapi = okapi.score(["token"])
    scores_bm25l = bm25l.score(["token"])
    scores_bm25plus = bm25plus.score(["token"])

    # For both docs, term frequency is 2. The long doc is penalized by Okapi.
    # BM25L and BM25+ should give higher score to the long doc than Okapi.
    assert scores_bm25l[1] > scores_okapi[1]
    assert scores_bm25plus[1] > scores_okapi[1]


def test_field_weighted_bm25():
    fields = {
        "filepath": [["src", "router", "py"], ["tests", "test_router", "py"]],
        "body": [["class", "router", "logic"], ["def", "test_router", "assert"]],
    }
    fw_bm25 = FieldWeightedBM25(field_weights={"filepath": 2.0, "body": 1.0}).fit(fields)
    scores = fw_bm25.score(["router"])
    assert len(scores) == 2
    assert scores[0] > 0.0


def test_ranker_r3_all_treatments_and_pool_preservation():
    ranker = R3Ranker()
    candidates = [
        {"path": "src/seed.py", "m1_score": 10.0, "m1_rank": 1, "scores": {"exact_symbol": 2.0, "field_bm25": 100.0}},
        {"path": "src/engine.py", "m1_score": 8.0, "m1_rank": 2, "scores": {"exact_symbol": 5.0, "field_bm25": 120.0}},
        {"path": "tests/test_engine.py", "m1_score": 7.0, "m1_rank": 3, "scores": {"exact_symbol": 0.5, "field_bm25": 90.0}},
    ]
    query = '{"changed_file": "src/seed.py", "pr_body": "fix engine bug"}'

    for t_code in ["A", "B", "C", "D", "E", "F", "G", "H", "I"]:
        reranked, telemetry = ranker.rank(candidates, query, treatment=t_code)
        assert len(reranked) == len(candidates), f"Treatment {t_code} dropped candidates!"
        assert telemetry["treatment"] == t_code
        # In treatments with SFS, seed should be demoted from rank 1
        if TREATMENTS[t_code]["sfs"]:
            assert reranked[0]["path"] != "src/seed.py"

