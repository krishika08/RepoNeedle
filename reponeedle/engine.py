"""
Main RepoNeedle Engine API.
Provides an integrated, token-budget-aware repository context retrieval system.
"""

import os
import time
from typing import List, Optional, Union, Dict, Set
import numpy as np
import pathspec

from reponeedle.models import (
    FileDoc,
    Query,
    RetrievalResult,
    ScoredFile,
    TaskType,
    BudgetConfig,
    AblationConfig,
    ContextTier,
)
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


class RepoNeedleEngine:
    """
    High-performance, workflow-adaptive repository context retrieval engine.
    """

    def __init__(
        self,
        docs: List[FileDoc] = None,
        budget_config: Optional[BudgetConfig] = None,
        ablation_config: Optional[AblationConfig] = None,
    ):
        self.budget_config = budget_config or BudgetConfig()
        self.ablation_config = ablation_config or AblationConfig()
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
        self.abstainer.fit(clean_docs)

    @classmethod
    def from_documents(
        cls,
        docs: List[FileDoc],
        budget_config: Optional[BudgetConfig] = None,
        ablation_config: Optional[AblationConfig] = None,
    ) -> "RepoNeedleEngine":
        """
        Instantiates engine from an in-memory list of FileDoc instances.
        """
        return cls(docs=docs, budget_config=budget_config, ablation_config=ablation_config)

    @classmethod
    def from_directory(
        cls,
        repo_dir: str,
        budget_config: Optional[BudgetConfig] = None,
        max_files: int = 3000,
        extra_ignore: List[str] = None,
    ) -> "RepoNeedleEngine":
        """
        Scans a local repository directory, parses files, and builds the retrieval index.
        """
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
                try:
                    # Skip large files (> 500KB)
                    if os.path.getsize(full_path) > 500_000:
                        continue
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception:
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
                    break
            if len(docs) >= max_files:
                break

        return cls(docs=docs, budget_config=budget_config, ablation_config=ablation_config)

    def retrieve(
        self,
        query: Union[str, Query],
        budget_tokens: Optional[int] = None,
        task_type: Optional[TaskType] = None,
        ablation_config: Optional[AblationConfig] = None,
    ) -> RetrievalResult:
        """
        Executes workflow-adaptive retrieval and packs results within the token budget.
        Supports controlled ablation overrides.
        """
        start_time = time.perf_counter()
        ablation = ablation_config or self.ablation_config or AblationConfig()

        if isinstance(query, str):
            query_obj = Query(text=query)
        else:
            query_obj = query

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
            )

        num_docs = len(self.docs)

        # 1. Workflow Classification / Fusion Weights (Factor D)
        if ablation.enable_router:
            inferred_task, metadata = self.router.classify_intent(query_obj)
            weights = self.router.get_fusion_weights(inferred_task)
        else:
            # Documented fixed static fusion: equal weighting among active signals, zero task boost
            inferred_task = TaskType.COMMENT2CONTEXT
            metadata = {}
            active_signals = sum([ablation.enable_lexical, ablation.enable_semantic, ablation.enable_graph])
            base_w = 1.0 / max(1, active_signals)
            weights = {
                "lexical": base_w if ablation.enable_lexical else 0.0,
                "semantic": base_w if ablation.enable_semantic else 0.0,
                "structural": base_w if ablation.enable_graph else 0.0,
                "workflow_boost": 0.0,
            }

        # 2. Base Signal Scoring (Factors A, B, C)
        lex_scores = self.lexical_index.score(query_obj.text) if ablation.enable_lexical else np.zeros(num_docs, dtype=np.float32)
        sem_scores = self.semantic_index.score(query_obj.text) if ablation.enable_semantic else np.zeros(num_docs, dtype=np.float32)
        struct_scores = self.repo_graph.pagerank_scores if ablation.enable_graph else np.zeros(num_docs, dtype=np.float32)

        workflow_boosts = np.zeros(num_docs, dtype=np.float32)

        # 3. Workflow-Specific Boosts (Active only when router is enabled)
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

        # 4. Fused Score Computation
        fused_scores = (
            weights["lexical"] * lex_scores +
            weights["semantic"] * sem_scores +
            weights["structural"] * struct_scores +
            weights["workflow_boost"] * workflow_boosts
        )
        fused_scores = np.maximum(0.0, fused_scores)

        # 4b. Relevance-Aware Graph Diffusion (Candidate D / E)
        if ablation.enable_graph_diffusion and len(self.repo_graph.graph) > 0:
            combined_hits = (lex_scores + sem_scores) if (ablation.enable_lexical and ablation.enable_semantic) else (lex_scores if ablation.enable_lexical else sem_scores)
            if len(combined_hits) > 0 and float(np.max(combined_hits)) > 0:
                top_seed_indices = np.argsort(combined_hits)[::-1][:5]
                diffused_boost = np.zeros(num_docs, dtype=np.float32)
                for s_idx in top_seed_indices:
                    seed_path = self.docs[s_idx].path
                    seed_val = float(combined_hits[s_idx])
                    if seed_val > 0 and seed_path in self.repo_graph.graph:
                        for neighbor in self.repo_graph.graph.neighbors(seed_path):
                            if neighbor in self.repo_graph.path_to_idx:
                                n_idx = self.repo_graph.path_to_idx[neighbor]
                                diffused_boost[n_idx] = max(diffused_boost[n_idx], float(seed_val * 0.25))
                fused_scores = fused_scores + 0.15 * diffused_boost

        # 4c. Documentation Distractor Filter (Candidate C / D / E)
        if ablation.enable_doc_filter:
            for idx, doc in enumerate(self.docs):
                p_lower = doc.path.lower()
                if any(seg in p_lower for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or p_lower.endswith((".md", ".rst", ".txt", ".adoc", ".html")):
                    fused_scores[idx] *= ablation.doc_filter_penalty

        # 5. Selective Abstention Check
        abstained, confidence, reason = self.abstainer.evaluate_abstention(
            query=query_obj.text,
            fused_scores=fused_scores,
        )

        exec_time = (time.perf_counter() - start_time) * 1000

        if abstained:
            return RetrievalResult(
                query=query_obj.text,
                task_type=inferred_task,
                abstained=True,
                confidence_score=confidence,
                selected_files=[],
                total_tokens=0,
                budget_tokens=eff_budget,
                candidate_count=num_docs,
                explanation=f"Abstained: {reason}",
                execution_time_ms=exec_time,
            )

        # 6. Budget-Aware Context Packing (Factor E)
        query_terms = self.tokenizer.tokenize_text(query_obj.text)
        candidates_with_scores = []
        for idx, doc in enumerate(self.docs):
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
            query_terms=query_terms,
            allow_skeletons=ablation.allow_skeletons,
        )

        total_tokens_used = sum(s.token_count for s in selected)

        return RetrievalResult(
            query=query_obj.text,
            task_type=inferred_task,
            abstained=False,
            confidence_score=confidence,
            selected_files=selected,
            total_tokens=total_tokens_used,
            budget_tokens=eff_budget,
            candidate_count=num_docs,
            explanation=f"Retrieved {len(selected)} files ({total_tokens_used}/{eff_budget} tokens). Task: {inferred_task.value}. {reason}",
            execution_time_ms=exec_time,
        )

