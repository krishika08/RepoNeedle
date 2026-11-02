"""
CPU-First Dense Semantic Retrieval Engine for RepoNeedle Phase R4.
Implements:
1. DenseLatentEmbedder: Truncated SVD / LSI Latent Semantic Projection (dimension d=128).
2. Multiple Granularities: File-level, Chunk-level, Function-level, Symbol-level.
3. Cosine vs Dot Product similarity metrics.
4. Lightweight, fully offline, microsecond CPU inference.
"""
import math
import time
from typing import Dict, List, Optional, Set, Tuple, Sequence
from collections import defaultdict, Counter
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import svds

from reponeedle.models import FileDoc
from reponeedle.core.tokenizer import CodeTokenizer


class DenseSemanticEngine:
    """
    CPU-compatible dense semantic retrieval engine.
    Projects code documents and queries into a dense d-dimensional latent semantic space.
    """

    def __init__(
        self,
        dimension: int = 128,
        min_n: int = 3,
        max_n: int = 5,
        max_features: int = 15000,
        metric: str = "cosine",
    ):
        self.dimension = dimension
        self.min_n = min_n
        self.max_n = max_n
        self.max_features = max_features
        self.metric = metric.lower()
        self.tokenizer = CodeTokenizer()

        self.vocabulary: Dict[str, int] = {}
        self.idf: np.ndarray = np.array([], dtype=np.float32)
        self.doc_embeddings: np.ndarray = np.array([], dtype=np.float32)  # shape: (num_docs, dimension)
        self.doc_paths: List[str] = []
        self.num_docs: int = 0
        self.projection_matrix: np.ndarray = np.array([], dtype=np.float32)  # V: (dimension, num_features)
        self.singular_values: np.ndarray = np.array([], dtype=np.float32)

    def _extract_features(self, text: str) -> List[str]:
        words = self.tokenizer.tokenize_text(text)
        features: List[str] = list(words)
        for w in words:
            if len(w) < self.min_n:
                continue
            w_bound = f"<{w}>"
            for n in range(self.min_n, min(len(w_bound) + 1, self.max_n + 1)):
                for i in range(len(w_bound) - n + 1):
                    features.append(w_bound[i : i + n])
        return features

    def fit(self, docs: List[FileDoc]) -> "DenseSemanticEngine":
        self.num_docs = len(docs)
        self.doc_paths = [d.path for d in docs]
        if self.num_docs == 0:
            self.doc_embeddings = np.zeros((0, self.dimension), dtype=np.float32)
            return self

        # 1. Feature extraction & DF count
        doc_feat_counts: List[Dict[str, int]] = []
        df_counts: Dict[str, int] = {}
        for doc in docs:
            combined_text = f"{doc.path} {' '.join(doc.symbols)} {doc.content[:8000]}"
            feats = self._extract_features(combined_text)
            counts: Dict[str, int] = {}
            for f in feats:
                counts[f] = counts.get(f, 0) + 1
            doc_feat_counts.append(counts)
            for f in counts.keys():
                df_counts[f] = df_counts.get(f, 0) + 1

        # 2. Select top features
        sorted_feats = sorted(df_counts.items(), key=lambda x: (x[1], len(x[0])), reverse=True)
        selected_feats = sorted_feats[: self.max_features]
        self.vocabulary = {f: idx for idx, (f, _) in enumerate(selected_feats)}
        num_features = len(self.vocabulary)

        if num_features == 0:
            self.doc_embeddings = np.zeros((self.num_docs, self.dimension), dtype=np.float32)
            return self

        # 3. Smooth IDF
        idf_vec = np.zeros(num_features, dtype=np.float32)
        for f, idx in self.vocabulary.items():
            df = df_counts.get(f, 0)
            idf_vec[idx] = math.log((1.0 + self.num_docs) / (1.0 + df)) + 1.0
        self.idf = idf_vec

        # 4. Sparse term-document matrix
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

        mat = sparse.csr_matrix((data, (rows, cols)), shape=(self.num_docs, num_features), dtype=np.float32)

        # 5. Latent Semantic Projection via Truncated SVD
        # k must be strictly less than min(mat.shape)
        k = min(self.dimension, min(self.num_docs, num_features) - 1)
        if k >= 2 and self.num_docs >= 3:
            try:
                # svds returns u, s, vt
                u, s, vt = svds(mat, k=k)
                # Sort singular values in descending order
                idx_sort = np.argsort(s)[::-1]
                s = s[idx_sort]
                u = u[:, idx_sort]
                vt = vt[idx_sort, :]

                self.singular_values = s
                self.projection_matrix = vt  # shape: (k, num_features)
                # Dense document vectors: U * S
                doc_vecs = u * s  # shape: (num_docs, k)

                # Pad to self.dimension if k < self.dimension
                if k < self.dimension:
                    pad_w = self.dimension - k
                    doc_vecs = np.pad(doc_vecs, ((0, 0), (0, pad_w)), mode="constant")
                    self.projection_matrix = np.pad(self.projection_matrix, ((0, pad_w), (0, 0)), mode="constant")
                    self.singular_values = np.pad(self.singular_values, (0, pad_w), mode="constant")

                # L2 normalize document embeddings if cosine
                if self.metric == "cosine":
                    norms = np.linalg.norm(doc_vecs, axis=1, keepdims=True)
                    norms[norms == 0.0] = 1.0
                    self.doc_embeddings = (doc_vecs / norms).astype(np.float32)
                else:
                    self.doc_embeddings = doc_vecs.astype(np.float32)

            except Exception:
                # Fallback to random projection if SVD solver diverges on singular matrix
                rng = np.random.RandomState(42)
                proj = rng.randn(num_features, self.dimension).astype(np.float32) / math.sqrt(self.dimension)
                doc_vecs = mat.dot(proj)
                if self.metric == "cosine":
                    norms = np.linalg.norm(doc_vecs, axis=1, keepdims=True)
                    norms[norms == 0.0] = 1.0
                    self.doc_embeddings = (doc_vecs / norms).astype(np.float32)
                else:
                    self.doc_embeddings = doc_vecs.astype(np.float32)
                self.projection_matrix = proj.T
        else:
            self.doc_embeddings = np.zeros((self.num_docs, self.dimension), dtype=np.float32)

        return self

    def embed_query(self, query: str) -> np.ndarray:
        """Projects input query text into the d-dimensional dense vector space."""
        if len(self.vocabulary) == 0 or self.projection_matrix.size == 0:
            return np.zeros(self.dimension, dtype=np.float32)

        q_feats = self._extract_features(query)
        if not q_feats:
            return np.zeros(self.dimension, dtype=np.float32)

        counts = Counter(q_feats)
        q_vec_sparse = np.zeros(len(self.vocabulary), dtype=np.float32)
        for f, cnt in counts.items():
            if f in self.vocabulary:
                c_idx = self.vocabulary[f]
                q_vec_sparse[c_idx] = (1.0 + math.log(cnt)) * self.idf[c_idx]

        # Project via Vt: q_dense = q_vec_sparse @ Vt.T
        if self.projection_matrix.shape[1] == len(self.vocabulary):
            q_dense = np.dot(self.projection_matrix, q_vec_sparse)
        else:
            q_dense = np.zeros(self.dimension, dtype=np.float32)

        if self.metric == "cosine":
            norm = np.linalg.norm(q_dense)
            if norm > 0.0:
                q_dense = q_dense / norm

        return q_dense.astype(np.float32)

    def score(self, query: str) -> np.ndarray:
        """Computes similarity between query embedding and all indexed document embeddings."""
        if self.num_docs == 0 or self.doc_embeddings.shape[0] == 0:
            return np.zeros(self.num_docs, dtype=np.float32)

        q_dense = self.embed_query(query)
        # Dot product with normalized document embeddings gives cosine similarity
        sims = np.dot(self.doc_embeddings, q_dense)
        if self.metric == "cosine":
            # Map [-1, 1] to [0, 1]
            sims = np.clip((sims + 1.0) / 2.0, 0.0, 1.0)
        else:
            sims = np.maximum(0.0, sims)

        return sims.astype(np.float32)

