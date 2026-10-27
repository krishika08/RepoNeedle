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
    ):
        self.budget_config = budget_config or BudgetConfig()
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
        self.docs = docs
        self.path_to_doc = {d.path: d for d in docs}
        self.lexical_index.fit(docs)
        self.semantic_index.fit(docs)
        self.repo_graph.fit(docs)
        self.abstainer.fit(docs)

    @classmethod
    def from_documents(
        cls,
        docs: List[FileDoc],
        budget_config: Optional[BudgetConfig] = None,
    ) -> "RepoNeedleEngine":
        """
        Instantiates engine from an in-memory list of FileDoc instances.
        """
        return cls(docs=docs, budget_config=budget_config)

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

                # AST symbol extraction for Python
                symbols, imports = [], []
                if ext == ".py":
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

        return cls(docs=docs, budget_config=budget_config)

    def retrieve(
        self,
        query: Union[str, Query],
        budget_tokens: Optional[int] = None,
        task_type: Optional[TaskType] = None,
    ) -> RetrievalResult:
        """
        Executes workflow-adaptive retrieval and packs results within the token budget.
        """
        start_time = time.perf_counter()

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

        # 1. Workflow Classification
        inferred_task, metadata = self.router.classify_intent(query_obj)
        weights = self.router.get_fusion_weights(inferred_task)

        # 2. Base Signal Scoring
        lex_scores = self.lexical_index.score(query_obj.text)
        sem_scores = self.semantic_index.score(query_obj.text)
        struct_scores = self.repo_graph.pagerank_scores

        num_docs = len(self.docs)
        workflow_boosts = np.zeros(num_docs, dtype=np.float32)

        # 3. Workflow-Specific Boosts
        if inferred_task == TaskType.TRACE2CODE:
            # Boost files matching frames in the traceback
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
            # Find candidate implementation targets from lexical/semantic scores
            top_target_indices = np.argsort(lex_scores + sem_scores)[::-1][:3]
            target_paths = [
                self.docs[i].path for i in top_target_indices
                if not self.docs[i].is_test
            ]
            test_scores = self.repo_graph.get_test_scores_for_target(target_paths)
            for idx, doc in enumerate(self.docs):
                if doc.is_test:
                    # Give baseline boost to tests for code2test plus linkage boost
                    workflow_boosts[idx] = max(0.4, float(test_scores[idx]))
                else:
                    # Penalize non-test files in code2test mode
                    workflow_boosts[idx] = -0.5

        elif inferred_task == TaskType.EDIT2RIPPLE:
            anchors = query_obj.anchor_files
            if not anchors:
                # Infer anchors from top lexical matches
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

        # 6. Budget-Aware Context Packing
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

