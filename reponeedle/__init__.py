"""
RepoNeedle: Token-Budget-Aware, Workflow-Adaptive Repository Context Retrieval for AI Coding Agents.
"""

from reponeedle.models import (
    FileDoc,
    Query,
    RetrievalResult,
    ScoredFile,
    TaskType,
    BudgetConfig,
    ContextTier,
)
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.packer import (
    CUDPackOptimizer,
    BudgetOptimizer,
    ExactTokenizer,
    CodeSpanExtractor,
)

__version__ = "1.0.0"
__all__ = [
    "RepoNeedleEngine",
    "FileDoc",
    "Query",
    "RetrievalResult",
    "ScoredFile",
    "TaskType",
    "BudgetConfig",
    "ContextTier",
    "CUDPackOptimizer",
    "BudgetOptimizer",
    "ExactTokenizer",
    "CodeSpanExtractor",
]

