"""
Quantify input-file self-retrieval / displacement across all 345 queries.
"""
import gzip
import json
import re
from collections import Counter

def check_seed_displacement():
    with open("reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl", "r", encoding="utf-8") as f:
        baseline_records = {r["sample_id"]: r for r in (json.loads(l) for l in f if l.strip())}
        
    m1_records = {}
    with gzip.open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                m1_records[data["query_id"]] = data

    seed_file_displacements = 0
    total_non_gold_rank1 = 0
    by_track_displacement = Counter()
    by_track_total = Counter()
    
    for qid, base in baseline_records.items():
        m1 = m1_records[qid]
        task = base.get("task_type", "unknown")
        by_track_total[task] += 1
        gold_files = set(base["gold_files"])
        cands = m1["candidates"]
        top1 = cands[0]["path"] if cands else None
        
        if top1 not in gold_files:
            total_non_gold_rank1 += 1
            query_text = m1.get("query_text", "")
            
            # Extract possible input files from query_text JSON or text
            is_seed = False
            # Check for JSON keys
            for key in ["changed_file", "given_file", "anchor_file", "file_path", "filename"]:
                pattern = rf'"{key}":\s*"([^"]+)"'
                m = re.search(pattern, query_text)
                if m and m.group(1) == top1:
                    is_seed = True
                    break
            
            # If not in json, check if top1 path is prominently in query_text
            if not is_seed and top1 in query_text:
                is_seed = True
                
            if is_seed:
                seed_file_displacements += 1
                by_track_displacement[task] += 1

    print(f"Total queries: {len(baseline_records)}")
    print(f"Total non-gold Rank 1: {total_non_gold_rank1}")
    print(f"Rank 1 is the query's input/seed file: {seed_file_displacements} ({seed_file_displacements/total_non_gold_rank1*100:.2f}% of non-gold Rank 1!)")
    print(f"By track displacement of Rank 1 by seed/input file:")
    for tr, cnt in by_track_displacement.items():
        print(f"  {tr:<18}: {cnt}/{by_track_total[tr]} ({cnt/by_track_total[tr]*100:.1f}%)")

if __name__ == "__main__":
    check_seed_displacement()

