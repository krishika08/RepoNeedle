import json

with open("research/v1_accuracy/m3_token_feasibility/M3_PER_QUERY_BUDGET_RESULTS.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        q = json.loads(line)
        f_raw = q["feasibility_by_budget"]["2048"]["fits_all_raw"]
        f_pkg = q["feasibility_by_budget"]["2048"]["fits_all_packaged"]
        if f_raw and not f_pkg:
            print(f"Pushed out query: {q['query_id']} ({q['repo']}), raw_tokens={q['total_gold_raw_tokens']}, packaged_tokens={q['total_gold_packaged_tokens']}, overhead={q['total_packaging_overhead']}")

