"""
Pydantic data models and schemas for RepoNeedle.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TaskType(str, Enum):
    AUTO = "auto"
    CODE2TEST = "code2test"
    COMMENT2CONTEXT = "comment2context"
    TRACE2CODE = "trace2code"
    EDIT2RIPPLE = "edit2ripple"
    SELECTIVE = "selective"


class ContextTier(str, Enum):
    FULL = "full"
    SKELETON = "skeleton"
    SNIPPET = "snippet"
    OMITTED = "omitted"


class FileDoc(BaseModel):
    path: str
    content: str
    token_count: int = 0
    language: str = "python"
    symbols: List[str] = Field(default_factory=list)
    imports: List[str] = Field(default_factory=list)
    is_test: bool = False
    line_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Query(BaseModel):
    text: str
    task_type: TaskType = TaskType.AUTO
    anchor_files: List[str] = Field(default_factory=list)
    budget_tokens: int = 4000
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ScoredFile(BaseModel):
    path: str
    score: float
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    structural_score: float = 0.0
    workflow_boost: float = 0.0
    token_count: int = 0
    tier: ContextTier = ContextTier.FULL
    rendered_content: str = ""
    explanation: str = ""


class RetrievalResult(BaseModel):
    query: str
    task_type: TaskType
    abstained: bool = False
    confidence_score: float = 1.0
    selected_files: List[ScoredFile] = Field(default_factory=list)
    total_tokens: int = 0
    budget_tokens: int = 4000
    candidate_count: int = 0
    explanation: str = ""
    execution_time_ms: float = 0.0


class BudgetConfig(BaseModel):
    max_tokens: int = 4000
    allow_skeletons: bool = True
    skeleton_token_cap: int = 350
    density_exponent: float = 0.75
    abstention_threshold: float = 0.12
