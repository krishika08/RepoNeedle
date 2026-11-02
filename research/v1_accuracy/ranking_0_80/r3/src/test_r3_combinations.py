import os
import sys
import math
import numpy as np
from typing import Dict, List, Set, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "r2", "src"))
from split import load_data
from seed_suppression import SeedExtractor, normalize_path
from test_intent import TestIntentClassifier, is_test_candidate

train_data, val_data, held_out_data = load_data()

def is_trace_query(query_text: str) -> bool:
    q_lower = query_text.lower()
    return any(kw in q_lower for kw in [
        "traceback", "stack trace", "build failed", "panic:", "exception:", 
        "failure_excerpt", "failed]"
    ]) or ("command" in query_text and "test" in query_text and "fail" in q_lower)

def evaluate(data: List[dict], ranker_fn) -> Dict[str, float]:
    rr_sum = 0.0
    r5_sum = 0.0
    r10_sum = 0.0
    r20_sum = 0.0
    hit1_count = 0
    total = len(data)
    
    for item in data:
        reranked = ranker_fn(item)
        golds = set(item["gold_files"])
        ranks = [idx + 1 for idx, c in enumerate(reranked) if c["path"] in golds]
        
        if ranks:
            first_rank = ranks[0]
            rr_sum += 1.0 / first_rank
            if first_rank == 1:
                hit1_count += 1
        
        k_gold_hits = sum(1 for c in reranked[:5] if c["path"] in golds)
        r5_sum += k_gold_hits / len(golds) if golds else 0.0
        
        k_gold_hits10 = sum(1 for c in reranked[:10] if c["path"] in golds)
        r10_sum += k_gold_hits10 / len(golds) if golds else 0.0
        
        k_gold_hits20 = sum(1 for c in reranked[:20] if c["path"] in golds)
        r20_sum += k_gold_hits20 / len(golds) if golds else 0.0
        
    return {
        "mrr": rr_sum / total if total > 0 else 0.0,
        "hit1": (hit1_count / total) * 100.0 if total > 0 else 0.0,
        "r5": r5_sum / total if total > 0 else 0.0,
        "r10": r10_sum / total if total > 0 else 0.0,
        "r20": r20_sum / total if total > 0 else 0.0,
        "total": total
    }

# Baseline: Treatment E
def rank_baseline_e(item: dict) -> List[dict]:
    query_text = item["query_text"]
    seeds = SeedExtractor.extract_seeds(query_text)
    intent = SeedExtractor.determine_intent(query_text, seeds)
    test_prob = TestIntentClassifier.predict_score(query_text)
    is_test = test_prob >= 0.5
    
    cands = []
    for c in item["candidates"]:
        cand = dict(c)
        path = cand["path"]
        norm_p = normalize_path(path)
        score = cand.get("m1_score", 0.0)
        
        if intent == "relational" and norm_p in seeds:
            score *= 0.01
        if is_test and is_test_candidate(path):
            score *= (1.0 + 1.5 * test_prob)
            
        cand["final_score"] = score
        cands.append(cand)
        
    cands.sort(key=lambda x: (x.get("final_score", 0.0), -x.get("m1_rank", 9999)), reverse=True)
    return cands

# Test different combinations of AST and BM25 enhancements
def make_ranker(
    ast_weight: float = 1.0,
    use_trace_suppression: bool = True,
    bm25_damping: bool = True,
    bm25_plus_delta: float = 0.5
):
    def rank_fn(item: dict) -> List[dict]:
        query_text = item["query_text"]
        seeds = SeedExtractor.extract_seeds(query_text)
        relational_intent = SeedExtractor.determine_intent(query_text, seeds)
        test_prob = TestIntentClassifier.predict_score(query_text)
        is_test = test_prob >= 0.5
        is_trace = is_trace_query(query_text)
        
        cands = []
        for c in item["candidates"]:
            cand = dict(c)
            path = cand["path"]
            norm_p = normalize_path(path)
            cand_is_test = is_test_candidate(path)
            
            # Base M1 score components
            m1_score = cand.get("m1_score", 0.0)
            scores = cand.get("scores", {})
            exact_sym = scores.get("exact_symbol", 0.0)
            field_bm25 = scores.get("field_bm25", 0.0)
            
            score = m1_score
            
            # 1. R2 SFS: Demote relational input seeds
            if relational_intent == "relational" and norm_p in seeds:
                score *= 0.01
                
            # 2. R2 TIP: Boost tests when query has test intent
            if is_test and cand_is_test:
                score *= (1.0 + 1.5 * test_prob)
                
            # 3. R3 Intent: If trace/failure query (and not test-seeking), demote tests
            if use_trace_suppression and is_trace and not is_test:
                if cand_is_test:
                    score *= 0.05
                    
            # 4. R3 AST Symbol Boosting:
            if ast_weight > 0.0 and exact_sym > 0.0:
                # Log-damped AST symbol factor
                ast_mult = 1.0 + ast_weight * math.log1p(exact_sym)
                score *= ast_mult
                
            # 5. R3 BM25 Length Normalization / Damping
            if bm25_damping and field_bm25 > 0.0:
                # Dampen runaway BM25 scores from massive files
                # Using Lv & Zhai lower-bound concept: dampen high BM25 outliers
                # while preserving minimum contribution
                log_ratio = math.log1p(field_bm25) / (1.0 + math.log1p(field_bm25))
                score *= (1.0 + bm25_plus_delta * log_ratio)
                
            cand["final_score"] = score
            cands.append(cand)
            
        cands.sort(key=lambda x: (x.get("final_score", 0.0), -x.get("m1_rank", 9999)), reverse=True)
        return cands
    return rank_fn

print("=== Baseline Treatment E ===")
print("Train:", evaluate(train_data, rank_baseline_e))
print("Val:  ", evaluate(val_data, rank_baseline_e))

print("\n=== Testing R3 Enhancements ===")
for ast_w in [0.0, 0.5, 1.0, 1.5]:
    for use_trace in [False, True]:
        for bm_damp in [False, True]:
            fn = make_ranker(ast_weight=ast_w, use_trace_suppression=use_trace, bm25_damping=bm_damp)
            val_res = evaluate(val_data, fn)
            train_res = evaluate(train_data, fn)
            print(f"ast={ast_w:<3} | trace={str(use_trace):<5} | bm_damp={str(bm_damp):<5} -> Val MRR: {val_res['mrr']:.4f} (Hit@1: {val_res['hit1']:.1f}%) | Train MRR: {train_res['mrr']:.4f}")

