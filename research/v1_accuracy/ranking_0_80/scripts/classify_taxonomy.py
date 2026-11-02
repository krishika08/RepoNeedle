"""
Taxonomy Classification Script for all 345 queries.
Classifies failure reasons into the mandated 10 categories.
"""
import gzip
import json
import os
import re
from collections import defaultdict, Counter

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

def extract_seeds(query_text):
    seed_files = set()
    for key in ["changed_file", "given_file", "anchor_file", "file_path", "filename"]:
        for match in re.finditer(rf'"{key}":\s*"([^"]+)"', query_text):
            seed_files.add(match.group(1))
    for match in re.finditer(r'\+\+\+ b/(\S+)', query_text):
        seed_files.add(match.group(1))
    for match in re.finditer(r'--- a/(\S+)', query_text):
        seed_files.add(match.group(1))
    return seed_files

def classify_taxonomy():
    with open("reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl", "r", encoding="utf-8") as f:
        baseline_records = {r["sample_id"]: r for r in (json.loads(l) for l in f if l.strip())}
        
    m1_records = {}
    with gzip.open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                m1_records[data["query_id"]] = data

    taxonomy_counts = Counter()
    query_taxonomy = {}
    
    # Categories:
    # 1. Lexical mismatch
    # 2. Identifier mismatch
    # 3. Query intent mismatch (e.g. seed trap / input file returned)
    # 4. Test versus implementation confusion
    # 5. Sibling implementation confusion
    # 6. Path mismatch
    # 7. Symbol definition mismatch
    # 8. Structural relationship error
    # 9. Candidate diversity failure
    # 10. Other / Unclassified
    # (Plus: Success / Rank 1)

    for qid, base in baseline_records.items():
        m1 = m1_records[qid]
        gold_files = set(base["gold_files"])
        cands = m1["candidates"]
        task = base.get("task_type", "unknown")
        query_text = m1.get("query_text", "")
        
        top1 = cands[0] if cands else None
        top1_path = top1["path"] if top1 else ""
        
        first_gold = None
        for c in cands:
            if c["path"] in gold_files:
                first_gold = c
                break
                
        r1_rank = first_gold["m1_rank"] if first_gold else None
        
        if r1_rank == 1:
            category = "Rank 1 Success"
            reason = "Gold target retrieved at Rank 1"
        else:
            seeds = extract_seeds(query_text)
            
            # Check 1: Did input seed displace gold? (Query intent mismatch)
            if top1_path in seeds and top1_path not in gold_files:
                category = "3. Query intent mismatch"
                reason = f"Rank 1 is the query's input seed file ({top1_path})"
            # Check 2: Test vs Implementation confusion
            elif task == "code2test" and not is_test_file(top1_path) and any(is_test_file(g) for g in gold_files):
                category = "4. Test versus implementation confusion"
                reason = f"code2test query ranked implementation file ({top1_path}) over test file ({first_gold['path']})"
            # Check 3: Sibling implementation confusion (same parent directory)
            elif first_gold and os.path.dirname(top1_path) == os.path.dirname(first_gold["path"]):
                category = "5. Sibling implementation confusion"
                reason = f"Rank 1 ({top1_path}) is sibling in same directory as gold ({first_gold['path']})"
            # Check 4: Structural relationship error (structural expansion high on distractor or gold far down due to missing edge)
            elif first_gold and first_gold.get("scores", {}).get("structural_expansion", 0) == 0 and top1.get("scores", {}).get("structural_expansion", 0) > 200:
                category = "8. Structural relationship error"
                reason = f"Distractor boosted by structural expansion ({top1.get('scores', {}).get('structural_expansion', 0):.1f}) while gold lacked structural link"
            # Check 5: Identifier mismatch (exact symbol score for gold is near zero while distractor has high exact symbol)
            elif first_gold and first_gold.get("scores", {}).get("exact_symbol", 0) < 0.5 and top1.get("scores", {}).get("exact_symbol", 0) > 5.0:
                category = "2. Identifier mismatch"
                reason = f"Gold lacks query identifier match (exact_symbol: {first_gold.get('scores', {}).get('exact_symbol', 0):.2f} vs {top1.get('scores', {}).get('exact_symbol', 0):.2f})"
            # Check 6: Lexical mismatch (field_bm25 or subwords score difference massive)
            elif first_gold and first_gold.get("scores", {}).get("field_bm25", 0) < 0.2 * top1.get("scores", {}).get("field_bm25", 1):
                category = "1. Lexical mismatch"
                reason = f"Lexical score ratio: gold {first_gold.get('scores', {}).get('field_bm25', 0):.1f} vs top1 {top1.get('scores', {}).get('field_bm25', 0):.1f}"
            # Check 7: Path mismatch (different deep directory structure, completely disjoint path tokens)
            elif first_gold and len(set(top1_path.split("/")) & set(first_gold["path"].split("/"))) <= 1:
                category = "6. Path mismatch"
                reason = f"Disjoint directory paths: {top1_path} vs {first_gold['path']}"
            # Check 8: Symbol definition mismatch
            elif first_gold and first_gold.get("scores", {}).get("exact_symbol", 0) > 0 and r1_rank > 10:
                category = "7. Symbol definition mismatch"
                reason = f"Symbol found in gold ({first_gold['path']}) but ranked at {r1_rank} behind usages/hubs"
            # Check 9: Candidate diversity failure (top 5 candidates share same directory/prefix)
            elif len(set(os.path.dirname(c["path"]) for c in cands[:5])) == 1:
                category = "9. Candidate diversity failure"
                reason = f"Top 5 candidates monopolized by directory {os.path.dirname(cands[0]['path'])}"
            else:
                category = "10. Other / Unclassified"
                reason = f"General ranking displacement (first gold rank {r1_rank})"
                
        taxonomy_counts[category] += 1
        query_taxonomy[qid] = {
            "sample_id": qid,
            "repo": base["repo"],
            "task_type": task,
            "r1_rank": r1_rank,
            "category": category,
            "reason": reason,
            "top1_path": top1_path,
            "gold_paths": list(gold_files)
        }

    print("=== TAXONOMY CLASSIFICATION SUMMARY ===")
    total = len(baseline_records)
    for cat, count in taxonomy_counts.most_common():
        print(f"  {cat:<42}: {count:3d} ({count/total*100:5.2f}%)")
        
    return query_taxonomy, taxonomy_counts

if __name__ == "__main__":
    classify_taxonomy()

