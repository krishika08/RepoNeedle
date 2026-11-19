"""
V2 Stage 3: the semantic index is exactly equivalent to the Stage 2 implementation.

``tests/reference_stage2_semantic.py`` is a verbatim copy of ``reponeedle/core/semantic.py`` at the Stage 2 baseline
(``0b27381``). Every semantic structure of the production index is compared with it, exactly, over corpora built to
stress the vocabulary order and over every ``max_features``/n-gram configuration of interest; then whole engines are
compared with the differential harness on all 225 frozen queries (every ranker, abstention, anchored change impact
and CUD-Pack).
"""

import hashlib
from pathlib import Path

import pytest

from index_equivalence import assert_equivalent, load_queries
from reponeedle.core.semantic import SubwordSemanticIndex
from reponeedle.engine import RepoNeedleEngine
from stage3_support import (CONFIGS, QUERY_TEXTS, ReferenceSemanticIndex, assert_semantic_equal, doc,
                            fit_both, fixture_docs, random_corpus, reference_semantic, tie_corpus)

REFERENCE = Path(__file__).resolve().parent / "reference_stage2_semantic.py"
# SHA-256 of reponeedle/core/semantic.py at 0b273814ba6b31ffa7aa1f13d612057ce0cfa7b9 (LF line endings).
STAGE2_SEMANTIC_SHA256 = "21d9c30bb8cf63e82b39b7008f10cad7de83f09c90ff9bbd811a9428273b2b9d"

FIXTURE = fixture_docs()
CORPORA = {
    "fixture repository": FIXTURE,
    "fixture repository, reversed": FIXTURE[::-1],
    "ties": tie_corpus(),
    "ties, reversed": tie_corpus()[::-1],
    "random seed 1": random_corpus(1),
    "random seed 2": random_corpus(2, n_docs=7),
    "single document": FIXTURE[:1],
    "documents without content": [doc("a"), doc("b/c"), doc("d.py", "", ["x"])],
    "repeated features": [doc("r.py", "token " * 500 + "tok " * 3), doc("s.py", "token")],
}


def test_reference_is_the_verbatim_stage2_module():
    text = REFERENCE.read_bytes().replace(b"\r\n", b"\n")
    body = text[text.index(b'"""\n\n') + 5:]
    assert hashlib.sha256(body).hexdigest() == STAGE2_SEMANTIC_SHA256
    assert b"reponeedle.core.semantic" not in body, "the reference must not import the code under test"
    assert ReferenceSemanticIndex.__module__ == "reference_stage2_semantic"


@pytest.mark.parametrize("config", list(CONFIGS), ids=list(CONFIGS))
@pytest.mark.parametrize("corpus", list(CORPORA), ids=list(CORPORA))
def test_every_semantic_structure_equals_the_reference(corpus, config):
    optimised, reference = fit_both(CORPORA[corpus], **CONFIGS[config])
    assert_semantic_equal(optimised, reference, f"{corpus} / {config}", queries=QUERY_TEXTS[::9])


def test_all_query_score_arrays_equal_the_reference():
    optimised, reference = fit_both(FIXTURE)
    assert_semantic_equal(optimised, reference, "fixture repository, all 225 queries", queries=QUERY_TEXTS)


def test_empty_repository_equals_the_reference():
    optimised, reference = fit_both([])
    assert_semantic_equal(optimised, reference, "empty", queries=QUERY_TEXTS[:5])


def test_repeated_fits_on_one_instance_equal_the_reference():
    """In-place refits reuse the per-document feature cache and must clear the query cache."""
    optimised, reference = SubwordSemanticIndex(), ReferenceSemanticIndex()
    sequence = [FIXTURE, FIXTURE[1:], FIXTURE[::-1], [], tie_corpus(), FIXTURE + random_corpus(4, 5), FIXTURE]
    for step, docs in enumerate(sequence):
        optimised.fit(list(docs))
        reference.fit(list(docs))
        assert_semantic_equal(optimised, reference, f"refit {step}", queries=QUERY_TEXTS[::15])


def test_whole_engine_equals_an_engine_with_the_reference_semantic_index(tmp_path):
    """Complete retrieval equivalence on all 225 queries: every ranker, abstention, change impact, CUD-Pack."""
    from equivalence_fixture import FILES, write_files

    repo = write_files(tmp_path / "repo", FILES)
    engine = RepoNeedleEngine.from_directory(str(repo))
    with reference_semantic():
        reference = RepoNeedleEngine.from_directory(str(repo))
    assert type(reference.semantic_index) is ReferenceSemanticIndex
    assert_equivalent(engine, reference, label="production semantic index vs Stage 2 reference",
                      queries=load_queries(), packing_queries=12)
