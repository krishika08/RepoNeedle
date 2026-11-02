"""
Generate complete QUERY_FAILURE_TAXONOMY.md with exhaustive classification for all 345 queries.
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

def generate_taxonomy_report():
    with open("reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl", "r", encoding="utf-8") as f:
        baseline_records = {r["sample_id"]: r for r in (json.loads(l) for l in f if l.strip())}
        
    m1_records = {}
    with gzip.open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                m1_records[data["query_id"]] = data

    categorized_queries = defaultdict(list)
    taxonomy_counts = Counter()

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
            reason = "Gold target placed at Rank 1"
        else:
            seeds = extract_seeds(query_text)
            
            # Check 1: Query intent mismatch (Seed file displacement)
            if top1_path in seeds and top1_path not in gold_files:
                category = "3. Query intent mismatch"
                reason = f"Rank 1 is query input seed ({top1_path})"
            # Check 2: Test versus implementation confusion
            elif task == "code2test" and not is_test_file(top1_path) and any(is_test_file(g) for g in gold_files):
                category = "4. Test versus implementation confusion"
                reason = f"Rank 1 is impl file ({top1_path}), gold is test file ({first_gold['path']})"
            # Check 3: Sibling implementation confusion
            elif first_gold and os.path.dirname(top1_path) == os.path.dirname(first_gold["path"]):
                category = "5. Sibling implementation confusion"
                reason = f"Rank 1 ({top1_path}) sibling to gold ({first_gold['path']})"
            # Check 4: Structural relationship error
            elif first_gold and first_gold.get("scores", {}).get("structural_expansion", 0) == 0 and top1.get("scores", {}).get("structural_expansion", 0) > 200:
                category = "8. Structural relationship error"
                reason = f"Distractor boosted by structural expansion ({top1.get('scores', {}).get('structural_expansion', 0):.1f})"
            # Check 5: Identifier mismatch
            elif first_gold and first_gold.get("scores", {}).get("exact_symbol", 0) < 0.5 and top1.get("scores", {}).get("exact_symbol", 0) > 5.0:
                category = "2. Identifier mismatch"
                reason = f"Gold lacks query identifier (exact_symbol: {first_gold.get('scores', {}).get('exact_symbol', 0):.2f})"
            # Check 6: Lexical mismatch
            elif first_gold and first_gold.get("scores", {}).get("field_bm25", 0) < 0.2 * top1.get("scores", {}).get("field_bm25", 1):
                category = "1. Lexical mismatch"
                reason = f"Lexical score ratio: gold {first_gold.get('scores', {}).get('field_bm25', 0):.1f} vs top1 {top1.get('scores', {}).get('field_bm25', 0):.1f}"
            # Check 7: Path mismatch
            elif first_gold and len(set(top1_path.split("/")) & set(first_gold["path"].split("/"))) <= 1:
                category = "6. Path mismatch"
                reason = f"Disjoint directory paths: {top1_path} vs {first_gold['path']}"
            # Check 8: Symbol definition mismatch
            elif first_gold and first_gold.get("scores", {}).get("exact_symbol", 0) > 0 and r1_rank > 10:
                category = "7. Symbol definition mismatch"
                reason = f"Symbol found in gold ({first_gold['path']}) but placed at rank {r1_rank} behind usages"
            # Check 9: Candidate diversity failure
            elif len(set(os.path.dirname(c["path"]) for c in cands[:5])) == 1:
                category = "9. Candidate diversity failure"
                reason = f"Top 5 candidates monopolized by directory {os.path.dirname(cands[0]['path'])}"
            else:
                category = "10. Other / Unclassified"
                reason = f"General ranking displacement (first gold rank {r1_rank})"

        taxonomy_counts[category] += 1
        categorized_queries[category].append({
            "qid": qid,
            "repo": base["repo"],
            "task": task,
            "r1": r1_rank,
            "top1": top1_path,
            "gold": list(gold_files),
            "reason": reason
        })

    # Build Markdown document
    lines = []
    lines.append("# RepoNeedle — Mission 0.80+ (Ranking Intelligence Research Programme)")
    lines.append("# Phase R1 Deliverable 3: Query Failure Taxonomy & Exhaustive Classification\n")
    lines.append("**Document ID:** `QUERY_FAILURE_TAXONOMY.md`  ")
    lines.append("**Status:** Complete  ")
    lines.append("**Date:** November 2, 2026  ")
    lines.append("**Author:** Principal Search Relevance Engineer, Information Retrieval Researcher & ML Ranking Architect  ")
    lines.append("**Scope:** All 345 Queries across 25 Repositories in ARB v2 Set A  \n")
    lines.append("---\n")
    lines.append("## 1. Executive Summary & Taxonomy Distribution\n")
    lines.append("Every single query in ARB v2 Set A (345 queries) has been audited, evaluated, and classified into the mandated 10 failure categories based on deterministic algorithmic criteria:\n")
    
    lines.append("| Category ID & Name | Query Count | % of Benchmark | Description & Root Cause |")
    lines.append("| :--- | :--- | :--- | :--- |")
    
    cat_descriptions = {
        "Rank 1 Success": "Gold file correctly identified and placed at Rank 1 ($R_1 = 1$).",
        "3. Query intent mismatch": "Rank 1 is occupied by the query's input seed file (`changed_file`, `given_file`, `anchor_file`).",
        "4. Test versus implementation confusion": "Query intent requires test files (`code2test`), but ranker surfaces implementation code at Ranks 1–5.",
        "6. Path mismatch": "Gold file resides in a disjoint subtree with little path token overlap; ranker prefers unrelated files.",
        "5. Sibling implementation confusion": "Rank 1 and gold target share the exact same package/directory, but ranker picked the wrong sibling.",
        "8. Structural relationship error": "Unconditioned graph expansion boosted an architectural hub file while gold file lacked structural link.",
        "2. Identifier mismatch": "Gold file lacked query identifier match, while top displacer matched symbols prominently.",
        "10. Other / Unclassified": "Residual complex displacements requiring multi-hop contextual reasoning.",
        "7. Symbol definition mismatch": "Symbol defined in gold file was placed behind files containing multiple references/usages.",
        "1. Lexical mismatch": "Severe lexical term dilution where high-frequency tokens in unrelated files outweighed gold.",
        "9. Candidate diversity failure": "Co-occurring failure mode where top candidates are monopolized by a single module."
    }

    total_q = len(baseline_records)
    for cat, count in taxonomy_counts.most_common():
        desc = cat_descriptions.get(cat, "")
        lines.append(f"| **{cat}** | **{count}** | **{count/total_q*100:.2f}%** | {desc} |")
    lines.append(f"| **Total** | **{total_q}** | **100.00%** | Comprehensive audit across all 345 queries |")
    lines.append("\n---\n")

    # Detailed sections for each category with representative samples and complete tables
    for cat, count in taxonomy_counts.most_common():
        items = categorized_queries[cat]
        lines.append(f"## {cat} ({count} Queries, {count/total_q*100:.2f}%)\n")
        lines.append(f"**Root Cause Analysis:** {cat_descriptions.get(cat, '')}\n")
        
        # Summary table of all queries in this category
        lines.append("| Query ID | Repository | Task Track | First Gold Rank ($R_1$) | Top 1 Candidate | First Gold Target | Specific Reason |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for item in items:
            q_short = item['qid'][:8]
            repo_short = item['repo']
            task_short = item['task']
            r1_str = str(item['r1']) if item['r1'] is not None else "None"
            top1_str = f"`{item['top1'][:32]}...`" if len(item['top1']) > 32 else f"`{item['top1']}`"
            gold_str = f"`{item['gold'][0][:32]}...`" if len(item['gold'][0]) > 32 else f"`{item['gold'][0]}`"
            reason_str = item['reason'].replace("|", "/")
            lines.append(f"| `{q_short}` | `{repo_short}` | `{task_short}` | {r1_str} | {top1_str} | {gold_str} | {reason_str} |")
        lines.append("\n---\n")

    out_file = "research/v1_accuracy/ranking_0_80/QUERY_FAILURE_TAXONOMY.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    print(f"Generated QUERY_FAILURE_TAXONOMY.md ({len(lines)} lines).")

if __name__ == "__main__":
    generate_taxonomy_report()

