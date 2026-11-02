"""
RepoNeedle: Token-Budget-Aware, Workflow-Adaptive Repository Context Retrieval for AI Coding Agents.
"""

from reponeedle.models import (
    FileDoc,
    Query,
    RetrievalResult,
    ScoredFile,
    TaskType,
    RankerType,
    BudgetConfig,
    ContextTier,
)
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.change_impact import ChangeImpactRanker, ChangeImpactConfig
from reponeedle.core.packer import (
    CUDPackOptimizer,
    BudgetOptimizer,
    ExactTokenizer,
    CodeSpanExtractor,
)

__version__ = "1.1.0"
__all__ = [
    "RepoNeedleEngine",
    "FileDoc",
    "Query",
    "RetrievalResult",
    "ScoredFile",
    "TaskType",
    "RankerType",
    "BudgetConfig",
    "ContextTier",
    "ChangeImpactRanker",
    "ChangeImpactConfig",
    "CUDPackOptimizer",
    "BudgetOptimizer",
    "ExactTokenizer",
    "CodeSpanExtractor",
]

