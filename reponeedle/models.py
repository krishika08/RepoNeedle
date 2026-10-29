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


class AblationConfig(BaseModel):
    """
    Controlled ablation switches for empirical component evaluation.
    Factor A: enable_lexical (BM25 field scoring)
    Factor B: enable_semantic (Subword semantic scoring)
    Factor C: enable_graph (PageRank & AST test/ripple linkage)
    Factor D: enable_router (Workflow-adaptive routing vs fixed static fusion)
    Factor E: allow_skeletons (Structural skeleton compression vs full only)
    Extended Factors:
    enable_doc_filter: Penalizes documentation distractor paths (0.5x default)
    enable_graph_diffusion: Relevance-aware 1-hop graph diffusion from seed query hits
    enable_polyglot_symbols: Multi-language AST/regex symbol extraction (Rust, Go, JS/TS)
    """
    enable_lexical: bool = True
    enable_semantic: bool = True
    enable_graph: bool = True
    enable_router: bool = True
    allow_skeletons: bool = True
    enable_doc_filter: bool = False
    doc_filter_penalty: float = 0.5
    enable_graph_diffusion: bool = False
    enable_polyglot_symbols: bool = False
    # Stage 3.9 Recovered Factors:
    enable_pagerank_fusion: bool = False
    max_diffusion_degree: int = 25
    decouple_bm25_symbols: bool = True
    # Stage 3.12 Cascaded Reranking:
    candidate_pool_size: Optional[int] = None

    @classmethod
    def candidate_a(cls) -> "AblationConfig":
        """Candidate A: Static lexical-plus-semantic hybrid, full files only, no router (EXP-004)."""
        return cls(
            enable_lexical=True,
            enable_semantic=True,
            enable_graph=True,
            enable_router=False,
            allow_skeletons=False,
            enable_doc_filter=False,
            enable_graph_diffusion=False,
            enable_polyglot_symbols=False,
        )

    @classmethod
    def candidate_b(cls) -> "AblationConfig":
        """Candidate B: Candidate A with structural skeleton compression (EXP-003)."""
        return cls(
            enable_lexical=True,
            enable_semantic=True,
            enable_graph=True,
            enable_router=False,
            allow_skeletons=True,
            enable_doc_filter=False,
            enable_graph_diffusion=False,
            enable_polyglot_symbols=False,
        )

    @classmethod
    def candidate_c(cls) -> "AblationConfig":
        """Candidate C: Candidate B with documentation-distractor filtering."""
        return cls(
            enable_lexical=True,
            enable_semantic=True,
            enable_graph=True,
            enable_router=False,
            allow_skeletons=True,
            enable_doc_filter=True,
            enable_graph_diffusion=False,
            enable_polyglot_symbols=False,
        )

    @classmethod
    def candidate_d(cls) -> "AblationConfig":
        """Candidate D: Candidate C with relevance-aware graph diffusion."""
        return cls(
            enable_lexical=True,
            enable_semantic=True,
            enable_graph=True,
            enable_router=False,
            allow_skeletons=True,
            enable_doc_filter=True,
            enable_graph_diffusion=True,
            enable_polyglot_symbols=False,
        )

    @classmethod
    def candidate_e(cls) -> "AblationConfig":
        """Candidate E: Candidate D with multilingual symbol-extraction (Rust, Go, JS/TS)."""
        return cls(
            enable_lexical=True,
            enable_semantic=True,
            enable_graph=True,
            enable_router=False,
            allow_skeletons=True,
            enable_doc_filter=True,
            enable_graph_diffusion=True,
            enable_polyglot_symbols=True,
        )

    @classmethod
    def candidate_f(cls) -> "AblationConfig":
        """Candidate F: Candidate E with audited polyglot graph diffusion."""
        return cls(
            enable_lexical=True,
            enable_semantic=True,
            enable_graph=True,
            enable_router=False,
            allow_skeletons=True,
            enable_doc_filter=True,
            enable_graph_diffusion=True,
            enable_polyglot_symbols=True,
            enable_pagerank_fusion=True,
            max_diffusion_degree=999999,
            decouple_bm25_symbols=False,
        )

    @classmethod
    def candidate_recovered(cls) -> "AblationConfig":
        """Stage 3.9 Recovered Candidate: Decoupled BM25 + Subword + DocFilter + Bounded Diffusion, NO PageRank."""
        return cls(
            enable_lexical=True,
            enable_semantic=True,
            enable_graph=True,
            enable_router=False,
            allow_skeletons=True,
            enable_doc_filter=True,
            doc_filter_penalty=0.5,
            enable_graph_diffusion=True,
            max_diffusion_degree=25,
            enable_polyglot_symbols=True,
            enable_pagerank_fusion=False,
            decouple_bm25_symbols=True,
        )

    @classmethod
    def config_09(cls) -> "AblationConfig":
        """Stage 3.9/3.10 Winning Quality Hybrid: Decoupled BM25 + Subwords + DocFilter (No PR, No Graph Diffusion)."""
        return cls(
            enable_lexical=True,
            enable_semantic=True,
            enable_graph=False,
            enable_router=False,
            allow_skeletons=True,
            enable_doc_filter=True,
            doc_filter_penalty=0.5,
            enable_graph_diffusion=False,
            enable_polyglot_symbols=True,
            enable_pagerank_fusion=False,
            decouple_bm25_symbols=True,
            candidate_pool_size=None,
        )

    @classmethod
    def config_10(cls, pool_size: int = 50) -> "AblationConfig":
        """Stage 3.10/3.12 Sparse Cascaded Reranker: BM25 Top-K Candidate Generation + Subword Reranking."""
        return cls(
            enable_lexical=True,
            enable_semantic=True,
            enable_graph=False,
            enable_router=False,
            allow_skeletons=True,
            enable_doc_filter=True,
            doc_filter_penalty=0.5,
            enable_graph_diffusion=False,
            enable_polyglot_symbols=True,
            enable_pagerank_fusion=False,
            decouple_bm25_symbols=True,
            candidate_pool_size=pool_size,
        )

    @classmethod
    def bm25_baseline(cls) -> "AblationConfig":
        """Pure BM25 baseline over raw full files without router or skeletons (EXP-016)."""
        return cls(
            enable_lexical=True,
            enable_semantic=False,
            enable_graph=False,
            enable_router=False,
            allow_skeletons=False,
            enable_doc_filter=False,
            enable_graph_diffusion=False,
            enable_polyglot_symbols=False,
        )


