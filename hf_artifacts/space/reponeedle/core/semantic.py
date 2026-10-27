"""
Subword and semantic vector similarity index for code repositories.
Operates completely offline with zero network dependency using vectorized n-gram and term embeddings.
"""

import math
from typing import List, Dict, Set
import numpy as np
from scipy import sparse

from reponeedle.models import FileDoc
from reponeedle.core.tokenizer import CodeTokenizer


class SubwordSemanticIndex:
    """
    Subword character n-gram and semantic term similarity index.
    Constructs high-dimensional subword feature representations to bridge lexical vocabulary mismatches,
    abbreviations, and morphological variations in code identifiers and task descriptions.
    """

    def __init__(
        self,
        min_n: int = 3,
        max_n: int = 5,
        max_features: int = 15000,
    ):
        self.min_n = min_n
        self.max_n = max_n
        self.max_features = max_features
        self.tokenizer = CodeTokenizer()
        
        self.vocabulary: Dict[str, int] = {}
        self.idf: np.ndarray = np.array([], dtype=np.float32)
        self.doc_matrix: sparse.csr_matrix = sparse.csr_matrix((0, 0), dtype=np.float32)
        self.num_docs: int = 0
        self.doc_paths: List[str] = []

    def _extract_features(self, text: str) -> List[str]:
        """
        Extracts both word tokens and character n-grams from text.
        """
        words = self.tokenizer.tokenize_text(text)
        features: List[str] = list(words)

        for w in words:
            if len(w) < self.min_n:
                continue
            # Add character n-grams
            w_bound = f"<{w}>"
            for n in range(self.min_n, min(len(w_bound) + 1, self.max_n + 1)):
                for i in range(len(w_bound) - n + 1):
                    features.append(w_bound[i : i + n])

        return features

    def fit(self, docs: List[FileDoc]) -> "SubwordSemanticIndex":
        """
        Fits semantic index on repository documents.
        """
        self.num_docs = len(docs)
        self.doc_paths = [d.path for d in docs]
        if self.num_docs == 0:
            return self

        # 1. Count document frequencies
        doc_feat_counts: List[Dict[str, int]] = []
        df_counts: Dict[str, int] = {}

        for doc in docs:
            # Combine path, symbols, and sample of body
            combined_text = f"{doc.path} {' '.join(doc.symbols)} {doc.content[:8000]}"
            feats = self._extract_features(combined_text)
            
            counts: Dict[str, int] = {}
            for f in feats:
                counts[f] = counts.get(f, 0) + 1
            doc_feat_counts.append(counts)

            for f in counts.keys():
                df_counts[f] = df_counts.get(f, 0) + 1

        # 2. Select top features by document frequency
        # Filter terms that appear in at least 1 doc, sort by DF
        sorted_feats = sorted(
            df_counts.items(),
            key=lambda x: (x[1], len(x[0])),
            reverse=True,
        )
        selected_feats = sorted_feats[: self.max_features]
        self.vocabulary = {f: idx for idx, (f, _) in enumerate(selected_feats)}
        num_features = len(self.vocabulary)

        if num_features == 0:
            self.doc_matrix = sparse.csr_matrix((self.num_docs, 0), dtype=np.float32)
            self.idf = np.zeros(0, dtype=np.float32)
            return self

        # 3. Compute smooth IDF: ln((1 + N) / (1 + df)) + 1
        idf_vec = np.zeros(num_features, dtype=np.float32)
        for f, idx in self.vocabulary.items():
            df = df_counts.get(f, 0)
            idf_vec[idx] = math.log((1.0 + self.num_docs) / (1.0 + df)) + 1.0
        self.idf = idf_vec

        # 4. Construct sparse document matrix with sublinear TF: 1 + ln(tf)
        rows, cols, data = [], [], []
        for d_idx, counts in enumerate(doc_feat_counts):
            for f, cnt in counts.items():
                if f in self.vocabulary:
                    c_idx = self.vocabulary[f]
                    tf = 1.0 + math.log(cnt)
                    val = tf * self.idf[c_idx]
                    rows.append(d_idx)
                    cols.append(c_idx)
                    data.append(val)

        mat = sparse.csr_matrix(
            (data, (rows, cols)),
            shape=(self.num_docs, num_features),
            dtype=np.float32,
        )
        
        # L2 normalize rows
        row_norms = sparse.linalg.norm(mat, axis=1)
        row_norms[row_norms == 0.0] = 1.0
        mat_norm = mat.multiply(sparse.csr_matrix(1.0 / row_norms[:, np.newaxis]))
        self.doc_matrix = mat_norm.tocsr()

        return self

    def score(self, query: str) -> np.ndarray:
        """
        Computes cosine similarity between query and all documents.
        Returns a float array of length num_docs in [0, 1].
        """
        if self.num_docs == 0 or len(self.vocabulary) == 0:
            return np.zeros(self.num_docs, dtype=np.float32)

        q_feats = self._extract_features(query)
        if not q_feats:
            return np.zeros(self.num_docs, dtype=np.float32)

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
            return np.zeros(self.num_docs, dtype=np.float32)

        q_vec = sparse.csr_matrix(
            (q_data, ([0] * len(q_cols), q_cols)),
            shape=(1, len(self.vocabulary)),
            dtype=np.float32,
        )
        q_norm = sparse.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec.multiply(1.0 / q_norm)

        # Dot product with normalized document matrix yields cosine similarities
        scores = self.doc_matrix.dot(q_vec.T).toarray().flatten()
        # Clip to [0, 1]
        scores = np.clip(scores, 0.0, 1.0)
        return scores
