"""
Reproducible baseline retrieval systems for comparison against RepoNeedle.
"""

from typing import List, Dict, Any, Tuple
import numpy as np

from reponeedle.models import FileDoc, Query, RetrievalResult, ScoredFile, ContextTier, TaskType
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex
from reponeedle.core.graph import RepoGraph
from reponeedle.core.tokenizer import estimate_tokens


class BM25Baseline:
    """Standard BM25 lexical retriever with naive greedy token packing."""

    def __init__(self, docs: List[FileDoc]):
        self.docs = docs
        self.index = BM25Index(path_weight=1.0, symbol_weight=1.0, body_weight=1.0).fit(docs)

    def retrieve(self, query: str, budget_tokens: int = 4000) -> RetrievalResult:
        scores = self.index.score(query)
        ranked_indices = np.argsort(scores)[::-1]

        selected: List[ScoredFile] = []
        tokens_used = 0

        for idx in ranked_indices:
            score = float(scores[idx])
            if score <= 0.0:
                continue
            doc = self.docs[idx]
            tok = doc.token_count if doc.token_count > 0 else estimate_tokens(doc.content)
            if tokens_used + tok <= budget_tokens:
                selected.append(
                    ScoredFile(
                        path=doc.path,
                        score=score,
                        token_count=tok,
                        tier=ContextTier.FULL,
                        rendered_content=doc.content,
                        explanation=f"BM25 baseline score: {score:.3f}",
                    )
                )
                tokens_used += tok

        return RetrievalResult(
            query=query,
            task_type=TaskType.COMMENT2CONTEXT,
            abstained=False,
            confidence_score=1.0,
            selected_files=selected,
            total_tokens=tokens_used,
            budget_tokens=budget_tokens,
            candidate_count=len(self.docs),
            explanation=f"BM25 selected {len(selected)} files.",
        )


class RepoMapBaseline:
    """RepoMap-style structural PageRank retriever with naive greedy token packing."""

    def __init__(self, docs: List[FileDoc]):
        self.docs = docs
        self.graph = RepoGraph().fit(docs)
        self.scores = self.graph.pagerank_scores

    def retrieve(self, query: str, budget_tokens: int = 4000) -> RetrievalResult:
        ranked_indices = np.argsort(self.scores)[::-1]

        selected: List[ScoredFile] = []
        tokens_used = 0

        for idx in ranked_indices:
            score = float(self.scores[idx])
            doc = self.docs[idx]
            tok = doc.token_count if doc.token_count > 0 else estimate_tokens(doc.content)
            if tokens_used + tok <= budget_tokens:
                selected.append(
                    ScoredFile(
                        path=doc.path,
                        score=score,
                        token_count=tok,
                        tier=ContextTier.FULL,
                        rendered_content=doc.content,
                        explanation=f"RepoMap PageRank centrality: {score:.3f}",
                    )
                )
                tokens_used += tok

        return RetrievalResult(
            query=query,
            task_type=TaskType.COMMENT2CONTEXT,
            abstained=False,
            confidence_score=1.0,
            selected_files=selected,
            total_tokens=tokens_used,
            budget_tokens=budget_tokens,
            candidate_count=len(self.docs),
            explanation=f"RepoMap selected {len(selected)} files.",
        )


class DenseSemanticBaseline:
    """Dense subword/semantic vector similarity retriever with naive greedy token packing."""

    def __init__(self, docs: List[FileDoc]):
        self.docs = docs
        self.index = SubwordSemanticIndex().fit(docs)

    def retrieve(self, query: str, budget_tokens: int = 4000) -> RetrievalResult:
        scores = self.index.score(query)
        ranked_indices = np.argsort(scores)[::-1]

        selected: List[ScoredFile] = []
        tokens_used = 0

        for idx in ranked_indices:
            score = float(scores[idx])
            if score <= 0.0:
                continue
            doc = self.docs[idx]
            tok = doc.token_count if doc.token_count > 0 else estimate_tokens(doc.content)
            if tokens_used + tok <= budget_tokens:
                selected.append(
                    ScoredFile(
                        path=doc.path,
                        score=score,
                        token_count=tok,
                        tier=ContextTier.FULL,
                        rendered_content=doc.content,
                        explanation=f"Dense semantic cosine similarity: {score:.3f}",
                    )
                )
                tokens_used += tok

        return RetrievalResult(
            query=query,
            task_type=TaskType.COMMENT2CONTEXT,
            abstained=False,
            confidence_score=1.0,
            selected_files=selected,
            total_tokens=tokens_used,
            budget_tokens=budget_tokens,
            candidate_count=len(self.docs),
            explanation=f"Dense Semantic selected {len(selected)} files.",
        )


class StaticHybridBaseline:
    """Fixed-weight Hybrid (BM25 + Semantic + RepoMap) without workflow adaptation or selective abstention."""

    def __init__(self, docs: List[FileDoc]):
        self.docs = docs
        self.bm25 = BM25Index().fit(docs)
        self.semantic = SubwordSemanticIndex().fit(docs)
        self.graph = RepoGraph().fit(docs)

    def retrieve(self, query: str, budget_tokens: int = 4000) -> RetrievalResult:
        s_bm25 = self.bm25.score(query)
        s_sem = self.semantic.score(query)
        s_pr = self.graph.pagerank_scores

        fused = (s_bm25 * 0.4) + (s_sem * 0.4) + (s_pr * 0.2)
        ranked_indices = np.argsort(fused)[::-1]

        selected: List[ScoredFile] = []
        tokens_used = 0

        for idx in ranked_indices:
            score = float(fused[idx])
            if score <= 0.0:
                continue
            doc = self.docs[idx]
            tok = doc.token_count if doc.token_count > 0 else estimate_tokens(doc.content)
            if tokens_used + tok <= budget_tokens:
                selected.append(
                    ScoredFile(
                        path=doc.path,
                        score=score,
                        token_count=tok,
                        tier=ContextTier.FULL,
                        rendered_content=doc.content,
                        explanation=f"Static Hybrid score: {score:.3f}",
                    )
                )
                tokens_used += tok

        return RetrievalResult(
            query=query,
            task_type=TaskType.COMMENT2CONTEXT,
            abstained=False,
            confidence_score=1.0,
            selected_files=selected,
            total_tokens=tokens_used,
            budget_tokens=budget_tokens,
            candidate_count=len(self.docs),
            explanation=f"Static Hybrid selected {len(selected)} files.",
        )

