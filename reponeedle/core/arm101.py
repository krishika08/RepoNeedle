"""
ARM-101 Ranker: Soft Lexical Damping with Verified Function-Call Graph Expansion.
"""

from __future__ import annotations

import os
import math
from typing import List, Dict, Optional, Any
import numpy as np

from reponeedle.models import FileDoc
from reponeedle.core.attenuation import compute_hub_attenuation
from reponeedle.core.function_graph import FunctionGraphEngine


class ARM101Ranker:
    """
    Controlled production ranker combining decoupled Okapi BM25, subword TF-IDF,
    verified function-call graph diffusion, and Soft Lexical Damping (tau = 0.25).
    """

    def __init__(
        self,
        policy: str = "unattenuated",
        soft_damping_tau: float = 0.25,
        forward_weight: float = 0.25,
        reverse_weight: float = 0.20,
        graph_weight: float = 0.25,
        class_to_test_weight: float = 0.35,
        doc_filter_penalty: float = 0.50,
    ):
        self.policy = policy
        self.soft_damping_tau = soft_damping_tau
        self.forward_weight = forward_weight
        self.reverse_weight = reverse_weight
        self.graph_weight = graph_weight
        self.class_to_test_weight = class_to_test_weight
        self.doc_filter_penalty = doc_filter_penalty

    def _is_pkg_compat(self, dir_a: str, dir_b: str) -> bool:
        return dir_a == dir_b or dir_a.startswith(dir_b) or dir_b.startswith(dir_a)

    def rank_with_scores(
        self,
        docs: List[FileDoc],
        bm25_scores: np.ndarray,
        semantic_scores: Optional[np.ndarray] = None,
        fg: Optional[FunctionGraphEngine] = None,
        repo_graph: Optional[Any] = None,
    ) -> Tuple[List[int], Dict[int, float]]:
        n_docs = len(docs)
        if n_docs <= 1:
            fused = {i: float(bm25_scores[i]) if len(bm25_scores) > i else 0.0 for i in range(n_docs)}
            return list(range(n_docs)), fused

        # 1. Deterministic BM25 sort order with path tie-breaking
        bm25_order = sorted(range(n_docs), key=lambda i: (-float(bm25_scores[i]), docs[i].path))
        seeds = bm25_order[:3]
        graph_boost = np.zeros(n_docs, dtype=np.float32)

        # 2. Base RepoGraph propagation
        if repo_graph is not None and getattr(repo_graph, "graph", None) is not None and len(repo_graph.graph) > 0:
            self._propagate_repograph(seeds, docs, bm25_scores, repo_graph, graph_boost)
            self._propagate_class_to_test(seeds, docs, bm25_scores, repo_graph, graph_boost)

        # 3. Function Graph propagation
        if fg is not None and getattr(fg, "graph", None) is not None and len(fg.graph) > 0:
            self._propagate_function_graph(seeds, docs, bm25_scores, fg, graph_boost)

        # 4. Fused score combination
        sem = semantic_scores if semantic_scores is not None else np.zeros(n_docs, dtype=np.float32)
        fused = {}
        for idx in range(n_docs):
            score = 0.60 * float(bm25_scores[idx]) + 0.15 * float(sem[idx]) + self.graph_weight * float(graph_boost[idx])
            p_lower = docs[idx].path.lower().replace("\\", "/")
            if any(seg in p_lower for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or p_lower.endswith((".md", ".rst", ".txt", ".adoc", ".html")):
                score *= self.doc_filter_penalty
            fused[idx] = float(score)

        sorted_by_fused = sorted(range(n_docs), key=lambda idx: (-fused[idx], docs[idx].path))

        # 5. Soft Lexical Damping (Rank 1 Guard)
        s1 = bm25_order[0]
        s2 = bm25_order[1] if n_docs > 1 else s1
        bm25_margin = max(0.0, float(bm25_scores[s1]) - float(bm25_scores[s2]))
        threshold = self.soft_damping_tau * bm25_margin

        best = sorted_by_fused[0]
        if best == s1 or (fused[best] - fused[s1] >= threshold):
            return sorted_by_fused, fused
        else:
            fused[s1] = fused[best] + 1e-4
            return [s1] + [idx for idx in sorted_by_fused if idx != s1], fused

    def rank(
        self,
        docs: List[FileDoc],
        bm25_scores: np.ndarray,
        semantic_scores: Optional[np.ndarray] = None,
        fg: Optional[FunctionGraphEngine] = None,
        repo_graph: Optional[Any] = None,
    ) -> List[int]:
        ranked_indices, _ = self.rank_with_scores(docs, bm25_scores, semantic_scores, fg, repo_graph)
        return ranked_indices

    def _propagate_function_graph(
        self,
        seeds: List[int],
        docs: List[FileDoc],
        bm25_scores: np.ndarray,
        fg: FunctionGraphEngine,
        graph_boost: np.ndarray,
    ):
        path_to_idx = fg.path_to_idx
        allowed = {"verified_call", "unique_global_call", "intra_file_call"}

        for s_idx in seeds:
            seed_p = docs[s_idx].path
            seed_score = float(bm25_scores[s_idx])
            if seed_score <= 0.0 or seed_p not in path_to_idx:
                continue

            seed_dir = os.path.dirname(seed_p.replace("\\", "/"))

            # Forward propagation (callees)
            callees = fg.callees_map.get(seed_p, {})
            out_deg = max(1, len(callees))
            for callee_p, conf in callees.items():
                if callee_p in path_to_idx:
                    c_idx = path_to_idx[callee_p]
                    edges = fg.file_to_file_edges.get((seed_p, callee_p), [])
                    matching = [e for e in edges if e.edge_type in allowed]
                    if not matching:
                        continue
                    edge_conf = max(e.confidence for e in matching)

                    callee_dir = os.path.dirname(callee_p.replace("\\", "/"))
                    is_test = docs[s_idx].is_test or docs[c_idx].is_test
                    if not is_test and not self._is_pkg_compat(seed_dir, callee_dir):
                        continue

                    in_deg = max(1, len(fg.callers_map.get(callee_p, {})))
                    callee_out_deg = max(1, len(fg.callees_map.get(callee_p, {})))
                    norm = 1.0 / math.sqrt(out_deg * in_deg)
                    boost = seed_score * self.forward_weight * edge_conf * norm

                    w_hub = compute_hub_attenuation(callee_p, in_deg, callee_out_deg, self.policy)
                    boost *= w_hub
                    graph_boost[c_idx] = max(graph_boost[c_idx], float(boost))

            # Reverse propagation (callers)
            callers = fg.callers_map.get(seed_p, {})
            in_deg_seed = max(1, len(callers))
            for caller_p, conf in callers.items():
                if caller_p in path_to_idx:
                    c_idx = path_to_idx[caller_p]
                    edges = fg.file_to_file_edges.get((caller_p, seed_p), [])
                    matching = [e for e in edges if e.edge_type in allowed]
                    if not matching:
                        continue
                    edge_conf = max(e.confidence for e in matching)

                    caller_dir = os.path.dirname(caller_p.replace("\\", "/"))
                    is_test = docs[s_idx].is_test or docs[c_idx].is_test
                    if not is_test and not self._is_pkg_compat(seed_dir, caller_dir):
                        continue

                    caller_in_deg = max(1, len(fg.callers_map.get(caller_p, {})))
                    caller_out_deg = max(1, len(fg.callees_map.get(caller_p, {})))
                    norm = 1.0 / math.sqrt(in_deg_seed * caller_out_deg)
                    boost = seed_score * self.reverse_weight * edge_conf * norm

                    w_hub = compute_hub_attenuation(caller_p, caller_in_deg, caller_out_deg, self.policy)
                    boost *= w_hub
                    graph_boost[c_idx] = max(graph_boost[c_idx], float(boost))

    def _propagate_repograph(
        self,
        seeds: List[int],
        docs: List[FileDoc],
        bm25_scores: np.ndarray,
        repo_graph: Any,
        graph_boost: np.ndarray,
    ):
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
                    succ_dir = os.path.dirname(succ.replace("\\", "/"))
                    if not self._is_pkg_compat(seed_dir, succ_dir):
                        continue
                    in_deg_succ = max(1, g.in_degree(succ))
                    norm = 1.0 / math.sqrt(out_deg * in_deg_succ)
                    boost = seed_score * 0.25 * norm
                    if self.policy == "uniform_log2":
                        boost *= (1.0 / math.log2(2.0 + in_deg_succ))
                    graph_boost[n_idx] = max(graph_boost[n_idx], float(boost))

            for pred in g.predecessors(seed_p):
                if pred in path_to_idx:
                    n_idx = path_to_idx[pred]
                    pred_dir = os.path.dirname(pred.replace("\\", "/"))
                    if not self._is_pkg_compat(seed_dir, pred_dir):
                        continue
                    out_deg_pred = max(1, g.out_degree(pred))
                    in_deg_pred = max(1, g.in_degree(pred))
                    norm = 1.0 / math.sqrt(in_deg_seed * out_deg_pred)
                    boost = seed_score * 0.10 * norm
                    if self.policy == "uniform_log2":
                        boost *= (1.0 / math.log2(2.0 + in_deg_pred))
                    graph_boost[n_idx] = max(graph_boost[n_idx], float(boost))

            self._apply_test_discovery(seed_p, seed_score, path_to_idx, graph_boost)

    def _apply_test_discovery(
        self,
        seed_path: str,
        seed_score: float,
        path_to_idx: Dict[str, int],
        graph_boost: np.ndarray,
    ):
        norm_p = seed_path.replace("\\", "/")
        stem = os.path.splitext(os.path.basename(norm_p))[0]
        ext = os.path.splitext(norm_p)[1].lower()
        cur_dir = os.path.dirname(norm_p)
        tc_list = []

        if ext == ".go":
            tc_list.append(f"{cur_dir}/{stem}_test.go" if cur_dir else f"{stem}_test.go")
        elif ext in (".py", ".pyi"):
            tc_list.append(f"{cur_dir}/test_{stem}.py" if cur_dir else f"test_{stem}.py")
            tc_list.append(f"tests/test_{stem}.py")
            tc_list.append(f"tests/{stem}_test.py")
        elif ext == ".rs":
            tc_list.append(f"tests/{stem}.rs")
            tc_list.append(f"tests/test_{stem}.rs")
        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            tc_list.append(f"{cur_dir}/{stem}.test{ext}" if cur_dir else f"{stem}.test{ext}")
            tc_list.append(f"{cur_dir}/__tests__/{stem}.test{ext}" if cur_dir else f"__tests__/{stem}.test{ext}")

        for tc in tc_list:
            if tc in path_to_idx:
                idx = path_to_idx[tc]
                graph_boost[idx] = max(graph_boost[idx], float(seed_score * 0.35))

    def _propagate_class_to_test(
        self,
        seeds: List[int],
        docs: List[FileDoc],
        bm25_scores: np.ndarray,
        repo_graph: Any,
        graph_boost: np.ndarray,
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
                        in_deg = max(1, len(test_to_prods.get(test_p, {seed_p})))
                        norm = 1.0 / math.sqrt(out_deg * in_deg)
                        boost = seed_score * self.class_to_test_weight * norm
                        if self.policy == "uniform_log2":
                            boost *= (1.0 / math.log2(2.0 + in_deg))
                        graph_boost[t_idx] = max(graph_boost[t_idx], float(boost))

            if seed_p in test_to_prods:
                target_prods = test_to_prods[seed_p]
                out_deg = max(1, len(target_prods))
                for prod_p in target_prods:
                    if prod_p in path_to_idx:
                        p_idx = path_to_idx[prod_p]
                        in_deg = max(1, len(prod_to_tests.get(prod_p, {seed_p})))
                        norm = 1.0 / math.sqrt(out_deg * in_deg)
                        boost = seed_score * self.class_to_test_weight * norm
                        if self.policy == "uniform_log2":
                            boost *= (1.0 / math.log2(2.0 + in_deg))
                        graph_boost[p_idx] = max(graph_boost[p_idx], float(boost))
