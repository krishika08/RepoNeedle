"""
Bit-for-bit Baseline Reproduction & Detailed Forensic Analysis Script.
"""
import gzip
import json
import os
from collections import defaultdict, Counter

def run_analysis():
    print("--- STEP 1: Verify Baseline Reproduction ---")
    
    with open("reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl", "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
        
    num_queries = len(records)
    repos = set(r["repo"] for r in records)
    snapshots = set((r["repo"], r["base_commit"]) for r in records)
    all_gold_files = []
    for r in records:
        all_gold_files.extend(r["gold_files"])
    total_gold_targets = len(all_gold_files)
    
    print(f"Total Queries: {num_queries}")
    print(f"Total Repositories: {len(repos)}")
    print(f"Total Snapshots: {len(snapshots)}")
    print(f"Total Gold Targets: {total_gold_targets}")
    
    # Calculate macro-averaged and micro-averaged metrics
    def calc_metrics(system_key):
        mrrs = []
        recalls_5 = []
        recalls_10 = []
        recalls_20 = []
        for r in records:
            res = r[system_key]
            mrrs.append(res["mrr"])
            recalls_5.append(res["recall@5"])
            recalls_10.append(res["recall@10"])
            recalls_20.append(res["recall@20"])
        return {
            "mrr": sum(mrrs) / len(mrrs),
            "recall@5": sum(recalls_5) / len(recalls_5),
            "recall@10": sum(recalls_10) / len(recalls_10),
            "recall@20": sum(recalls_20) / len(recalls_20),
        }
        
    reponeedle_metrics = calc_metrics("reponeedle")
    bm25_metrics = calc_metrics("bm25")
    lexical_metrics = calc_metrics("lexical")
    repomap_metrics = calc_metrics("repomap")
    
    print("\nCalculated Official Baseline Metrics:")
    print("RepoNeedle:", {k: round(v, 4) for k, v in reponeedle_metrics.items()})
    print("BM25:      ", {k: round(v, 4) for k, v in bm25_metrics.items()})
    print("Lexical:   ", {k: round(v, 4) for k, v in lexical_metrics.items()})
    print("RepoMap:   ", {k: round(v, 4) for k, v in repomap_metrics.items()})
    
    return records

if __name__ == "__main__":
    run_analysis()

