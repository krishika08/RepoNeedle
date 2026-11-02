"""
Phase R6 Multi-Treatment Ranking Architecture.
Implements the 8 controlled treatments evaluated in Phase R6:
- A: Original V1 Baseline (Raw BM25 / lexical scoring)
- B: R2 Treatment E (Seed File Suppression + Test Intent Prior)
- C: R4 Treatment D (Dense Semantic + Multi-Hop Structural)
- D: R5 Treatment F (Full Typed Change-Impact with original uncalibrated edges)
- E: R5 Without Heuristic Edges (Ablation of directory proximity, test stem, doc match)
- F: R5 With Verified Graph Relationships Only (Strictly AST-resolved calls, imports, symbols, build)
- G: R5 With Confidence-Calibrated Relationship Evidence (Bayesian confidence propagation)
- H: Best Combined Model (Verified structural impact + calibrated heuristics + TIP)
"""

import os
import re
from typing import Dict, List, Any, Optional
from graph_evidence import GraphEvidenceAuditor

TREATMENTS = ["A", "B", "C", "D", "E", "F", "G", "H"]

TEST_PATTERNS = re.compile(
    r"\b(?:test[a-z]*|spec[a-z]*|assert[a-z]*|verify[a-z]*|check[a-z]*|reproduc[a-z]*|regression)\b",
    re.I
)


class R6Ranker:
    """Multi-treatment ranker for independent benchmark evaluation."""

    @staticmethod
    def detect_test_intent(query_text: str) -> bool:
        return bool(TEST_PATTERNS.search(query_text))

    @classmethod
    def score_candidate(
        cls,
        candidate: Dict[str, Any],
        query_text: str,
        seeds: List[str],
        treatment: str,
        is_test_query: bool,
    ) -> float:
        c_path = candidate.get("path", "").replace("\\", "/").lower()
        c_base = os.path.basename(c_path)
        is_cand_test = "test" in c_path or c_base.startswith("test_") or c_base.endswith("_test.py") or c_base.endswith("test.rs")
        
        base_score = float(candidate.get("m1_score", 0.0))
        scores_map = candidate.get("scores", {})
        sym_score = float(scores_map.get("exact_symbol", 0.0))
        sub_score = float(scores_map.get("subwords", 0.0))

        # Treatment A: Original V1 Baseline
        if treatment == "A":
            return base_score

        # Common R2 Prior (SFS + TIP)
        sfs_mult = 0.01 if (seeds and c_path in [s.replace("\\", "/").lower() for s in seeds]) else 1.0
        tip_mult = 1.45 if (is_test_query and is_cand_test) else (0.85 if (not is_test_query and is_cand_test) else 1.0)
        r2_score = base_score * sfs_mult * tip_mult

        if treatment == "B":
            return r2_score

        # Treatment C: R4 Treatment D (Dense Semantic + Structural)
        if treatment == "C":
            return r2_score + 0.015 * sub_score + 0.25 * sym_score

        # Graph audit for treatments D, E, F, G, H
        edges = GraphEvidenceAuditor.audit_edges(candidate, seeds, query_text)
        query_intent = "test" if is_test_query else "general"

        if treatment == "D":
            impact = GraphEvidenceAuditor.compute_edge_impact_score(edges, mode="full", query_intent=query_intent)
            return r2_score + 3.0 * impact

        elif treatment == "E":
            impact = GraphEvidenceAuditor.compute_edge_impact_score(edges, mode="no_heuristics", query_intent=query_intent)
            return r2_score + 3.0 * impact

        elif treatment == "F":
            impact = GraphEvidenceAuditor.compute_edge_impact_score(edges, mode="verified_only", query_intent=query_intent)
            return r2_score + 3.5 * impact

        elif treatment == "G":
            impact = GraphEvidenceAuditor.compute_edge_impact_score(edges, mode="calibrated", query_intent=query_intent)
            return r2_score + 4.0 * impact

        elif treatment == "H":
            # Best Combined: Calibrated Bayesian impact + exact symbol channel reinforcement
            impact = GraphEvidenceAuditor.compute_edge_impact_score(edges, mode="calibrated", query_intent=query_intent)
            return r2_score + 3.8 * impact + 0.20 * sym_score

        raise ValueError(f"Unknown treatment: {treatment}")

    @classmethod
    def rank_candidates(
        cls,
        candidates: List[Dict[str, Any]],
        query_text: str,
        seeds: List[str],
        treatment: str,
    ) -> List[Dict[str, Any]]:
        is_test_query = cls.detect_test_intent(query_text)
        scored = []
        for cand in candidates:
            score = cls.score_candidate(cand, query_text, seeds, treatment, is_test_query)
            scored.append((score, cand))

        # Sort descending by score; tie-break on m1_score, then path
        scored.sort(key=lambda x: (x[0], x[1].get("m1_score", 0.0), x[1].get("path", "")), reverse=True)
        return [cand for _, cand in scored]

