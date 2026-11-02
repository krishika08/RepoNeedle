"""
BM25 Variants Implementation and Controlled Length Normalization Suite.
Implements:
1. Standard BM25 (Okapi)
2. BM25L (Lv & Zhai, 2011: Lower-bounding term frequency normalization)
3. BM25+ (Lv & Zhai, 2011: Additive lower-bound correction)
4. FieldWeightedBM25 (Multi-field code retrieval engine)
"""
import math
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict, Counter
import numpy as np


class BM25Base:
    """Base class for BM25 term weighting variants."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.num_docs: int = 0
        self.avg_doc_len: float = 0.0
        self.doc_lengths: np.ndarray = np.array([], dtype=np.float32)
        self.idf: Dict[str, float] = {}
        self.inverted_index: Dict[str, List[Tuple[int, float]]] = defaultdict(list)

    def _compute_idf(self, doc_freqs: Dict[str, int]) -> Dict[str, float]:
        """Computes Robertson-Sparck Jones smoothed IDF."""
        idf_dict = {}
        for term, df in doc_freqs.items():
            # Standard smoothed Robertson IDF: ln((N - n + 0.5) / (n + 0.5) + 1.0)
            val = math.log(1.0 + (self.num_docs - df + 0.5) / (df + 0.5))
            idf_dict[term] = max(0.0, val)
        return idf_dict


class BM25Okapi(BM25Base):
    """
    Standard BM25Okapi.
    Formula:
        Score = sum_t IDF(t) * (f * (k1 + 1)) / (f + k1 * (1 - b + b * (|d| / avgdl)))
    """

    def fit(self, tokenized_docs: List[List[str]]) -> "BM25Okapi":
        self.num_docs = len(tokenized_docs)
        self.inverted_index.clear()
        self.idf.clear()

        if self.num_docs == 0:
            self.avg_doc_len = 0.0
            self.doc_lengths = np.array([], dtype=np.float32)
            return self

        lengths = [len(d) for d in tokenized_docs]
        self.doc_lengths = np.array(lengths, dtype=np.float32)
        self.avg_doc_len = float(np.mean(self.doc_lengths)) if self.num_docs > 0 else 1.0

        doc_freqs: Dict[str, int] = defaultdict(int)
        for doc_idx, tokens in enumerate(tokenized_docs):
            counts = Counter(tokens)
            for t, count in counts.items():
                doc_freqs[t] += 1
                self.inverted_index[t].append((doc_idx, float(count)))

        self.idf = self._compute_idf(doc_freqs)
        return self

    def score(self, query_tokens: List[str]) -> np.ndarray:
        scores = np.zeros(self.num_docs, dtype=np.float32)
        if self.num_docs == 0 or self.avg_doc_len == 0.0:
            return scores

        q_counts = Counter(query_tokens)
        k1_plus_1 = self.k1 + 1.0
        # Normalization factor: k1 * (1 - b + b * (|d| / avgdl))
        doc_norms = self.k1 * (1.0 - self.b + self.b * (self.doc_lengths / self.avg_doc_len))

        for term, qtf in q_counts.items():
            if term not in self.inverted_index:
                continue
            idf_val = self.idf.get(term, 0.0)
            if idf_val <= 0:
                continue

            for doc_idx, tf in self.inverted_index[term]:
                scores[doc_idx] += idf_val * (tf * k1_plus_1) / (tf + doc_norms[doc_idx])

        return scores


class BM25L(BM25Base):
    """
    BM25L (Lv & Zhai, 2011).
    Corrects BM25Okapi's excessive long-document penalization by shifting normalized term frequency
    with a positive parameter delta (default delta = 0.5):
        c'(t, d) = f(t, d) / (1 - b + b * (|d| / avgdl))
        Score = sum_t IDF(t) * ((k1 + 1) * (c' + delta)) / (k1 + c' + delta)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75, delta: float = 0.5):
        super().__init__(k1=k1, b=b)
        self.delta = delta

    def fit(self, tokenized_docs: List[List[str]]) -> "BM25L":
        self.num_docs = len(tokenized_docs)
        self.inverted_index.clear()
        self.idf.clear()

        if self.num_docs == 0:
            self.avg_doc_len = 0.0
            self.doc_lengths = np.array([], dtype=np.float32)
            return self

        lengths = [len(d) for d in tokenized_docs]
        self.doc_lengths = np.array(lengths, dtype=np.float32)
        self.avg_doc_len = float(np.mean(self.doc_lengths)) if self.num_docs > 0 else 1.0

        doc_freqs: Dict[str, int] = defaultdict(int)
        for doc_idx, tokens in enumerate(tokenized_docs):
            counts = Counter(tokens)
            for t, count in counts.items():
                doc_freqs[t] += 1
                self.inverted_index[t].append((doc_idx, float(count)))

        self.idf = self._compute_idf(doc_freqs)
        return self

    def score(self, query_tokens: List[str]) -> np.ndarray:
        scores = np.zeros(self.num_docs, dtype=np.float32)
        if self.num_docs == 0 or self.avg_doc_len == 0.0:
            return scores

        q_counts = Counter(query_tokens)
        k1_plus_1 = self.k1 + 1.0
        # Length normalization factor per doc: 1 - b + b * (|d| / avgdl)
        b_norm = (1.0 - self.b + self.b * (self.doc_lengths / self.avg_doc_len))

        for term, qtf in q_counts.items():
            if term not in self.inverted_index:
                continue
            idf_val = self.idf.get(term, 0.0)
            if idf_val <= 0:
                continue

            for doc_idx, tf in self.inverted_index[term]:
                c_prime = tf / b_norm[doc_idx]
                shifted = c_prime + self.delta
                scores[doc_idx] += idf_val * (k1_plus_1 * shifted) / (self.k1 + shifted)

        return scores


class BM25Plus(BM25Base):
    """
    BM25+ (Lv & Zhai, 2011).
    Adds an additive lower bound delta > 0 to the term weight for matched terms:
        Score = sum_t IDF(t) * [ (f * (k1 + 1)) / (f + k1 * (1 - b + b * (|d| / avgdl))) + delta ]
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75, delta: float = 0.5):
        super().__init__(k1=k1, b=b)
        self.delta = delta

    def fit(self, tokenized_docs: List[List[str]]) -> "BM25Plus":
        self.num_docs = len(tokenized_docs)
        self.inverted_index.clear()
        self.idf.clear()

        if self.num_docs == 0:
            self.avg_doc_len = 0.0
            self.doc_lengths = np.array([], dtype=np.float32)
            return self

        lengths = [len(d) for d in tokenized_docs]
        self.doc_lengths = np.array(lengths, dtype=np.float32)
        self.avg_doc_len = float(np.mean(self.doc_lengths)) if self.num_docs > 0 else 1.0

        doc_freqs: Dict[str, int] = defaultdict(int)
        for doc_idx, tokens in enumerate(tokenized_docs):
            counts = Counter(tokens)
            for t, count in counts.items():
                doc_freqs[t] += 1
                self.inverted_index[t].append((doc_idx, float(count)))

        self.idf = self._compute_idf(doc_freqs)
        return self

    def score(self, query_tokens: List[str]) -> np.ndarray:
        scores = np.zeros(self.num_docs, dtype=np.float32)
        if self.num_docs == 0 or self.avg_doc_len == 0.0:
            return scores

        q_counts = Counter(query_tokens)
        k1_plus_1 = self.k1 + 1.0
        doc_norms = self.k1 * (1.0 - self.b + self.b * (self.doc_lengths / self.avg_doc_len))

        for term, qtf in q_counts.items():
            if term not in self.inverted_index:
                continue
            idf_val = self.idf.get(term, 0.0)
            if idf_val <= 0:
                continue

            for doc_idx, tf in self.inverted_index[term]:
                okapi_part = (tf * k1_plus_1) / (tf + doc_norms[doc_idx])
                scores[doc_idx] += idf_val * (okapi_part + self.delta)

        return scores


class FieldWeightedBM25:
    """
    Field-weighted BM25 supporting configurable weights per code field:
    filepath, symbol_names, signatures, comments, body.
    """

    def __init__(
        self,
        variant: str = "bm25l",
        k1: float = 1.5,
        b: float = 0.75,
        delta: float = 0.5,
        field_weights: Optional[Dict[str, float]] = None,
    ):
        self.variant = variant.lower()
        self.k1 = k1
        self.b = b
        self.delta = delta
        self.field_weights = field_weights or {
            "filepath": 2.5,
            "symbol_names": 3.0,
            "signatures": 2.0,
            "comments": 1.0,
            "body": 1.0,
        }
        self.indices: Dict[str, BM25Base] = {}

    def _create_variant_index(self) -> BM25Base:
        if self.variant == "bm25l":
            return BM25L(k1=self.k1, b=self.b, delta=self.delta)
        elif self.variant == "bm25+":
            return BM25Plus(k1=self.k1, b=self.b, delta=self.delta)
        else:
            return BM25Okapi(k1=self.k1, b=self.b)

    def fit(self, field_tokens_by_field: Dict[str, List[List[str]]]) -> "FieldWeightedBM25":
        self.indices.clear()
        for field, tokens_list in field_tokens_by_field.items():
            idx = self._create_variant_index()
            idx.fit(tokens_list)
            self.indices[field] = idx
        return self

    def score(self, query_tokens: List[str]) -> np.ndarray:
        if not self.indices:
            return np.array([], dtype=np.float32)

        first_idx = next(iter(self.indices.values()))
        total_scores = np.zeros(first_idx.num_docs, dtype=np.float32)

        for field, weight in self.field_weights.items():
            if field in self.indices and weight > 0.0:
                f_score = self.indices[field].score(query_tokens)
                total_scores += weight * f_score

        return total_scores


def profile_length_bias():
    """
    Profiles how BM25Okapi, BM25L, and BM25+ behave as document length varies
    from 10 tokens to 10,000 tokens for constant term occurrence (tf = 2).
    """
    lengths = [10, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
    avg_len = 500.0

    # Synthetic document corpus with varying length
    docs = []
    for l in lengths:
        doc = ["needle", "needle"] + [f"word_{i}" for i in range(l - 2)]
        docs.append(doc)

    okapi = BM25Okapi(k1=1.5, b=0.75).fit(docs)
    bm25l = BM25L(k1=1.5, b=0.75, delta=0.5).fit(docs)
    bm25plus = BM25Plus(k1=1.5, b=0.75, delta=0.5).fit(docs)

    scores_okapi = okapi.score(["needle"])
    scores_bm25l = bm25l.score(["needle"])
    scores_bm25plus = bm25plus.score(["needle"])

    results = []
    for idx, l in enumerate(lengths):
        results.append({
            "length": l,
            "len_ratio": l / avg_len,
            "okapi": float(scores_okapi[idx]),
            "bm25l": float(scores_bm25l[idx]),
            "bm25plus": float(scores_bm25plus[idx]),
        })
    return results


if __name__ == "__main__":
    profile = profile_length_bias()
    print("=== Controlled Length Bias Profile (tf = 2, avgdl = 500) ===")
    print(f"{'Length':<8} | {'Ratio':<6} | {'BM25Okapi':<10} | {'BM25L':<10} | {'BM25+':<10} | {'Okapi Drop':<10}")
    print("-" * 65)
    base_okapi = profile[0]["okapi"]
    for r in profile:
        drop = ((base_okapi - r["okapi"]) / base_okapi) * 100.0 if base_okapi > 0 else 0.0
        print(f"{r['length']:<8} | {r['len_ratio']:<6.2f} | {r['okapi']:<10.4f} | {r['bm25l']:<10.4f} | {r['bm25plus']:<10.4f} | {drop:<10.1f}%")

