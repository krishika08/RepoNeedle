"""
Comprehensive Ablations and Hyperparameter Sweeps on Training Set.
Validates stability on Validation Set.
"""
from evaluate_r2 import evaluate_dataset
from split import load_data
import json

def run_ablations():
    train_data, val_data, _ = load_data()
    print("=== RUNNING ABLATION STUDIES ===")

    # 1. SFS Demotion Strength Sweep (Treatment B)
    print("\n--- 1. SFS Demotion Factor Sweep on Training Set ---")
    factors = [0.001, 0.005, 0.01, 0.05, 0.1, 0.2, 0.5, 1.0]
    sfs_sweep_results = []
    for gamma in factors:
        cfg = {"sfs_demotion_factor": gamma}
        res_tr, _ = evaluate_dataset(train_data, "B", cfg)
        res_val, _ = evaluate_dataset(val_data, "B", cfg)
        print(f"  gamma = {gamma:<5}: Train MRR = {res_tr['mrr']:.4f} (Hit@1 = {res_tr['hit@1']*100:.1f}%) | Val MRR = {res_val['mrr']:.4f} (Hit@1 = {res_val['hit@1']*100:.1f}%) | Trap = {res_tr['seed_self_retrieval_count']}")
        sfs_sweep_results.append({"gamma": gamma, "train_mrr": res_tr["mrr"], "val_mrr": res_val["mrr"]})

    # 2. Intent Guard Ablation for SFS
    print("\n--- 2. SFS Intent Guard Ablation ---")
    # Compare:
    # (a) Original ranker (Treatment A)
    # (b) Seed detection without suppression (telemetry only)
    # (c) SFS with Intent Guard (relational only)
    print(f"  (a) Baseline Ranker:          Train MRR = {evaluate_dataset(train_data, 'A')[0]['mrr']:.4f}")
    print(f"  (b) SFS with Intent Guard:    Train MRR = {evaluate_dataset(train_data, 'B')[0]['mrr']:.4f}")

    # 3. TIP Boost Weight Sweep (Treatment C)
    print("\n--- 3. TIP Boost Weight Sweep on Training Set ---")
    weights = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    tip_sweep_results = []
    for beta in weights:
        cfg = {"tip_boost_weight": beta}
        res_tr, _ = evaluate_dataset(train_data, "C", cfg)
        res_val, _ = evaluate_dataset(val_data, "C", cfg)
        print(f"  beta = {beta:<4}: Train MRR = {res_tr['mrr']:.4f} (Hit@1 = {res_tr['hit@1']*100:.1f}%) | Val MRR = {res_val['mrr']:.4f} (Hit@1 = {res_val['hit@1']*100:.1f}%)")
        tip_sweep_results.append({"beta": beta, "train_mrr": res_tr["mrr"], "val_mrr": res_val["mrr"]})

    # 4. SMS Weight Sweep (Treatment D and Treatment F)
    print("\n--- 4. SMS Weight Sweep on Training Set ---")
    sms_weights = [0.1, 0.2, 0.3, 0.5, 0.8, 1.0]
    sms_sweep_results = []
    for w in sms_weights:
        cfg = {"sms_weight": w}
        res_tr, _ = evaluate_dataset(train_data, "D", cfg)
        res_val, _ = evaluate_dataset(val_data, "D", cfg)
        print(f"  w_sms = {w:<4} (SMS alone): Train MRR = {res_tr['mrr']:.4f} | Val MRR = {res_val['mrr']:.4f}")
        
    print("\n--- 5. Combined SFS + TIP + SMS (Treatment H) Parameter Tuning ---")
    for w_sms in [0.1, 0.2, 0.3, 0.5]:
        cfg = {"sfs_demotion_factor": 0.01, "tip_boost_weight": 1.5, "sms_weight": w_sms}
        res_tr, _ = evaluate_dataset(train_data, "H", cfg)
        res_val, _ = evaluate_dataset(val_data, "H", cfg)
        print(f"  w_sms = {w_sms:<4}: Train MRR = {res_tr['mrr']:.4f} (Hit@1 = {res_tr['hit@1']*100:.1f}%) | Val MRR = {res_val['mrr']:.4f} (Hit@1 = {res_val['hit@1']*100:.1f}%)")

if __name__ == "__main__":
    run_ablations()

