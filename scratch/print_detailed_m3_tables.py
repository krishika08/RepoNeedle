import json
from pathlib import Path
from collections import defaultdict

with open("research/v1_accuracy/m3_token_feasibility/M3_ORACLE_CEILING.json", "r", encoding="utf-8") as f:
    d = json.load(f)

print("=== BUDGET ANALYSIS ===")
for b, data in d["budget_feasibility_analysis"].items():
    print(f"\n--- Budget {b} ({data['budget_tokens']} tokens) ---")
    c_pkg = data["complete_gold_coverage_ceiling"]
    raw = data["raw_tokens_comparison"]
    imp = data["impossibility_metrics"]
    rec = data["oracle_recall_ceilings"]
    print(f"Feasible (Packaged): {c_pkg['feasible_queries_count']}/345 ({c_pkg['feasible_queries_pct']:.4%})")
    print(f"Feasible (Raw):      {raw['raw_feasible_queries_count']}/345 ({raw['raw_feasible_queries_pct']:.4%})")
    print(f"Packaging Penalty:   {raw['packaging_overhead_penalty_queries']} queries pushed out by packaging overhead")
    print(f"Single-gold feasible: {c_pkg['single_gold_feasible_count']}/227 ({c_pkg['single_gold_feasible_pct']:.4%})")
    print(f"Multi-gold feasible:  {c_pkg['multi_gold_feasible_count']}/118 ({c_pkg['multi_gold_feasible_pct']:.4%})")
    print(f"Impossible queries:   {imp['impossible_queries_count']}/345 ({imp['impossible_queries_pct']:.4%})")
    print(f"Oracle Micro Recall:  {rec['knapsack_micro_recall_ceiling']:.6f} ({rec['oracle_gold_files_retrieved']}/{rec['total_gold_files']})")
    print(f"Oracle Macro Recall:  {rec['knapsack_macro_recall_ceiling']:.6f}")
    print(f"Track breakdown of impossible: {imp['impossible_by_track']}")
    print(f"Repo breakdown of impossible (top 5): {sorted(imp['impossible_by_repo'].items(), key=lambda x: -x[1])[:5]}")

