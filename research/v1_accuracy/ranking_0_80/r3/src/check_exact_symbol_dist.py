import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "r2", "src"))
from split import load_data
from test_intent import is_test_candidate

train_data, val_data, held_out_data = load_data()

for split_name, split_data in [("Train", train_data), ("Validation", val_data)]:
    gold_exact_scores = []
    nongold_exact_scores = []
    
    for item in split_data:
        golds = set(item["gold_files"])
        for c in item["candidates"]:
            es = c.get("scores", {}).get("exact_symbol", 0.0)
            if c["path"] in golds:
                gold_exact_scores.append(es)
            else:
                nongold_exact_scores.append(es)
                
    print(f"=== {split_name} Exact Symbol Score Distribution ===")
    print(f"  Gold candidates:    mean={np.mean(gold_exact_scores):.3f}, median={np.median(gold_exact_scores):.3f}, >0: {(np.array(gold_exact_scores) > 0).mean()*100:.1f}%")
    print(f"  Non-gold candidates:mean={np.mean(nongold_exact_scores):.3f}, median={np.median(nongold_exact_scores):.3f}, >0: {(np.array(nongold_exact_scores) > 0).mean()*100:.1f}%")

