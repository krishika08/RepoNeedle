"""
Integrated R2 Ranker Module supporting Treatments A through H.
Enables controlled, reproducible evaluation of individual and combined ranking features.
"""
import os
import sys
import time
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seed_suppression import SeedExtractor, SeedSuppressor, normalize_path
from test_intent import TestIntentClassifier, TestIntentPrior, is_test_candidate
from stem_symmetry import StemDirectorySymmetry, StemSymmetryReranker

DEFAULT_CONFIG = {
    # R2.1 SFS
    "sfs_demotion_factor": 0.01,
    # R2.2 TIP
    "tip_boost_weight": 1.5,
    "tip_threshold": 0.5,
    # R2.3 SMS
    "sms_weight": 0.5,
}

TREATMENTS = {
    "A": {"sfs": False, "tip": False, "sms": False, "name": "Frozen Baseline (M1)"},
    "B": {"sfs": True,  "tip": False, "sms": False, "name": "SFS Alone"},
    "C": {"sfs": False, "tip": True,  "sms": False, "name": "TIP Alone"},
    "D": {"sfs": False, "tip": False, "sms": True,  "name": "SMS Alone"},
    "E": {"sfs": True,  "tip": True,  "sms": False, "name": "SFS + TIP"},
    "F": {"sfs": True,  "tip": False, "sms": True,  "name": "SFS + SMS"},
    "G": {"sfs": False, "tip": True,  "sms": True,  "name": "TIP + SMS"},
    "H": {"sfs": True,  "tip": True,  "sms": True,  "name": "SFS + TIP + SMS (Combined)"},
}

class R2Ranker:
    """Configurable ranking pipeline executing treatments A through H."""

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
        """
        Executes specified treatment on candidate pool.
        Returns:
            reranked_candidates: Sorted candidate list with final ranks and scores.
            telemetry: Execution metadata and latency.
        """
        start_time = time.perf_counter()
        treatment_spec = TREATMENTS.get(treatment, TREATMENTS["A"])

        use_sfs = treatment_spec["sfs"]
        use_tip = treatment_spec["tip"]
        use_sms = treatment_spec["sms"]

        # 1. Extract query context signals
        seeds = SeedExtractor.extract_seeds(query_text)
        intent = SeedExtractor.determine_intent(query_text, seeds)
        test_intent_prob = TestIntentClassifier.predict_score(query_text)
        is_test_intent = test_intent_prob >= self.config["tip_threshold"]

        telemetry = {
            "treatment": treatment,
            "treatment_name": treatment_spec["name"],
            "seeds": list(seeds),
            "intent": intent,
            "test_intent_prob": test_intent_prob,
            "is_test_intent": is_test_intent,
            "sfs_applied": False,
            "tip_applied": False,
            "sms_applied": False,
        }

        # If Treatment A (Baseline), preserve original M1 ordering bit-for-bit
        if treatment == "A":
            reranked = [dict(c) for c in candidates]
            # Verify sorted by m1_rank
            reranked.sort(key=lambda x: x.get("m1_rank", 9999))
            for idx, c in enumerate(reranked, 1):
                c["rank"] = idx
                c["final_score"] = c.get("m1_score", 0.0)
            telemetry["latency_ms"] = (time.perf_counter() - start_time) * 1000.0
            return reranked, telemetry

        # Transform candidate scores
        sfs_factor = self.config["sfs_demotion_factor"]
        tip_weight = self.config["tip_boost_weight"]
        sms_weight = self.config["sms_weight"]

        modified = []
        for c in candidates:
            cand = dict(c)
            path = cand.get("path", "")
            norm_path = normalize_path(path)
            base_score = cand.get("m1_score", 0.0)
            score = base_score

            # 1. SFS feature
            if use_sfs and intent == "relational" and norm_path in seeds:
                score *= sfs_factor
                cand["sfs_demoted"] = True
                telemetry["sfs_applied"] = True
            else:
                cand["sfs_demoted"] = False

            # 2. TIP feature
            if use_tip and is_test_intent and is_test_candidate(path):
                tip_multiplier = 1.0 + (tip_weight * test_intent_prob)
                score *= tip_multiplier
                cand["tip_boosted"] = True
                telemetry["tip_applied"] = True
            else:
                cand["tip_boosted"] = False

            # 3. SMS feature
            if use_sms and intent == "relational" and seeds:
                sms_score = StemDirectorySymmetry.score_candidate(seeds, path)
                if sms_score > 0.1:
                    sms_multiplier = 1.0 + (sms_weight * sms_score)
                    score *= sms_multiplier
                    cand["sms_boosted"] = True
                    telemetry["sms_applied"] = True
                else:
                    cand["sms_boosted"] = False
            else:
                cand["sms_boosted"] = False

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
    train_data, _, _ = load_data()
    ranker = R2Ranker()
    
    print("Testing R2Ranker on sample query across all treatments A..H:")
    sample = train_data[0]
    golds = set(sample["gold_files"])
    print(f"Query ID: {sample['query_id']} | Repo: {sample['repo']} | Gold: {golds}")
    
    for t_code in ["A", "B", "C", "D", "E", "F", "G", "H"]:
        reranked, telem = ranker.rank(sample["candidates"], sample["query_text"], treatment=t_code)
        # Find first gold rank
        first_gold = next((c for c in reranked if c["path"] in golds), None)
        fg_rank = first_gold["rank"] if first_gold else "None"
        top1 = reranked[0]["path"] if reranked else "None"
        print(f"  Treatment {t_code} ({TREATMENTS[t_code]['name']:<28}): First Gold Rank = {fg_rank:<4} | Top-1: {top1[:35]}")

