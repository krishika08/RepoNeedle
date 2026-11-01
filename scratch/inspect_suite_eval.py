import json

with open("research/v1_accuracy/m3_cud_pack/compact_context_acceptance_suite.json", "r", encoding="utf-8") as f:
    suite = json.load(f)

with open("research/v1_accuracy/m3_cud_pack/PER_QUERY_PACKING_RESULTS.jsonl", "r", encoding="utf-8") as f:
    results = {json.loads(line)["query_id"]: json.loads(line) for line in f}

print("=== INSPECTING COMPACT SUITE EVALUATION ===")
for idx, s in enumerate(suite, 1):
    qid = s["query_id"]
    res = results[qid]["budgets"]["4096"]
    selected_paths = {sf["path"]: sf for sf in res["selected_files"]}
    
    all_ok = True
    reasons = []
    for sp in s["annotated_spans"]:
        gp = sp["gold_path"]
        sym = sp["target_symbol"]
        if gp not in selected_paths:
            all_ok = False
            reasons.append(f"File {gp} not selected (selected {len(selected_paths)} files)")
        else:
            item = selected_paths[gp]
            # check if symbol is in rendered_content
            # wait, in PER_QUERY_PACKING_RESULTS, we don't store full rendered_content, but tier!
            reasons.append(f"File {gp} selected as {item['tier']} (rank {item['rank']})")

    status = "PASS" if all_ok else "FAIL"
    print(f"Q {idx:>2} ({qid[:8]}): {status} | {reasons}")

