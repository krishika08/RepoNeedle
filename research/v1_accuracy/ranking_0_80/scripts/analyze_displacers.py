"""
Feature discrepancy analysis: Gold vs Displacer.
Analyze lexical, symbol, path, and structural features between Gold files and the files displacing them.
"""
import gzip
import json
import os
import re
from collections import defaultdict, Counter
import numpy as np

def analyze_displacers():
    with open("reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl", "r", encoding="utf-8") as f:
        baseline_records = {r["sample_id"]: r for r in (json.loads(l) for l in f if l.strip())}
        
    m1_records = {}
    with gzip.open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                m1_records[data["query_id"]] = data

    print("=== DISPLACER FEATURE ANALYSIS ===")
    
    # We want to understand for queries where first gold is rank > 1:
    # 1. What rank is the first gold?
    # 2. What are the score differences between Rank 1 and First Gold?
    # 3. What channels did Rank 1 have that First Gold lacked, or vice versa?
    
    channel_counts_rank1 = Counter()
    channel_counts_gold = Counter()
    
    score_diffs = defaultdict(list)
    
    # Path naming patterns:
    # e.g., how often does the gold filename share the exact base stem with a symbol in the query?
    stem_matches_gold = 0
    stem_matches_top1 = 0
    
    for qid, base in baseline_records.items():
        m1 = m1_records[qid]
        gold_files = set(base["gold_files"])
        cands = m1["candidates"]
        
        top1 = cands[0]
        for ch in top1.get("channels", []):
            channel_counts_rank1[ch] += 1
            
        first_gold = None
        for c in cands:
            if c["path"] in gold_files:
                first_gold = c
                break
                
        if first_gold:
            for ch in first_gold.get("channels", []):
                channel_counts_gold[ch] += 1
                
            # Channel scores
            for ch_name in ["exact_symbol", "field_bm25", "subwords", "structural_expansion"]:
                s_top1 = top1.get("scores", {}).get(ch_name, 0.0)
                s_gold = first_gold.get("scores", {}).get(ch_name, 0.0)
                score_diffs[ch_name].append(s_top1 - s_gold)
                
    print("\nChannel presence at Rank 1:")
    for ch, count in channel_counts_rank1.most_common():
        print(f"  {ch:<25}: {count}/345 ({count/345*100:.1f}%)")
        
    print("\nChannel presence in First Gold candidate:")
    for ch, count in channel_counts_gold.most_common():
        print(f"  {ch:<25}: {count}/345 ({count/345*100:.1f}%)")
        
    print("\nAverage Score Margin (Rank 1 - First Gold):")
    for ch, diffs in score_diffs.items():
        print(f"  {ch:<25}: Mean diff = {np.mean(diffs):.2f}, Median = {np.median(diffs):.2f}")

if __name__ == "__main__":
    analyze_displacers()

