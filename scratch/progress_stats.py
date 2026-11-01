import json, pathlib
from collections import Counter
import numpy as np

p = pathlib.Path("research/v1_accuracy/m1_candidate_generation/checkpoint_m1.jsonl")
records = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]

qids = [r["query_id"] for r in records]
counts = Counter(qids)
dups = {k: v for k, v in counts.items() if v > 1}

repos = Counter(r["repo"] for r in records)
tracks = Counter(r["track"] for r in records)

all_golds = sum(r["configs"]["all_channels"]["gold_count"] for r in records)
found_golds = sum(r["configs"]["all_channels"]["golds_found"] for r in records)
found_golds_50 = sum(r["configs"]["all_channels"]["golds_found_at_50"] for r in records)

micro_rec = found_golds / all_golds if all_golds > 0 else 0.0
macro_rec = float(np.mean([r["configs"]["all_channels"]["candidate_recall"] for r in records]))
comp_cov = float(np.mean([r["configs"]["all_channels"]["complete_coverage"] for r in records]))

micro_rec_50 = found_golds_50 / all_golds if all_golds > 0 else 0.0
macro_rec_50 = float(np.mean([r["configs"]["all_channels"]["recall_at_50"] for r in records]))
comp_cov_50 = float(np.mean([1.0 if r["configs"]["all_channels"]["golds_found_at_50"] == r["configs"]["all_channels"]["gold_count"] else 0.0 for r in records]))

pools = [r["configs"]["all_channels"]["candidate_pool_size"] for r in records]

# Failed queries (Recall < 1.0)
failed_recall = [r for r in records if r["configs"]["all_channels"]["candidate_recall"] < 1.0]

# Failed Recall@50
failed_r50 = [r for r in records if r["configs"]["all_channels"]["recall_at_50"] < 1.0]

print("=== CURRENT CHECKPOINT PROGRESS ===")
print(f"Total Completed Queries:     {len(records)}")
print(f"Unique Query IDs:            {len(counts)}")
print(f"Duplicate Records:           {len(dups)}")
print(f"Unverified Records (Ver 1.0): 29 (Records 1-29)")
print(f"Verified Records (Ver 1.1):   {len(records) - 29} (Records 30-{len(records)})")
print()
print("Repository Distribution:")
for r, c in repos.most_common():
    print(f"  {r}: {c} queries")
print()
print("Track Distribution:")
for t, c in tracks.most_common():
    print(f"  {t}: {c} queries")
print()
print("Candidate Recall Metrics (All Completed):")
print(f"  A. Micro Candidate Recall:      {micro_rec:.4f} ({micro_rec*100:.2f}%) [{found_golds}/{all_golds}]")
print(f"  B. Macro Candidate Recall:      {macro_rec:.4f} ({macro_rec*100:.2f}%)")
print(f"  C. Complete-Gold Coverage:      {comp_cov:.4f} ({comp_cov*100:.2f}%)")
print(f"  D. Candidate Recall@50 (Macro): {macro_rec_50:.4f} ({macro_rec_50*100:.2f}%)")
print(f"     Candidate Recall@50 (Micro): {micro_rec_50:.4f} ({micro_rec_50*100:.2f}%) [{found_golds_50}/{all_golds}]")
print(f"  E. Complete-Gold Coverage@50:   {comp_cov_50:.4f} ({comp_cov_50*100:.2f}%)")
print(f"  F. Candidate Pool Size:")
print(f"       Mean:   {np.mean(pools):.1f}")
print(f"       Median: {np.median(pools):.1f}")
print(f"       p95:    {np.percentile(pools, 95):.1f}")
print(f"       Max:    {max(pools)}")
print()
print(f"Queries with Candidate Recall < 1.0: {len(failed_recall)}")
print(f"Queries with Recall@50 < 1.0:         {len(failed_r50)}")

