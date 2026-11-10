"""
Main RepoNeedle Engine API.
Provides an integrated, token-budget-aware repository context retrieval system.
"""

import os
import time
import logging
import pathlib
import numbers
from typing import List, Optional, Union, Dict, Set
import numpy as np
import pathspec

from reponeedle.models import (
    FileDoc,
    Query,
    RetrievalResult,
    ScoredFile,
    TaskType,
    RankerType,
    BudgetConfig,
    AblationConfig,
    ContextTier,
    AbstentionDiagnostics,
    IndexingDiagnostics,
)
from reponeedle.core.function_graph import FunctionGraphEngine
from reponeedle.core.arm101 import ARM101Ranker
from reponeedle.core.cascade import CascadedRanker
from reponeedle.core.change_impact import ChangeImpactRanker, ChangeImpactConfig
from reponeedle.core.tokenizer import CodeTokenizer, estimate_tokens
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex
from reponeedle.core.graph import RepoGraph
from reponeedle.core.router import WorkflowRouter
from reponeedle.core.abstention import SelectiveAbstainer
from reponeedle.core.budget import BudgetOptimizer

DEFAULT_IGNORE_PATTERNS = [
    ".git", ".svn", ".hg", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".tox", ".venv", "venv", "env", "node_modules", "dist", "build",
    "*.pyc", "*.pyo", "*.pyd", "*.so", "*.dll", "*.dylib", "*.exe",
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.ico", "*.pdf", "*.zip", "*.tar.gz",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
]

# Files strictly larger than this many bytes are excluded from the index (a file exactly at
# the limit is indexed). Exclusions are recorded in RepoNeedleEngine.indexing_diagnostics.
DEFAULT_MAX_FILE_SIZE_BYTES = 500_000

logger = logging.getLogger(__name__)


def relpath_escapes_root(rel_path: str) -> bool:
    """True if a relative path climbs out of its base (first component is '..').

    Component-aware: names that merely start with '..' (e.g. '..cache/x') do not escape."""
    parts = pathlib.PurePath(rel_path).parts
    return bool(parts) and parts[0] == os.pardir


def is_path_within_root(path: str, real_root: str) -> bool:
    """True if the canonical `path` is `real_root` itself or lies beneath it (component-aware)."""
    try:
        root_n = os.path.normcase(real_root)
        return os.path.commonpath([root_n, os.path.normcase(path)]) == root_n
    except ValueError:  # different drives / mixed absolute-relative paths
        return False


def resolve_within_root(path: str, real_root: str) -> Optional[str]:
    """
    Resolve `path` to its canonical location (following symlinks and, on Windows, junctions).

    Returns the resolved path if it stays inside `real_root`, or None if it resolves outside.
    Raises OSError (or RuntimeError/ValueError) if resolution fails, e.g. broken links or loops.
    """
    resolved = os.path.realpath(path, strict=True)
    return resolved if is_path_within_root(resolved, real_root) else None


def validate_max_file_size_bytes(value) -> int:
    """
    Validates a file-size limit. The contract is a strictly positive integer number of bytes.

    Raises:
        TypeError: If the value is not an integer (bool is rejected).
        ValueError: If the value is zero or negative.
    """
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise TypeError(
            f"max_file_size_bytes must be a positive integer number of bytes, got {type(value).__name__}."
        )
    value = int(value)
    if value <= 0:
        raise ValueError(f"max_file_size_bytes must be a positive integer (> 0), got {value}.")
    return value


class RepoNeedleEngine:
    """
    High-performance, workflow-adaptive repository context retrieval engine.
    """

    def __init__(
        self,
        docs: List[FileDoc] = None,
        budget_config: Optional[BudgetConfig] = None,
        ablation_config: Optional[AblationConfig] = None,
        ranker: Optional[Union[str, RankerType]] = RankerType.LEGACY,
        ranking_engine: Optional[Union[str, RankerType]] = None,
        change_impact_config: Optional[ChangeImpactConfig] = None,
    ):
        self.budget_config = budget_config or BudgetConfig()
        self.ablation_config = ablation_config or AblationConfig()
        raw_ranker = ranking_engine if ranking_engine is not None else ranker
        if raw_ranker is not None:
            if isinstance(raw_ranker, RankerType):
                self.ranker = raw_ranker
            else:
                self.ranker = RankerType(str(raw_ranker).lower())
        else:
            self.ranker = RankerType.LEGACY

        self.tokenizer = CodeTokenizer()
        self.router = WorkflowRouter()
        self.budget_optimizer = BudgetOptimizer(self.budget_config)
        
        self.docs: List[FileDoc] = []
        self.path_to_doc: Dict[str, FileDoc] = {}
        
        # Sub-indices
        self.lexical_index = BM25Index()
        self.semantic_index = SubwordSemanticIndex()
        self.repo_graph = RepoGraph()
        self.abstainer = SelectiveAbstainer(
            confidence_threshold=self.budget_config.abstention_threshold
        )
        self.function_graph = FunctionGraphEngine()
        self.arm101_ranker = ARM101Ranker()
        self.cascaded_ranker = CascadedRanker()
        self.change_impact_config = change_impact_config or ChangeImpactConfig()
        self.change_impact_ranker = ChangeImpactRanker(self.change_impact_config)

        # Populated with scan statistics by from_directory(); "documents" source otherwise.
        self.indexing_diagnostics = IndexingDiagnostics(source="documents", indexed_files=0)

        if docs:
            self._fit(docs)

    def _fit(self, docs: List[FileDoc]):
        """
        Fits all internal indices on the document collection.
        """
        # Deduplicate docs by path (preserving latest content)
        deduped: Dict[str, FileDoc] = {}
        for d in docs:
            deduped[d.path] = d
        clean_docs = list(deduped.values())

        self.docs = clean_docs
        self.path_to_doc = deduped

        # Polyglot symbol extraction if enabled and symbols missing
        if self.ablation_config.enable_polyglot_symbols:
            for d in clean_docs:
                if not d.symbols and not d.imports:
                    syms, imps = RepoGraph.extract_polyglot_symbols(d.content, d.path)
                    if syms or imps:
                        d.symbols = syms
                        d.imports = imps

        self.lexical_index.fit(clean_docs)
        self.semantic_index.fit(clean_docs)
        self.repo_graph.fit(clean_docs)
        self.function_graph.build_graph(clean_docs)
        self.abstainer.fit(clean_docs)
        self.indexing_diagnostics.indexed_files = len(clean_docs)

    def update_document(self, doc: FileDoc):
        """
        Incrementally updates or inserts a single document in the engine's indices.
        Uses cached representation tokens for unchanged files to minimize re-parsing overhead
        while preserving bit-identical mathematical ranking consistency.
        """
        self.update_documents([doc])

    def update_documents(self, docs: List[FileDoc]):
        """
        Incrementally updates or inserts multiple documents in the engine's indices.
        Uses cached representation tokens for unchanged files to minimize re-parsing overhead
        while preserving bit-identical mathematical ranking consistency.
        """
        if not docs:
            return

        for d in docs:
            self.path_to_doc[d.path] = d

        clean_docs = list(self.path_to_doc.values())
        self.docs = clean_docs

        # Polyglot symbol extraction if enabled and symbols missing
        if self.ablation_config.enable_polyglot_symbols:
            for d in docs:
                if not d.symbols and not d.imports:
                    syms, imps = RepoGraph.extract_polyglot_symbols(d.content, d.path)
                    if syms or imps:
                        d.symbols = syms
                        d.imports = imps

        self.lexical_index.fit(clean_docs)
        self.semantic_index.fit(clean_docs)
        self.repo_graph.fit(clean_docs)
        self.function_graph.build_graph(clean_docs)
        self.abstainer.fit(clean_docs)
        self.indexing_diagnostics.indexed_files = len(clean_docs)

    def query(self, *args, **kwargs) -> RetrievalResult:
        """Alias for retrieve() to provide intuitive querying API."""
        return self.retrieve(*args, **kwargs)

    @classmethod
    def from_documents(
        cls,
        docs: List[FileDoc],
        budget_config: Optional[BudgetConfig] = None,
        ablation_config: Optional[AblationConfig] = None,
        ranker: Optional[Union[str, RankerType]] = RankerType.LEGACY,
        ranking_engine: Optional[Union[str, RankerType]] = None,
        change_impact_config: Optional[ChangeImpactConfig] = None,
    ) -> "RepoNeedleEngine":
        """
        Instantiates engine from an in-memory list of FileDoc instances.
        """
        return cls(
            docs=docs,
            budget_config=budget_config,
            ablation_config=ablation_config,
            ranker=ranker,
            ranking_engine=ranking_engine,
            change_impact_config=change_impact_config,
        )

    @classmethod
    def from_directory(
        cls,
        repo_dir: str,
        budget_config: Optional[BudgetConfig] = None,
        max_files: int = 3000,
        extra_ignore: List[str] = None,
        ablation_config: Optional[AblationConfig] = None,
        ranker: Optional[Union[str, RankerType]] = RankerType.LEGACY,
        ranking_engine: Optional[Union[str, RankerType]] = None,
        change_impact_config: Optional[ChangeImpactConfig] = None,
        max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    ) -> "RepoNeedleEngine":
        """
        Scans a local repository directory, parses files, and builds the retrieval index.

        Files strictly larger than ``max_file_size_bytes`` (default 500,000) are excluded from
        the index. Every exclusion (oversized or unreadable) is recorded by repository-relative
        path in ``engine.indexing_diagnostics`` and summarized via a WARNING on the
        ``reponeedle.engine`` logger (stderr by default). File contents are never recorded.

        Raises:
            TypeError / ValueError: If ``max_file_size_bytes`` is not a positive integer.
        """
        max_file_size_bytes = validate_max_file_size_bytes(max_file_size_bytes)
        repo_dir = os.path.abspath(repo_dir)
        ignore_patterns = list(DEFAULT_IGNORE_PATTERNS)
        if extra_ignore:
            ignore_patterns.extend(extra_ignore)

        gitignore_path = os.path.join(repo_dir, ".gitignore")
        if os.path.isfile(gitignore_path):
            try:
                with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            ignore_patterns.append(line)
            except Exception:
                pass

        spec = pathspec.PathSpec.from_lines("gitwildmatch", ignore_patterns)
        docs: List[FileDoc] = []
        skipped_large: List[str] = []
        unreadable: List[str] = []
        outside_root: List[str] = []
        max_files_reached = False
        # Canonical repository root: every indexed file must resolve beneath it.
        real_root = os.path.realpath(repo_dir)

        for root, dirs, files in os.walk(repo_dir):
            # Prune ignored directories
            rel_root = os.path.relpath(root, repo_dir).replace("\\", "/")
            if rel_root == ".":
                rel_root = ""

            dirs[:] = [
                d for d in dirs
                if not spec.match_file(f"{rel_root}/{d}" if rel_root else d)
                and d not in DEFAULT_IGNORE_PATTERNS
            ]

            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), repo_dir).replace("\\", "/")
                if spec.match_file(rel_path):
                    continue

                # Filter non-code/text files
                ext = os.path.splitext(file)[1].lower()
                if ext not in (".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".md", ".toml", ".yaml", ".yml", ".json"):
                    continue

                full_path = os.path.join(root, file)
                # Containment: resolve links BEFORE touching the target, and read only the
                # validated canonical path (never the link itself). Links resolving outside the
                # repository are skipped and recorded by their in-repository path only.
                try:
                    resolved = resolve_within_root(full_path, real_root)
                except (OSError, RuntimeError, ValueError):  # broken link, loop, permission error
                    unreadable.append(rel_path)
                    continue
                if resolved is None:
                    outside_root.append(rel_path)
                    continue
                try:
                    file_size = os.path.getsize(resolved)
                except OSError:
                    unreadable.append(rel_path)
                    continue
                # Exclude oversized files (strictly greater than the limit), but record them.
                if file_size > max_file_size_bytes:
                    skipped_large.append(rel_path)
                    continue
                try:
                    with open(resolved, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception:
                    unreadable.append(rel_path)
                    continue

                # Detect if test file
                norm_lower = rel_path.lower()
                is_test = (
                    "test" in norm_lower or
                    "tests/" in norm_lower or
                    norm_lower.startswith("test_") or
                    norm_lower.endswith("_test.py")
                )

                # AST symbol extraction (Python or Polyglot)
                symbols, imports = [], []
                if ablation_config and ablation_config.enable_polyglot_symbols:
                    symbols, imports = RepoGraph.extract_polyglot_symbols(content, rel_path)
                elif ext == ".py":
                    symbols, imports = RepoGraph.extract_python_ast(content, rel_path)

                tokens = estimate_tokens(content)
                docs.append(
                    FileDoc(
                        path=rel_path,
                        content=content,
                        token_count=tokens,
                        language="python" if ext == ".py" else ext[1:],
                        symbols=symbols,
                        imports=imports,
                        is_test=is_test,
                        line_count=len(content.splitlines()),
                    )
                )

                if len(docs) >= max_files:
                    max_files_reached = True
                    break
            if len(docs) >= max_files:
                max_files_reached = True
                break

        engine = cls(
            docs=docs,
            budget_config=budget_config,
            ablation_config=ablation_config,
            ranker=ranker,
            ranking_engine=ranking_engine,
            change_impact_config=change_impact_config,
        )

        skipped_large.sort()
        unreadable.sort()
        outside_root.sort()
        engine.indexing_diagnostics = IndexingDiagnostics(
            source="directory",
            indexed_files=len(engine.docs),
            max_file_size_bytes=max_file_size_bytes,
            skipped_large_files=len(skipped_large),
            skipped_paths=skipped_large,
            skipped_unreadable_files=len(unreadable),
            unreadable_paths=unreadable,
            skipped_symlink_outside_repository=len(outside_root),
            symlink_outside_repository_paths=outside_root,
            max_files=max_files,
            max_files_reached=max_files_reached,
        )
        if outside_root:
            logger.warning(
                "RepoNeedle skipped %d linked file(s) that resolve outside the repository root "
                "(reason: symlink_outside_repository); their targets were not read. See indexing "
                "diagnostics (symlink_outside_repository_paths) for the in-repository link paths.",
                len(outside_root),
            )

        # Summaries only (counts + limit): no paths or contents in log records.
        if skipped_large:
            logger.warning(
                "RepoNeedle skipped %d file(s) larger than max_file_size_bytes=%d; they are not "
                "indexed or searchable. See indexing diagnostics (skipped_paths) for details.",
                len(skipped_large),
                max_file_size_bytes,
            )
        if unreadable:
            logger.warning(
                "RepoNeedle could not read %d file(s) during indexing. See indexing diagnostics "
                "(unreadable_paths) for details.",
                len(unreadable),
            )
        if max_files_reached:
            logger.warning(
                "RepoNeedle stopped indexing at max_files=%d; remaining files were not indexed.",
                max_files,
            )

        return engine

    def retrieve(
        self,
        query: Union[str, Query],
        budget_tokens: Optional[int] = None,
        task_type: Optional[TaskType] = None,
        ablation_config: Optional[AblationConfig] = None,
        ranker: Optional[Union[str, RankerType]] = None,
        ranking_engine: Optional[Union[str, RankerType]] = None,
        change_impact_config: Optional[ChangeImpactConfig] = None,
        anchor_files: Optional[List[str]] = None,
        enable_experimental_abstention: Optional[bool] = None,
    ) -> RetrievalResult:
        """
        Executes workflow-adaptive retrieval and packs results within the token budget.
        Supports controlled ablation overrides and modular ranker architectures.

        enable_experimental_abstention:
            Per-call override for the experimental, uncalibrated abstention heuristic.
            None (default) uses ``budget_config.enable_experimental_abstention`` (False unless
            configured). Passing ``task_type=TaskType.SELECTIVE`` does NOT enable abstention.
            Empty repositories always return an abstained result regardless of this flag.
        """
        start_time = time.perf_counter()
        ablation = ablation_config or self.ablation_config or AblationConfig()
        if enable_experimental_abstention is None:
            abstention_enabled = bool(getattr(self.budget_config, "enable_experimental_abstention", False))
        else:
            abstention_enabled = bool(enable_experimental_abstention)
        abstention_threshold = float(self.abstainer.confidence_threshold)

        raw_ranker = ranking_engine if ranking_engine is not None else ranker
        if raw_ranker is not None:
            if isinstance(raw_ranker, RankerType):
                effective_ranker = raw_ranker.value.lower()
            else:
                effective_ranker = str(raw_ranker).lower()
        else:
            effective_ranker = self.ranker.value.lower() if isinstance(self.ranker, RankerType) else str(self.ranker).lower()

        if effective_ranker not in ("legacy", "bm25", "arm101", "cascade", "change_impact"):
            raise ValueError(
                f"Unknown ranker '{effective_ranker}'. Valid rankers are: 'legacy', 'bm25', 'arm101', 'cascade', 'change_impact'."
            )

        if anchor_files:
            norm_anchors = [a.replace("\\", "/") for a in anchor_files]
            if isinstance(query, str):
                query_obj = Query(text=query, anchor_files=norm_anchors)
            else:
                query_obj = query
                query_obj.anchor_files = norm_anchors
        elif isinstance(query, str):
            query_obj = Query(text=query)
        else:
            query_obj = query
            if query_obj.anchor_files:
                query_obj.anchor_files = [a.replace("\\", "/") for a in query_obj.anchor_files]

        if task_type:
            query_obj.task_type = task_type
        if budget_tokens:
            query_obj.budget_tokens = budget_tokens

        eff_budget = query_obj.budget_tokens or self.budget_config.max_tokens

        # Handle empty repository edge case
        if not self.docs:
            return RetrievalResult(
                query=query_obj.text,
                task_type=TaskType.COMMENT2CONTEXT,
                abstained=True,
                confidence_score=0.0,
                selected_files=[],
                total_tokens=0,
                budget_tokens=eff_budget,
                candidate_count=0,
                explanation="Repository contains no candidate files.",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                ranker=effective_ranker,
                ranked_files=[],
                abstention=AbstentionDiagnostics(
                    enabled=abstention_enabled,
                    status="empty_repository",
                    threshold=abstention_threshold,
                    reason="Repository contains no candidate files (structural; independent of the experimental heuristic).",
                ),
            )

        num_docs = len(self.docs)

        # 1. Base Signal Scoring (Factors A, B)
        lex_scores = self.lexical_index.score(query_obj.text) if ablation.enable_lexical else np.zeros(num_docs, dtype=np.float32)

        cand_indices = None
        if ablation.candidate_pool_size is not None and ablation.candidate_pool_size > 0:
            if num_docs > ablation.candidate_pool_size:
                cand_indices = np.argsort(-lex_scores)[: ablation.candidate_pool_size]

        sem_scores = self.semantic_index.score(query_obj.text, candidate_indices=cand_indices) if ablation.enable_semantic else np.zeros(num_docs, dtype=np.float32)

        # 2. Workflow Classification & Ranker Dispatch
        impact_exps: Dict[int, str] = {}
        if effective_ranker == "arm101":
            inferred_task = query_obj.task_type or TaskType.COMMENT2CONTEXT
            ranked_indices, fused_map = self.arm101_ranker.rank_with_scores(
                self.docs, lex_scores, sem_scores, self.function_graph, self.repo_graph
            )
            fused_scores = np.array([fused_map.get(i, 0.0) for i in range(num_docs)], dtype=np.float32)
            struct_scores = np.zeros(num_docs, dtype=np.float32)
            workflow_boosts = np.zeros(num_docs, dtype=np.float32)

        elif effective_ranker == "bm25":
            inferred_task = query_obj.task_type or TaskType.COMMENT2CONTEXT
            ranked_indices = sorted(range(num_docs), key=lambda i: (-float(lex_scores[i]), self.docs[i].path))
            fused_scores = lex_scores.copy()
            struct_scores = np.zeros(num_docs, dtype=np.float32)
            workflow_boosts = np.zeros(num_docs, dtype=np.float32)

        elif effective_ranker == "cascade":
            inferred_task = query_obj.task_type or TaskType.COMMENT2CONTEXT
            ranked_indices = self.cascaded_ranker.rank(
                self.docs, lex_scores, sem_scores, self.repo_graph, inferred_task.value if inferred_task else None
            )
            fused_scores = np.zeros(num_docs, dtype=np.float32)
            for r, idx in enumerate(ranked_indices):
                if float(lex_scores[idx]) > 0:
                    fused_scores[idx] = max(0.001, float(num_docs - r) / float(num_docs))
            struct_scores = np.zeros(num_docs, dtype=np.float32)
            workflow_boosts = np.zeros(num_docs, dtype=np.float32)

        elif effective_ranker == "change_impact":
            # Restores the behaviour of the published PyPI 1.1.0 wheel: AUTO queries report the
            # router-classified task; explicit task types are reported unchanged. Reporting only:
            # the change-impact ranker receives `query_obj`, which is not modified here.
            if query_obj.task_type == TaskType.AUTO:
                inferred_task, _ = self.router.classify_intent(query_obj)
            else:
                inferred_task = query_obj.task_type
            ci_cfg = change_impact_config or getattr(self, "change_impact_config", None) or ChangeImpactConfig()
            ranked_indices, fused_scores, impact_exps = self.change_impact_ranker.rank_with_scores(
                self.docs, lex_scores, sem_scores, query_obj, config_override=ci_cfg
            )
            struct_scores = np.zeros(num_docs, dtype=np.float32)
            workflow_boosts = np.zeros(num_docs, dtype=np.float32)

        else:  # "legacy"
            if ablation.enable_router:
                inferred_task, metadata = self.router.classify_intent(query_obj)
                weights = self.router.get_fusion_weights(inferred_task)
            else:
                inferred_task = TaskType.COMMENT2CONTEXT
                metadata = {}
                use_pr = ablation.enable_graph and getattr(ablation, "enable_pagerank_fusion", False)
                active_signals = sum([ablation.enable_lexical, ablation.enable_semantic, use_pr])
                base_w = 1.0 / max(1, active_signals)
                weights = {
                    "lexical": base_w if ablation.enable_lexical else 0.0,
                    "semantic": base_w if ablation.enable_semantic else 0.0,
                    "structural": base_w if use_pr else 0.0,
                    "workflow_boost": 0.0,
                }

            use_pr = ablation.enable_graph and getattr(ablation, "enable_pagerank_fusion", False)
            struct_scores = self.repo_graph.pagerank_scores if use_pr else np.zeros(num_docs, dtype=np.float32)
            workflow_boosts = np.zeros(num_docs, dtype=np.float32)

            if ablation.enable_router and weights.get("workflow_boost", 0.0) > 0.0:
                if inferred_task == TaskType.TRACE2CODE:
                    frames = metadata.get("trace_frames", [])
                    for frame_path, line_no, func_name in frames:
                        clean_frame = frame_path.replace("\\", "/").lower()
                        for idx, doc in enumerate(self.docs):
                            doc_lower = doc.path.lower()
                            if clean_frame.endswith(doc_lower) or doc_lower.endswith(clean_frame):
                                workflow_boosts[idx] = max(workflow_boosts[idx], 1.0)
                            elif func_name and func_name in doc.symbols:
                                workflow_boosts[idx] = max(workflow_boosts[idx], 0.7)

                elif inferred_task == TaskType.CODE2TEST:
                    if ablation.enable_graph:
                        top_target_indices = np.argsort(lex_scores + sem_scores)[::-1][:3]
                        target_paths = [
                            self.docs[i].path for i in top_target_indices
                            if not self.docs[i].is_test
                        ]
                        test_scores = self.repo_graph.get_test_scores_for_target(target_paths)
                    else:
                        test_scores = np.zeros(num_docs, dtype=np.float32)
                    for idx, doc in enumerate(self.docs):
                        if doc.is_test:
                            workflow_boosts[idx] = max(0.4, float(test_scores[idx]))
                        else:
                            workflow_boosts[idx] = -0.5

                elif inferred_task == TaskType.EDIT2RIPPLE:
                    if ablation.enable_graph:
                        anchors = query_obj.anchor_files
                        if not anchors:
                            top_idx = int(np.argmax(lex_scores)) if len(lex_scores) > 0 else 0
                            anchors = [self.docs[top_idx].path]
                        workflow_boosts = self.repo_graph.get_ripple_scores(anchors)

            fused_scores = (
                weights["lexical"] * lex_scores +
                weights["semantic"] * sem_scores +
                weights["structural"] * struct_scores +
                weights["workflow_boost"] * workflow_boosts
            )
            fused_scores = np.maximum(0.0, fused_scores)

            if cand_indices is not None:
                cand_mask = np.zeros(num_docs, dtype=bool)
                cand_mask[cand_indices] = True
                fused_scores[~cand_mask] = 0.0

            if ablation.enable_graph_diffusion and len(self.repo_graph.graph) > 0:
                combined_hits = (lex_scores + sem_scores) if (ablation.enable_lexical and ablation.enable_semantic) else (lex_scores if ablation.enable_lexical else sem_scores)
                if len(combined_hits) > 0 and float(np.max(combined_hits)) > 0:
                    top_seed_indices = np.argsort(combined_hits)[::-1][:5]
                    diffused_boost = np.zeros(num_docs, dtype=np.float32)
                    max_deg = getattr(ablation, "max_diffusion_degree", 25)
                    for s_idx in top_seed_indices:
                        seed_path = self.docs[s_idx].path
                        seed_val = float(combined_hits[s_idx])
                        if seed_val > 0 and seed_path in self.repo_graph.graph:
                            seed_deg = self.repo_graph.graph.degree(seed_path)
                            if seed_deg <= max_deg:
                                for succ in self.repo_graph.graph.successors(seed_path):
                                    if succ in self.repo_graph.path_to_idx and self.repo_graph.graph.degree(succ) <= max_deg:
                                        n_idx = self.repo_graph.path_to_idx[succ]
                                        diffused_boost[n_idx] = max(diffused_boost[n_idx], float(seed_val * 0.25))
                                for pred in self.repo_graph.graph.predecessors(seed_path):
                                    if pred in self.repo_graph.path_to_idx and self.repo_graph.graph.degree(pred) <= max_deg:
                                        n_idx = self.repo_graph.path_to_idx[pred]
                                        diffused_boost[n_idx] = max(diffused_boost[n_idx], float(seed_val * 0.20))
                    fused_scores = fused_scores + 0.15 * diffused_boost

            if ablation.enable_doc_filter:
                for idx, doc in enumerate(self.docs):
                    p_lower = doc.path.lower()
                    if any(seg in p_lower for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or p_lower.endswith((".md", ".rst", ".txt", ".adoc", ".html")):
                        fused_scores[idx] *= ablation.doc_filter_penalty

            ranked_indices = sorted(range(num_docs), key=lambda idx: (-float(fused_scores[idx]), self.docs[idx].path))

        ranked_paths = [self.docs[i].path for i in ranked_indices]

        # 3. Experimental Selective Abstention Check (opt-in only).
        # The heuristic score is always computed so `confidence_score` keeps its existing meaning
        # (an uncalibrated signal), but it only decides the outcome when explicitly enabled.
        heuristic_abstained, confidence, reason = self.abstainer.evaluate_abstention(
            query=query_obj.text,
            fused_scores=fused_scores,
        )

        exec_time = (time.perf_counter() - start_time) * 1000

        if abstention_enabled:
            abstention_diag = AbstentionDiagnostics(
                enabled=True,
                status="evaluated",
                threshold=abstention_threshold,
                reason=reason,
            )
            outcome_note = f"Experimental abstention check passed (uncalibrated heuristic): {reason}"
        else:
            abstention_diag = AbstentionDiagnostics(
                enabled=False,
                status="disabled",
                threshold=abstention_threshold,
                reason=(
                    "Experimental abstention disabled (default); out-of-scope queries are not "
                    "detected and results are returned regardless of query scope."
                ),
            )
            outcome_note = "Experimental abstention disabled."

        if abstention_enabled and heuristic_abstained:
            return RetrievalResult(
                query=query_obj.text,
                task_type=inferred_task,
                abstained=True,
                confidence_score=confidence,
                selected_files=[],
                total_tokens=0,
                budget_tokens=eff_budget,
                candidate_count=num_docs,
                explanation=f"Abstained: {reason} (Experimental abstention heuristic; not production-calibrated.)",
                execution_time_ms=exec_time,
                ranker=effective_ranker,
                ranked_files=ranked_paths,
                abstention=abstention_diag,
            )

        # 4. Budget-Aware Context Packing (ordered by ranked_indices)
        query_terms = self.tokenizer.tokenize_text(query_obj.text)
        candidates_with_scores = []
        for idx in ranked_indices:
            doc = self.docs[idx]
            c_scores = {
                "lexical": float(lex_scores[idx]),
                "semantic": float(sem_scores[idx]),
                "structural": float(struct_scores[idx]),
                "workflow_boost": float(workflow_boosts[idx]),
            }
            candidates_with_scores.append((doc, float(fused_scores[idx]), c_scores))

        selected = self.budget_optimizer.pack_context(
            candidate_files=candidates_with_scores,
            budget_tokens=eff_budget,
            query_text=query_obj.text,
            query_terms=query_terms,
            allow_skeletons=ablation.allow_skeletons,
            mode=self.budget_config.mode if self.budget_config.mode != "auto" else ("complete" if ablation_config is not None else None),
        )

        total_tokens_used = sum(s.token_count for s in selected)
        rendered_context = self.budget_optimizer.tokenizer.render_prompt(selected)

        if effective_ranker == "change_impact" and impact_exps:
            path_to_exp = {self.docs[i].path: exp for i, exp in impact_exps.items()}
            for sf in selected:
                if sf.path in path_to_exp and path_to_exp[sf.path]:
                    sf.explanation = path_to_exp[sf.path]

        return RetrievalResult(
            query=query_obj.text,
            task_type=inferred_task,
            abstained=False,
            confidence_score=confidence,
            selected_files=selected,
            total_tokens=total_tokens_used,
            budget_tokens=eff_budget,
            candidate_count=num_docs,
            explanation=f"Retrieved {len(selected)} files ({total_tokens_used}/{eff_budget} tokens). Ranker: {effective_ranker}. Task: {inferred_task.value}. {outcome_note}",
            execution_time_ms=(time.perf_counter() - start_time) * 1000,
            ranker=effective_ranker,
            ranked_files=ranked_paths,
            rendered_context=rendered_context,
            abstention=abstention_diag,
        )
