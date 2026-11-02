"""
Inspect individual query failures and distractor characteristics.
"""
import gzip
import json
from collections import defaultdict, Counter

def inspect_query_distractors():
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

    print("=== INSPECTING SAMPLE QUERIES BY TRACK ===")
    
    tracks = ["code2test", "comment2context", "edit2ripple", "trace2code"]
    
    for tr in tracks:
        print(f"\n==================== TRACK: {tr} ====================")
        matching_qids = [qid for qid, b in baseline_records.items() if b.get("task_type") == tr]
        # Look at the first 3 queries of this track
        for qid in matching_qids[:3]:
            base = baseline_records[qid]
            m1 = m1_records[qid]
            gold_files = base["gold_files"]
            query_text = m1.get("query_text", "")
            
            # Find gold candidate info
            m1_cands = m1["candidates"]
            m1_map = {c["path"]: c for c in m1_cands}
            
            gold_ranks = [m1_map[g]["m1_rank"] for g in gold_files if g in m1_map]
            first_gold_rank = min(gold_ranks) if gold_ranks else "None"
            first_gold_path = [g for g in gold_files if g in m1_map and m1_map[g]["m1_rank"] == first_gold_rank]
            first_gold_cand = m1_map[first_gold_path[0]] if first_gold_path else None
            
            top1_cand = m1_cands[0] if m1_cands else None
            
            print(f"\nQuery ID: {qid} | Repo: {base['repo']}")
            print(f"Query snippet: {query_text[:120].strip()}...")
            print(f"Gold targets ({len(gold_files)}): {gold_files}")
            print(f"First Gold Rank in M1: {first_gold_rank}")
            if first_gold_cand:
                print(f"  Gold cand: {first_gold_cand['path']}")
                print(f"  Gold channels: {first_gold_cand['channels']}")
                print(f"  Gold scores: {first_gold_cand['scores']}")
            if top1_cand:
                print(f"  Top 1 cand: {top1_cand['path']}")
                print(f"  Top 1 channels: {top1_cand['channels']}")
                print(f"  Top 1 scores: {top1_cand['scores']}")
                
if __name__ == "__main__":
    inspect_query_distractors()

