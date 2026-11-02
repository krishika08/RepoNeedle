"""
Cross-correlation and deep forensic analysis between v0.1.0 baseline and M1 frozen candidates.
"""
import gzip
import json
from collections import defaultdict, Counter

def analyze_cross_correlation():
    # Load v0.1.0 baseline records
    with open("reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl", "r", encoding="utf-8") as f:
        baseline_records = {r["sample_id"]: r for r in (json.loads(l) for l in f if l.strip())}
        
    print(f"Loaded {len(baseline_records)} baseline records.")
    
    # Load M1 frozen candidates
    m1_records = {}
    with gzip.open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                m1_records[data["query_id"]] = data
                
    print(f"Loaded {len(m1_records)} M1 records.")
    
    # Check intersection
    common_ids = set(baseline_records.keys()) & set(m1_records.keys())
    print(f"Common query IDs: {len(common_ids)}")
    
    # Let's inspect tracks and task types
    task_types = Counter()
    repos = Counter()
    m1_r1_ranks = []
    v0_r1_ranks = []
    
    for qid, base in baseline_records.items():
        m1 = m1_records.get(qid)
        task_types[base.get("task_type", "unknown")] += 1
        repos[base["repo"]] += 1
        
        gold_files = set(base["gold_files"])
        
        # v0.1.0 top files
        v0_top_files = base["reponeedle"]["top_files"]
        v0_r1 = None
        for rank, fpath in enumerate(v0_top_files, 1):
            if fpath in gold_files:
                v0_r1 = rank
                break
        v0_r1_ranks.append(v0_r1)
        
        # M1 candidates
        if m1:
            m1_r1 = None
            for cand in m1["candidates"]:
                if cand["path"] in gold_files:
                    m1_r1 = cand["m1_rank"]
                    break
            m1_r1_ranks.append(m1_r1)
            
    print("\nTask Types Distribution:")
    for tt, count in task_types.most_common():
        print(f"  {tt}: {count}")
        
    print(f"\nRepositories count: {len(repos)}")
    
    # Rank distribution comparison
    def summarize_ranks(ranks, label):
        print(f"\n=== Rank Distribution for {label} ===")
        total = len(ranks)
        r1_count = sum(1 for r in ranks if r == 1)
        r_le_3 = sum(1 for r in ranks if r is not None and r <= 3)
        r_le_5 = sum(1 for r in ranks if r is not None and r <= 5)
        r_le_10 = sum(1 for r in ranks if r is not None and r <= 10)
        r_le_20 = sum(1 for r in ranks if r is not None and r <= 20)
        r_gt_20 = sum(1 for r in ranks if r is not None and r > 20)
        r_none = sum(1 for r in ranks if r is None)
        
        print(f"Rank = 1:   {r1_count:3d} ({r1_count/total*100:5.2f}%)")
        print(f"Rank <= 3:  {r_le_3:3d} ({r_le_3/total*100:5.2f}%)")
        print(f"Rank <= 5:  {r_le_5:3d} ({r_le_5/total*100:5.2f}%)")
        print(f"Rank <= 10: {r_le_10:3d} ({r_le_10/total*100:5.2f}%)")
        print(f"Rank <= 20: {r_le_20:3d} ({r_le_20/total*100:5.2f}%)")
        print(f"Rank > 20:  {r_gt_20:3d} ({r_gt_20/total*100:5.2f}%)")
        print(f"Unretrieved:{r_none:3d} ({r_none/total*100:5.2f}%)")
        
        # Calculate reciprocal rank mean
        rr = [1.0/r if r is not None else 0.0 for r in ranks]
        print(f"Mean Reciprocal Rank (MRR): {sum(rr)/len(rr):.4f}")

    summarize_ranks(v0_r1_ranks, "Baseline v0.1.0 (Top-20 truncated)")
    summarize_ranks(m1_r1_ranks, "M1 Multi-Channel Candidate Generation (Full Pool)")

if __name__ == "__main__":
    analyze_cross_correlation()

