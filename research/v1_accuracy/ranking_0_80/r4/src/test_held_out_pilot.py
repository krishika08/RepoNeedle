import os
import sys
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "r2", "src")))
from split import load_data
from test_fusion_pilot import treatments, evaluate_rankings

train_data, val_data, held_out_data = load_data()

print("=== Evaluation of Treatments A through H on Held-Out Split (75 queries) ===")
print(f"{'Code':<4} | {'Treatment':<32} | {'Held MRR':<10} | {'Held Hit@1':<11} | {'Held R@20':<10}")
print("-" * 75)
for code, (name, fn) in treatments.items():
    held_m = evaluate_rankings(held_out_data, fn)
    print(f"{code:<4} | {name:<32} | {held_m['mrr']:<10.4f} | {held_m['hit1_pct']:<10.2f}% | {held_m['recall@20']:<10.4f}")

