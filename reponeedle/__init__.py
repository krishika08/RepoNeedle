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
)
from reponeedle.engine import RepoNeedleEngine

__version__ = "0.1.0"
__all__ = [
    "RepoNeedleEngine",
    "FileDoc",
    "Query",
    "RetrievalResult",
    "ScoredFile",
    "TaskType",
    "BudgetConfig",
]

