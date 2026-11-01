import json
import numpy as np

with open("research/v1_accuracy/m3_context_optimization/M3_BASELINE_RAW_RESULTS.jsonl", "r", encoding="utf-8") as f:
    raw = [json.loads(line) for line in f]

dev_ids = {r["query_id"] for r in raw[::7][:50]}
dev_raw = [r for r in raw if r["query_id"] in dev_ids]

print(f"Loaded {len(dev_raw)} baseline records for dev queries.")

for B in ["2048", "4096", "8192", "16384"]:
    b_records = [r["budgets"][B] for r in dev_raw]
    comp_full = sum(1 for b in b_records if b["gold_metrics"]["complete_gold_full"])
    comp_any = sum(1 for b in b_records if b["gold_metrics"]["complete_gold_any"])
    micro_full = sum(b["gold_metrics"]["gold_full_count"] for b in b_records) / sum(r["num_gold_files"] for r in dev_raw)
    micro_any = sum(b["gold_metrics"]["gold_any_count"] for b in b_records) / sum(r["num_gold_files"] for r in dev_raw)
    overflows = sum(1 for b in b_records if b["is_overflow_event_exact"])
    
    print(f"M3.2 Baseline Budget {B:>5}: Complete (Full): {comp_full/len(dev_raw):6.2%} | Complete (Any): {comp_any/len(dev_raw):6.2%} | Micro (Full): {micro_full:6.2%} | Micro (Any): {micro_any:6.2%} | Overflows: {overflows}/{len(dev_raw)} ({overflows/len(dev_raw):.1%})")

