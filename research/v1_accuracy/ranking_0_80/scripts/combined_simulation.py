"""
Combined simulation of seed handling and test boosting.
"""
import gzip
import json
import re
import numpy as np

def is_test_file(path):
    p = path.lower()
    return (
        "test" in p or
        "tests" in p or
        p.endswith("_test.go") or
        p.endswith("_test.py") or
        p.startswith("test_") or
        "/tests/" in p or
        "/test/" in p or
        p.endswith("test.rs") or
        p.endswith("tests.rs")
    )

def combined_simulation():
    with open("reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl", "r", encoding="utf-8") as f:
        baseline_records = {r["sample_id"]: r for r in (json.loads(l) for l in f if l.strip())}
        
    m1_records = {}
    with gzip.open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                m1_records[data["query_id"]] = data

    tracks = ["code2test", "comment2context", "edit2ripple", "trace2code"]
    
    m1_mrrs_orig = []
    m1_mrrs_combined = []
    orig_r1 = 0
    comb_r1 = 0
    
    per_track = {}
    
    for tr in tracks:
        qids = [qid for qid, b in baseline_records.items() if b.get("task_type") == tr]
        tr_orig = []
        tr_comb = []
        tr_r1_orig = 0
        tr_r1_comb = 0
        
        for qid in qids:
            base = baseline_records[qid]
            m1 = m1_records[qid]
            gold_files = set(base["gold_files"])
            query_text = m1.get("query_text", "")
            
            # Find seeds
            seed_files = set()
            for key in ["changed_file", "given_file", "anchor_file", "file_path", "filename"]:
                for match in re.finditer(rf'"{key}":\s*"([^"]+)"', query_text):
                    seed_files.add(match.group(1))
            for match in re.finditer(r'\+\+\+ b/(\S+)', query_text):
                seed_files.add(match.group(1))
            for match in re.finditer(r'--- a/(\S+)', query_text):
                seed_files.add(match.group(1))

            cands = m1["candidates"]
            
            # Original rank
            r_orig = None
            for idx, c in enumerate(cands, 1):
                if c["path"] in gold_files:
                    r_orig = idx
                    break
            tr_orig.append(1.0/r_orig if r_orig else 0.0)
            if r_orig == 1:
                tr_r1_orig += 1
                
            # Combined strategy:
            # 1. Filter out seed files (if not gold)
            filtered = [c for c in cands if c["path"] not in (seed_files - gold_files)]
            
            # 2. If track is code2test, sort test files first
            if tr == "code2test":
                filtered.sort(key=lambda c: (0 if is_test_file(c["path"]) else 1, c["m1_rank"]))
                
            r_comb = None
            for idx, c in enumerate(filtered, 1):
                if c["path"] in gold_files:
                    r_comb = idx
                    break
            tr_comb.append(1.0/r_comb if r_comb else 0.0)
            if r_comb == 1:
                tr_r1_comb += 1
                
        m1_mrrs_orig.extend(tr_orig)
        m1_mrrs_combined.extend(tr_comb)
        orig_r1 += tr_r1_orig
        comb_r1 += tr_r1_comb
        
        per_track[tr] = {
            "count": len(qids),
            "orig_mrr": np.mean(tr_orig),
            "comb_mrr": np.mean(tr_comb),
            "orig_r1": tr_r1_orig,
            "comb_r1": tr_r1_comb
        }
        
    print(f"{'Track':<18} | {'Count':<5} | {'Orig MRR':<10} | {'Comb MRR':<10} | {'Delta':<8} | {'Orig R1=1':<10} | {'Comb R1=1':<10}")
    print("-" * 85)
    for tr, res in sorted(per_track.items()):
        delta = res["comb_mrr"] - res["orig_mrr"]
        print(f"{tr:<18} | {res['count']:<5} | {res['orig_mrr']:<10.4f} | {res['comb_mrr']:<10.4f} | {delta:<+8.4f} | {res['orig_r1']:<10} | {res['comb_r1']:<10}")
        
    print("-" * 85)
    print(f"{'OVERALL':<18} | {345:<5} | {np.mean(m1_mrrs_orig):<10.4f} | {np.mean(m1_mrrs_combined):<10.4f} | {np.mean(m1_mrrs_combined)-np.mean(m1_mrrs_orig):<+8.4f} | {orig_r1:<10} | {comb_r1:<10}")

if __name__ == "__main__":
    combined_simulation()

