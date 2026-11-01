"""
Token-budget-aware context selection and knapsack packing engine.
Preserves backwards compatibility with legacy reponeedle.core.budget imports while
delegating directly to the production CUD-Pack engine (reponeedle.core.packer).
"""

from reponeedle.core.packer import (
    ExactTokenizer,
    CodeSpanExtractor,
    CUDPackOptimizer,
    BudgetOptimizer,
    filter_query_terms,
    BENCHMARK_TOKEN_PATTERN,
    COMMON_STOPWORDS,
)

__all__ = [
    "ExactTokenizer",
    "CodeSpanExtractor",
    "CUDPackOptimizer",
    "BudgetOptimizer",
    "filter_query_terms",
    "BENCHMARK_TOKEN_PATTERN",
    "COMMON_STOPWORDS",
]
