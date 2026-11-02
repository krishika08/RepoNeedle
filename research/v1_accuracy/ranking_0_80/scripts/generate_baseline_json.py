"""
Generate BASELINE_REPRODUCTION.json with exact bit-for-bit metrics and query details.
"""
import gzip
import json
import numpy as np

def generate_baseline_reproduction():
    with open("reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl", "r", encoding="utf-8") as f:
        baseline_records = [json.loads(l) for l in f if l.strip()]
        
    m1_records = {}
    with gzip.open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                m1_records[data["query_id"]] = data

    repos = sorted(list(set(r["repo"] for r in baseline_records)))
    snapshots = sorted(list(set((r["repo"], r["base_commit"]) for r in baseline_records)))
    
    total_gold = sum(len(r["gold_files"]) for r in baseline_records)
    
    def calc_aggregates(key):
        return {
            "mrr": float(np.mean([r[key]["mrr"] for r in baseline_records])),
            "recall@5": float(np.mean([r[key]["recall@5"] for r in baseline_records])),
            "recall@10": float(np.mean([r[key]["recall@10"] for r in baseline_records])),
            "recall@20": float(np.mean([r[key]["recall@20"] for r in baseline_records])),
        }

    reponeedle_agg = calc_aggregates("reponeedle")
    bm25_agg = calc_aggregates("bm25")
    lexical_agg = calc_aggregates("lexical")
    repomap_agg = calc_aggregates("repomap")
    
    # Calculate M1 metrics
    m1_mrrs = []
    m1_r5 = []
    m1_r10 = []
    m1_r20 = []
    m1_r50 = []
    m1_total_recall = []
    
    per_query_data = []
    
    for r in baseline_records:
        qid = r["sample_id"]
        gold_files = set(r["gold_files"])
        m1 = m1_records[qid]
        cands = m1["candidates"]
        
        cand_map = {c["path"]: c for c in cands}
        gold_ranks = [cand_map[g]["m1_rank"] for g in gold_files if g in cand_map]
        
        first_gold_rank = min(gold_ranks) if gold_ranks else None
        mrr = 1.0 / first_gold_rank if first_gold_rank else 0.0
        r5 = sum(1 for rank in gold_ranks if rank <= 5) / len(gold_files)
        r10 = sum(1 for rank in gold_ranks if rank <= 10) / len(gold_files)
        r20 = sum(1 for rank in gold_ranks if rank <= 20) / len(gold_files)
        r50 = sum(1 for rank in gold_ranks if rank <= 50) / len(gold_files)
        tot_rec = len(gold_ranks) / len(gold_files)
        
        m1_mrrs.append(mrr)
        m1_r5.append(r5)
        m1_r10.append(r10)
        m1_r20.append(r20)
        m1_r50.append(r50)
        m1_total_recall.append(tot_rec)
        
        per_query_data.append({
            "query_id": qid,
            "repo": r["repo"],
            "base_commit": r["base_commit"],
            "task_type": r["task_type"],
            "gold_files": r["gold_files"],
            "reponeedle_v0": {
                "mrr": r["reponeedle"]["mrr"],
                "recall@5": r["reponeedle"]["recall@5"],
                "recall@10": r["reponeedle"]["recall@10"],
                "recall@20": r["reponeedle"]["recall@20"],
                "top_1_file": r["reponeedle"]["top_files"][0] if r["reponeedle"]["top_files"] else None
            },
            "m1_candidate_pool": {
                "mrr": mrr,
                "first_gold_rank": first_gold_rank,
                "recall@5": r5,
                "recall@10": r10,
                "recall@20": r20,
                "recall@50": r50,
                "total_recall": tot_rec,
                "top_1_file": cands[0]["path"] if cands else None,
                "num_candidates": len(cands)
            }
        })

    m1_agg = {
        "mrr": float(np.mean(m1_mrrs)),
        "recall@5": float(np.mean(m1_r5)),
        "recall@10": float(np.mean(m1_r10)),
        "recall@20": float(np.mean(m1_r20)),
        "recall@50": float(np.mean(m1_r50)),
        "total_candidate_recall": float(np.mean(m1_total_recall)),
        "hit@1": sum(1 for m in m1_mrrs if m == 1.0) / len(m1_mrrs)
    }

    reproduction_data = {
        "benchmark_metadata": {
            "name": "Agent Retrieval Bench (ARB) v2 Set A",
            "queries_count": len(baseline_records),
            "repositories_count": len(repos),
            "snapshots_count": len(snapshots),
            "gold_targets_count": total_gold,
            "repositories": repos
        },
        "official_frozen_baselines": {
            "reponeedle_v0_1_0": {
                "description": "RepoNeedle v0.1.0 release frozen baseline",
                "mrr": round(reponeedle_agg["mrr"], 4),
                "recall@5": round(reponeedle_agg["recall@5"], 4),
                "recall@10": round(reponeedle_agg["recall@10"], 4),
                "recall@20": round(reponeedle_agg["recall@20"], 4),
                "exact_metrics": reponeedle_agg
            },
            "bm25": {
                "description": "Standard BM25 baseline",
                "mrr": round(bm25_agg["mrr"], 4),
                "recall@5": round(bm25_agg["recall@5"], 4),
                "recall@10": round(bm25_agg["recall@10"], 4),
                "recall@20": round(bm25_agg["recall@20"], 4),
                "exact_metrics": bm25_agg
            },
            "lexical": {
                "description": "Dense/sparse lexical baseline",
                "mrr": round(lexical_agg["mrr"], 4),
                "recall@5": round(lexical_agg["recall@5"], 4),
                "recall@10": round(lexical_agg["recall@10"], 4),
                "recall@20": round(lexical_agg["recall@20"], 4),
                "exact_metrics": lexical_agg
            },
            "repomap": {
                "description": "Aider RepoMap PageRank baseline",
                "mrr": round(repomap_agg["mrr"], 4),
                "recall@5": round(repomap_agg["recall@5"], 4),
                "recall@10": round(repomap_agg["recall@10"], 4),
                "recall@20": round(repomap_agg["recall@20"], 4),
                "exact_metrics": repomap_agg
            }
        },
        "m1_multi_channel_candidate_reference": {
            "description": "Frozen M1 multi-channel candidate generation pool",
            "mrr": round(m1_agg["mrr"], 4),
            "recall@5": round(m1_agg["recall@5"], 4),
            "recall@10": round(m1_agg["recall@10"], 4),
            "recall@20": round(m1_agg["recall@20"], 4),
            "recall@50": round(m1_agg["recall@50"], 4),
            "total_candidate_recall": round(m1_agg["total_candidate_recall"], 4),
            "hit@1": round(m1_agg["hit@1"], 4),
            "exact_metrics": m1_agg
        },
        "per_query_evaluations": per_query_data
    }

    out_path = "research/v1_accuracy/ranking_0_80/BASELINE_REPRODUCTION.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(reproduction_data, f, indent=2)
        
    print(f"Saved BASELINE_REPRODUCTION.json ({len(reproduction_data['per_query_evaluations'])} records).")

if __name__ == "__main__":
    generate_baseline_reproduction()

