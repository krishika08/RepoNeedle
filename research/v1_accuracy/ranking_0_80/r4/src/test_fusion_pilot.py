import os
import sys
import gzip
import json
import math
import numpy as np
from typing import Dict, List, Set, Tuple
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "r2", "src")))
from split import load_data
from seed_suppression import SeedExtractor, normalize_path
from test_intent import TestIntentClassifier, is_test_candidate

train_data, val_data, held_out_data = load_data()

def evaluate_rankings(data: List[dict], ranker_fn) -> Dict[str, float]:
    rr_sum = 0.0
    hit1 = 0
    r5 = 0.0
    r10 = 0.0
    r20 = 0.0
    total = len(data)

    for item in data:
        reranked = ranker_fn(item)
        golds = set(item["gold_files"])
        ranks = [idx + 1 for idx, c in enumerate(reranked) if c["path"] in golds]
        if ranks:
            first_rank = ranks[0]
            rr_sum += 1.0 / first_rank
            if first_rank == 1:
                hit1 += 1
            r5 += sum(1 for r in ranks if r <= 5) / len(golds)
            r10 += sum(1 for r in ranks if r <= 10) / len(golds)
            r20 += sum(1 for r in ranks if r <= 20) / len(golds)

    return {
        "mrr": rr_sum / total if total else 0.0,
        "hit1_pct": (hit1 / total) * 100.0 if total else 0.0,
        "recall@5": r5 / total if total else 0.0,
        "recall@10": r10 / total if total else 0.0,
        "recall@20": r20 / total if total else 0.0,
        "total": total,
    }

# Baseline: Treatment A (Frozen R2 Treatment E)
def rank_treatment_a(item: dict) -> List[dict]:
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

# Treatment B: Dense semantic retrieval alone (subwords score alone)
def rank_treatment_b(item: dict) -> List[dict]:
    cands = []
    for c in item["candidates"]:
        cand = dict(c)
        score = cand.get("scores", {}).get("subwords", 0.0)
        cand["final_score"] = score
        cands.append(cand)
    cands.sort(key=lambda x: (x.get("final_score", 0.0), -x.get("m1_rank", 9999)), reverse=True)
    return cands

# Treatment C: Multi-hop graph retrieval alone (structural expansion score alone)
def rank_treatment_c(item: dict) -> List[dict]:
    cands = []
    for c in item["candidates"]:
        cand = dict(c)
        score = cand.get("scores", {}).get("structural_expansion", 0.0)
        cand["final_score"] = score
        cands.append(cand)
    cands.sort(key=lambda x: (x.get("final_score", 0.0), -x.get("m1_rank", 9999)), reverse=True)
    return cands

# Treatment D: R2 + dense retrieval (R2 baseline score boosted by dense semantic score)
def rank_treatment_d(item: dict) -> List[dict]:
    base_ranked = rank_treatment_a(item)
    max_dense = max((c.get("scores", {}).get("subwords", 0.0) for c in base_ranked), default=1.0) or 1.0
    cands = []
    for c in base_ranked:
        cand = dict(c)
        dense_norm = cand.get("scores", {}).get("subwords", 0.0) / max_dense
        cand["final_score"] = cand["final_score"] * (1.0 + 0.3 * dense_norm)
        cands.append(cand)
    cands.sort(key=lambda x: (x.get("final_score", 0.0), -x.get("m1_rank", 9999)), reverse=True)
    return cands

# Treatment E: R2 + graph retrieval (R2 baseline score boosted by structural expansion score)
def rank_treatment_e(item: dict) -> List[dict]:
    base_ranked = rank_treatment_a(item)
    max_graph = max((c.get("scores", {}).get("structural_expansion", 0.0) for c in base_ranked), default=1.0) or 1.0
    cands = []
    for c in base_ranked:
        cand = dict(c)
        graph_norm = cand.get("scores", {}).get("structural_expansion", 0.0) / max_graph
        cand["final_score"] = cand["final_score"] * (1.0 + 0.2 * graph_norm)
        cands.append(cand)
    cands.sort(key=lambda x: (x.get("final_score", 0.0), -x.get("m1_rank", 9999)), reverse=True)
    return cands

# Treatment F: Dense + graph
def rank_treatment_f(item: dict) -> List[dict]:
    cands = []
    max_dense = max((c.get("scores", {}).get("subwords", 0.0) for c in item["candidates"]), default=1.0) or 1.0
    max_graph = max((c.get("scores", {}).get("structural_expansion", 0.0) for c in item["candidates"]), default=1.0) or 1.0
    for c in item["candidates"]:
        cand = dict(c)
        d_norm = cand.get("scores", {}).get("subwords", 0.0) / max_dense
        g_norm = cand.get("scores", {}).get("structural_expansion", 0.0) / max_graph
        cand["final_score"] = 0.7 * d_norm + 0.3 * g_norm
        cands.append(cand)
    cands.sort(key=lambda x: (x.get("final_score", 0.0), -x.get("m1_rank", 9999)), reverse=True)
    return cands

# Treatment G: R2 + dense + graph
def rank_treatment_g(item: dict) -> List[dict]:
    base_ranked = rank_treatment_a(item)
    max_dense = max((c.get("scores", {}).get("subwords", 0.0) for c in base_ranked), default=1.0) or 1.0
    max_graph = max((c.get("scores", {}).get("structural_expansion", 0.0) for c in base_ranked), default=1.0) or 1.0
    cands = []
    for c in base_ranked:
        cand = dict(c)
        d_norm = cand.get("scores", {}).get("subwords", 0.0) / max_dense
        g_norm = cand.get("scores", {}).get("structural_expansion", 0.0) / max_graph
        cand["final_score"] = cand["final_score"] * (1.0 + 0.25 * d_norm + 0.15 * g_norm)
        cands.append(cand)
    cands.sort(key=lambda x: (x.get("final_score", 0.0), -x.get("m1_rank", 9999)), reverse=True)
    return cands

# Treatment H: Calibrated Hybrid Fusion (Reciprocal Rank Fusion of R2, Dense, and Graph)
def rank_treatment_h(item: dict) -> List[dict]:
    # Compute rank positions in each channel
    candidates = item["candidates"]
    r2_ranked = rank_treatment_a(item)
    r2_ranks = {c["path"]: idx + 1 for idx, c in enumerate(r2_ranked)}

    dense_ranked = sorted(candidates, key=lambda c: c.get("scores", {}).get("subwords", 0.0), reverse=True)
    dense_ranks = {c["path"]: idx + 1 for idx, c in enumerate(dense_ranked)}

    graph_ranked = sorted(candidates, key=lambda c: c.get("scores", {}).get("structural_expansion", 0.0), reverse=True)
    graph_ranks = {c["path"]: idx + 1 for idx, c in enumerate(graph_ranked)}

    # RRF with calibrated k = 60
    k_rrf = 60.0
    cands = []
    for c in candidates:
        cand = dict(c)
        p = cand["path"]
        rrf_score = (
            0.60 * (1.0 / (k_rrf + r2_ranks.get(p, 9999))) +
            0.25 * (1.0 / (k_rrf + dense_ranks.get(p, 9999))) +
            0.15 * (1.0 / (k_rrf + graph_ranks.get(p, 9999)))
        )
        cand["final_score"] = rrf_score
        cands.append(cand)

    cands.sort(key=lambda x: (x.get("final_score", 0.0), -x.get("m1_rank", 9999)), reverse=True)
    return cands

treatments = {
    "A": ("Frozen R2 Baseline (Treatment E)", rank_treatment_a),
    "B": ("Dense Retrieval Alone", rank_treatment_b),
    "C": ("Multi-hop Graph Alone", rank_treatment_c),
    "D": ("R2 + Dense Retrieval", rank_treatment_d),
    "E": ("R2 + Graph Retrieval", rank_treatment_e),
    "F": ("Dense + Graph", rank_treatment_f),
    "G": ("R2 + Dense + Graph", rank_treatment_g),
    "H": ("Calibrated Hybrid Fusion (RRF)", rank_treatment_h),
}

print("=== Pilot Evaluation of Treatments A through H on Validation Set ===")
print(f"{'Code':<4} | {'Treatment':<32} | {'Val MRR':<9} | {'Val Hit@1':<10} | {'Val R@20':<9} | {'Train MRR':<10}")
print("-" * 85)
for code, (name, fn) in treatments.items():
    val_m = evaluate_rankings(val_data, fn)
    train_m = evaluate_rankings(train_data, fn)
    print(f"{code:<4} | {name:<32} | {val_m['mrr']:<9.4f} | {val_m['hit1_pct']:<9.2f}% | {val_m['recall@20']:<9.4f} | {train_m['mrr']:<10.4f}")

