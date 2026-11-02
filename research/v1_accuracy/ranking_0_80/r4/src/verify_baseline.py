import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "r2", "src")))
from split import load_data
from evaluate_r2 import evaluate_dataset

train_data, val_data, held_out_data = load_data()
all_data = train_data + val_data + held_out_data

val_metrics, _ = evaluate_dataset(val_data, treatment="E")
held_metrics, _ = evaluate_dataset(held_out_data, treatment="E")

print(f"Treatment E Val MRR:      {val_metrics['mrr']:.4f}")
print(f"Treatment E Held-Out MRR: {held_metrics['mrr']:.4f}")
print(f"Treatment E Val Hit@1:    {val_metrics['hit@1']*100:.2f}%")
print(f"Treatment E Held Hit@1:   {held_metrics['hit@1']*100:.2f}%")

total_golds = sum(len(d['gold_files']) for d in all_data)
rec_golds = sum(len(set(d['gold_files']) & set(c['path'] for c in d['candidates'])) for d in all_data)
print(f"Full-pool candidate recall: {rec_golds}/{total_golds}")
