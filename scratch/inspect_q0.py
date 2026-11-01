import json

with open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl", "r", encoding="utf-8") as f:
    r = json.loads(f.readline())
    print("Gold files:", r["gold_files"])
    for i, c in enumerate(r["candidates"][:25], 1):
        is_gold = c["path"] in r["gold_files"]
        print(f"Rank {i:>2}: {c['path']} (score: {c['m1_score']:.4f}, gold={is_gold})")

