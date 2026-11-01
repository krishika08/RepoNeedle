import json

with open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        q = json.loads(line)
        if q["query_id"].startswith(("a9432b3d", "c7ce74f4")):
            print(q["query_id"], "Golds:", q["gold_files"])
            for r, c in enumerate(q["candidates"][:25], 1):
                if c["path"] in q["gold_files"]:
                    print(f"  Rank {r}: {c['path']} (score: {c['m1_score']})")

