"""
V2 Stage 3: numerical exactness of the single-pass semantic fit.

- the matrix values equal the Stage 2 scalar expression ``(1.0 + math.log(cnt)) * idf[c]`` after float32
  conversion for EVERY stored value, in whatever promotion mode this numpy uses (the CI matrix runs numpy 1.24.4 /
  SciPy 1.10.1 with ``NPY_PROMOTION_STATE`` legacy and weak, and numpy 2.x);
- the pre-normalised matrix handed to ``scipy.sparse.linalg.norm`` is exactly the reference's;
- a wrong or unknown promotion rule is caught by the per-fit self-check and falls back to the scalar expression;
- index dtypes are the ones SciPy selects for the reference;
- boundary configurations (no documents, no features, ``max_features`` 0 and 1, all features tied, documents without
  features, repeated features) are identical to the reference.
"""

import math
import os

import numpy as np
import pytest
import scipy.sparse.linalg as sparse_linalg

from reponeedle.core import semantic
from reponeedle.core.semantic import SubwordSemanticIndex
from stage3_support import (QUERY_TEXTS, ReferenceSemanticIndex, assert_semantic_equal, doc, fit_both,
                            fixture_docs, is_float32_product, random_corpus, tie_corpus)

FIXTURE = fixture_docs()


def _scalar_values(sem):
    """The Stage 2 expression for every kept (document, feature) pair, in the Stage 2 triplet order."""
    out = []
    for d in sem.doc_paths:
        counts = sem._doc_feature_cache[d][1]
        for f, cnt in counts.items():
            if f in sem.vocabulary:
                out.append(((1.0 + math.log(cnt)) * sem.idf[sem.vocabulary[f]], sem.vocabulary[f]))
    return out


def test_detected_product_rule_is_what_the_expression_returns():
    rule = semantic.product_rule()
    assert rule == (semantic.PRODUCT_FLOAT32 if is_float32_product() else semantic.PRODUCT_FLOAT64_THEN_FLOAT32)
    expected = os.environ.get("REPONEEDLE_EXPECT_PRODUCT_RULE")      # set by the CI compatibility jobs
    if expected:
        assert rule == expected, (rule, expected, np.__version__, os.environ.get("NPY_PROMOTION_STATE"))


@pytest.mark.parametrize("corpus", ["fixture", "random", "ties"])
def test_every_matrix_value_equals_the_scalar_expression(corpus):
    docs = {"fixture": FIXTURE, "random": random_corpus(5, 60), "ties": tie_corpus()}[corpus]
    captured = []
    real = sparse_linalg.norm

    def spy(mat, *a, **k):
        captured.append(mat.copy())
        return real(mat, *a, **k)

    sem = SubwordSemanticIndex()
    try:
        sparse_linalg.norm = spy
        sem.fit(docs)
    finally:
        sparse_linalg.norm = real
    pre = captured[0]
    scalar = _scalar_values(sem)
    expected = np.array([v for v, _ in scalar], dtype=np.float32)
    # The pre-normalised matrix is in canonical (row, column) order; reorder the scalar values the same way.
    rows = np.repeat(np.arange(sem.num_docs), [sum(1 for f in sem._doc_feature_cache[p][1] if f in sem.vocabulary)
                                               for p in sem.doc_paths])
    cols = np.array([c for _, c in scalar], dtype=np.int64)
    order = np.lexsort((cols, rows))
    assert pre.data.tobytes() == expected[order].tobytes(), "a matrix value differs from the scalar expression"
    distinct_tf = {cnt for p in sem.doc_paths for cnt in sem._doc_feature_cache[p][1].values()}
    if corpus != "ties":           # the tie corpus has three TF values by construction
        assert len(distinct_tf) > 10, "the corpus should exercise many TF values"
    assert sem.fit_stats["product_rule"] == semantic.product_rule()
    assert sem.fit_stats["product_self_check_values"] > 0


@pytest.mark.parametrize("corpus", ["fixture", "random", "ties"])
def test_pre_normalised_matrix_equals_the_reference(corpus):
    docs = {"fixture": FIXTURE, "random": random_corpus(6, 50), "ties": tie_corpus()}[corpus]
    captured = {}
    real = sparse_linalg.norm

    def spy_for(name):
        def spy(mat, *a, **k):
            captured.setdefault(name, mat.copy())
            return real(mat, *a, **k)
        return spy

    try:
        sparse_linalg.norm = spy_for("optimised")
        SubwordSemanticIndex().fit(docs)
        sparse_linalg.norm = spy_for("reference")
        ReferenceSemanticIndex().fit(docs)
    finally:
        sparse_linalg.norm = real
    a, b = captured["optimised"], captured["reference"]
    assert a.format == b.format and a.shape == b.shape and a.dtype == b.dtype
    for k in ("indptr", "indices", "data"):
        x, y = getattr(a, k), getattr(b, k)
        assert x.dtype == y.dtype and x.tobytes() == y.tobytes(), k


@pytest.mark.parametrize("wrong", [semantic.PRODUCT_FLOAT32, semantic.PRODUCT_FLOAT64_THEN_FLOAT32,
                                   semantic.PRODUCT_SCALAR])
def test_a_wrong_or_unknown_rule_falls_back_to_the_scalar_expression(monkeypatch, wrong):
    """The two vectorised rules differ on thousands of values; the self-check must catch the wrong one."""
    actual = semantic.product_rule()
    monkeypatch.setattr(semantic, "product_rule", lambda: wrong)
    optimised, reference = fit_both(FIXTURE)
    assert_semantic_equal(optimised, reference, f"forced rule {wrong}", queries=QUERY_TEXTS[::20])
    if wrong == actual:
        assert optimised.fit_stats["product_rule"] == actual
    else:
        assert optimised.fit_stats["product_rule"] == semantic.PRODUCT_SCALAR
        assert optimised.fit_stats["product_self_check_values"] == 0


@pytest.mark.parametrize("limit", [0, 1, 7])
def test_tf_values_without_the_dense_table_equal_the_reference(monkeypatch, limit):
    """Counts above DENSE_TF_TABLE_LIMIT use np.unique instead of the dense table: the same values."""
    monkeypatch.setattr(semantic, "DENSE_TF_TABLE_LIMIT", limit)
    optimised, reference = fit_both(FIXTURE + [doc("rep.py", "repeated " * 40 + "once")])
    assert_semantic_equal(optimised, reference, f"dense TF table limit {limit}", queries=QUERY_TEXTS[::20])
    counts = np.array([1, 2, 3, 40, 9, 1, 40], dtype=np.int64)
    expected = np.array([1.0 + math.log(c) for c in counts.tolist()], dtype=np.float64)
    assert SubwordSemanticIndex._tf_values(counts).tobytes() == expected.tobytes()


def test_the_two_vectorised_rules_really_differ_on_this_corpus():
    """Guards the self-check test above: on this corpus the rules are not accidentally interchangeable."""
    sem = SubwordSemanticIndex().fit(FIXTURE)
    tf = []
    cols = []
    for p in sem.doc_paths:
        for f, cnt in sem._doc_feature_cache[p][1].items():
            if f in sem.vocabulary:
                tf.append(1.0 + math.log(cnt))
                cols.append(sem.vocabulary[f])
    tf = np.array(tf)
    idf = sem.idf[np.array(cols)]
    weak = tf.astype(np.float32) * idf
    legacy = (tf * idf.astype(np.float64)).astype(np.float32)
    assert (weak != legacy).any()


def test_index_dtypes_are_the_ones_scipy_selects_for_the_reference():
    optimised, reference = fit_both(FIXTURE)
    for k in ("indptr", "indices"):
        assert getattr(optimised.doc_matrix, k).dtype == getattr(reference.doc_matrix, k).dtype == np.int32
    assert optimised.idf.dtype == np.float32
    # The normalised matrix's dtype is whatever SciPy's row norm returns (float64 in recent SciPy, float32 in
    # SciPy 1.10): the same operations as Stage 2, so the same dtype as the reference.
    assert optimised.doc_matrix.data.dtype == reference.doc_matrix.data.dtype


BOUNDARIES = {
    "no documents": ([], {}),
    "max_features=0": (FIXTURE, {"max_features": 0}),
    "max_features=1": (FIXTURE, {"max_features": 1}),
    "all features tied": (tie_corpus(n_docs=5, n_words=9), {"max_features": 23}),
    "documents without features": ([doc(""), doc(" "), doc("_")], {}),
    "some documents without features": ([doc(""), doc("a.py", "alpha beta"), doc(" ")], {}),
    "features in one document only": ([doc(f"u{i}.py", f"unique{i}word{i} other{i}") for i in range(6)], {}),
    "repeated features": ([doc("r.py", "abc " * 1000), doc("s.py", "abc abc xyz")], {}),
    "max_features larger than the feature count": (FIXTURE[:2], {"max_features": 10 ** 9}),
    "negative max_features (Python slice semantics)": (FIXTURE[:3], {"max_features": -5}),
}


@pytest.mark.parametrize("name", list(BOUNDARIES), ids=list(BOUNDARIES))
def test_boundary_behaviour_equals_the_reference(name):
    docs, config = BOUNDARIES[name]
    optimised, reference = fit_both(docs, **config)
    assert_semantic_equal(optimised, reference, name, queries=QUERY_TEXTS[:20])
    assert optimised.score("alpha").dtype == reference.score("alpha").dtype


def test_documents_without_features_really_have_none():
    sem = SubwordSemanticIndex().fit([doc(""), doc("a.py", "alpha")])
    assert sem._doc_feature_cache[""][1] == {}
    assert sem.fit_stats["document_feature_pairs"] == len(sem._doc_feature_cache["a.py"][1])
