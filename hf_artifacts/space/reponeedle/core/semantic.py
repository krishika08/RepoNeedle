"""
Subword and semantic vector similarity index for code repositories.
Operates completely offline with zero network dependency using vectorized n-gram and term embeddings.

V2 Stage 3 (exact high-performance reconstruction): ``fit()`` recomputes the whole index on every call, exactly as
the Stage 2 implementation did (``tests/reference_stage2_semantic.py`` is a verbatim copy, and the tests compare
every structure with it bit for bit), but in a single pass over the documents' ordered feature counts followed by
array operations instead of per-pair Python loops. Per-document feature extraction lives in ``semantic_features``.
"""

import math
import sys
import time
import warnings
from itertools import count
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import sparse

from reponeedle.core import semantic_features
from reponeedle.core.semantic_features import FEATURES_SIGNATURE_VERSION  # noqa: F401  (re-exported)
from reponeedle.models import FileDoc

__all__ = ["SubwordSemanticIndex", "FEATURES_SIGNATURE_VERSION", "product_rule", "PRODUCT_FLOAT32",
           "PRODUCT_FLOAT64_THEN_FLOAT32", "PRODUCT_SCALAR"]

# How each matrix value ``tf * idf[c]`` (a Python float times a numpy float32 scalar) is evaluated, as observed for
# the expression itself on every fit: numpy >= 2 (NEP 50) and numpy 1.x with weak promotion return float32; numpy
# 1.x with legacy promotion returns float64, which the CSR constructor then rounds to float32.
PRODUCT_FLOAT32 = "float32"
PRODUCT_FLOAT64_THEN_FLOAT32 = "float64_then_float32"
PRODUCT_SCALAR = "scalar"          # an unrecognised result type: the Stage 2 per-value loop is used instead
SELF_CHECK_SAMPLES = 64
DENSE_TF_TABLE_LIMIT = 1 << 24     # largest count served by a dense TF lookup table (else np.unique)


def shared_feature_counts(counts: Dict[str, int]) -> Dict[str, int]:
    """
    The same counts (same keys, values and insertion order) with every feature string interned, so a feature that
    occurs in many documents is stored once instead of once per document (V2 Stage 4). Per-document feature caches
    dominate the retained memory of a built engine; without this, each (document, feature) pair holds its own string
    object. Applied to extracted counts (``fit``) and to counts decoded from the persistent cache (``store``).
    """
    return dict(zip(map(sys.intern, counts), counts.values()))


def product_rule() -> str:
    """The result type of the expression the matrix values use, evaluated now (promotion can change at runtime)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        probe = 1.0 * np.float32(1.0)
    if type(probe) is np.float32:
        return PRODUCT_FLOAT32
    if type(probe) is np.float64:
        return PRODUCT_FLOAT64_THEN_FLOAT32
    return PRODUCT_SCALAR


class SubwordSemanticIndex:
    """
    Subword character n-gram and semantic term similarity index.
    Constructs high-dimensional subword feature representations to bridge lexical vocabulary mismatches,
    abbreviations, and morphological variations in code identifiers and task descriptions.
    """

    # Per-document extraction (fingerprinted for persisted artifacts as ``semantic_features``), bound directly.
    _extract_features = semantic_features.extract_features
    _feature_text = staticmethod(semantic_features.feature_text)
    doc_signature = semantic_features.doc_signature
    _count_features = semantic_features.count_features

    def __init__(
        self,
        min_n: int = 3,
        max_n: int = 5,
        max_features: int = 15000,
    ):
        self.min_n = min_n
        self.max_n = max_n
        self.max_features = max_features
        self.tokenizer = semantic_features.new_tokenizer()

        self.vocabulary: Dict[str, int] = {}
        self.idf: np.ndarray = np.array([], dtype=np.float32)
        self.doc_matrix: sparse.csr_matrix = sparse.csr_matrix((0, 0), dtype=np.float32)
        self.num_docs: int = 0
        self.doc_paths: List[str] = []
        self._query_cache: Dict[str, Optional[sparse.csr_matrix]] = {}
        self._doc_feature_cache: Dict[str, Tuple[str, Dict[str, int]]] = {}
        # Diagnostics of the last fit only (not index state: never read by scoring or compared for equivalence).
        self.fit_stats: Dict[str, Any] = {}
        self._fits = 0

    def fit(self, docs: List[FileDoc]) -> "SubwordSemanticIndex":
        """
        Fits semantic index on repository documents.

        The result is identical to the Stage 2 algorithm: document frequencies in first-seen order (documents in
        the given order, each document's features in first-occurrence order), the top ``max_features`` features
        by (document frequency, feature length) descending with ties in first-seen order, smooth IDF
        ``ln((1 + N) / (1 + df)) + 1`` stored as float32, sublinear TF ``1 + ln(tf)``, and L2-normalised rows.
        """
        t_start = time.perf_counter()
        self._query_cache.clear()
        previous = set(self.vocabulary) if self._fits else None
        self._fits += 1
        self.num_docs = len(docs)
        self.doc_paths = [d.path for d in docs]
        stats: Dict[str, Any] = {"documents": self.num_docs, "feature_cache_hits": 0, "feature_cache_misses": 0,
                                 "documents_reextracted": 0, "document_feature_pairs": 0, "distinct_features": 0,
                                 "vocabulary_size": 0, "matrix_nnz": 0, "idf_entries_computed": 0,
                                 "product_rule": None, "product_self_check_values": 0,
                                 "vocabulary_added": None, "vocabulary_removed": None}
        timings = {"feature_collection_ms": 0.0, "feature_counting_ms": 0.0, "vocabulary_selection_ms": 0.0,
                   "idf_ms": 0.0, "matrix_assembly_ms": 0.0, "normalisation_ms": 0.0}
        try:
            if self.num_docs == 0:
                # Same derived state as a never-fitted index: nothing from an earlier fit may survive.
                self.vocabulary = {}
                self.idf = np.array([], dtype=np.float32)
                self.doc_matrix = sparse.csr_matrix((0, 0), dtype=np.float32)
                return self
            self._fit_documents(docs, stats, timings)
            return self
        finally:
            if previous is not None:
                stats["vocabulary_added"] = sum(1 for f in self.vocabulary if f not in previous)
                stats["vocabulary_removed"] = sum(1 for f in previous if f not in self.vocabulary)
            stats.update({k: round(v * 1000, 3) for k, v in timings.items()})
            stats["fit_ms"] = round((time.perf_counter() - t_start) * 1000, 3)
            self.fit_stats = stats

    def _fit_documents(self, docs: List[FileDoc], stats: Dict[str, Any], timings: Dict[str, float]) -> None:
        # 1. Per-document feature counts: the signature-validated cache, else extraction.
        t = time.perf_counter()
        doc_feat_counts: List[Dict[str, int]] = []
        cache = self._doc_feature_cache
        for doc in docs:
            cache_key = doc.path
            content_sig = self.doc_signature(doc)
            cached = cache.get(cache_key)
            if cached is not None and cached[0] == content_sig:
                counts = cached[1]
                stats["feature_cache_hits"] += 1
            else:
                counts = self.shared_feature_counts(self._count_features(doc))
                cache[cache_key] = (content_sig, counts)
                stats["feature_cache_misses"] += 1
            doc_feat_counts.append(counts)
        stats["documents_reextracted"] = stats["feature_cache_misses"]
        timings["feature_collection_ms"] = time.perf_counter() - t

        # 2. One pass over every (document, feature) pair, in document order and each document's insertion order.
        # ``first_ticket.setdefault(feature, ticket)`` records, for a feature's FIRST occurrence, the running pair
        # number at that moment; every later occurrence returns that same number. Features' insertion order is
        # therefore the Stage 2 ``df_counts`` order, and the recorded numbers increase in that order.
        t = time.perf_counter()
        lengths = np.fromiter(map(len, doc_feat_counts), dtype=np.int64, count=len(doc_feat_counts))
        n_pairs = int(lengths.sum())
        first_ticket: Dict[str, int] = {}
        setdefault = first_ticket.setdefault
        ticket = count()
        pair_ticket = np.empty(n_pairs, dtype=np.int64)
        pair_count = np.empty(n_pairs, dtype=np.int64)
        pos = 0
        for counts in doc_feat_counts:
            n = len(counts)
            pair_ticket[pos:pos + n] = np.fromiter(map(setdefault, counts, ticket), dtype=np.int64, count=n)
            pair_count[pos:pos + n] = np.fromiter(counts.values(), dtype=np.int64, count=n)
            pos += n
        features = list(first_ticket)
        n_features = len(features)
        firsts = np.fromiter(first_ticket.values(), dtype=np.int64, count=n_features)
        del first_ticket
        # Dense feature id = first-seen index: every pair's ticket is exactly its feature's first ticket, and first
        # tickets are distinct pair numbers (< n_pairs), so one gather maps each pair to its feature.
        dense_of_ticket = np.empty(n_pairs, dtype=np.int64)
        dense_of_ticket[firsts] = np.arange(n_features, dtype=np.int64)
        pair_feature = dense_of_ticket[pair_ticket]
        del pair_ticket, firsts, dense_of_ticket
        # A document's counts have each feature once, so pairs per feature = documents containing it.
        df = np.bincount(pair_feature, minlength=n_features).astype(np.int64, copy=False)
        stats.update(document_feature_pairs=n_pairs, distinct_features=n_features)
        timings["feature_counting_ms"] = time.perf_counter() - t

        # 3. Vocabulary: Stage 2 sorts (df, len) descending with a STABLE sort, so ties keep first-seen order.
        # lexsort's last key is the primary key; the first-seen index makes the order total (and the sort stable).
        t = time.perf_counter()
        feat_len = np.fromiter(map(len, features), dtype=np.int64, count=n_features)
        order = np.lexsort((np.arange(n_features, dtype=np.int64), -feat_len, -df))
        selected = order[: self.max_features].tolist()
        self.vocabulary = {features[i]: idx for idx, i in enumerate(selected)}
        num_features = len(self.vocabulary)
        stats["vocabulary_size"] = num_features
        timings["vocabulary_selection_ms"] = time.perf_counter() - t

        if num_features == 0:
            self.doc_matrix = sparse.csr_matrix((self.num_docs, 0), dtype=np.float32)
            self.idf = np.zeros(0, dtype=np.float32)
            return

        # 4. Smooth IDF: ln((1 + N) / (1 + df)) + 1, the same scalar expression per entry, stored as float32.
        t = time.perf_counter()
        idf_vec = np.zeros(num_features, dtype=np.float32)
        df_selected = df[selected].tolist()
        for idx in range(num_features):
            idf_vec[idx] = math.log((1.0 + self.num_docs) / (1.0 + df_selected[idx])) + 1.0
        self.idf = idf_vec
        stats["idf_entries_computed"] = num_features
        timings["idf_ms"] = time.perf_counter() - t

        # 5. Sparse document matrix with sublinear TF 1 + ln(tf), through the same SciPy constructor.
        t = time.perf_counter()
        column_of = np.full(n_features, -1, dtype=np.int64)
        column_of[selected] = np.arange(num_features, dtype=np.int64)
        cols = column_of[pair_feature]
        del pair_feature, column_of
        keep = cols >= 0
        cols = cols[keep]
        rows = np.repeat(np.arange(self.num_docs, dtype=np.int64), lengths)[keep]
        tf_counts = pair_count[keep]
        del keep, pair_count
        data, rule, checked = self._matrix_values(tf_counts, cols, idf_vec)
        stats.update(product_rule=rule, product_self_check_values=checked)
        mat = sparse.csr_matrix(
            (data, (rows, cols)),
            shape=(self.num_docs, num_features),
            dtype=np.float32,
        )
        del data, rows, cols, tf_counts
        stats["matrix_nnz"] = int(mat.nnz)
        timings["matrix_assembly_ms"] = time.perf_counter() - t

        # L2 normalize rows (unchanged)
        t = time.perf_counter()
        row_norms = sparse.linalg.norm(mat, axis=1)
        row_norms[row_norms == 0.0] = 1.0
        mat_norm = mat.multiply(sparse.csr_matrix(1.0 / row_norms[:, np.newaxis]))
        self.doc_matrix = mat_norm.tocsr()
        timings["normalisation_ms"] = time.perf_counter() - t

    shared_feature_counts = staticmethod(shared_feature_counts)

    @staticmethod
    def _tf_values(tf_counts: np.ndarray) -> np.ndarray:
        """``1.0 + math.log(count)`` per pair (float64), evaluated once per distinct count by the same expression."""
        if tf_counts.size == 0:
            return np.zeros(0, dtype=np.float64)
        largest = int(tf_counts.max())
        if largest <= DENSE_TF_TABLE_LIMIT:
            table = np.zeros(largest + 1, dtype=np.float64)
            for c in np.flatnonzero(np.bincount(tf_counts, minlength=largest + 1)).tolist():
                table[c] = 1.0 + math.log(c)
            return table[tf_counts]
        distinct, inverse = np.unique(tf_counts, return_inverse=True)
        table = np.array([1.0 + math.log(int(c)) for c in distinct.tolist()], dtype=np.float64)
        return table[inverse.reshape(-1)]

    @staticmethod
    def _matrix_values(tf_counts: np.ndarray, cols: np.ndarray, idf: np.ndarray) -> Tuple[Any, str, int]:
        """
        The values ``(1.0 + math.log(cnt)) * idf[c]`` of every kept pair, evaluated exactly as the Stage 2 scalar
        expression is in this numpy (see ``product_rule``). TF values come from the same ``math.log`` expression,
        once per distinct count. A sample of values is re-evaluated with the scalar expression itself; any
        difference (or an unrecognised promotion rule) falls back to the scalar expression for every value.
        """
        rule = product_rule()
        if rule != PRODUCT_SCALAR:
            tf = SubwordSemanticIndex._tf_values(tf_counts)
            if rule == PRODUCT_FLOAT32:
                data = tf.astype(np.float32) * idf[cols]
            else:
                data = (tf * idf[cols].astype(np.float64)).astype(np.float32)
            n = len(data)
            sample = sorted(set(np.linspace(0, n - 1, num=min(n, SELF_CHECK_SAMPLES), dtype=np.int64).tolist()))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                expected = np.array([(1.0 + math.log(int(tf_counts[i]))) * idf[int(cols[i])] for i in sample],
                                    dtype=np.float32)
            if expected.tobytes() == data[sample].tobytes():
                return data, rule, len(sample)
        # The Stage 2 per-value expression, verbatim.
        values = [(1.0 + math.log(cnt)) * idf[c] for cnt, c in zip(tf_counts.tolist(), cols.tolist())]
        return values, PRODUCT_SCALAR, 0

    def _get_query_vector(self, query: str) -> Optional[sparse.csr_matrix]:
        """
        Extracts features and builds normalized sparse query vector with caching.
        """
        if query in self._query_cache:
            return self._query_cache[query]

        q_feats = self._extract_features(query)
        if not q_feats:
            self._query_cache[query] = None
            return None

        q_counts: Dict[str, int] = {}
        for f in q_feats:
            q_counts[f] = q_counts.get(f, 0) + 1

        # Build query vector
        q_cols, q_data = [], []
        for f, cnt in q_counts.items():
            if f in self.vocabulary:
                c_idx = self.vocabulary[f]
                tf = 1.0 + math.log(cnt)
                val = tf * self.idf[c_idx]
                q_cols.append(c_idx)
                q_data.append(val)

        if not q_cols:
            self._query_cache[query] = None
            return None

        q_vec = sparse.csr_matrix(
            (q_data, ([0] * len(q_cols), q_cols)),
            shape=(1, len(self.vocabulary)),
            dtype=np.float32,
        )
        q_norm = sparse.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec.multiply(1.0 / q_norm)

        # LRU eviction if cache exceeds 512 entries
        if len(self._query_cache) >= 512:
            self._query_cache.pop(next(iter(self._query_cache)))
        self._query_cache[query] = q_vec
        return q_vec

    def score(
        self,
        query: str,
        candidate_indices: Optional[Sequence[int]] = None,
    ) -> np.ndarray:
        """
        Computes cosine similarity between query and documents.
        Supports candidate_indices to evaluate sparse cascaded candidate subsets.
        Returns a float array of length num_docs in [0, 1].
        """
        if self.num_docs == 0 or len(self.vocabulary) == 0:
            return np.zeros(self.num_docs, dtype=np.float32)

        q_vec = self._get_query_vector(query)
        if q_vec is None:
            return np.zeros(self.num_docs, dtype=np.float32)

        if candidate_indices is not None:
            cand_list = list(candidate_indices) if not isinstance(candidate_indices, list) else candidate_indices
            if not cand_list:
                return np.zeros(self.num_docs, dtype=np.float32)
            sub_matrix = self.doc_matrix[cand_list]
            cand_scores = sub_matrix.dot(q_vec.T).toarray().flatten()
            scores = np.zeros(self.num_docs, dtype=np.float32)
            scores[cand_list] = np.clip(cand_scores, 0.0, 1.0)
            return scores

        # Dot product with normalized document matrix yields cosine similarities across all docs
        scores = self.doc_matrix.dot(q_vec.T).toarray().flatten()
        scores = np.clip(scores, 0.0, 1.0)
        return scores
