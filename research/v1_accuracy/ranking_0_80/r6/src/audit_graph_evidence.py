"""
Phase R6: Graph Evidence Audit Script.
Analyzes the empirical precision, recall, false-positive rate, and false-negative rate
of Confirmed vs Heuristic graph edges across the independent benchmark dataset.
"""

import os
import gzip
import json
from collections import defaultdict
from typing import Dict, List, Any

from graph_evidence import GraphEvidenceAuditor, EdgeProvenance, CONFIRMED_TYPES, HEURISTIC_TYPES


def run_graph_evidence_audit(benchmark_path: str) -> Dict[str, Any]:
    with gzip.open(benchmark_path, "rt", encoding="utf-8") as f:
        dataset = json.load(f)

    stats = {
        "total_queries": len(dataset),
        "total_candidates_examined": 0,
        "total_edges_extracted": 0,
        "edge_counts_by_provenance": defaultdict(int),
        "confirmed_edge_count": 0,
        "heuristic_edge_count": 0,
        # Performance on gold targets (True Positives vs False Negatives)
        "confirmed_tp": 0,
        "confirmed_fp": 0,
        "heuristic_tp": 0,
        "heuristic_fp": 0,
        "gold_targets_with_no_edge": 0,
        "gold_targets_total": 0,
    }

    for record in dataset:
        seeds = record.get("seed_files", [])
        gold_files = set(record["_evaluator_gold"]["gold_files"])
        candidates = record["candidates"]
        query_text = record["query_text"]

        stats["total_candidates_examined"] += len(candidates)
        stats["gold_targets_total"] += len(gold_files)

        for cand in candidates:
            c_path = cand["path"]
            is_gold = c_path in gold_files

            edges = GraphEvidenceAuditor.audit_edges(cand, seeds, query_text)
            stats["total_edges_extracted"] += len(edges)

            has_confirmed = any(e["is_confirmed"] for e in edges)
            has_heuristic = any(not e["is_confirmed"] for e in edges)

            for e in edges:
                prov = e["provenance"]
                stats["edge_counts_by_provenance"][prov] += 1
                if e["is_confirmed"]:
                    stats["confirmed_edge_count"] += 1
                else:
                    stats["heuristic_edge_count"] += 1

            if has_confirmed:
                if is_gold:
                    stats["confirmed_tp"] += 1
                else:
                    stats["confirmed_fp"] += 1

            if has_heuristic:
                if is_gold:
                    stats["heuristic_tp"] += 1
                else:
                    stats["heuristic_fp"] += 1

            if is_gold and not edges:
                stats["gold_targets_with_no_edge"] += 1

    # Compute metrics
    conf_total = stats["confirmed_tp"] + stats["confirmed_fp"]
    conf_prec = stats["confirmed_tp"] / conf_total if conf_total > 0 else 0.0
    conf_fpr = stats["confirmed_fp"] / (stats["total_candidates_examined"] - stats["gold_targets_total"]) if stats["total_candidates_examined"] > stats["gold_targets_total"] else 0.0

    heur_total = stats["heuristic_tp"] + stats["heuristic_fp"]
    heur_prec = stats["heuristic_tp"] / heur_total if heur_total > 0 else 0.0
    heur_fpr = stats["heuristic_fp"] / (stats["total_candidates_examined"] - stats["gold_targets_total"]) if stats["total_candidates_examined"] > stats["gold_targets_total"] else 0.0

    report = {
        "summary": {
            "total_queries": stats["total_queries"],
            "total_candidates": stats["total_candidates_examined"],
            "total_edges": stats["total_edges_extracted"],
            "confirmed_edges": stats["confirmed_edge_count"],
            "heuristic_edges": stats["heuristic_edge_count"],
        },
        "precision_audit": {
            "confirmed_precision": round(conf_prec, 4),
            "confirmed_false_positive_rate": round(conf_fpr, 4),
            "confirmed_tp": stats["confirmed_tp"],
            "confirmed_fp": stats["confirmed_fp"],
            "heuristic_precision": round(heur_prec, 4),
            "heuristic_false_positive_rate": round(heur_fpr, 4),
            "heuristic_tp": stats["heuristic_tp"],
            "heuristic_fp": stats["heuristic_fp"],
        },
        "edge_breakdown": dict(stats["edge_counts_by_provenance"]),
    }

    return report


if __name__ == "__main__":
    src_dir = os.path.dirname(os.path.abspath(__file__))
    bm_path = os.path.join(src_dir, "..", "independent_benchmark.json.gz")
    rep = run_graph_evidence_audit(bm_path)
    print(json.dumps(rep, indent=2))

    out_file = os.path.join(src_dir, "..", "graph_evidence_audit.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2)
    print(f"Audit saved to: {os.path.abspath(out_file)}")

