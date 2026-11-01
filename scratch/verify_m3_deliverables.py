import json
from pathlib import Path

p_json = Path("research/v1_accuracy/m3_token_feasibility/M3_ORACLE_CEILING.json")
p_jsonl = Path("research/v1_accuracy/m3_token_feasibility/M3_PER_QUERY_BUDGET_RESULTS.jsonl")

print(f"{p_json}: exists={p_json.exists()}, size={p_json.stat().st_size} bytes")
print(f"{p_jsonl}: exists={p_jsonl.exists()}, size={p_jsonl.stat().st_size} bytes")

with open(p_json, "r", encoding="utf-8") as f:
    d = json.load(f)
    print("Budgets analyzed:", list(d["budget_feasibility_analysis"].keys()))
    for b in ["2k", "4k", "8k", "16k", "32k"]:
        info = d["budget_feasibility_analysis"][b]
        c_count = info["complete_gold_coverage_ceiling"]["feasible_queries_count"]
        c_pct = info["complete_gold_coverage_ceiling"]["feasible_queries_pct"]
        imp_count = info["impossibility_metrics"]["impossible_queries_count"]
        micro = info["oracle_recall_ceilings"]["knapsack_micro_recall_ceiling"]
        macro = info["oracle_recall_ceilings"]["knapsack_macro_recall_ceiling"]
        print(f"Budget {b:>3}: Feasible={c_count:>3}/345 ({c_pct:6.2%}) | Impossible={imp_count:>2} | Micro Rec={micro:.4f} | Macro Rec={macro:.4f}")

# Check lines in jsonl
with open(p_jsonl, "r", encoding="utf-8") as f:
    lines = [json.loads(l) for l in f]
print(f"JSONL contains {len(lines)} valid JSON lines.")

