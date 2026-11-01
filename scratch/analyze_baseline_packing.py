import json
from collections import defaultdict, Counter
import numpy as np

with open("research/v1_accuracy/m3_context_optimization/M3_BASELINE_SUMMARY.json", "r", encoding="utf-8") as f:
    summary = json.load(f)

# Load raw results
with open("research/v1_accuracy/m3_context_optimization/M3_BASELINE_RAW_RESULTS.jsonl", "r", encoding="utf-8") as f:
    raw = [json.loads(line) for line in f]

print(f"Loaded {len(raw)} raw query records.")

# 1. Investigate context losses for each budget:
loss_categories = {
    "2048": Counter(),
    "4096": Counter(),
    "8192": Counter(),
    "16384": Counter(),
    "32768": Counter(),
}

# Detailed causes:
# - Ranking too low (M1 rank > 20 or > 50)
# - Distractor displacement (gold was in top-20, but distractor files consumed budget before it)
# - Skeletonization (gold included as skeleton, eliding implementation)
# - Large file displacement (a large distractor > 1,500 tokens consumed budget)

for r in raw:
    qid = r["query_id"]
    golds = set(r["gold_files"])
    for b_str in ["2048", "4096", "8192", "16384", "32768"]:
        b_data = r["budgets"][b_str]
        selected_paths = {s["path"]: s for s in b_data["selected_files"]}
        for g in golds:
            if g not in selected_paths:
                # Find rank of g in candidate list
                # Look up from loss_reasons or determine
                reasons = [lr for lr in b_data["loss_reasons"] if g in lr]
                r_text = reasons[0] if reasons else "excluded"
                if "ranked at #" in r_text:
                    rank_num = int(r_text.split("ranked at #")[1].split(";")[0].split()[0])
                    if rank_num > 50:
                        loss_categories[b_str]["rank_gt_50"] += 1
                    elif rank_num > 20:
                        loss_categories[b_str]["rank_21_to_50"] += 1
                    elif rank_num > len(selected_paths):
                        loss_categories[b_str]["distractor_budget_exhaustion_top20"] += 1
                    else:
                        loss_categories[b_str]["skipped_oversized"] += 1
                else:
                    loss_categories[b_str]["not_in_candidates"] += 1
            else:
                s = selected_paths[g]
                if s["tier"] == "skeleton":
                    loss_categories[b_str]["skeletonized"] += 1

print("\n=== CONTEXT LOSS CAUSES BY BUDGET ===")
for b_str, counts in loss_categories.items():
    print(f"\nBudget {b_str}:")
    total_losses = sum(counts.values())
    for k, v in counts.most_common():
        print(f"  {k:35}: {v:3} ({v/514:.2%} of all 514 targets, {v/total_losses:.2%} of losses)")

# 2. Token Allocation: Relevant vs Non-Relevant
print("\n=== TOKEN ALLOCATION (RELEVANT VS DISTRACTOR) ===")
for b_str in ["2048", "4096", "8192", "16384", "32768"]:
    tot_tokens = sum(r["budgets"][b_str]["tokens_used_estimated"] for r in raw)
    gold_tokens = sum(r["budgets"][b_str]["gold_metrics"]["gold_tokens_estimated"] for r in raw)
    dist_tokens = sum(r["budgets"][b_str]["gold_metrics"]["distractor_tokens_estimated"] for r in raw)
    yield_ratio = gold_tokens / tot_tokens if tot_tokens > 0 else 0
    print(f"Budget {b_str:>5}: Total Packed={tot_tokens:,} | Gold Tokens={gold_tokens:,} ({yield_ratio:.2%}) | Distractor Tokens={dist_tokens:,} ({1-yield_ratio:.2%})")

# 3. Per-Repository Performance at 4k and 8k
repo_metrics = defaultdict(lambda: defaultdict(list))
for r in raw:
    repo = r["repo"]
    for b_str in ["4096", "8192"]:
        b_data = r["budgets"][b_str]
        repo_metrics[b_str][repo].append(b_data["gold_metrics"]["micro_recall_any"])

print("\n=== REPOSITORY LEVEL MICRO RECALL (ANY) AT 4k and 8k ===")
print(f"{'Repository':<30} | {'4k Rec':<8} | {'8k Rec':<8}")
print("-" * 50)
for repo in sorted(repo_metrics["4096"].keys()):
    r4 = np.mean(repo_metrics["4096"][repo])
    r8 = np.mean(repo_metrics["8192"][repo])
    print(f"{repo:<30} | {r4:8.2%} | {r8:8.2%}")

