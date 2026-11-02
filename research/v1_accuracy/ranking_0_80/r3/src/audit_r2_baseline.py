"""
Audit and verification of R2 baseline, per-query records, seed trap reconciliation,
classifier lineage, and repository-clustered bootstrap.
"""
import json
import os
import re
from collections import defaultdict, Counter
import numpy as np

def audit_r2():
    print("=== AUDIT 1: Verify PER_QUERY_COMPARISON.jsonl ===")
    jsonl_path = "research/v1_accuracy/ranking_0_80/r2/PER_QUERY_COMPARISON.jsonl"
    with open(jsonl_path, "r", encoding="utf-8") as f:
        records = [json.loads(l) for l in f if l.strip()]

    print(f"Total query records in jsonl: {len(records)}")
    assert len(records) == 345, f"Expected 345 records, got {len(records)}"

    # Check splits
    splits = Counter(r["split"] for r in records)
    print(f"Splits distribution: {dict(splits)}")
    assert splits["train"] == 210
    assert splits["val"] == 60
    assert splits["held_out"] == 75

    # Check all 8 treatments present
    treatments = ["A", "B", "C", "D", "E", "F", "G", "H"]
    for r in records:
        for t in treatments:
            assert t in r["treatments"], f"Missing treatment {t} in query {r['query_id']}"

    # Compute MRR, Hit@1, Recall@20 across splits
    def eval_split_metrics(split_name, t_code):
        sub = [r for r in records if r["split"] == split_name] if split_name != "overall" else records
        rrs = [r["treatments"][t_code]["rr"] for r in sub]
        r1s = [1 if r["treatments"][t_code]["rank"] == 1 else 0 for r in sub]
        r20s = [r["treatments"][t_code]["r20"] for r in sub]
        traps = [1 if r["treatments"][t_code]["rank1_is_seed"] else 0 for r in sub]
        return {
            "mrr": float(np.mean(rrs)),
            "hit@1": float(np.mean(r1s)),
            "hit@1_count": sum(r1s),
            "recall@20": float(np.mean(r20s)),
            "seed_traps": sum(traps),
        }

    print("\n--- Reproduced Metrics for Treatment A (Baseline M1) ---")
    for s in ["train", "val", "held_out", "overall"]:
        m = eval_split_metrics(s, "A")
        print(f"  {s:<10}: MRR = {m['mrr']:.4f} | Hit@1 = {m['hit@1']*100:.2f}% ({m['hit@1_count']}) | R@20 = {m['recall@20']:.4f} | Traps = {m['seed_traps']}")

    print("\n--- Reproduced Metrics for Treatment E (Champion: SFS + TIP) ---")
    for s in ["train", "val", "held_out", "overall"]:
        m = eval_split_metrics(s, "E")
        print(f"  {s:<10}: MRR = {m['mrr']:.4f} | Hit@1 = {m['hit@1']*100:.2f}% ({m['hit@1_count']}) | R@20 = {m['recall@20']:.4f} | Traps = {m['seed_traps']}")

    print("\n--- Reproduced Metrics for Treatment H (Composite: SFS + TIP + SMS) ---")
    for s in ["train", "val", "held_out", "overall"]:
        m = eval_split_metrics(s, "H")
        print(f"  {s:<10}: MRR = {m['mrr']:.4f} | Hit@1 = {m['hit@1']*100:.2f}% ({m['hit@1_count']}) | R@20 = {m['recall@20']:.4f} | Traps = {m['seed_traps']}")

    print("\n=== AUDIT 2: Reconcile Seed Trap Discrepancy (R1 vs R2) ===")
    # In R1: 259 queries reported where top1 path was anywhere in query text or json.
    # In R2: 211 queries where top1 path was extracted from explicit metadata keys or diff headers.
    r1_loose_traps = 0
    r2_strict_traps = 0
    
    with open("reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl", "r", encoding="utf-8") as f:
        base_recs = {r["sample_id"]: r for r in (json.loads(l) for l in f if l.strip())}
    import gzip
    m1_recs = {}
    with gzip.open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                m1_recs[d["query_id"]] = d

    # Import R2 SeedExtractor
    import sys
    sys.path.insert(0, "research/v1_accuracy/ranking_0_80/r2/src")
    from seed_suppression import SeedExtractor, normalize_path

    discrepancy_reasons = Counter()

    for qid, b in base_recs.items():
        m1 = m1_recs[qid]
        golds = set(b["gold_files"])
        cands = m1["candidates"]
        top1 = cands[0]["path"] if cands else ""
        top1_norm = normalize_path(top1)
        qtext = m1.get("query_text", "")

        is_non_gold = (top1 not in golds)
        if not is_non_gold:
            continue

        # Strict R2 extractor
        r2_seeds = SeedExtractor.extract_seeds(qtext)
        is_r2_trap = (top1_norm in r2_seeds)
        if is_r2_trap:
            r2_strict_traps += 1

        # Loose R1 check (from R1 seed_displacement.py)
        is_r1_trap = False
        for key in ["changed_file", "given_file", "anchor_file", "file_path", "filename"]:
            m = re.search(rf'"{key}":\s*"([^"]+)"', qtext)
            if m and m.group(1) == top1:
                is_r1_trap = True
                break
        if not is_r1_trap and top1 in qtext:
            is_r1_trap = True
        if is_r1_trap:
            r1_loose_traps += 1

        if is_r1_trap and not is_r2_trap:
            # Why did R1 count it but R2 didn't?
            if "failure_excerpt" in qtext and top1 in qtext:
                discrepancy_reasons["Traceback/Terminal mention (trace2code)"] += 1
            elif "diff_hunk_context" in qtext and top1 in qtext:
                discrepancy_reasons["Diff context body mention"] += 1
            else:
                discrepancy_reasons["Prose / PR body substring mention"] += 1

    print(f"R1 Loose Trap Count:   {r1_loose_traps} queries")
    print(f"R2 Strict Trap Count:  {r2_strict_traps} queries")
    print(f"Discrepancy:           {r1_loose_traps - r2_strict_traps} queries")
    print("Discrepancy Breakdown:")
    for reason, cnt in discrepancy_reasons.items():
        print(f"  {reason:<45}: {cnt}")

    print("\n=== AUDIT 3: Cluster-Aware vs Query-Level Bootstrap Comparison ===")
    # Compare query-level bootstrap vs cluster-level bootstrap on Treatment E Validation set
    val_records = [r for r in records if r["split"] == "val"]
    val_repos = sorted(list(set(r["repo"] for r in val_records)))
    print(f"Validation repositories ({len(val_repos)}): {val_repos}")
    
    val_diffs = np.array([r["treatments"]["E"]["rr"] - r["treatments"]["A"]["rr"] for r in val_records])
    
    # 1. Query-level bootstrap (R2 method)
    rng = np.random.default_rng(42)
    n_q = len(val_diffs)
    boot_q = rng.choice(val_diffs, size=(10000, n_q), replace=True).mean(axis=1)
    ci_q_low, ci_q_high = np.percentile(boot_q, [2.5, 97.5])
    
    # 2. Repository-clustered bootstrap (proper clustered method)
    repo_to_diffs = defaultdict(list)
    for r in val_records:
        repo_to_diffs[r["repo"]].append(r["treatments"]["E"]["rr"] - r["treatments"]["A"]["rr"])
        
    boot_c = []
    n_repos = len(val_repos)
    for _ in range(10000):
        sampled_repos = rng.choice(val_repos, size=n_repos, replace=True)
        sample_diffs = []
        for repo in sampled_repos:
            sample_diffs.extend(repo_to_diffs[repo])
        boot_c.append(np.mean(sample_diffs))
    ci_c_low, ci_c_high = np.percentile(boot_c, [2.5, 97.5])
    
    print(f"Validation Set Delta MRR (Treatment E vs Baseline M1): +{np.mean(val_diffs):.4f}")
    print(f"  Query-Level Bootstrap 95% CI:       [{ci_q_low:+.4f}, {ci_q_high:+.4f}] (Width: {ci_q_high - ci_q_low:.4f})")
    print(f"  Repository-Clustered Bootstrap 95% CI:[{ci_c_low:+.4f}, {ci_c_high:+.4f}] (Width: {ci_c_high - ci_c_low:.4f})")

if __name__ == "__main__":
    audit_r2()

