import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "r2", "src"))
from split import load_data
from test_intent import is_test_candidate

train_data, val_data, held_out_data = load_data()
all_data = train_data + val_data + held_out_data

for ttype in ["trace2code", "code2test", "comment2context", "edit2ripple"]:
    sub = [item for item in all_data if item["task_type"] == ttype]
    test_golds = 0
    impl_golds = 0
    total_golds = 0
    for item in sub:
        for g in item["gold_files"]:
            total_golds += 1
            if is_test_candidate(g):
                test_golds += 1
            else:
                impl_golds += 1
    pct_test = (test_golds / total_golds) * 100 if total_golds else 0
    print(f"Task: {ttype:<18} | Total golds: {total_golds:<4} | Test golds: {test_golds:<4} ({pct_test:.1f}%) | Impl golds: {impl_golds:<4}")
