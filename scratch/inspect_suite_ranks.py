import json

with open("research/v1_accuracy/m3_cud_pack/compact_context_acceptance_suite.json", "r", encoding="utf-8") as f:
    suite = json.load(f)

with open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl", "r", encoding="utf-8") as f:
    q_map = {json.loads(line)["query_id"]: json.loads(line) for line in f}

print("=== INSPECTING COMPACT ACCEPTANCE SUITE QUERIES ===")
for idx, s in enumerate(suite, 1):
    qid = s["query_id"]
    q = q_map[qid]
    golds = set(s["gold_files"])
    ranks = []
    for r, c in enumerate(q["candidates"], 1):
        if c["path"] in golds:
            ranks.append((c["path"], r, c["m1_score"]))
    print(f"Suite Query {idx:>2} ({qid[:8]}) | Repo: {s['repo']} | Track: {s['track']} | Golds: {len(golds)} | Ranks: {ranks}")

