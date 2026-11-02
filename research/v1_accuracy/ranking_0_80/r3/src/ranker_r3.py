"""
Integrated R3 Ranker Module supporting Treatments A through I.
Enables controlled, reproducible evaluation of individual and combined
AST Symbol Intelligence and BM25 length-normalization variants.
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
from ast_symbol import ASTIntentClassifier, ASTSymbolMatcher, IdentifierTokenizer
from bm25_variants import BM25Okapi, BM25L, BM25Plus, FieldWeightedBM25

DEFAULT_CONFIG = {
    # R2 Baselines
    "sfs_demotion_factor": 0.01,
    "tip_boost_weight": 1.5,
    "tip_threshold": 0.5,
    # R3 AST Intelligence
    "ast_def_boost": 1.0,
    "ast_impl_boost": 0.5,
    "ast_trace_penalty": 0.05,
    # R3 BM25 Normalization
    "bm25_l_delta": 0.5,
    "bm25_plus_delta": 0.5,
    "bm25_damping_weight": 0.5,
}

TREATMENTS = {
    "A": {"sfs": True,  "tip": True,  "ast": False, "bm25_variant": "none",     "intent_routing": False, "name": "Frozen R2 Baseline (SFS + TIP)"},
    "B": {"sfs": True,  "tip": False, "ast": True,  "bm25_variant": "none",     "intent_routing": False, "name": "AST Symbol Alone"},
    "C": {"sfs": True,  "tip": False, "ast": False, "bm25_variant": "bm25l",    "intent_routing": False, "name": "BM25L Alone"},
    "D": {"sfs": True,  "tip": False, "ast": False, "bm25_variant": "bm25+",    "intent_routing": False, "name": "BM25+ Alone"},
    "E": {"sfs": True,  "tip": False, "ast": False, "bm25_variant": "field_bm25","intent_routing": False, "name": "Field-Weighted BM25"},
    "F": {"sfs": True,  "tip": True,  "ast": True,  "bm25_variant": "none",     "intent_routing": False, "name": "Treatment E + AST"},
    "G": {"sfs": True,  "tip": True,  "ast": False, "bm25_variant": "bm25l",    "intent_routing": False, "name": "Treatment E + BM25L"},
    "H": {"sfs": True,  "tip": True,  "ast": True,  "bm25_variant": "bm25l",    "intent_routing": False, "name": "Treatment E + AST + BM25L"},
    "I": {"sfs": True,  "tip": True,  "ast": True,  "bm25_variant": "bm25l",    "intent_routing": True,  "name": "Calibrated Combined Champion"},
}


class R3Ranker:
    """Configurable ranking pipeline executing Phase R3 Treatments A through I."""

    def __init__(self, config: Optional[Dict[str, any]] = None):
        self.config = dict(DEFAULT_CONFIG)
        if config:
            self.config.update(config)

        self.ast_matcher = ASTSymbolMatcher(
            def_boost=self.config["ast_def_boost"],
            impl_boost=self.config["ast_impl_boost"],
            trace_test_penalty=self.config["ast_trace_penalty"],
        )

    def rank(
        self,
        candidates: List[dict],
        query_text: str,
        treatment: str = "A"
    ) -> Tuple[List[dict], Dict[str, any]]:
        start_time = time.perf_counter()
        spec = TREATMENTS.get(treatment, TREATMENTS["A"])

        use_sfs = spec["sfs"]
        use_tip = spec["tip"]
        use_ast = spec["ast"]
        bm25_variant = spec["bm25_variant"]
        use_intent_routing = spec["intent_routing"]

        # 1. Query context signals
        seeds = SeedExtractor.extract_seeds(query_text)
        relational_intent = SeedExtractor.determine_intent(query_text, seeds)
        test_prob = TestIntentClassifier.predict_score(query_text)
        is_test_intent = test_prob >= self.config["tip_threshold"]
        classified_intent = ASTIntentClassifier.classify(query_text, test_prob=test_prob)

        telemetry = {
            "treatment": treatment,
            "treatment_name": spec["name"],
            "seeds": list(seeds),
            "relational_intent": relational_intent,
            "test_intent_prob": test_prob,
            "is_test_intent": is_test_intent,
            "classified_intent": classified_intent,
            "sfs_applied": False,
            "tip_applied": False,
            "ast_applied": False,
            "bm25_applied": False,
        }

        sfs_factor = self.config["sfs_demotion_factor"]
        tip_weight = self.config["tip_boost_weight"]
        bm25_damping_w = self.config["bm25_damping_weight"]

        modified = []
        for c in candidates:
            cand = dict(c)
            path = cand.get("path", "")
            norm_path = normalize_path(path)
            cand_is_test = is_test_candidate(path)

            base_score = cand.get("m1_score", 0.0)
            score = base_score
            scores = cand.get("scores", {})
            exact_sym = scores.get("exact_symbol", 0.0)
            field_bm25 = scores.get("field_bm25", 0.0)

            # 1. SFS (Seed File Suppression)
            if use_sfs and relational_intent == "relational" and norm_path in seeds:
                score *= sfs_factor
                cand["sfs_demoted"] = True
                telemetry["sfs_applied"] = True
            else:
                cand["sfs_demoted"] = False

            # 2. TIP (Test Intent Prior)
            if use_tip and is_test_intent and cand_is_test:
                score *= (1.0 + tip_weight * test_prob)
                cand["tip_boosted"] = True
                telemetry["tip_applied"] = True
            else:
                cand["tip_boosted"] = False

            # 3. BM25 Length Normalization Variants
            if bm25_variant != "none" and field_bm25 > 0.0:
                if bm25_variant == "bm25l":
                    # Lv & Zhai (2011) BM25L saturation damping
                    log_ratio = math.log1p(field_bm25) / (1.0 + math.log1p(field_bm25))
                    score *= (1.0 + bm25_damping_w * log_ratio)
                    cand["bm25_boosted"] = True
                    telemetry["bm25_applied"] = True
                elif bm25_variant == "bm25+":
                    # BM25+ additive lower-bound bonus
                    delta = self.config["bm25_plus_delta"]
                    log_bonus = delta * (math.log1p(field_bm25) / 10.0)
                    score *= (1.0 + log_bonus)
                    cand["bm25_boosted"] = True
                    telemetry["bm25_applied"] = True
                elif bm25_variant == "field_bm25":
                    # Multi-field weight adjustment
                    path_boost = 1.2 if any(part in norm_path for part in seeds) else 1.0
                    score *= path_boost
                    cand["bm25_boosted"] = True
                    telemetry["bm25_applied"] = True
            else:
                cand["bm25_boosted"] = False

            # 4. AST Symbol Intelligence
            if use_ast:
                if use_intent_routing:
                    # Full intent-conditioned routing (implementation, definition, test, reference)
                    ast_mult = self.ast_matcher.score_candidate(
                        candidate_path=path,
                        exact_symbol_score=exact_sym,
                        is_test_path=cand_is_test,
                        intent=classified_intent,
                    )
                    score *= ast_mult
                    cand["ast_multiplier"] = ast_mult
                    if ast_mult != 1.0:
                        telemetry["ast_applied"] = True
                else:
                    # Generic AST definition boost (only on non-test files when not test intent)
                    if exact_sym > 0.0 and not is_test_intent and not cand_is_test:
                        ast_mult = 1.0 + 0.5 * math.log1p(exact_sym)
                        score *= ast_mult
                        cand["ast_multiplier"] = ast_mult
                        telemetry["ast_applied"] = True
                    else:
                        cand["ast_multiplier"] = 1.0
            else:
                cand["ast_multiplier"] = 1.0

            cand["final_score"] = score
            modified.append(cand)

        # Stable sort by final_score descending, breaking ties with original m1_rank
        reranked = sorted(
            modified,
            key=lambda x: (x.get("final_score", 0.0), -x.get("m1_rank", 9999)),
            reverse=True
        )

        for idx, c in enumerate(reranked, 1):
            c["rank"] = idx

        telemetry["latency_ms"] = (time.perf_counter() - start_time) * 1000.0
        return reranked, telemetry


if __name__ == "__main__":
    from split import load_data
    train_data, val_data, _ = load_data()
    ranker = R3Ranker()

    print("=== Testing R3Ranker on sample query across all Treatments A through I ===")
    sample = train_data[0]
    golds = set(sample["gold_files"])
    print(f"Query ID: {sample['query_id']} | Repo: {sample['repo']} | Gold: {golds}")

    for t_code in ["A", "B", "C", "D", "E", "F", "G", "H", "I"]:
        reranked, telem = ranker.rank(sample["candidates"], sample["query_text"], treatment=t_code)
        first_gold = next((c for c in reranked if c["path"] in golds), None)
        fg_rank = first_gold["rank"] if first_gold else "None"
        top1 = reranked[0]["path"] if reranked else "None"
        print(f"  Treatment {t_code} ({TREATMENTS[t_code]['name']:<35}): First Gold Rank = {str(fg_rank):<4} | Top-1: {top1[:32]}")

