import json

with open("research/v1_accuracy/m3_token_feasibility/M3_ORACLE_CEILING.json", "r", encoding="utf-8") as f:
    d = json.load(f)

ledger_4k = d["budget_feasibility_analysis"]["4k"]["impossible_queries_ledger"]
print(f"Total 4k impossible queries: {len(ledger_4k)}")

# Sort by overflow
ledger_4k.sort(key=lambda x: -x["budget_overflow_tokens"])
for item in ledger_4k[:10]:
    print(f"Query {item['query_id']} | Repo: {item['repo']} | Track: {item['track']} | Golds: {item['num_gold_files']} | Tokens: {item['total_packaged_tokens']} | Overflow: +{item['budget_overflow_tokens']} | Knapsack: {item['oracle_max_gold_retrievable']}/{item['num_gold_files']} ({item['oracle_recall_ceiling']:.2f})")

print("\nSmallest 4k overflow:")
for item in ledger_4k[-5:]:
    print(f"Query {item['query_id']} | Repo: {item['repo']} | Track: {item['track']} | Golds: {item['num_gold_files']} | Tokens: {item['total_packaged_tokens']} | Overflow: +{item['budget_overflow_tokens']} | Knapsack: {item['oracle_max_gold_retrievable']}/{item['num_gold_files']} ({item['oracle_recall_ceiling']:.2f})")

