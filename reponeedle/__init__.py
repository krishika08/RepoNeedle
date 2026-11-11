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
    AbstentionDiagnostics,
    IndexingDiagnostics,
)
from reponeedle.engine import RepoNeedleEngine, DEFAULT_MAX_FILE_SIZE_BYTES
from reponeedle.core.change_impact import ChangeImpactRanker, ChangeImpactConfig
from reponeedle.core.packer import (
    CUDPackOptimizer,
    BudgetOptimizer,
    ExactTokenizer,
    CodeSpanExtractor,
)

__version__ = "1.2.0"
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
    "AbstentionDiagnostics",
    "IndexingDiagnostics",
    "DEFAULT_MAX_FILE_SIZE_BYTES",
    "ChangeImpactRanker",
    "ChangeImpactConfig",
    "CUDPackOptimizer",
    "BudgetOptimizer",
    "ExactTokenizer",
    "CodeSpanExtractor",
]

