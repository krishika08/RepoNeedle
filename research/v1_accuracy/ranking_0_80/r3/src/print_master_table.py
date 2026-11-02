import json

with open("research/v1_accuracy/ranking_0_80/r3/master_metrics.json", "r") as f:
    m = json.load(f)

print("Treatment | Split | MRR | Hit@1 | R@5 | R@10 | R@20 | Latency")
for t in ["A", "B", "C", "D", "E", "F", "G", "H", "I"]:
    for s in ["val", "train", "held_out", "overall"]:
        d = m[t][s]
        print(f"{t:<3} | {s:<8} | {d['mrr']:.4f} | {d['hit1_pct']:.2f}% | {d['recall_at_5']:.4f} | {d['recall_at_10']:.4f} | {d['recall_at_20']:.4f} | {d['latency_mean_ms']:.2f}ms")

