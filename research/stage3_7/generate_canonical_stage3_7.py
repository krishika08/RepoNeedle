"""
Stage 3.7: Generate Canonical Evaluation Results and Per-Query JSONL.
"""

import csv
import json
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
STAGE_DIR = ROOT_DIR / "research" / "stage3_7"


def main():
    s36_path = ROOT_DIR / "research" / "stage3_6" / "PER_QUERY_RESULTS.csv"
    rows = list(csv.DictReader(open(s36_path, encoding="utf-8")))

    by_sys = defaultdict(list)
    per_query_records = defaultdict(dict)

    for r in rows:
        sys_id = r["system_id"]
        qid = r["query_id"]
        mrr = float(r["mrr"])
        r5 = float(r["recall_at_5"])
        r10 = float(r["recall_at_10"])
        r20 = float(r["recall_at_20"])
        p5 = float(r["precision_at_5"])
        bcy8k = float(r["bcy_at_8k"])
        hit20 = 1.0 if r20 > 0.0 else 0.0

        record = {
            "query_id": qid,
            "repo": r["repo"],
            "task_type": r["task_type"],
            "language": r["language"],
            "system_id": sys_id,
            "mrr": mrr,
            "recall_at_5": r5,
            "recall_at_10": r10,
            "recall_at_20": r20,
            "hit_at_20": hit20,
            "precision_at_5": p5,
            "bcy_at_8k": bcy8k,
        }
        by_sys[sys_id].append(record)
        per_query_records[qid][sys_id] = record

    can_rows = []
    for sys_id in ["BASE-BM25", "CAND-C", "CAND-F", "BASE-REPOMAP"]:
        sys_list = by_sys[sys_id]
        n = len(sys_list)
        mrr_val = float(np.mean([x["mrr"] for x in sys_list]))
        r5_val = float(np.mean([x["recall_at_5"] for x in sys_list]))
        r10_val = float(np.mean([x["recall_at_10"] for x in sys_list]))
        r20_val = float(np.mean([x["recall_at_20"] for x in sys_list]))
        hit20_val = float(np.mean([x["hit_at_20"] for x in sys_list]))
        p5_val = float(np.mean([x["precision_at_5"] for x in sys_list]))
        bcy8k_val = float(np.mean([x["bcy_at_8k"] for x in sys_list]))

        can_rows.append({
            "system_id": sys_id,
            "evaluation_scope": "Full Repository Corpus (N=345)",
            "query_count": n,
            "mrr": f"{mrr_val:.4f}",
            "recall_at_5": f"{r5_val:.4f}",
            "recall_at_10": f"{r10_val:.4f}",
            "recall_at_20_fractional": f"{r20_val:.4f}",
            "hit_at_20_binary": f"{hit20_val:.4f}",
            "precision_at_5": f"{p5_val:.4f}",
            "bcy_at_8k": f"{bcy8k_val:.4f}",
        })

    out_csv = STAGE_DIR / "CANONICAL_RESULTS.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(can_rows[0].keys()))
        w.writeheader()
        w.writerows(can_rows)
    print(f"Wrote {out_csv.name}")

    out_jsonl = STAGE_DIR / "PER_QUERY_RESULTS.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for qid in sorted(per_query_records.keys()):
            f.write(json.dumps({"query_id": qid, "systems": per_query_records[qid]}) + "\n")
    print(f"Wrote {out_jsonl.name} ({len(per_query_records)} queries)")

    for r in can_rows:
        print(r)


if __name__ == "__main__":
    main()
