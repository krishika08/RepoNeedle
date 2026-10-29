"""
Stage 3.12: Factorial Graph Retrieval Engine.

Implements the 2^3 factorial ranking architecture with:
  - Factor A: Soft Lexical Damping (dynamic margin gate replacing rigid Rank 1-3 freeze)
  - Factor B: In-Degree Hub Attenuation (inverse logarithmic in-degree penalty: 1 / log2(2 + deg_in))
  - Factor C: Verified Call Edges Only (excluding noisy structural/heuristic method edges)
"""

from __future__ import annotations

import os
import math
from typing import List, Dict, Set, Tuple, Optional, Any
from collections import defaultdict
import networkx as nx
import numpy as np

from reponeedle.models import FileDoc
from research.stage3_11.function_graph_engine import (
    FunctionGraphEngine,
    FunctionSymbol,
    CallSite,
    FunctionGraphEdge,
)


class FactorialCascadedRanker:
    """
    Cascaded retrieval ranker supporting the 2^3 factorial experimental matrix
    and historical control baselines.
    """

    def __init__(
        self,
        mode: str = "factorial",  # 'bm25', 'control', 'factorial', 'no_freeze'
        factor_a_soft_damping: bool = False,
        factor_b_hub_attenuation: bool = False,
        factor_c_verified_only: bool = False,
        soft_damping_tau: float = 0.25,
        forward_weight: float = 0.25,
        reverse_weight: float = 0.20,
        degree_normalized: bool = True,
        package_fencing: bool = True,
        doc_filter_penalty: float = 0.50,
        graph_weight: float = 0.25,
        class_to_test_weight: float = 0.35,
    ):
        self.mode = mode
        self.factor_a_soft_damping = factor_a_soft_damping
        self.factor_b_hub_attenuation = factor_b_hub_attenuation
        self.factor_c_verified_only = factor_c_verified_only
        self.soft_damping_tau = soft_damping_tau

        self.forward_weight = forward_weight
        self.reverse_weight = reverse_weight
        self.degree_normalized = degree_normalized
        self.package_fencing = package_fencing
        self.doc_filter_penalty = doc_filter_penalty
        self.graph_weight = graph_weight
        self.class_to_test_weight = class_to_test_weight

    def rank(
        self,
        docs: List[FileDoc],
        bm25_scores: np.ndarray,
        semantic_scores: Optional[np.ndarray] = None,
        function_graph: Optional[FunctionGraphEngine] = None,
        repo_graph: Optional[Any] = None,
        task_type: Optional[str] = None,
    ) -> List[int]:
        """Executes ranking over candidate documents under configured factorial arm."""
        n_docs = len(docs)
        if n_docs == 0:
            return []

        # 1. Deterministic BM25 base ranking
        bm25_order = sorted(range(n_docs), key=lambda i: (-float(bm25_scores[i]), docs[i].path))

        # Mode BM25: pure lexical
        if self.mode == "bm25":
            return bm25_order

        # 2. Diffusion Seeds: always top 3 BM25 candidates
        seeds = bm25_order[:3]
        graph_boost = np.zeros(n_docs, dtype=np.float32)

        # Mode CONTROL (Stage 3.10 Control Cascade): file-level imports only, rigid freeze
        if self.mode == "control":
            if n_docs <= 3:
                return bm25_order
            protected_indices = bm25_order[:3]
            eligible_indices = bm25_order[3:]
            eligible_set = set(eligible_indices)

            if repo_graph is not None and len(repo_graph.graph) > 0:
                self._propagate_repograph(seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost, apply_hub_atten=False)
                self._propagate_class_to_test(seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost, apply_hub_atten=False)

            return self._fuse_and_sort_rigid(docs, bm25_scores, semantic_scores, graph_boost, protected_indices, eligible_indices)

        # Mode NO_FREEZE (Stage 3.11 Exploratory Reference): full function graph, no freeze, no damping
        if self.mode == "no_freeze":
            eligible_set = set(range(n_docs))
            if repo_graph is not None and len(repo_graph.graph) > 0:
                self._propagate_repograph(seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost, apply_hub_atten=False)
                self._propagate_class_to_test(seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost, apply_hub_atten=False)
            if function_graph is not None and len(function_graph.graph) > 0:
                self._propagate_function_graph(
                    seeds, docs, bm25_scores, eligible_set, function_graph, graph_boost,
                    verified_only=False, apply_hub_atten=False
                )
            return self._fuse_and_sort_unconstrained(docs, bm25_scores, semantic_scores, graph_boost, list(range(n_docs)))

        # Mode FACTORIAL: Configured by Factor A, B, C
        if not self.factor_a_soft_damping:
            # Factor A is OFF -> Rigid Rank 1-3 freeze
            if n_docs <= 3:
                return bm25_order
            protected_indices = bm25_order[:3]
            eligible_indices = bm25_order[3:]
            eligible_set = set(eligible_indices)

            # File-level base propagation
            if repo_graph is not None and len(repo_graph.graph) > 0:
                self._propagate_repograph(
                    seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost,
                    apply_hub_atten=self.factor_b_hub_attenuation
                )
                self._propagate_class_to_test(
                    seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost,
                    apply_hub_atten=self.factor_b_hub_attenuation
                )

            # Function graph propagation
            if function_graph is not None and len(function_graph.graph) > 0:
                self._propagate_function_graph(
                    seeds, docs, bm25_scores, eligible_set, function_graph, graph_boost,
                    verified_only=self.factor_c_verified_only,
                    apply_hub_atten=self.factor_b_hub_attenuation
                )

            return self._fuse_and_sort_rigid(docs, bm25_scores, semantic_scores, graph_boost, protected_indices, eligible_indices)

        else:
            # Factor A is ON -> Soft Lexical Damping with dynamic margin gating
            eligible_set = set(range(n_docs))

            # File-level base propagation
            if repo_graph is not None and len(repo_graph.graph) > 0:
                self._propagate_repograph(
                    seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost,
                    apply_hub_atten=self.factor_b_hub_attenuation
                )
                self._propagate_class_to_test(
                    seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost,
                    apply_hub_atten=self.factor_b_hub_attenuation
                )

            # Function graph propagation
            if function_graph is not None and len(function_graph.graph) > 0:
                self._propagate_function_graph(
                    seeds, docs, bm25_scores, eligible_set, function_graph, graph_boost,
                    verified_only=self.factor_c_verified_only,
                    apply_hub_atten=self.factor_b_hub_attenuation
                )

            return self._fuse_and_sort_soft_damping(
                docs, bm25_scores, semantic_scores, graph_boost, bm25_order
            )

    def _propagate_function_graph(
        self,
        seeds: List[int],
        docs: List[FileDoc],
        bm25_scores: np.ndarray,
        eligible_set: Set[int],
        fg: FunctionGraphEngine,
        graph_boost: np.ndarray,
        verified_only: bool,
        apply_hub_atten: bool,
    ):
        """Propagates scores along directed function-level call graph edges with optional hub attenuation."""
        path_to_idx = fg.path_to_idx
        allowed_types = {"verified_call", "unique_global_call", "intra_file_call"}
        if not verified_only:
            allowed_types.update({"structural_method_call", "directory_local_call"})

        for s_idx in seeds:
            seed_p = docs[s_idx].path
            seed_score = float(bm25_scores[s_idx])
            if seed_score <= 0.0 or seed_p not in fg.path_to_idx:
                continue

            seed_dir = os.path.dirname(seed_p.replace("\\", "/"))

            # 1. Forward propagation (Caller Seed -> Callee Candidate)
            callees = fg.callees_map.get(seed_p, {})
            out_deg = max(1, len(callees))
            for callee_p, conf in callees.items():
                if callee_p in path_to_idx:
                    c_idx = path_to_idx[callee_p]
                    if c_idx in eligible_set:
                        # Filter edge types
                        edges = fg.file_to_file_edges.get((seed_p, callee_p), [])
                        matching_edges = [e for e in edges if e.edge_type in allowed_types]
                        if not matching_edges:
                            continue
                        edge_conf = max(e.confidence for e in matching_edges)

                        # Package fencing
                        if self.package_fencing:
                            callee_dir = os.path.dirname(callee_p.replace("\\", "/"))
                            is_test_edge = docs[s_idx].is_test or docs[c_idx].is_test
                            if not is_test_edge and not self._is_package_compatible(seed_dir, callee_dir):
                                continue

                        in_deg = max(1, len(fg.callers_map.get(callee_p, {})))
                        norm_factor = 1.0 / math.sqrt(out_deg * in_deg) if self.degree_normalized else 1.0
                        boost = seed_score * self.forward_weight * edge_conf * norm_factor

                        # Factor B: In-Degree Hub Attenuation
                        if apply_hub_atten:
                            w_hub = 1.0 / math.log2(2.0 + in_deg)
                            boost *= w_hub

                        graph_boost[c_idx] = max(graph_boost[c_idx], float(boost))

            # 2. Reverse propagation (Callee Seed -> Caller Candidate)
            callers = fg.callers_map.get(seed_p, {})
            in_deg_seed = max(1, len(callers))
            for caller_p, conf in callers.items():
                if caller_p in path_to_idx:
                    c_idx = path_to_idx[caller_p]
                    if c_idx in eligible_set:
                        edges = fg.file_to_file_edges.get((caller_p, seed_p), [])
                        matching_edges = [e for e in edges if e.edge_type in allowed_types]
                        if not matching_edges:
                            continue
                        edge_conf = max(e.confidence for e in matching_edges)

                        if self.package_fencing:
                            caller_dir = os.path.dirname(caller_p.replace("\\", "/"))
                            is_test_edge = docs[s_idx].is_test or docs[c_idx].is_test
                            if not is_test_edge and not self._is_package_compatible(seed_dir, caller_dir):
                                continue

                        out_deg_caller = max(1, len(fg.callees_map.get(caller_p, {})))
                        norm_factor = 1.0 / math.sqrt(in_deg_seed * out_deg_caller) if self.degree_normalized else 1.0
                        boost = seed_score * self.reverse_weight * edge_conf * norm_factor

                        # Factor B: In-Degree Hub Attenuation on caller target
                        if apply_hub_atten:
                            in_deg_caller = max(1, len(fg.callers_map.get(caller_p, {})))
                            w_hub = 1.0 / math.log2(2.0 + in_deg_caller)
                            boost *= w_hub

                        graph_boost[c_idx] = max(graph_boost[c_idx], float(boost))

    def _propagate_repograph(
        self,
        seeds: List[int],
        docs: List[FileDoc],
        bm25_scores: np.ndarray,
        eligible_set: Set[int],
        repo_graph: Any,
        graph_boost: np.ndarray,
        apply_hub_atten: bool = False,
    ):
        """Propagates scores along file-level import graph edges."""
        g = repo_graph.graph
        path_to_idx = repo_graph.path_to_idx

        for s_idx in seeds:
            seed_p = docs[s_idx].path
            seed_score = float(bm25_scores[s_idx])
            if seed_score <= 0.0 or seed_p not in g:
                continue

            seed_dir = os.path.dirname(seed_p.replace("\\", "/"))
            out_deg = max(1, g.out_degree(seed_p))
            in_deg_seed = max(1, g.in_degree(seed_p))

            for succ in g.successors(seed_p):
                if succ in path_to_idx:
                    n_idx = path_to_idx[succ]
                    if n_idx in eligible_set:
                        if self.package_fencing:
                            succ_dir = os.path.dirname(succ.replace("\\", "/"))
                            if not self._is_package_compatible(seed_dir, succ_dir):
                                continue
                        in_deg_succ = max(1, g.in_degree(succ))
                        norm = 1.0 / math.sqrt(out_deg * in_deg_succ) if self.degree_normalized else 1.0
                        boost = seed_score * 0.25 * norm
                        if apply_hub_atten:
                            boost *= (1.0 / math.log2(2.0 + in_deg_succ))
                        graph_boost[n_idx] = max(graph_boost[n_idx], float(boost))

            for pred in g.predecessors(seed_p):
                if pred in path_to_idx:
                    n_idx = path_to_idx[pred]
                    if n_idx in eligible_set:
                        if self.package_fencing:
                            pred_dir = os.path.dirname(pred.replace("\\", "/"))
                            if not self._is_package_compatible(seed_dir, pred_dir):
                                continue
                        out_deg_pred = max(1, g.out_degree(pred))
                        norm = 1.0 / math.sqrt(in_deg_seed * out_deg_pred) if self.degree_normalized else 1.0
                        boost = seed_score * 0.10 * norm
                        if apply_hub_atten:
                            in_deg_pred = max(1, g.in_degree(pred))
                            boost *= (1.0 / math.log2(2.0 + in_deg_pred))
                        graph_boost[n_idx] = max(graph_boost[n_idx], float(boost))

            # Test discovery
            self._apply_test_discovery(seed_p, seed_score, eligible_set, path_to_idx, graph_boost)

    def _apply_test_discovery(self, seed_path: str, seed_score: float, eligible_set: Set[int], path_to_idx: Dict[str, int], graph_boost: np.ndarray):
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

    def _propagate_class_to_test(
        self,
        seeds: List[int],
        docs: List[FileDoc],
        bm25_scores: np.ndarray,
        eligible_set: Set[int],
        repo_graph: Any,
        graph_boost: np.ndarray,
        apply_hub_atten: bool = False,
    ):
        prod_to_tests = getattr(repo_graph, "prod_to_test_invocations", {})
        test_to_prods = getattr(repo_graph, "test_to_prod_invocations", {})
        path_to_idx = repo_graph.path_to_idx

        for s_idx in seeds:
            seed_p = docs[s_idx].path
            seed_score = float(bm25_scores[s_idx])
            if seed_score <= 0.0:
                continue

            if seed_p in prod_to_tests:
                target_tests = prod_to_tests[seed_p]
                out_deg = max(1, len(target_tests))
                for test_p in target_tests:
                    if test_p in path_to_idx:
                        t_idx = path_to_idx[test_p]
                        if t_idx in eligible_set:
                            in_deg = max(1, len(test_to_prods.get(test_p, {seed_p})))
                            norm = 1.0 / math.sqrt(out_deg * in_deg) if self.degree_normalized else 1.0
                            boost = seed_score * self.class_to_test_weight * norm
                            if apply_hub_atten:
                                boost *= (1.0 / math.log2(2.0 + in_deg))
                            graph_boost[t_idx] = max(graph_boost[t_idx], float(boost))

            if seed_p in test_to_prods:
                target_prods = test_to_prods[seed_p]
                out_deg = max(1, len(target_prods))
                for prod_p in target_prods:
                    if prod_p in path_to_idx:
                        p_idx = path_to_idx[prod_p]
                        if p_idx in eligible_set:
                            in_deg = max(1, len(prod_to_tests.get(prod_p, {seed_p})))
                            norm = 1.0 / math.sqrt(out_deg * in_deg) if self.degree_normalized else 1.0
                            boost = seed_score * self.class_to_test_weight * norm
                            if apply_hub_atten:
                                boost *= (1.0 / math.log2(2.0 + in_deg))
                            graph_boost[p_idx] = max(graph_boost[p_idx], float(boost))

    def _compute_fused_score(
        self,
        doc: FileDoc,
        b_score: float,
        s_score: float,
        g_boost: float,
    ) -> float:
        score = 0.60 * b_score + 0.15 * s_score + self.graph_weight * g_boost
        p_lower = doc.path.lower()
        if any(seg in p_lower for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or p_lower.endswith((".md", ".rst", ".txt", ".adoc", ".html")):
            score *= self.doc_filter_penalty
        return float(score)

    def _fuse_and_sort_rigid(
        self,
        docs: List[FileDoc],
        bm25_scores: np.ndarray,
        semantic_scores: Optional[np.ndarray],
        graph_boost: np.ndarray,
        protected_indices: List[int],
        eligible_indices: List[int],
    ) -> List[int]:
        n_docs = len(docs)
        sem = semantic_scores if semantic_scores is not None else np.zeros(n_docs, dtype=np.float32)

        rerank_scores = {}
        for idx in eligible_indices:
            rerank_scores[idx] = self._compute_fused_score(
                docs[idx], float(bm25_scores[idx]), float(sem[idx]), float(graph_boost[idx])
            )

        reranked_eligible = sorted(
            eligible_indices,
            key=lambda idx: (-rerank_scores[idx], docs[idx].path)
        )
        return protected_indices + reranked_eligible

    def _fuse_and_sort_unconstrained(
        self,
        docs: List[FileDoc],
        bm25_scores: np.ndarray,
        semantic_scores: Optional[np.ndarray],
        graph_boost: np.ndarray,
        all_indices: List[int],
    ) -> List[int]:
        n_docs = len(docs)
        sem = semantic_scores if semantic_scores is not None else np.zeros(n_docs, dtype=np.float32)

        rerank_scores = {}
        for idx in all_indices:
            rerank_scores[idx] = self._compute_fused_score(
                docs[idx], float(bm25_scores[idx]), float(sem[idx]), float(graph_boost[idx])
            )

        return sorted(
            all_indices,
            key=lambda idx: (-rerank_scores[idx], docs[idx].path)
        )

    def _fuse_and_sort_soft_damping(
        self,
        docs: List[FileDoc],
        bm25_scores: np.ndarray,
        semantic_scores: Optional[np.ndarray],
        graph_boost: np.ndarray,
        bm25_order: List[int],
    ) -> List[int]:
        """
        Factor A: Dynamic Lexical Margin Gating.
        Allows candidate to displace Rank 1 if and only if fused score exceeds Rank 1 fused score
        by tau * (BM25_1 - BM25_2). Candidates at ranks >= 2 are freely re-ranked by fused score.
        """
        n_docs = len(docs)
        if n_docs <= 1:
            return list(bm25_order)

        sem = semantic_scores if semantic_scores is not None else np.zeros(n_docs, dtype=np.float32)

        # 1. Compute fused score for every candidate
        fused_scores = {}
        for idx in range(n_docs):
            fused_scores[idx] = self._compute_fused_score(
                docs[idx], float(bm25_scores[idx]), float(sem[idx]), float(graph_boost[idx])
            )

        # 2. Sort all candidates by descending fused score (tie-breaking on doc path)
        sorted_by_fused = sorted(range(n_docs), key=lambda idx: (-fused_scores[idx], docs[idx].path))

        # 3. Dynamic Margin Gate for Rank 1
        s1 = bm25_order[0]
        s2 = bm25_order[1] if n_docs > 1 else s1
        bm25_margin = max(0.0, float(bm25_scores[s1]) - float(bm25_scores[s2]))
        displacement_threshold = self.soft_damping_tau * bm25_margin

        best_candidate = sorted_by_fused[0]

        if best_candidate == s1:
            # s1 won Rank 1 naturally
            return sorted_by_fused

        # Best candidate is not s1: evaluate displacement condition
        fused_margin = fused_scores[best_candidate] - fused_scores[s1]

        if fused_margin >= displacement_threshold:
            # Overwhelming graph evidence: best candidate displaces s1
            return sorted_by_fused
        else:
            # Margin condition failed: protect s1 at Rank 1, re-rank all remaining candidates
            remaining = [idx for idx in sorted_by_fused if idx != s1]
            return [s1] + remaining

    def _is_package_compatible(self, dir_a: str, dir_b: str) -> bool:
        if dir_a == dir_b:
            return True
        if dir_a.startswith(dir_b) or dir_b.startswith(dir_a):
            return True
        return False


def create_arm_ranker(
    arm_id: str,
    soft_damping_tau: float = 0.25,
) -> FactorialCascadedRanker:
    """Factory helper to create a FactorialCascadedRanker for any named arm or baseline."""
    # Baselines
    if arm_id == "BASE-BM25":
        return FactorialCascadedRanker(mode="bm25")
    elif arm_id == "CONTROL-CASCADE":
        return FactorialCascadedRanker(mode="control")
    elif arm_id == "STAGE3_11-NO-FREEZE":
        return FactorialCascadedRanker(mode="no_freeze")

    # The 8 Factorial Arms
    arm_configs = {
        # Arm 0: A=Off, B=Off, C=Off (Stage 3.11 Frozen Reference)
        "ARM-000": {"factor_a_soft_damping": False, "factor_b_hub_attenuation": False, "factor_c_verified_only": False},
        # Arm 1: A=On, B=Off, C=Off
        "ARM-100": {"factor_a_soft_damping": True, "factor_b_hub_attenuation": False, "factor_c_verified_only": False},
        # Arm 2: A=Off, B=On, C=Off
        "ARM-010": {"factor_a_soft_damping": False, "factor_b_hub_attenuation": True, "factor_c_verified_only": False},
        # Arm 3: A=Off, B=Off, C=On
        "ARM-001": {"factor_a_soft_damping": False, "factor_b_hub_attenuation": False, "factor_c_verified_only": True},
        # Arm 4: A=On, B=On, C=Off
        "ARM-110": {"factor_a_soft_damping": True, "factor_b_hub_attenuation": True, "factor_c_verified_only": False},
        # Arm 5: A=On, B=Off, C=On
        "ARM-101": {"factor_a_soft_damping": True, "factor_b_hub_attenuation": False, "factor_c_verified_only": True},
        # Arm 6: A=Off, B=On, C=On
        "ARM-011": {"factor_a_soft_damping": False, "factor_b_hub_attenuation": True, "factor_c_verified_only": True},
        # Arm 7: A=On, B=On, C=On (STAGE-3.12-PROPOSED)
        "ARM-111": {"factor_a_soft_damping": True, "factor_b_hub_attenuation": True, "factor_c_verified_only": True},
    }

    # Map aliases
    alias_map = {
        "ARM-000-CONTROL": "ARM-000",
        "STAGE3_11-FROZEN": "ARM-000",
        "FUNCTION-GRAPH": "ARM-000",
        "ARM-A": "ARM-100",
        "ARM-100-DAMPED": "ARM-100",
        "ARM-B": "ARM-010",
        "ARM-010-HUB-ATTEN": "ARM-010",
        "ARM-C": "ARM-001",
        "ARM-001-VERIFIED": "ARM-001",
        "ARM-AB": "ARM-110",
        "ARM-110-DAMP-HUB": "ARM-110",
        "ARM-AC": "ARM-101",
        "ARM-101-DAMP-VERIF": "ARM-101",
        "ARM-BC": "ARM-011",
        "ARM-011-HUB-VERIF": "ARM-011",
        "ARM-ABC": "ARM-111",
        "ARM-111-PROPOSED": "ARM-111",
        "STAGE-3.12-PROPOSED": "ARM-111",
    }

    resolved = alias_map.get(arm_id, arm_id)
    if resolved not in arm_configs:
        raise ValueError(f"Unknown arm or baseline id: {arm_id}")

    cfg = arm_configs[resolved]
    return FactorialCascadedRanker(
        mode="factorial",
        soft_damping_tau=soft_damping_tau,
        **cfg
    )

