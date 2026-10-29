"""
Stage 3.14 Pilot Evaluation of Hub Attenuation Variants.
Tests candidate attenuation policies on a subset or full set to observe empirical behavior.
"""

import sys
import os
import json
import math
import time
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
STAGE12_DIR = ROOT_DIR / "research" / "stage3_12"
STAGE10_2_DIR = ROOT_DIR / "research" / "stage3_10_2"

sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(STAGE12_DIR))

from agent_retrieval_bench.baseline import read_jsonl, target_gold_files, query_text_for_eval
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.engine import RepoNeedleEngine
from research.stage3_11.function_graph_engine import FunctionGraphEngine
import research.stage3_10_2.independent_metrics as im


def detect_file_language(path: str) -> str:
    p = path.lower()
    if p.endswith((".go",)):
        return "go"
    if p.endswith((".py", ".pyi")):
        return "python"
    if p.endswith((".rs",)):
        return "rust"
    if p.endswith((".ts", ".tsx", ".js", ".jsx")):
        return "typescript"
    if p.endswith((".java",)):
        return "java"
    return "unknown"


def compute_hub_attenuation(
    path: str,
    in_deg: int,
    out_deg: int,
    policy: str,
) -> float:
    if policy == "unattenuated":  # ARM-101
        return 1.0

    if policy == "uniform_log2":  # ARM-111
        return 1.0 / math.log2(2.0 + in_deg)

    lang = detect_file_language(path)
    p_lower = path.lower()
    is_util_name = any(u in p_lower for u in ["util", "helper", "compat", "common", "format", "log"])

    if policy == "lang_calibrated":
        # Python: full attenuation; Go: zero attenuation; Rust/TS/Java: mild attenuation
        if lang == "python":
            return 1.0 / math.log2(2.0 + in_deg)
        elif lang == "go":
            return 1.0  # Zero attenuation in Go
        elif lang in ("rust", "typescript", "java"):
            return 1.0 / math.log2(2.0 + 0.5 * in_deg)
        else:
            return 1.0

    if policy == "structural_role":
        # Language-agnostic: attenuate only if pure sink (calls few/nothing) or utility name
        if is_util_name:
            return 1.0 / math.log2(2.0 + in_deg)
        if in_deg >= 3 and out_deg <= 1:
            return 1.0 / math.log2(2.0 + in_deg)
        return 1.0

    if policy == "combined_lang_role":
        if lang == "go":
            # In Go, only attenuate if explicitly named utility AND is a sink
            if is_util_name and out_deg <= 1:
                return 1.0 / math.log2(2.0 + in_deg)
            return 1.0
        elif lang == "python":
            return 1.0 / math.log2(2.0 + in_deg)
        else:
            if is_util_name or (in_deg >= 3 and out_deg <= 1):
                return 1.0 / math.log2(2.0 + in_deg)
            return 1.0

    if policy == "degree_threshold_15":
        if in_deg >= 15:
            return 0.5
        return 1.0

    return 1.0


class ExperimentalLanguageRanker:
    def __init__(self, policy: str = "unattenuated", soft_damping_tau: float = 0.25):
        self.policy = policy
        self.soft_damping_tau = soft_damping_tau
        self.forward_weight = 0.25
        self.reverse_weight = 0.20
        self.graph_weight = 0.25
        self.class_to_test_weight = 0.35
        self.doc_filter_penalty = 0.50

    def rank(self, docs, bm25_scores, semantic_scores, fg, repo_graph):
        n_docs = len(docs)
        if n_docs <= 1:
            return list(range(n_docs))

        bm25_order = sorted(range(n_docs), key=lambda i: (-float(bm25_scores[i]), docs[i].path))
        seeds = bm25_order[:3]
        graph_boost = np.zeros(n_docs, dtype=np.float32)

        # Base repograph propagation
        if repo_graph is not None and len(repo_graph.graph) > 0:
            self._propagate_repograph(seeds, docs, bm25_scores, repo_graph, graph_boost)
            self._propagate_class_to_test(seeds, docs, bm25_scores, repo_graph, graph_boost)

        # Function graph propagation
        if fg is not None and len(fg.graph) > 0:
            self._propagate_function_graph(seeds, docs, bm25_scores, fg, graph_boost)

        # Soft lexical damping score fusion
        sem = semantic_scores if semantic_scores is not None else np.zeros(n_docs, dtype=np.float32)
        fused = {}
        for idx in range(n_docs):
            score = 0.60 * float(bm25_scores[idx]) + 0.15 * float(sem[idx]) + self.graph_weight * float(graph_boost[idx])
            p_lower = docs[idx].path.lower()
            if any(seg in p_lower for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or p_lower.endswith((".md", ".rst", ".txt", ".adoc", ".html")):
                score *= self.doc_filter_penalty
            fused[idx] = float(score)

        sorted_by_fused = sorted(range(n_docs), key=lambda idx: (-fused[idx], docs[idx].path))
        s1 = bm25_order[0]
        s2 = bm25_order[1] if n_docs > 1 else s1
        bm25_margin = max(0.0, float(bm25_scores[s1]) - float(bm25_scores[s2]))
        threshold = self.soft_damping_tau * bm25_margin

        best = sorted_by_fused[0]
        if best == s1 or (fused[best] - fused[s1] >= threshold):
            return sorted_by_fused
        else:
            return [s1] + [idx for idx in sorted_by_fused if idx != s1]

    def _propagate_function_graph(self, seeds, docs, bm25_scores, fg, graph_boost):
        path_to_idx = fg.path_to_idx
        allowed = {"verified_call", "unique_global_call", "intra_file_call"}

        for s_idx in seeds:
            seed_p = docs[s_idx].path
            seed_score = float(bm25_scores[s_idx])
            if seed_score <= 0.0 or seed_p not in path_to_idx:
                continue

            seed_dir = os.path.dirname(seed_p.replace("\\", "/"))

            # Forward
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

            # Reverse
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

                    out_deg_caller = max(1, len(fg.callees_map.get(caller_p, {})))
                    in_deg_caller = max(1, len(fg.callers_map.get(caller_p, {})))
                    norm = 1.0 / math.sqrt(in_deg_seed * out_deg_caller)
                    boost = seed_score * self.reverse_weight * edge_conf * norm

                    w_hub = compute_hub_attenuation(caller_p, in_deg_caller, out_deg_caller, self.policy)
                    boost *= w_hub
                    graph_boost[c_idx] = max(graph_boost[c_idx], float(boost))

    def _propagate_repograph(self, seeds, docs, bm25_scores, repo_graph, graph_boost):
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

    def _apply_test_discovery(self, seed_path, seed_score, path_to_idx, graph_boost):
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

    def _propagate_class_to_test(self, seeds, docs, bm25_scores, repo_graph, graph_boost):
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

    def _is_pkg_compat(self, dir_a, dir_b):
        return dir_a == dir_b or dir_a.startswith(dir_b) or dir_b.startswith(dir_a)

