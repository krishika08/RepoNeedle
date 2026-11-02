"""
Simulation: What happens to MRR if input seed files are excluded from candidates when searching for downstream/related targets?
"""
import gzip
import json
import re
import numpy as np

def simulate_seed_exclusion():
    with open("reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl", "r", encoding="utf-8") as f:
        baseline_records = {r["sample_id"]: r for r in (json.loads(l) for l in f if l.strip())}
        
    m1_records = {}
    with gzip.open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                m1_records[data["query_id"]] = data

    tracks = ["code2test", "comment2context", "edit2ripple", "trace2code"]
    
    # Analyze per-track impact
    results = {}
    for tr in tracks:
        qids = [qid for qid, b in baseline_records.items() if b.get("task_type") == tr]
        m1_mrrs_orig = []
        m1_mrrs_excl_seed = []
        r1_hits_orig = 0
        r1_hits_excl = 0
        
        for qid in qids:
            base = baseline_records[qid]
            m1 = m1_records[qid]
            gold_files = set(base["gold_files"])
            query_text = m1.get("query_text", "")
            
            # Find seed file(s)
            seed_files = set()
            for key in ["changed_file", "given_file", "anchor_file", "file_path", "filename"]:
                for match in re.finditer(rf'"{key}":\s*"([^"]+)"', query_text):
                    seed_files.add(match.group(1))
            
            # Also check if query text has diff header +++ b/path
            for match in re.finditer(r'\+\+\+ b/(\S+)', query_text):
                seed_files.add(match.group(1))
            for match in re.finditer(r'--- a/(\S+)', query_text):
                seed_files.add(match.group(1))

            cands_orig = m1["candidates"]
            # Exclude seeds that are not gold files
            # (Note: we should verify if any seed is in gold files)
            seeds_not_gold = seed_files - gold_files
            cands_excl = [c for c in cands_orig if c["path"] not in seeds_not_gold]
            
            # Orig rank of first gold
            r1_orig = None
            for idx, c in enumerate(cands_orig, 1):
                if c["path"] in gold_files:
                    r1_orig = idx
                    break
            mrr_orig = 1.0 / r1_orig if r1_orig else 0.0
            m1_mrrs_orig.append(mrr_orig)
            if r1_orig == 1:
                r1_hits_orig += 1
                
            # Excluded seed rank of first gold
            r1_excl = None
            for idx, c in enumerate(cands_excl, 1):
                if c["path"] in gold_files:
                    r1_excl = idx
                    break
            mrr_excl = 1.0 / r1_excl if r1_excl else 0.0
            m1_mrrs_excl_seed.append(mrr_excl)
            if r1_excl == 1:
                r1_hits_excl += 1
                
        results[tr] = {
            "count": len(qids),
            "mrr_orig": np.mean(m1_mrrs_orig),
            "mrr_excl": np.mean(m1_mrrs_excl_seed),
            "r1_orig": r1_hits_orig,
            "r1_excl": r1_hits_excl,
        }
        
    print(f"{'Track':<18} | {'Count':<5} | {'Orig MRR':<10} | {'Excl MRR':<10} | {'Delta':<8} | {'Orig R1=1':<10} | {'Excl R1=1':<10}")
    print("-" * 85)
    overall_orig = []
    overall_excl = []
    tot_r1_orig = 0
    tot_r1_excl = 0
    for tr, res in sorted(results.items()):
        delta = res["mrr_excl"] - res["mrr_orig"]
        print(f"{tr:<18} | {res['count']:<5} | {res['mrr_orig']:<10.4f} | {res['mrr_excl']:<10.4f} | {delta:<+8.4f} | {res['r1_orig']:<10} | {res['r1_excl']:<10}")
        tot_r1_orig += res["r1_orig"]
        tot_r1_excl += res["r1_excl"]
        
    tot_orig_mrr = sum(res["mrr_orig"] * res["count"] for res in results.values()) / 345
    tot_excl_mrr = sum(res["mrr_excl"] * res["count"] for res in results.values()) / 345
    print("-" * 85)
    print(f"{'OVERALL':<18} | {345:<5} | {tot_orig_mrr:<10.4f} | {tot_excl_mrr:<10.4f} | {tot_excl_mrr-tot_orig_mrr:<+8.4f} | {tot_r1_orig:<10} | {tot_r1_excl:<10}")

if __name__ == "__main__":
    simulate_seed_exclusion()

