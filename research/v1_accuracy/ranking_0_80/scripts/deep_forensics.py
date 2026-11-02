"""
Comprehensive forensic breakdown by task type, repository, and channel provenance.
"""
import gzip
import json
from collections import defaultdict, Counter
import numpy as np

def deep_forensics():
    # Load v0.1.0 baseline records
    with open("reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl", "r", encoding="utf-8") as f:
        baseline_records = {r["sample_id"]: r for r in (json.loads(l) for l in f if l.strip())}
        
    # Load M1 frozen candidates
    m1_records = {}
    with gzip.open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                m1_records[data["query_id"]] = data

    print("=== BREAKDOWN BY TASK TYPE ===")
    by_task = defaultdict(lambda: {"v0_mrr": [], "m1_mrr": [], "v0_r20": [], "m1_r20": [], "ranks_m1": []})
    by_repo = defaultdict(lambda: {"v0_mrr": [], "m1_mrr": [], "v0_r20": [], "m1_r20": [], "count": 0})
    
    for qid, base in baseline_records.items():
        m1 = m1_records[qid]
        task = base.get("task_type", "unknown")
        repo = base["repo"]
        gold_files = set(base["gold_files"])
        
        # v0 metrics
        v0_mrr = base["reponeedle"]["mrr"]
        v0_r20 = base["reponeedle"]["recall@20"]
        
        # M1 metrics
        # find ranks of all gold files in M1
        m1_cand_map = {c["path"]: c for c in m1["candidates"]}
        gold_ranks_m1 = []
        for gf in gold_files:
            if gf in m1_cand_map:
                gold_ranks_m1.append(m1_cand_map[gf]["m1_rank"])
        
        first_gold_rank_m1 = min(gold_ranks_m1) if gold_ranks_m1 else None
        m1_mrr = 1.0 / first_gold_rank_m1 if first_gold_rank_m1 else 0.0
        m1_r20 = sum(1 for r in gold_ranks_m1 if r <= 20) / len(gold_files)
        
        by_task[task]["v0_mrr"].append(v0_mrr)
        by_task[task]["m1_mrr"].append(m1_mrr)
        by_task[task]["v0_r20"].append(v0_r20)
        by_task[task]["m1_r20"].append(m1_r20)
        by_task[task]["ranks_m1"].append(first_gold_rank_m1)
        
        by_repo[repo]["v0_mrr"].append(v0_mrr)
        by_repo[repo]["m1_mrr"].append(m1_mrr)
        by_repo[repo]["v0_r20"].append(v0_r20)
        by_repo[repo]["m1_r20"].append(m1_r20)
        by_repo[repo]["count"] += 1

    print(f"{'Task Type':<18} | {'Count':<5} | {'v0 MRR':<8} | {'M1 MRR':<8} | {'v0 R@20':<8} | {'M1 R@20':<8} | {'M1 R1=1':<8} | {'M1 R1<=5':<8}")
    print("-" * 85)
    for task, data in sorted(by_task.items()):
        cnt = len(data["v0_mrr"])
        v0_m = np.mean(data["v0_mrr"])
        m1_m = np.mean(data["m1_mrr"])
        v0_r = np.mean(data["v0_r20"])
        m1_r = np.mean(data["m1_r20"])
        r1_1 = sum(1 for r in data["ranks_m1"] if r == 1)
        r1_5 = sum(1 for r in data["ranks_m1"] if r is not None and r <= 5)
        print(f"{task:<18} | {cnt:<5} | {v0_m:<8.4f} | {m1_m:<8.4f} | {v0_r:<8.4f} | {m1_r:<8.4f} | {r1_1:<8} | {r1_5:<8}")

    print("\n=== BREAKDOWN BY REPOSITORY ===")
    print(f"{'Repository':<35} | {'Count':<5} | {'v0 MRR':<8} | {'M1 MRR':<8} | {'v0 R@20':<8} | {'M1 R@20':<8}")
    print("-" * 80)
    for repo, data in sorted(by_repo.items(), key=lambda x: -x[1]["count"]):
        cnt = data["count"]
        v0_m = np.mean(data["v0_mrr"])
        m1_m = np.mean(data["m1_mrr"])
        v0_r = np.mean(data["v0_r20"])
        m1_r = np.mean(data["m1_r20"])
        print(f"{repo:<35} | {cnt:<5} | {v0_m:<8.4f} | {m1_m:<8.4f} | {v0_r:<8.4f} | {m1_r:<8.4f}")

if __name__ == "__main__":
    deep_forensics()

