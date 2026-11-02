"""
Unified R5 Ranker Module implementing Treatments A through H.
Enables controlled evaluation of:
- Treatment A: R2 Treatment E (Authoritative Baseline Reference)
- Treatment B: R4 Treatment D (Best Dense Semantic Ranker)
- Treatment C: File-Level Retrieval Alone
- Treatment D: Function-Level Lexical Retrieval
- Treatment E: Function-Level Semantic Retrieval
- Treatment F: Change-Impact Retrieval (Typed Graph)
- Treatment G: Multi-Target Retrieval (Role-Aware MMR Selection)
- Treatment H: Combined Hierarchical Retrieval (File + Function + Impact + Multi-Target)
"""
import os
import sys
import time
import math
from typing import Dict, List, Optional, Set, Tuple, Any

# Path resolution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "r2", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "r4", "src"))

from seed_suppression import SeedExtractor, normalize_path
from test_intent import TestIntentClassifier, is_test_candidate
from code_unit import CodeUnitIndexer
from query_alignment import CodeUnitScorer, QueryIntentDetector
from change_impact import ChangeImpactEngine
from multi_target import MultiTargetSelector

DEFAULT_CONFIG = {
    # R2 Baselines
    "sfs_demotion_factor": 0.01,
    "tip_boost_weight": 1.5,
    "tip_threshold": 0.5,
    # R4 Dense
    "dense_weight": 0.30,
    # R5 Function-Level
    "unit_weight": 0.35,
    # R5 Change-Impact
    "impact_weight": 0.20,
    # R5 Multi-Target MMR
    "diversity_lambda": 0.75,
}

TREATMENTS = {
    "A": {"name": "R2 Treatment E (Authoritative Reference)", "mode": "r2"},
    "B": {"name": "R4 Treatment D (Best Dense Semantic)",     "mode": "r4_dense"},
    "C": {"name": "File-Level Retrieval Alone",              "mode": "file_only"},
    "D": {"name": "Function-Level Lexical Retrieval",        "mode": "unit_lexical"},
    "E": {"name": "Function-Level Semantic Retrieval",       "mode": "unit_semantic"},
    "F": {"name": "Change-Impact Retrieval (Typed Graph)",   "mode": "change_impact"},
    "G": {"name": "Multi-Target Retrieval (Role-Aware MMR)", "mode": "multi_target"},
    "H": {"name": "Combined Hierarchical Retrieval",         "mode": "hierarchical"},
}


class R5Ranker:
    """Configurable ranking pipeline executing Phase R5 Treatments A through H."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = dict(DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self.selector = MultiTargetSelector(diversity_lambda=self.config["diversity_lambda"])

    def rank(
        self,
        candidates: List[Dict[str, Any]],
        query_text: str,
        treatment: str = "A",
        corpus_docs: Optional[Dict[str, str]] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        start_time = time.perf_counter()
        spec = TREATMENTS.get(treatment, TREATMENTS["A"])
        mode = spec["mode"]

        # 1. Query Context & Intent Extraction
        seeds = SeedExtractor.extract_seeds(query_text)
        relational_intent = SeedExtractor.determine_intent(query_text, seeds)
        test_prob = TestIntentClassifier.predict_score(query_text)
        is_test_intent = test_prob >= self.config["tip_threshold"]
        intent_category = QueryIntentDetector.detect(query_text)
        query_tokens = CodeUnitIndexer.tokenize_identifiers(query_text)

        telemetry = {
            "treatment": treatment,
            "treatment_name": spec["name"],
            "seeds": list(seeds),
            "relational_intent": relational_intent,
            "test_intent_prob": test_prob,
            "is_test_intent": is_test_intent,
            "intent_category": intent_category,
            "mode": mode,
        }

        sfs_factor = self.config["sfs_demotion_factor"]
        tip_weight = self.config["tip_boost_weight"]
        dense_w = self.config["dense_weight"]
        unit_w = self.config["unit_weight"]
        impact_w = self.config["impact_weight"]

        # 2. Compute Change-Impact Scores if mode requires it
        impact_scores: Dict[str, float] = {}
        if mode in ("change_impact", "hierarchical") and seeds:
            impact_scores = ChangeImpactEngine.compute_candidate_impact(
                list(seeds), candidates, query_intent=intent_category
            )

        # 3. Normalization factors
        max_dense = max((c.get("scores", {}).get("subwords", 0.0) for c in candidates), default=1.0) or 1.0

        modified: List[Dict[str, Any]] = []
        for c in candidates:
            cand = dict(c)
            path = cand.get("path", "")
            norm_path = normalize_path(path)
            cand_is_test = is_test_candidate(path)

            base_m1_score = cand.get("m1_score", 0.0)
            scores = cand.get("scores", {})
            raw_dense = scores.get("subwords", 0.0)
            d_norm = (raw_dense / max_dense) if max_dense > 0 else 0.0

            # A. Baseline R2 Score (SFS + TIP)
            r2_score = base_m1_score
            if relational_intent == "relational" and norm_path in seeds:
                r2_score *= sfs_factor
                cand["sfs_demoted"] = True
            else:
                cand["sfs_demoted"] = False

            if is_test_intent and cand_is_test:
                r2_score *= (1.0 + tip_weight * test_prob)
                cand["tip_boosted"] = True
            else:
                cand["tip_boosted"] = False

            # B. Function-Level Code-Unit Score & Source Span
            raw_unit_score, unit_meta = CodeUnitScorer.score_candidate_unit(
                cand, query_text, query_tokens, intent=intent_category
            )
            cand["best_unit"] = unit_meta["best_unit"]
            norm_unit_score = min(raw_unit_score / 5.0, 1.0)

            # C. Change-Impact Score
            cand_impact = impact_scores.get(path, 0.0)
            cand["impact_score"] = float(cand_impact)

            # --- BRANCH BY TREATMENT ---
            if mode == "r2":
                # Treatment A: Frozen R2 Baseline
                final_score = r2_score

            elif mode == "r4_dense":
                # Treatment B: R4 Treatment D (Dense Multiplicative Gating)
                final_score = r2_score * (1.0 + dense_w * d_norm)

            elif mode == "file_only":
                # Treatment C: File-Level Alone (Raw M1 BM25 without SFS/TIP)
                final_score = base_m1_score

            elif mode == "unit_lexical":
                # Treatment D: Function-Level Lexical Retrieval (R2 + Code Unit BM25 Alignment)
                final_score = r2_score * (1.0 + unit_w * norm_unit_score)

            elif mode == "unit_semantic":
                # Treatment E: Function-Level Semantic Retrieval (R2 + Unit + Dense)
                final_score = r2_score * (1.0 + 0.20 * norm_unit_score + 0.20 * d_norm)

            elif mode == "change_impact":
                # Treatment F: Change-Impact Retrieval (R2 + Typed Impact Graph)
                final_score = r2_score * (1.0 + impact_w * cand_impact)

            elif mode == "multi_target":
                # Treatment G: Pre-score with R4 Dense, MMR diversity applied subsequently
                final_score = r2_score * (1.0 + dense_w * d_norm)

            elif mode == "hierarchical":
                # Treatment H: Combined Hierarchical (R2 + Unit + Dense + Impact)
                final_score = r2_score * (1.0 + 0.25 * norm_unit_score + 0.15 * d_norm + 0.10 * cand_impact)

            else:
                final_score = r2_score

            cand["score"] = float(final_score)
            cand["final_score"] = float(final_score)
            modified.append(cand)

        # Initial stable sort by final_score descending, tie-break by m1_rank
        sorted_candidates = sorted(
            modified,
            key=lambda x: (x.get("final_score", 0.0), -x.get("m1_rank", 9999)),
            reverse=True
        )

        # Apply Multi-Target MMR Diversity Selection if in Treatment G or H
        if mode in ("multi_target", "hierarchical"):
            reranked = self.selector.select_diverse_targets(sorted_candidates, top_k=20)
        else:
            reranked = sorted_candidates
            for idx, c in enumerate(reranked, 1):
                c["rank"] = idx

        telemetry["latency_ms"] = (time.perf_counter() - start_time) * 1000.0
        return reranked, telemetry
