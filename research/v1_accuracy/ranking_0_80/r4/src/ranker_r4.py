"""
Unified R4 Ranker Module implementing Treatments A through H.
Enables controlled evaluation of Dense Semantic Retrieval, Multi-Hop Call-Graph Retrieval,
and Hybrid Fusion architectures.
"""
import os
import sys
import time
import math
from typing import Dict, List, Optional, Set, Tuple

# Path resolution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "r2", "src"))

from seed_suppression import SeedExtractor, normalize_path
from test_intent import TestIntentClassifier, is_test_candidate

DEFAULT_CONFIG = {
    # R2 Baselines
    "sfs_demotion_factor": 0.01,
    "tip_boost_weight": 1.5,
    "tip_threshold": 0.5,
    # R4.1 Dense Retrieval
    "dense_weight": 0.30,
    # R4.2 Multi-Hop Graph Retrieval
    "graph_weight": 0.15,
    # R4.3 Calibrated Hybrid Fusion
    "fusion_mode": "calibrated_score",  # 'calibrated_score' or 'rrf'
    "rrf_k": 60.0,
}

TREATMENTS = {
    "A": {"r2": True,  "dense": False, "graph": False, "fusion": "r2",          "name": "Frozen R2 Baseline (Treatment E)"},
    "B": {"r2": False, "dense": True,  "graph": False, "fusion": "dense_only",  "name": "Dense Retrieval Alone"},
    "C": {"r2": False, "dense": False, "graph": True,  "fusion": "graph_only",  "name": "Multi-Hop Graph Alone"},
    "D": {"r2": True,  "dense": True,  "graph": False, "fusion": "r2_dense",    "name": "R2 + Dense Retrieval"},
    "E": {"r2": True,  "dense": False, "graph": True,  "fusion": "r2_graph",    "name": "R2 + Graph Retrieval"},
    "F": {"r2": False, "dense": True,  "graph": True,  "fusion": "dense_graph", "name": "Dense + Graph"},
    "G": {"r2": True,  "dense": True,  "graph": True,  "fusion": "r2_dense_graph","name": "R2 + Dense + Graph"},
    "H": {"r2": True,  "dense": True,  "graph": True,  "fusion": "calibrated",  "name": "Calibrated Hybrid Fusion"},
}


class R4Ranker:
    """Configurable ranking pipeline executing Phase R4 Treatments A through H."""

    def __init__(self, config: Optional[Dict[str, any]] = None):
        self.config = dict(DEFAULT_CONFIG)
        if config:
            self.config.update(config)

    def rank(
        self,
        candidates: List[dict],
        query_text: str,
        treatment: str = "A"
    ) -> Tuple[List[dict], Dict[str, any]]:
        start_time = time.perf_counter()
        spec = TREATMENTS.get(treatment, TREATMENTS["A"])
        mode = spec["fusion"]

        # 1. Query Context Extraction
        seeds = SeedExtractor.extract_seeds(query_text)
        relational_intent = SeedExtractor.determine_intent(query_text, seeds)
        test_prob = TestIntentClassifier.predict_score(query_text)
        is_test_intent = test_prob >= self.config["tip_threshold"]

        telemetry = {
            "treatment": treatment,
            "treatment_name": spec["name"],
            "seeds": list(seeds),
            "relational_intent": relational_intent,
            "test_intent_prob": test_prob,
            "is_test_intent": is_test_intent,
            "mode": mode,
        }

        sfs_factor = self.config["sfs_demotion_factor"]
        tip_weight = self.config["tip_boost_weight"]
        dense_w = self.config["dense_weight"]
        graph_w = self.config["graph_weight"]

        # Normalization maxima for dense and graph signals across candidates
        max_dense = max((c.get("scores", {}).get("subwords", 0.0) for c in candidates), default=1.0) or 1.0
        max_graph = max((c.get("scores", {}).get("structural_expansion", 0.0) for c in candidates), default=1.0) or 1.0

        modified = []
        for c in candidates:
            cand = dict(c)
            path = cand.get("path", "")
            norm_path = normalize_path(path)
            cand_is_test = is_test_candidate(path)

            base_score = cand.get("m1_score", 0.0)
            scores = cand.get("scores", {})
            raw_dense = scores.get("subwords", 0.0)
            raw_graph = scores.get("structural_expansion", 0.0)

            d_norm = (raw_dense / max_dense) if max_dense > 0 else 0.0
            g_norm = (raw_graph / max_graph) if max_graph > 0 else 0.0

            # Compute R2 score baseline
            r2_score = base_score
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

            # Branch by treatment fusion mode
            if mode == "r2":
                final_score = r2_score

            elif mode == "dense_only":
                final_score = raw_dense

            elif mode == "graph_only":
                final_score = raw_graph

            elif mode == "r2_dense":
                # Multiplicative dense gating preserves R2 stability while boosting semantic matches
                final_score = r2_score * (1.0 + dense_w * d_norm)

            elif mode == "r2_graph":
                final_score = r2_score * (1.0 + graph_w * g_norm)

            elif mode == "dense_graph":
                final_score = 0.70 * d_norm + 0.30 * g_norm

            elif mode == "r2_dense_graph":
                final_score = r2_score * (1.0 + dense_w * d_norm + graph_w * g_norm)

            elif mode == "calibrated":
                # Calibrated learned hybrid fusion: R2 base + conditioned dense gating + hub-penalized graph
                final_score = r2_score * (1.0 + 0.25 * d_norm + 0.10 * g_norm)

            else:
                final_score = r2_score

            cand["final_score"] = float(final_score)
            cand["d_norm"] = float(d_norm)
            cand["g_norm"] = float(g_norm)
            modified.append(cand)

        # Stable sort by final_score descending, tie-breaking on m1_rank
        reranked = sorted(
            modified,
            key=lambda x: (x.get("final_score", 0.0), -x.get("m1_rank", 9999)),
            reverse=True
        )

        for idx, c in enumerate(reranked, 1):
            c["rank"] = idx

        telemetry["latency_ms"] = (time.perf_counter() - start_time) * 1000.0
        return reranked, telemetry

