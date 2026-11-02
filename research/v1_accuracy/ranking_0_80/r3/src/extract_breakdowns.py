import os
import sys
import json
from collections import defaultdict
import numpy as np

jsonl_path = "research/v1_accuracy/ranking_0_80/r3/PER_QUERY_COMPARISON.jsonl"
records = []
with open(jsonl_path, "r", encoding="utf-8") as f:
    for line in f:
        records.append(json.loads(line))

# Breakdown by task type for A and I
tasks = ["code2test", "trace2code", "comment2context", "edit2ripple"]
print("=== Task Type Breakdown (MRR) ===")
print(f"{'Task':<18} | {'Count':<5} | {'Treatment A':<12} | {'Treatment I':<12} | {'Delta':<10}")
print("-" * 65)
for t in tasks:
    sub = [r for r in records if r["task_type"] == t]
    mrr_a = np.mean([r["treatments"]["A"]["reciprocal_rank"] for r in sub])
    mrr_i = np.mean([r["treatments"]["I"]["reciprocal_rank"] for r in sub])
    print(f"{t:<18} | {len(sub):<5} | {mrr_a:<12.4f} | {mrr_i:<12.4f} | {mrr_i - mrr_a:<+10.4f}")

# Breakdown by repo on Validation set
val_records = [r for r in records if r["split"] == "val"]
repos = sorted(list(set(r["repo"] for r in val_records)))
print("\n=== Validation Repositories Breakdown (MRR) ===")
print(f"{'Repository':<25} | {'Count':<5} | {'Treatment A':<12} | {'Treatment I':<12} | {'Delta':<10}")
print("-" * 72)
for rp in repos:
    sub = [r for r in val_records if r["repo"] == rp]
    mrr_a = np.mean([r["treatments"]["A"]["reciprocal_rank"] for r in sub])
    mrr_i = np.mean([r["treatments"]["I"]["reciprocal_rank"] for r in sub])
    print(f"{rp:<25} | {len(sub):<5} | {mrr_a:<12.4f} | {mrr_i:<12.4f} | {mrr_i - mrr_a:<+10.4f}")

