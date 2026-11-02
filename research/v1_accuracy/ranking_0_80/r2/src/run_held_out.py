"""
Single Blind Held-Out Evaluation for Phase R2.
Runs once on the frozen 75 held-out test queries without any tuning.
"""
import json
import numpy as np
from split import load_data
from evaluate_r2 import evaluate_dataset
from statistical_validation import bootstrap_ci, paired_permutation_test

def run_held_out_evaluation():
    _, _, held_out_data = load_data()
    print(f"=== FROZEN HELD-OUT EVALUATION ({len(held_out_data)} queries across 5 repositories) ===")

    # Configurations selected from validation
    cfg_e = {"sfs_demotion_factor": 0.05, "tip_boost_weight": 1.5, "tip_threshold": 0.5}
    cfg_h = {"sfs_demotion_factor": 0.05, "tip_boost_weight": 1.5, "sms_weight": 0.1}

    # Evaluate Treatment A (Baseline)
    sum_a, recs_a = evaluate_dataset(held_out_data, "A")
    # Evaluate Treatment E (Selected Champion)
    sum_e, recs_e = evaluate_dataset(held_out_data, "E", cfg_e)
    # Evaluate Treatment H (Composite)
    sum_h, recs_h = evaluate_dataset(held_out_data, "H", cfg_h)

    print("\n--- HELD-OUT TEST RESULTS ---")
    print(f"Baseline M1 (A):       MRR = {sum_a['mrr']:.4f} | Hit@1 = {sum_a['hit@1']*100:.2f}% ({sum_a['hit@1_count']}/75) | R@20 = {sum_a['recall@20']:.4f} | Seed Trap = {sum_a['seed_self_retrieval_count']}")
    print(f"Treatment E (SFS+TIP): MRR = {sum_e['mrr']:.4f} | Hit@1 = {sum_e['hit@1']*100:.2f}% ({sum_e['hit@1_count']}/75) | R@20 = {sum_e['recall@20']:.4f} | Seed Trap = {sum_e['seed_self_retrieval_count']}")
    print(f"Treatment H (All 3):   MRR = {sum_h['mrr']:.4f} | Hit@1 = {sum_h['hit@1']*100:.2f}% ({sum_h['hit@1_count']}/75) | R@20 = {sum_h['recall@20']:.4f} | Seed Trap = {sum_h['seed_self_retrieval_count']}")

    # Significance of Treatment E vs A on Held-Out Test Set
    rr_a = np.array([r["rr"] for r in recs_a])
    rr_e = np.array([r["rr"] for r in recs_e])
    diff_e = rr_e - rr_a
    ci_low_e, ci_high_e, p_non_pos_e = bootstrap_ci(diff_e)
    perm_p_e = paired_permutation_test(rr_e, rr_a)

    print(f"\nTreatment E Significance on Held-Out Test:")
    print(f"  Delta MRR:       {np.mean(diff_e):+.4f} ({(np.mean(diff_e)/np.mean(rr_a))*100:+.1f}% relative)")
    print(f"  95% Bootstrap CI:[{ci_low_e:+.4f}, {ci_high_e:+.4f}]")
    print(f"  Permutation p:   {perm_p_e:.4f}")

    # Per-Task Breakdown on Held-out
    print("\n--- Held-Out Per-Task Breakdown ---")
    by_task_a = {}
    by_task_e = {}
    for r in recs_a:
        by_task_a.setdefault(r["task_type"], []).append(r["rr"])
    for r in recs_e:
        by_task_e.setdefault(r["task_type"], []).append(r["rr"])

    for task in sorted(by_task_a.keys()):
        m_a = np.mean(by_task_a[task])
        m_e = np.mean(by_task_e[task])
        print(f"  {task:<18} (n={len(by_task_a[task]):<2}): Base M1 = {m_a:.4f} | Treatment E = {m_e:.4f} (Delta: {m_e-m_a:+.4f})")

    # Save to JSON
    out_path = "research/v1_accuracy/ranking_0_80/r2/held_out_evaluation.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "metrics_A": sum_a,
            "metrics_E": sum_e,
            "metrics_H": sum_h,
            "significance_E_vs_A": {
                "delta_mrr": float(np.mean(diff_e)),
                "rel_pct": float(np.mean(diff_e)/np.mean(rr_a)*100),
                "ci_95": [ci_low_e, ci_high_e],
                "permutation_p": perm_p_e
            }
        }, f, indent=2)
    print(f"\nSaved held-out report to {out_path}")

if __name__ == "__main__":
    run_held_out_evaluation()

