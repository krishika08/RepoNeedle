"""
Verify Stage 2 matrix completeness, sample-configuration coverage,
and orthogonal separation of ranking vs context packing.
"""

import json
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent

pred_file = ROOT_DIR / "research" / "stage2_results" / "PER_SAMPLE_ABLATIONS.jsonl"
records = [json.loads(l) for l in open(pred_file, encoding="utf-8") if l.strip()]

print(f"Total records in PER_SAMPLE_ABLATIONS.jsonl: {len(records)}")

# 1. Sample ID uniqueness & completeness
sample_ids = [r["sample_id"] for r in records]
unique_ids = set(sample_ids)
duplicates = len(sample_ids) - len(unique_ids)
print(f"Unique sample IDs: {len(unique_ids)} (Duplicates: {duplicates})")

# Check by subset
by_subset = defaultdict(int)
for r in records:
    by_subset[r.get("subset", r.get("task_type"))] += 1
for s, count in sorted(by_subset.items()):
    print(f"  Track {s:20s}: {count} samples")

# 2. Configuration completeness
config_ids = [f"EXP-{i:03d}" for i in range(1, 33)]
completeness = {}
nan_counts = defaultdict(int)
failed_evals = defaultdict(int)

for cid in config_ids:
    eval_count = 0
    for r in records:
        if cid in r["evaluations"]:
            eval_data = r["evaluations"][cid]
            if eval_data is None:
                failed_evals[cid] += 1
            elif any(np.isnan(eval_data[m]) for m in ["mrr", "recall@5", "recall@10", "recall@20", "bcy@4k", "bcy@8k"]):
                nan_counts[cid] += 1
            else:
                eval_count += 1
        else:
            failed_evals[cid] += 1
    completeness[cid] = eval_count

print(f"\nConfiguration Coverage:")
all_345 = all(c == 345 for c in completeness.values())
print(f"All 32 configurations have exactly 345/345 valid evaluations: {all_345}")
print(f"Total NaNs across all 32 configs: {sum(nan_counts.values())}")
print(f"Total failed/missing across all 32 configs: {sum(failed_evals.values())}")

# 3. Orthogonal Separation of Ranking vs Context Packing (Factor E)
# Check all 16 pairs of (E=1 vs E=0)
print(f"\nOrthogonal Separation Check (Ranking identical between E=1 and E=0):")
ranking_identical = True
bcy_differs = True

pairs = [
    ("EXP-001", "EXP-002"),
    ("EXP-003", "EXP-004"),
    ("EXP-005", "EXP-006"),
    ("EXP-007", "EXP-008"),
    ("EXP-009", "EXP-010"),
    ("EXP-011", "EXP-012"),
    ("EXP-013", "EXP-014"),
    ("EXP-015", "EXP-016"),
    ("EXP-017", "EXP-018"),
    ("EXP-019", "EXP-020"),
    ("EXP-021", "EXP-022"),
    ("EXP-023", "EXP-024"),
    ("EXP-025", "EXP-026"),
    ("EXP-027", "EXP-028"),
    ("EXP-029", "EXP-030"),
    ("EXP-031", "EXP-032"),
]

for e1, e0 in pairs:
    mrr_diffs = [abs(r["evaluations"][e1]["mrr"] - r["evaluations"][e0]["mrr"]) for r in records]
    r20_diffs = [abs(r["evaluations"][e1]["recall@20"] - r["evaluations"][e0]["recall@20"]) for r in records]
    bcy_diffs = [abs(r["evaluations"][e1]["bcy@8k"] - r["evaluations"][e0]["bcy@8k"]) for r in records]

    max_mrr_diff = max(mrr_diffs)
    max_r20_diff = max(r20_diffs)
    mean_bcy_diff = np.mean(bcy_diffs)

    if max_mrr_diff > 1e-9 or max_r20_diff > 1e-9:
        ranking_identical = False
        print(f"  WARNING: Ranking mismatch between {e1} and {e0}: max MRR diff = {max_mrr_diff}")
    if mean_bcy_diff == 0:
        bcy_differs = False
        print(f"  WARNING: BCY identical between {e1} and {e0}")

print(f"All 16 pairs have strictly identical file rankings (MRR & Recall diff = 0.000000): {ranking_identical}")
print(f"Skeletons strictly modify token packing efficiency (BCY differs): {bcy_differs}")

