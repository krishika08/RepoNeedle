"""
Pydantic data models and schemas for RepoNeedle.
"""

from enum import Enum
from typing import List, Literal, Optional, Dict, Any, Tuple
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TaskType(str, Enum):
    AUTO = "auto"
    CODE2TEST = "code2test"
    COMMENT2CONTEXT = "comment2context"
    TRACE2CODE = "trace2code"
    EDIT2RIPPLE = "edit2ripple"
    SELECTIVE = "selective"


class RankerType(str, Enum):
    LEGACY = "legacy"
    BM25 = "bm25"
    ARM101 = "arm101"
    CASCADE = "cascade"
    CHANGE_IMPACT = "change_impact"


class ContextTier(str, Enum):
    FULL = "full"
    FULL_FILE = "full_file"
    FOCUS_SPAN = "focus_span"
    SKELETON = "skeleton"
    INTERFACE = "interface"
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


class AbstentionDiagnostics(BaseModel):
    """
    Describes how (and whether) the experimental abstention heuristic influenced a retrieval.

    status values:
        "disabled"          - Heuristic not applied (default). Results are returned regardless of
                              whether the query is in scope for the repository.
        "evaluated"         - Caller opted in; the heuristic decided whether to abstain.
        "empty_repository"  - No candidate files exist; the result is abstained structurally,
                              independent of the heuristic and of the opt-in flag.

    The heuristic is experimental and NOT production-calibrated (ARB v2 selective split:
    0 of 82 negative samples correctly abstained). `experimental` and `calibrated` are
    reported on every result so downstream consumers never mistake it for a calibrated signal.
    """
    enabled: bool = False
    status: str = "disabled"
    experimental: bool = True
    calibrated: bool = False
    threshold: float = 0.12
    reason: str = ""


class IndexingDiagnostics(BaseModel):
    """
    Records what was (and was not) indexed. Never stores file contents: only
    repository-relative paths and counts.

    source:
        "directory" - built by RepoNeedleEngine.from_directory (scan statistics are populated).
        "documents" - built from in-memory FileDoc objects (no scan was performed).
    """
    source: str = "documents"
    indexed_files: int = 0
    max_file_size_bytes: Optional[int] = None
    skipped_large_files: int = 0
    skipped_paths: List[str] = Field(default_factory=list)
    skipped_unreadable_files: int = 0
    unreadable_paths: List[str] = Field(default_factory=list)
    # Files (symlinks or, on Windows, junction members) whose canonical location is outside the
    # repository root. Reason code: "symlink_outside_repository". Only the in-repository link path
    # is recorded; the target path and contents are never read or stored.
    skipped_symlink_outside_repository: int = 0
    symlink_outside_repository_paths: List[str] = Field(default_factory=list)
    # Directories that were not traversed. Directory symlinks and Windows junctions are never
    # followed (on every platform); files beneath an in-repository link target are still indexed
    # through their real path. Directories that would revisit an already-traversed directory
    # (cycles) or whose canonical location is outside the repository root are also skipped.
    # Only the in-repository path is recorded; link targets are never listed or stored.
    skipped_directories: int = 0
    skipped_directory_paths: List[str] = Field(default_factory=list)
    # Subset of skipped_directories whose canonical location is outside the repository root
    # (or cannot be resolved, e.g. broken links).
    skipped_directories_outside_repository: int = 0
    max_files: Optional[int] = None
    max_files_reached: bool = False


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
    ranker: Optional[str] = "legacy"
    ranked_files: Optional[List[str]] = None
    rendered_context: str = ""
    # Added in 1.2.0 (optional; None for results built outside RepoNeedleEngine.retrieve).
    abstention: Optional[AbstentionDiagnostics] = None

    @property
    def packed_files(self) -> List[ScoredFile]:
        """Convenience alias for selected_files (CUD-Pack packed files)."""
        return self.selected_files


class BudgetConfig(BaseModel):
    max_tokens: int = 4000
    allow_skeletons: bool = True
    skeleton_token_cap: int = 350
    density_exponent: float = 0.75
    abstention_threshold: float = 0.12
    # Experimental, uncalibrated out-of-scope abstention heuristic. Disabled by default since 1.2.0.
    # When False, retrieval never abstains on heuristic grounds (empty repositories still abstain).
    # Selecting TaskType.SELECTIVE does NOT enable it; this flag (or the per-call override on
    # RepoNeedleEngine.retrieve) is the only opt-in.
    enable_experimental_abstention: bool = False
    mode: str = "auto"  # "auto", "compact", "complete"
    capacity_elasticity: Optional[float] = None
    candidate_pool_cutoff: int = 85
    exact_tokenizer: bool = True
    # Focus-span extractor used by CUD-Pack. "legacy" (default) is the original line-window/AST-name
    # extractor, unchanged. "ast_blocks" (opt-in) renders the smallest complete function/method/declaration
    # blocks containing query matches (Python via `ast`; TypeScript/TSX, Go, Rust, Java, C++ via the optional
    # Tree-sitter extra) and falls back to "legacy" per file. See docs/AST_BLOCK_SLICING.md.
    focus_span_strategy: Literal["legacy", "ast_blocks"] = "legacy"


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
    # V2 (opt-in): structural extractor for the function-level call graph (used by the `arm101` ranker).
    # "regex" is the 1.2.0 behaviour. "tree_sitter" parses TypeScript/TSX, Go, Rust, Java and C++ with
    # Tree-sitter when the optional `treesitter` extra is installed, falling back to "regex" per file
    # when a parser is unavailable. Python always uses the `ast` extractor.
    structural_parser: Literal["regex", "tree_sitter"] = "regex"

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




class ScipConfig(BaseModel):
    """
    Opt-in ingestion of an externally generated SCIP index (``index.scip``) into the function graph.

    Requires the optional ``scip`` extra (Protobuf). RepoNeedle never runs an indexer: generate the
    index with your language's SCIP indexer and regenerate it after source changes.
    """
    index_path: str = Field(description="Path to the .scip file to ingest.")
    repo_root: Optional[str] = Field(
        default=None,
        description=(
            "Repository the index must describe. from_directory() sets it to repo_dir; it is required "
            "for engines built from in-memory documents."
        ),
    )
    allow_project_root_mismatch: bool = Field(
        default=False,
        description=(
            "Accept an index whose Metadata.project_root differs from repo_root (for example one built "
            "in CI). Document paths are still validated against repo_root."
        ),
    )
    max_index_bytes: int = Field(
        default=256 * 1024 * 1024, gt=0,
        description="Indexes larger than this are rejected before they are read.",
    )
    on_error: Literal["raise", "skip"] = Field(
        default="raise",
        description="'raise': a SCIP problem raises ScipIngestionError. 'skip': continue without SCIP; "
                    "the reason is recorded in the SCIP diagnostics.",
    )


class IndexCacheConfig(BaseModel):
    """
    Opt-in persistent index cache (V2 Stages 1-2): ``RepoNeedleEngine.from_directory(..., index_cache=...)``.

    Per-file derived data (document metadata, BM25 term counts, semantic features, abstainer vocabularies,
    function-graph and class-to-test extraction records, typed dependency keys and each file's resolved graph
    edges) is stored in a per-repository SQLite database and reused on later starts for files whose inputs are
    unchanged. Graph resolution is repeated only for files affected by a change; the semantic index (exact
    single-pass reconstruction, V2 Stage 3), PageRank and the other global structures are recomputed in full, so
    results are identical to a build without a cache. Raw source text is never stored.
    See docs/PERSISTENT_INDEXING_DESIGN.md.
    """
    model_config = ConfigDict(extra="forbid")

    cache_dir: Optional[str] = Field(
        default=None,
        description="Directory for cache databases. Default: a per-user cache directory outside the repository.",
    )
    enabled: bool = Field(default=True, description="False: behave exactly as without a cache configuration.")
    validation: Literal["content", "stat"] = Field(
        default="content",
        description=(
            "How unchanged files are recognised. Every file is read eagerly, so content digests are always "
            "compared; 'stat' is accepted and reported as 'content' in the diagnostics."
        ),
    )
    rebuild_policy: Literal["auto", "never", "always"] = Field(
        default="auto",
        description=(
            "'auto': set an unusable cache aside and rebuild. 'never': raise IndexCacheError instead. "
            "'always': ignore any existing cache and build it again."
        ),
    )
    read_only: bool = Field(default=False, description="Use a valid cache but never write to it.")
    verify: bool = Field(
        default=False,
        description="Also run PRAGMA integrity_check and verify artifacts no published generation references.",
    )
    persist_exclude: List[str] = Field(
        default_factory=list,
        description=(
            "gitwildmatch patterns (repository-relative). Matching files are indexed in memory as usual, but "
            "nothing derived from them is written to the cache."
        ),
    )
    max_db_bytes: int = Field(default=2 * 1024 ** 3, gt=0, description="Per-repository database size limit.")
    max_total_bytes: int = Field(default=10 * 1024 ** 3, gt=0, description="Limit across the cache directory.")
    busy_timeout_s: float = Field(default=30.0, gt=0, le=3600, description="SQLite busy timeout in seconds.")

    @field_validator("cache_dir")
    @classmethod
    def _check_cache_dir(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and (not v.strip() or "\x00" in v):
            raise ValueError("cache_dir must be a non-empty path without NUL characters")
        return v

    @field_validator("persist_exclude")
    @classmethod
    def _check_patterns(cls, patterns: List[str]) -> List[str]:
        import pathspec

        for p in patterns:
            if not isinstance(p, str) or not p.strip() or "\x00" in p:
                raise ValueError(f"invalid persist_exclude pattern {p!r}")
        try:
            pathspec.PathSpec.from_lines("gitwildmatch", patterns)
        except Exception as exc:  # pathspec raises several exception types for malformed patterns
            raise ValueError(f"invalid persist_exclude pattern: {exc}") from exc
        return list(patterns)

    @model_validator(mode="after")
    def _check_limits(self) -> "IndexCacheConfig":
        if self.max_total_bytes < self.max_db_bytes:
            raise ValueError("max_total_bytes must be at least max_db_bytes")
        return self


class IndexUpdateReport(BaseModel):
    """What one cached build or ``RepoNeedleEngine.refresh()`` did. Counts and paths only, never contents."""
    state: str = Field(description="'published', 'loaded_read_only', 'not_persisted' or 'disabled'.")
    reason: str = ""
    generation: Optional[int] = None
    validation: str = "content"
    files_indexed: int = 0
    files_persisted: int = 0
    files_persist_excluded: int = 0
    files_reused: int = 0
    files_extracted: int = 0
    added: List[str] = Field(default_factory=list)
    modified: List[str] = Field(default_factory=list)
    deleted: List[str] = Field(default_factory=list)
    renamed: List[Tuple[str, str]] = Field(default_factory=list)
    artifacts_written: int = 0
    artifacts_reused: int = 0
    artifacts_collected: int = 0
    global_structures: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "How each stage was produced: 'incremental' (work proportional to the change), 'partially_incremental' "
            "(proportional parts plus named global O(N) parts), 'recomputed_in_full', 'reused' or 'fallback_full' "
            "(an incremental path was available but could not be used; see fallbacks)."
        ),
    )
    fallbacks: Dict[str, str] = Field(default_factory=dict, description="Stage -> why it fell back to full work.")
    work_counters: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description=("Per-stage work counters (files, keys, edges, postings, tokens). 'semantic' holds the semantic "
                     "index's fit diagnostics (feature-cache hits and misses, pairs, distinct features, vocabulary "
                     "size, non-zeros, the numeric product rule, sub-stage timings); it is recomputed in full."))
    file_ids_assigned: int = 0
    file_ids_retired: int = 0
    migrated_from_schema: Optional[int] = None
    privacy_purge: str = Field(
        default="not_required",
        description=(
            "'not_required'; 'complete' (previously persisted data of persist_exclude'd files was deleted, freed "
            "pages were overwritten and the WAL was checkpointed and truncated); or 'pending' (another connection "
            "still held an older read snapshot, so old pages may remain in the database file or WAL until a later "
            "refresh() completes the checkpoint). Not a guarantee about the physical storage medium."
        ),
    )
    rebuilt_from_scratch: bool = False
    timings_ms: Dict[str, float] = Field(default_factory=dict)
