"""
Field-weighted BM25Okapi sparse lexical retrieval engine for code repositories.
"""

import math
from typing import List, Dict, Tuple
from collections import defaultdict
import numpy as np

from reponeedle.core.tokenizer import CodeTokenizer
from reponeedle.models import FileDoc


class BM25Index:
    """
    Field-weighted BM25Okapi index tailored for codebases.
    Computes distinct weighted term frequencies for:
    - Path tokens (weight: path_weight)
    - Defined symbol names (weight: symbol_weight)
    - Code body text (weight: body_weight)
    """

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        path_weight: float = 2.5,
        symbol_weight: float = 2.0,
        body_weight: float = 1.0,
        decouple_symbols: bool = True,
    ):
        self.k1 = k1
        self.b = b
        self.path_weight = path_weight
        self.symbol_weight = symbol_weight
        self.body_weight = body_weight
        self.decouple_symbols = decouple_symbols
        
        self.tokenizer = CodeTokenizer()
        self.docs: List[FileDoc] = []
        self.doc_paths: List[str] = []
        self.num_docs: int = 0
        self.avg_doc_len: float = 0.0
        
        # Term statistics
        self.doc_frequencies: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_term_freqs: List[Dict[str, float]] = []
        self.doc_lengths: np.ndarray = np.array([], dtype=np.float32)
        self.inverted_index: Dict[str, List[Tuple[int, float]]] = {}
        self.doc_len_norms: np.ndarray = np.array([], dtype=np.float32)

    def fit(self, docs: List[FileDoc]) -> "BM25Index":
        """
        Indexes a collection of FileDoc objects.
        """
        self.docs = docs
        self.num_docs = len(docs)
        self.doc_paths = [d.path for d in docs]
        self.doc_frequencies = {}
        self.doc_term_freqs = []
        doc_lengths_list: List[float] = []

        if self.num_docs == 0:
            self.avg_doc_len = 0.0
            return self

        for doc in docs:
            # 1. Path tokens
            path_tokens = self.tokenizer.tokenize_path(doc.path)
            
            # 2. Symbol tokens
            symbol_tokens = []
            for s in doc.symbols:
                symbol_tokens.extend(self.tokenizer.tokenize_text(s))
            
            # 3. Content body tokens
            body_tokens = self.tokenizer.tokenize_text(doc.content)

            # Combined term counts with field weights
            weighted_counts: Dict[str, float] = {}
            for t in path_tokens:
                weighted_counts[t] = weighted_counts.get(t, 0.0) + self.path_weight
            for t in symbol_tokens:
                weighted_counts[t] = weighted_counts.get(t, 0.0) + self.symbol_weight
            for t in body_tokens:
                weighted_counts[t] = weighted_counts.get(t, 0.0) + self.body_weight

            effective_len = max(1.0, float(len(body_tokens) + len(path_tokens))) if self.decouple_symbols else sum(weighted_counts.values())
            doc_lengths_list.append(effective_len)
            self.doc_term_freqs.append(weighted_counts)

            # Document frequency
            for term in set(weighted_counts.keys()):
                self.doc_frequencies[term] = self.doc_frequencies.get(term, 0) + 1

        self.doc_lengths = np.array(doc_lengths_list, dtype=np.float32)
        self.avg_doc_len = float(np.mean(self.doc_lengths)) if len(self.doc_lengths) > 0 else 1.0

        # Build inverted postings list: term -> list of (doc_index, tf)
        inverted = defaultdict(list)
        for doc_idx, term_counts in enumerate(self.doc_term_freqs):
            for term, tf in term_counts.items():
                inverted[term].append((doc_idx, tf))
        self.inverted_index = dict(inverted)

        # Precompute document length normalization terms: k1 * (1 - b + b * (doc_len / avg_dl))
        if self.avg_doc_len > 0:
            self.doc_len_norms = self.k1 * (1.0 - self.b + self.b * (self.doc_lengths / self.avg_doc_len))
        else:
            self.doc_len_norms = np.ones(self.num_docs, dtype=np.float32) * self.k1

        # Precompute Robertson-Sparck Jones IDF with smoothing
        # IDF(q) = ln((N - n + 0.5) / (n + 0.5) + 1.0)
        self.idf = {}
        for term, df in self.doc_frequencies.items():
            idf_val = math.log((self.num_docs - df + 0.5) / (df + 0.5) + 1.0)
            self.idf[term] = max(0.0, idf_val)

        return self

    def score(self, query: str) -> np.ndarray:
        """
        Scores all indexed documents against the input query string.
        Returns an array of floats of length num_docs.
        """
        if self.num_docs == 0:
            return np.array([], dtype=np.float32)

        q_tokens = self.tokenizer.tokenize_text(query)
        scores = np.zeros(self.num_docs, dtype=np.float32)
        if not q_tokens:
            return scores

        # Collect term counts in query
        q_term_counts: Dict[str, int] = {}
        for t in q_tokens:
            q_term_counts[t] = q_term_counts.get(t, 0) + 1

        k1_plus_1 = self.k1 + 1.0

        for term, q_cnt in q_term_counts.items():
            if term not in self.idf:
                continue
            term_idf = self.idf[term]
            if term_idf <= 0.0:
                continue

            postings = self.inverted_index.get(term, [])
            for doc_idx, tf in postings:
                denom = tf + self.doc_len_norms[doc_idx]
                term_score = term_idf * (tf * k1_plus_1) / denom
                scores[doc_idx] += term_score

        # Max-normalize scores to [0, 1] range for unified fusion
        max_score = float(np.max(scores)) if len(scores) > 0 else 0.0
        if max_score > 0.0:
            scores = scores / max_score

        return scores

