"""
Check test file pattern in code2test gold files and simulate test file boosting.
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

def test_boosting_simulation():
    with open("reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl", "r", encoding="utf-8") as f:
        baseline_records = {r["sample_id"]: r for r in (json.loads(l) for l in f if l.strip())}
        
    m1_records = {}
    with gzip.open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                m1_records[data["query_id"]] = data

    c2t_qids = [qid for qid, b in baseline_records.items() if b.get("task_type") == "code2test"]
    
    total_golds = 0
    test_golds = 0
    for qid in c2t_qids:
        for gf in baseline_records[qid]["gold_files"]:
            total_golds += 1
            if is_test_file(gf):
                test_golds += 1
                
    print(f"code2test gold files: {test_golds}/{total_golds} ({test_golds/total_golds*100:.2f}%) are test files!")
    
    # Simulate: If we boost test files when query is code2test
    # (or when query has test intent: "test", "tests", "PR body", etc.)
    # Let's see what happens to MRR in code2test!
    m1_orig_mrrs = []
    boosted_mrrs = []
    orig_r1 = 0
    boosted_r1 = 0
    
    for qid in c2t_qids:
        base = baseline_records[qid]
        m1 = m1_records[qid]
        gold_files = set(base["gold_files"])
        cands = m1["candidates"]
        
        # Original
        r_orig = None
        for idx, c in enumerate(cands, 1):
            if c["path"] in gold_files:
                r_orig = idx
                break
        m1_orig_mrrs.append(1.0/r_orig if r_orig else 0.0)
        if r_orig == 1:
            orig_r1 += 1
            
        # Re-rank by: test files first (preserving internal order), then non-test files
        reordered = sorted(cands, key=lambda c: (0 if is_test_file(c["path"]) else 1, c["m1_rank"]))
        r_boosted = None
        for idx, c in enumerate(reordered, 1):
            if c["path"] in gold_files:
                r_boosted = idx
                break
        boosted_mrrs.append(1.0/r_boosted if r_boosted else 0.0)
        if r_boosted == 1:
            boosted_r1 += 1

    print(f"\nIn code2test ({len(c2t_qids)} queries):")
    print(f"Original M1 MRR: {np.mean(m1_orig_mrrs):.4f} (Rank 1 hits: {orig_r1})")
    print(f"Test-Boosted MRR: {np.mean(boosted_mrrs):.4f} (Rank 1 hits: {boosted_r1})")
    print(f"Delta MRR: {np.mean(boosted_mrrs) - np.mean(m1_orig_mrrs):+.4f}")

if __name__ == "__main__":
    test_boosting_simulation()

