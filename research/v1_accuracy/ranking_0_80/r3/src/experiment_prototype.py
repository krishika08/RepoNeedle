import os
import sys
import gzip
import json
import math
import re
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "r2", "src"))
from split import load_data, TRAIN_REPOS, VAL_REPOS, HELD_OUT_REPOS
from seed_suppression import SeedExtractor, normalize_path
from test_intent import TestIntentClassifier, is_test_candidate

# R3 Intent & AST symbols
DEF_KEYWORDS = {"def", "class", "function", "fn", "struct", "trait", "interface", "type", "enum"}
REF_KEYWORDS = {"call", "caller", "callers", "usages", "references", "invocations", "ripple", "anchor_diff"}
TRACE_KEYWORDS = {"traceback", "stack trace", "fail", "failed", "panic", "error", "exception", "build failed", "test failed"}

def detect_query_intent(query_text: str, test_prob: float) -> str:
    q_lower = query_text.lower()
    
    if test_prob >= 0.5:
        return "test_seeking"
        
    is_trace = any(kw in q_lower for kw in ["traceback", "stack trace", "build failed", "panic:", "exception:", "failure_excerpt"]) or "command" in query_text and "test" in query_text and "fail" in q_lower
    if is_trace:
        return "implementation_seeking"
        
    is_ref = any(kw in q_lower for kw in ["caller", "callers", "call site", "usages", "references", "used in", "invoked"]) or "anchor_diff" in query_text
    if is_ref:
        return "reference_seeking"
        
    is_def = any(kw in q_lower for kw in ["where is", "defined in", "definition", "implementing", "declaration"]) or any(re.search(rf"\b{kw}\s+[A-Za-z_]", q_lower) for kw in DEF_KEYWORDS)
    if is_def:
        return "definition_seeking"
        
    return "general"

def evaluate_predictions(data: List[dict], ranker_fn) -> Dict[str, float]:
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
        
        # Recall@k
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

train_data, val_data, held_out_data = load_data()

# Baseline: R2 Treatment E
def rank_treatment_e(item: dict) -> List[dict]:
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
        
        # SFS
        if intent == "relational" and norm_p in seeds:
            score *= 0.01
            
        # TIP
        if is_test and is_test_candidate(path):
            score *= (1.0 + 1.5 * test_prob)
            
        cand["final_score"] = score
        cands.append(cand)
        
    cands.sort(key=lambda x: (x.get("final_score", 0.0), -x.get("m1_rank", 9999)), reverse=True)
    return cands

print("--- Treatment E (Frozen R2 Baseline) ---")
res_train_e = evaluate_predictions(train_data, rank_treatment_e)
res_val_e = evaluate_predictions(val_data, rank_treatment_e)
print(f"Train: MRR = {res_train_e['marr'] if 'marr' in res_train_e else res_train_e['mrr']:.4f} | Hit@1 = {res_train_e['hit1']:.2f}% | R@20 = {res_train_e['r20']:.4f}")
print(f"Val:   MRR = {res_val_e['mrr']:.4f} | Hit@1 = {res_val_e['hit1']:.2f}% | R@20 = {res_val_e['r20']:.4f}")

