"""
Stage 3.9: Cascaded Lexical-First Retrieval Architecture.

Implements a controlled, rank-preserving cascade:
  1. Computes base BM25 lexical ranking with deterministic tie-breaking.
  2. Preserves the top-3 BM25 results and their exact relative order (protecting early MRR).
  3. Applies degree-normalized, bounded graph expansion only to eligible ranks (>= 4).
  4. Enforces package and workspace boundary fencing to reject spurious cross-package edges.
  5. Implements evidence-backed test-to-implementation discovery for code2test workflows.
  6. 100% deterministic ranking and fully ablatable configuration flags.
"""

from __future__ import annotations

import os
import math
from typing import List, Tuple, Dict, Set, Optional, Any
import numpy as np

from reponeedle.models import FileDoc


class CascadedRanker:
    """
    Controlled lexical-first cascaded ranker that protects high-confidence
    BM25 results while leveraging bounded graph expansion for remaining ranks.
    """

    def __init__(
        self,
        top_k_preserve: int = 3,
        enable_graph_expansion: bool = True,
        degree_normalized: bool = True,
        package_fencing: bool = True,
        test_discovery: bool = True,
        doc_filter_penalty: float = 0.5,
        graph_weight: float = 0.25,
        enable_class_to_test: bool = False,
        enable_degree_matched_control: bool = False,
        class_to_test_weight: float = 0.35,
    ):
        self.top_k_preserve = top_k_preserve
        self.enable_graph_expansion = enable_graph_expansion
        self.degree_normalized = degree_normalized
        self.package_fencing = package_fencing
        self.test_discovery = test_discovery
        self.doc_filter_penalty = doc_filter_penalty
        self.graph_weight = graph_weight
        self.enable_class_to_test = enable_class_to_test
        self.enable_degree_matched_control = enable_degree_matched_control
        self.class_to_test_weight = class_to_test_weight

    def rank(
        self,
        docs: List[FileDoc],
        bm25_scores: np.ndarray,
        semantic_scores: Optional[np.ndarray] = None,
        repo_graph: Optional[Any] = None,
        task_type: Optional[str] = None,
    ) -> List[int]:
        """
        Executes cascaded ranking over documents, returning sorted document indices.
        Guarantees that the top-K BM25 indices remain in positions 0..(K-1) in identical order.
        """
        n_docs = len(docs)
        if n_docs == 0:
            return []
        if n_docs <= self.top_k_preserve:
            # When total documents <= preserve window, sort purely by BM25
            return sorted(range(n_docs), key=lambda i: (-float(bm25_scores[i]), docs[i].path))

        # 1. Deterministic BM25 base ranking
        bm25_order = sorted(range(n_docs), key=lambda i: (-float(bm25_scores[i]), docs[i].path))

        # 2. Top-K Lexical Freeze
        k = min(self.top_k_preserve, n_docs)
        protected_indices = bm25_order[:k]
        eligible_indices = bm25_order[k:]
        eligible_set = set(eligible_indices)

        # Base candidate scores for eligible files
        sem = semantic_scores if semantic_scores is not None else np.zeros(n_docs, dtype=np.float32)

        # 3. Graph Expansion on Eligible Candidates
        graph_boost = np.zeros(n_docs, dtype=np.float32)

        if self.enable_graph_expansion and repo_graph is not None and len(repo_graph.graph) > 0:
            g = repo_graph.graph
            path_to_idx = repo_graph.path_to_idx

            # Seeds are the protected top-K lexical hits
            seeds = protected_indices
            for s_idx in seeds:
                seed_doc = docs[s_idx]
                seed_p = seed_doc.path
                seed_score = float(bm25_scores[s_idx])
                if seed_score <= 0.0 or seed_p not in g:
                    continue

                seed_dir = os.path.dirname(seed_p.replace("\\", "/"))
                out_deg = max(1, g.out_degree(seed_p))
                in_deg_seed = max(1, g.in_degree(seed_p))

                # A. Successor propagation (dependencies / callees)
                for succ in g.successors(seed_p):
                    if succ in path_to_idx:
                        n_idx = path_to_idx[succ]
                        if n_idx in eligible_set:
                            # Package boundary check
                            if self.package_fencing:
                                succ_dir = os.path.dirname(succ.replace("\\", "/"))
                                # Allow if same directory, or if child/parent, or common root crate/pkg
                                if not self._is_package_compatible(seed_dir, succ_dir, seed_p, succ, repo_graph):
                                    continue

                            if self.degree_normalized:
                                in_deg_succ = max(1, g.in_degree(succ))
                                norm_factor = 1.0 / math.sqrt(out_deg * in_deg_succ)
                                boost_val = seed_score * 0.25 * norm_factor
                            else:
                                boost_val = seed_score * 0.25

                            graph_boost[n_idx] = max(graph_boost[n_idx], float(boost_val))

                # B. Predecessor propagation (callers / importers, strictly attenuated)
                for pred in g.predecessors(seed_p):
                    if pred in path_to_idx:
                        n_idx = path_to_idx[pred]
                        if n_idx in eligible_set:
                            if self.package_fencing:
                                pred_dir = os.path.dirname(pred.replace("\\", "/"))
                                if not self._is_package_compatible(seed_dir, pred_dir, seed_p, pred, repo_graph):
                                    continue

                            if self.degree_normalized:
                                out_deg_pred = max(1, g.out_degree(pred))
                                norm_factor = 1.0 / math.sqrt(in_deg_seed * out_deg_pred)
                                boost_val = seed_score * 0.10 * norm_factor
                            else:
                                boost_val = seed_score * 0.20

                            graph_boost[n_idx] = max(graph_boost[n_idx], float(boost_val))

                # C. Test-to-Implementation Discovery for code2test workflows
                if self.test_discovery:
                    self._apply_test_discovery(seed_p, seed_score, eligible_set, path_to_idx, docs, graph_boost)

                # D. Class-to-Test Invocation Linkage (Stage 3.10)
                if self.enable_class_to_test:
                    self._apply_class_to_test_invocation(seed_p, seed_score, eligible_set, path_to_idx, docs, repo_graph, graph_boost)

        # 4. Score Fusion for Ranks >= K
        # Normalizes signals and applies doc filter penalty
        rerank_scores = {}
        for idx in eligible_indices:
            doc = docs[idx]
            b_score = float(bm25_scores[idx])
            s_score = float(sem[idx])
            g_score = float(graph_boost[idx])

            # Fused score for eligible pool
            score = 0.60 * b_score + 0.15 * s_score + self.graph_weight * g_score

            # Documentation filter
            p_lower = doc.path.lower()
            if any(seg in p_lower for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or p_lower.endswith((".md", ".rst", ".txt", ".adoc", ".html")):
                score *= self.doc_filter_penalty

            rerank_scores[idx] = score

        # 5. Deterministic sorting of eligible candidates
        reranked_eligible = sorted(
            eligible_indices,
            key=lambda idx: (-rerank_scores[idx], docs[idx].path)
        )

        # Return protected top-K followed by cascaded candidates
        return protected_indices + reranked_eligible

    def _is_package_compatible(
        self,
        dir_a: str,
        dir_b: str,
        path_a: str,
        path_b: str,
        repo_graph: Any,
    ) -> bool:
        """Verifies if two files share package context or explicit manifest dependencies."""
        if dir_a == dir_b:
            return True
        # Check subdirectories
        if dir_a.startswith(dir_b) or dir_b.startswith(dir_a):
            return True
        # Check manifest dependencies
        crates = getattr(repo_graph, "manifest_crates", {})
        crate_a = None
        crate_b = None
        for cname, cdir in crates.items():
            if path_a.startswith(cdir):
                crate_a = cname
            if path_b.startswith(cdir):
                crate_b = cname
        if crate_a and crate_b and crate_a == crate_b:
            return True
        crate_deps = getattr(repo_graph, "crate_dependencies", {})
        if crate_a and crate_b:
            if crate_b in crate_deps.get(crate_a, set()) or crate_a in crate_deps.get(crate_b, set()):
                return True
        return False

    def _apply_test_discovery(
        self,
        seed_path: str,
        seed_score: float,
        eligible_set: Set[int],
        path_to_idx: Dict[str, int],
        docs: List[FileDoc],
        graph_boost: np.ndarray,
    ):
        """Discovers corresponding test files using multi-language naming conventions."""
        norm_p = seed_path.replace("\\", "/")
        stem = os.path.splitext(os.path.basename(norm_p))[0]
        ext = os.path.splitext(norm_p)[1].lower()
        cur_dir = os.path.dirname(norm_p)

        test_candidates = []
        if ext == ".go":
            test_candidates.append(f"{cur_dir}/{stem}_test.go" if cur_dir else f"{stem}_test.go")
        elif ext in (".py", ".pyi"):
            test_candidates.append(f"{cur_dir}/test_{stem}.py" if cur_dir else f"test_{stem}.py")
            test_candidates.append(f"tests/test_{stem}.py")
            test_candidates.append(f"tests/{stem}_test.py")
        elif ext in (".rs",):
            test_candidates.append(f"tests/{stem}.rs")
            test_candidates.append(f"tests/test_{stem}.rs")
        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            test_candidates.append(f"{cur_dir}/{stem}.test{ext}" if cur_dir else f"{stem}.test{ext}")
            test_candidates.append(f"{cur_dir}/__tests__/{stem}.test{ext}" if cur_dir else f"__tests__/{stem}.test{ext}")

        for tc in test_candidates:
            if tc in path_to_idx:
                idx = path_to_idx[tc]
                if idx in eligible_set:
                    graph_boost[idx] = max(graph_boost[idx], float(seed_score * 0.35))


    def _apply_class_to_test_invocation(
        self,
        seed_path: str,
        seed_score: float,
        eligible_set: Set[int],
        path_to_idx: Dict[str, int],
        docs: List[FileDoc],
        repo_graph: Any,
        graph_boost: np.ndarray,
    ):
        """
        Propagates relevance between production files and test files via evidence-backed
        class and method invocation relationships.
        """
        if not repo_graph:
            return

        if self.enable_degree_matched_control:
            prod_to_tests = getattr(repo_graph, "degree_matched_prod_to_test", {})
            test_to_prods = getattr(repo_graph, "degree_matched_test_to_prod", {})
        else:
            prod_to_tests = getattr(repo_graph, "prod_to_test_invocations", {})
            test_to_prods = getattr(repo_graph, "test_to_prod_invocations", {})

        # If seed is production file, find test files that invoke it
        if seed_path in prod_to_tests:
            target_tests = prod_to_tests[seed_path]
            out_deg = max(1, len(target_tests))
            for test_p in target_tests:
                if test_p in path_to_idx:
                    t_idx = path_to_idx[test_p]
                    if t_idx in eligible_set:
                        in_deg = max(1, len(test_to_prods.get(test_p, {seed_path})))
                        norm_factor = 1.0 / math.sqrt(out_deg * in_deg) if self.degree_normalized else 1.0
                        boost = seed_score * self.class_to_test_weight * norm_factor
                        graph_boost[t_idx] = max(graph_boost[t_idx], float(boost))

        # If seed is test file, find production files whose classes it exercises
        if seed_path in test_to_prods:
            target_prods = test_to_prods[seed_path]
            out_deg = max(1, len(target_prods))
            for prod_p in target_prods:
                if prod_p in path_to_idx:
                    p_idx = path_to_idx[prod_p]
                    if p_idx in eligible_set:
                        in_deg = max(1, len(prod_to_tests.get(prod_p, {seed_path})))
                        norm_factor = 1.0 / math.sqrt(out_deg * in_deg) if self.degree_normalized else 1.0
                        boost = seed_score * self.class_to_test_weight * norm_factor
                        graph_boost[p_idx] = max(graph_boost[p_idx], float(boost))
