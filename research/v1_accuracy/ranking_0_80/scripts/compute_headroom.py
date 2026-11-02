"""
Compute mathematical headroom and MRR loss decomposition.
"""
import gzip
import json
import numpy as np

def compute_headroom():
    with open("reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl", "r", encoding="utf-8") as f:
        baseline_records = {r["sample_id"]: r for r in (json.loads(l) for l in f if l.strip())}
        
    m1_records = {}
    with gzip.open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                m1_records[data["query_id"]] = data

    v0_first_ranks = []
    m1_first_ranks = []
    
    for qid, base in baseline_records.items():
        gold_files = set(base["gold_files"])
        
        # v0.1.0
        v0_r = None
        for idx, f in enumerate(base["reponeedle"]["top_files"], 1):
            if f in gold_files:
                v0_r = idx
                break
        v0_first_ranks.append(v0_r)
        
        # M1
        m1_r = None
        for c in m1_records[qid]["candidates"]:
            if c["path"] in gold_files:
                m1_r = c["m1_rank"]
                break
        m1_first_ranks.append(m1_r)

    print("=== MRR LOSS DECOMPOSITION & HEADROOM ===")
    
    # Baseline MRR
    v0_mrr = np.mean([1.0/r if r is not None else 0.0 for r in v0_first_ranks])
    m1_mrr = np.mean([1.0/r if r is not None else 0.0 for r in m1_first_ranks])
    print(f"Baseline v0.1.0 MRR: {v0_mrr:.4f} (Loss: {1.0 - v0_mrr:.4f})")
    print(f"M1 Candidates MRR:   {m1_mrr:.4f} (Loss: {1.0 - m1_mrr:.4f})")
    
    # Theoretical Headroom simulations on M1 candidate pool:
    # What if Top-K gold candidates were promoted to Rank 1?
    for k in [1, 2, 3, 4, 5, 10, 15, 20, 50, 100]:
        sim_ranks = [1 if (r is not None and r <= k) else r for r in m1_first_ranks]
        sim_mrr = np.mean([1.0/r if r is not None else 0.0 for r in sim_ranks])
        hit_at_k = sum(1 for r in m1_first_ranks if r is not None and r <= k)
        print(f"Promoting Gold in Top-{k:<2d} to Rank 1: MRR = {sim_mrr:.4f} (+{sim_mrr - m1_mrr:+.4f}) [Coverage: {hit_at_k}/345 ({hit_at_k/345*100:.1f}%)]")

    # Quantify loss contributions:
    # For each query, delta_loss = 1.0 - (1.0 / r)
    loss_contributions = []
    for qid, r in zip(baseline_records.keys(), m1_first_ranks):
        rr = 1.0/r if r is not None else 0.0
        loss = 1.0 - rr
        loss_contributions.append((qid, loss, r, baseline_records[qid]["repo"], baseline_records[qid].get("task_type")))
        
    loss_contributions.sort(key=lambda x: -x[1])
    
    print("\nTop 10 queries contributing the most MRR loss in M1:")
    for qid, loss, r, repo, task in loss_contributions[:10]:
        print(f"  Query {qid} ({repo}, {task}): First Gold Rank = {r}, Loss = {loss:.4f}")

if __name__ == "__main__":
    compute_headroom()

