"""
Comprehensive evaluation metrics for repository context retrieval and token budgeting.
"""

import math
from typing import List, Set, Dict, Any
import numpy as np


class RetrievalEvaluator:
    """
    Computes standard IR metrics and agent-centric context budgeting metrics:
    - Recall@k (k=1, 3, 5, 10)
    - Mean Reciprocal Rank (MRR)
    - nDCG@k
    - Budgeted Context Coverage (BCC@B tokens)
    - Irrelevant Tokens Retrieved (Context Bloat)
    - Selective Retrieval Metrics (Precision, Recall, F1 for abstention)
    """

    @staticmethod
    def recall_at_k(ranked_paths: List[str], gold_paths: Set[str], k: int) -> float:
        if not gold_paths:
            return 1.0 if not ranked_paths else 0.0
        top_k = ranked_paths[:k]
        hits = sum(1 for p in top_k if p in gold_paths)
        return hits / len(gold_paths)

    @staticmethod
    def reciprocal_rank(ranked_paths: List[str], gold_paths: Set[str]) -> float:
        if not gold_paths:
            return 0.0
        for rank, p in enumerate(ranked_paths, start=1):
            if p in gold_paths:
                return 1.0 / rank
        return 0.0

    @staticmethod
    def ndcg_at_k(ranked_paths: List[str], gold_paths: Set[str], k: int) -> float:
        if not gold_paths:
            return 1.0 if not ranked_paths else 0.0
        top_k = ranked_paths[:k]
        dcg = 0.0
        for i, p in enumerate(top_k):
            rel = 1.0 if p in gold_paths else 0.0
            dcg += rel / math.log2(i + 2)

        # Ideal DCG
        idcg = sum(1.0 / math.log2(i + 2) for i in range(min(k, len(gold_paths))))
        if idcg == 0.0:
            return 0.0
        return dcg / idcg

    @staticmethod
    def evaluate_budgeted_packing(
        selected_files: List[Any],  # List of objects with .path and .token_count
        gold_paths: Set[str],
        budget_tokens: int,
    ) -> Dict[str, float]:
        """
        Evaluates context yield within token budget:
        - coverage: fraction of gold files present in packed selection
        - irrelevant_tokens: tokens consumed by files not in gold_paths
        - tokens_used: total tokens packed
        - budget_utilization: tokens_used / budget_tokens
        """
        if not gold_paths:
            # For selective/no-gold cases:
            tokens_wasted = sum(getattr(f, "token_count", 0) for f in selected_files)
            return {
                "coverage": 1.0 if len(selected_files) == 0 else 0.0,
                "irrelevant_tokens": float(tokens_wasted),
                "tokens_used": float(tokens_wasted),
                "budget_utilization": float(tokens_wasted) / max(1, budget_tokens),
            }

        packed_paths = [getattr(f, "path", str(f)) for f in selected_files]
        hits = sum(1 for p in packed_paths if p in gold_paths)
        coverage = hits / len(gold_paths)

        irrelevant_tokens = 0
        total_tokens = 0
        for f in selected_files:
            p = getattr(f, "path", str(f))
            t = getattr(f, "token_count", 0)
            total_tokens += t
            if p not in gold_paths:
                irrelevant_tokens += t

        return {
            "coverage": coverage,
            "irrelevant_tokens": float(irrelevant_tokens),
            "tokens_used": float(total_tokens),
            "budget_utilization": float(total_tokens) / max(1, budget_tokens),
        }

