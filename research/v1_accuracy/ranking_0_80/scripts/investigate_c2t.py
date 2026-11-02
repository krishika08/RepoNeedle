"""
Detailed investigation of code2test failures.
"""
import gzip
import json
import re

def investigate_code2test():
    with open("reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl", "r", encoding="utf-8") as f:
        baseline_records = {r["sample_id"]: r for r in (json.loads(l) for l in f if l.strip())}
        
    m1_records = {}
    with gzip.open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                m1_records[data["query_id"]] = data

    c2t_qids = [qid for qid, b in baseline_records.items() if b.get("task_type") == "code2test"]
    print(f"Total code2test queries: {len(c2t_qids)}")
    
    # Inspect 10 queries
    for qid in c2t_qids[:10]:
        base = baseline_records[qid]
        m1 = m1_records[qid]
        gold_files = set(base["gold_files"])
        cands = m1["candidates"]
        
        # Look at top 5 candidates
        print(f"\nQuery: {qid} | Repo: {base['repo']}")
        query_text = m1.get("query_text", "")
        m = re.search(r'"changed_file":\s*"([^"]+)"', query_text)
        changed_file = m.group(1) if m else "None"
        print(f"Changed file: {changed_file}")
        print(f"Gold files: {gold_files}")
        
        for idx, c in enumerate(cands[:5], 1):
            is_gold = " [GOLD]" if c["path"] in gold_files else ""
            is_changed = " [CHANGED FILE]" if c["path"] == changed_file else ""
            print(f"  Rank {idx:2d}: {c['path']} (score: {c['m1_score']:.4f}, ch: {c['channels']}){is_gold}{is_changed}")
            
        # Find where gold is
        gold_ranks = [c["m1_rank"] for c in cands if c["path"] in gold_files]
        print(f"  Gold ranks in M1: {gold_ranks}")

if __name__ == "__main__":
    investigate_code2test()

