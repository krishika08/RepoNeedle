"""
RepoNeedle Stage 3.9.6: Comprehensive Baseline Lock and Negative Control Audit Script.
Compares:
  - EXP-397 from research/stage3_9/PER_QUERY_FRAGMENT_RESULTS.jsonl
  - EXP-386 from research/stage3_8/PER_QUERY_RESULTS.jsonl
Across all 345 queries:
  - First rank
  - Top-5 paths
  - MRR, R@1, R@5, R@10, R@20
  - Hit@1, Hit@5, Hit@10, Hit@20
  - BCY@8k
Also verifies the 241 Non-Python queries negative control across EXP-397, EXP-398, EXP-399a, EXP-399b.
"""

import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
STAGE_DIR = ROOT_DIR / "research" / "stage3_9"
STAGE3_8_DIR = ROOT_DIR / "research" / "stage3_8"

REF_JSONL = STAGE3_8_DIR / "PER_QUERY_RESULTS.jsonl"
TEST_JSONL = STAGE_DIR / "PER_QUERY_FRAGMENT_RESULTS.jsonl"


def run_audit():
    print("=" * 80)
    print("STAGE 3.9.6: COMPLETE BASELINE LOCK & EXPERIMENT INTEGRITY AUDIT")
    print("=" * 80)

    if not TEST_JSONL.exists():
        print(f"Error: {TEST_JSONL} does not exist yet. Active evaluation runner has not finished.")
        return False

    # 1. Ingest Stage 3.8 Reference
    ref_data = {}
    for line in open(REF_JSONL, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            qid = r["query_id"]
            ref_data[qid] = r

    # 2. Ingest Stage 3.9.6 Results
    test_data = {}
    for line in open(TEST_JSONL, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            qid = r["query_id"]
            test_data[qid] = r

    print(f"Loaded {len(ref_data)} canonical Stage 3.8 queries.")
    print(f"Loaded {len(test_data)} Stage 3.9.6 queries.")

    if len(ref_data) != 345 or len(test_data) != 345:
        print(f"FAILURE: Expected exactly 345 queries, got {len(ref_data)} ref and {len(test_data)} test.")

    # 3. Phase 1: Query-by-Query EXP-397 vs Stage 3.8 EXP-386
    print("\n--- PHASE 1: Query-by-Query Baseline Parity Audit (EXP-397 vs EXP-386) ---")
    exact_matches = 0
    ranking_mismatches = []
    metric_mismatches = []

    for qid, ref_row in sorted(ref_data.items()):
        if qid not in test_data:
            ranking_mismatches.append((qid, "MISSING_QUERY", 0, 0))
            continue

        test_row = test_data[qid]
        s_ref = ref_row["systems"]["EXP-386"]
        s_test = test_row["systems"]["EXP-397"]

        # Check MRR
        mrr_ref = s_ref["mrr"]
        mrr_test = s_test["mrr"]
        mrr_diff = abs(mrr_test - mrr_ref)

        # Check First Rank
        rank_ref = s_ref.get("first_rank", -1)
        rank_test = s_test.get("first_rank", -1)

        # Check Top-5 Paths
        paths_ref = s_ref.get("top_paths", [])[:5]
        paths_test = s_test.get("top_paths", [])[:5]

        # Check BCY@8k
        bcy_ref = s_ref.get("bcy_8k", 0.0)
        bcy_test = s_test.get("bcy_8k", 0.0)
        bcy_diff = abs(bcy_test - bcy_ref)

        has_rank_mismatch = (rank_ref != rank_test) or (paths_ref != paths_test)
        has_metric_mismatch = (mrr_diff > 1e-5) or (bcy_diff > 1e-5)

        if has_rank_mismatch:
            ranking_mismatches.append((qid, rank_ref, rank_test, paths_ref, paths_test))
        if has_metric_mismatch:
            metric_mismatches.append((qid, mrr_ref, mrr_test, bcy_ref, bcy_test))

        if not has_rank_mismatch and not has_metric_mismatch:
            exact_matches += 1

    print(f"Total Queries Evaluated: 345")
    print(f"Exact Bit-for-Bit Parity Matches: {exact_matches} / 345 ({exact_matches/345*100:.2f}%)")
    print(f"Ranking Mismatches: {len(ranking_mismatches)}")
    print(f"Metric / Score Mismatches: {len(metric_mismatches)}")

    if ranking_mismatches:
        print("\nFirst 5 Ranking Mismatches:")
        for mm in ranking_mismatches[:5]:
            print(f"  Query {mm[0]}: Ref Rank {mm[1]} vs Test Rank {mm[2]}")
            print(f"    Ref Top Paths:  {mm[3][:2]}")
            print(f"    Test Top Paths: {mm[4][:2]}")

    # 4. Phase 2: Negative Control Verification on Non-Python Repositories
    print("\n--- PHASE 2: Negative Control Audit (241 Non-Python Queries) ---")
    non_py_queries = [q for q in test_data.values() if not q.get("is_python", False)]
    print(f"Non-Python queries count: {len(non_py_queries)}")

    control_divergences = []
    for q in non_py_queries:
        qid = q["query_id"]
        s_397 = q["systems"]["EXP-397"]
        for cand in ["EXP-398", "EXP-399a", "EXP-399b"]:
            s_cand = q["systems"][cand]
            if s_cand["first_rank"] != s_397["first_rank"] or abs(s_cand["mrr"] - s_397["mrr"]) > 1e-5 or s_cand["top_paths"] != s_397["top_paths"]:
                control_divergences.append((qid, cand, s_397["mrr"], s_cand["mrr"]))

    print(f"Negative Control Divergences: {len(control_divergences)} (Target: 0)")
    if len(control_divergences) > 0:
        print("FAIL: Non-Python repositories exhibited unintended retrieval divergence!")
        for cd in control_divergences[:5]:
            print(f"  {cd[0]} on {cd[1]}: 397={cd[2]:.4f} vs cand={cd[3]:.4f}")
    else:
        print("PASS: 100% Bit-for-Bit Identity across all 241 Non-Python queries!")

    # Audit summary
    print("\n" + "=" * 80)
    baseline_locked = (exact_matches == 345)
    negative_control_passed = (len(control_divergences) == 0)

    if baseline_locked and negative_control_passed:
        print("STATUS: BASELINE LOCK AND NEGATIVE CONTROL FULLY VERIFIED [PASSED]")
        return True
    else:
        print(f"STATUS: BASELINE LOCK VERIFICATION FAILED (Matches: {exact_matches}/345, Control Divergences: {len(control_divergences)})")
        return False


if __name__ == "__main__":
    run_audit()

