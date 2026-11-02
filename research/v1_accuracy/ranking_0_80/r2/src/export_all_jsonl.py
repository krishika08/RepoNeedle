"""
Export all 345 queries (train, val, held-out) to PER_QUERY_COMPARISON.jsonl.
"""
import json
from split import load_data
from evaluate_r2 import evaluate_dataset

def export_all():
    train_data, val_data, held_out_data = load_data()
    all_treatments = ["A", "B", "C", "D", "E", "F", "G", "H"]
    cfg_e = {"sfs_demotion_factor": 0.05, "tip_boost_weight": 1.5, "tip_threshold": 0.5}
    cfg_h = {"sfs_demotion_factor": 0.05, "tip_boost_weight": 1.5, "sms_weight": 0.1}

    def eval_all(dataset):
        res = {}
        for t in all_treatments:
            cfg = cfg_h if t in ["F", "H"] else (cfg_e if t in ["B", "C", "E"] else None)
            _, recs = evaluate_dataset(dataset, t, cfg)
            res[t] = recs
        return res

    tr_evals = eval_all(train_data)
    val_evals = eval_all(val_data)
    h_evals = eval_all(held_out_data)

    out_path = "research/v1_accuracy/ranking_0_80/r2/PER_QUERY_COMPARISON.jsonl"
    count = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for split_name, data, evals in [("train", train_data, tr_evals), ("val", val_data, val_evals), ("held_out", held_out_data, h_evals)]:
            for i in range(len(data)):
                row = {
                    "query_id": data[i]["query_id"],
                    "split": split_name,
                    "repo": data[i]["repo"],
                    "task_type": data[i]["task_type"],
                    "gold_files": data[i]["gold_files"],
                    "treatments": {
                        t: {
                            "rank": evals[t][i]["first_gold_rank"],
                            "rr": evals[t][i]["rr"],
                            "r20": evals[t][i]["recall@20"],
                            "top1": evals[t][i]["top1_path"],
                            "rank1_is_seed": evals[t][i]["rank1_is_seed"],
                        } for t in all_treatments
                    }
                }
                f.write(json.dumps(row) + "\n")
                count += 1
    print(f"Exported all {count} queries to {out_path}")

if __name__ == "__main__":
    export_all()

