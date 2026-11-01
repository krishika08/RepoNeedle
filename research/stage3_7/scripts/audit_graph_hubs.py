"""
Stage 3.7: Graph Hub Dilution & Score Diffusion Diagnostics.
Measures graph topological properties (degree distributions, hubs, components)
and traces score diffusion before/after forward and backward propagation across all ARB v2 queries.
"""

import sys
import os
import json
import csv
import time
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np
import networkx as nx

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
STAGE_DIR = ROOT_DIR / "research" / "stage3_7"
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import (
    read_jsonl,
    target_gold_files,
    hard_negative_files,
    query_text_for_eval,
)
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.engine import RepoNeedleEngine


def run_graph_audit():
    print("=" * 80)
    print("STAGE 3.7: AUDIT GRAPH TOPOLOGY, HUBS & DIFFUSION SCORE DILUTION")
    print("=" * 80)

    # 1. Corpus Manifest
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    manifest_raw = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            manifest_raw[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]

    # 2. Benchmark Subsets
    subsets_def = [
        ("code2test", ARB_DIR / "data" / "benchmark" / "v2_code2test" / "samples.jsonl"),
        ("comment2context", ARB_DIR / "data" / "benchmark" / "v2_comment2context" / "samples.jsonl"),
        ("trace2code", ARB_DIR / "data" / "benchmark" / "v2_trace2code" / "samples.jsonl"),
        ("edit2ripple", ARB_DIR / "data" / "benchmark" / "v2_edit2ripple" / "samples.jsonl"),
    ]

    all_samples = []
    for sname, spath in subsets_def:
        for r in read_jsonl(spath):
            r["_subset_name"] = sname
            all_samples.append(r)

    by_corpus = defaultdict(list)
    for s in all_samples:
        by_corpus[(s["repo"], s["base_commit"])].append(s)

    graph_hub_rows = []
    diffusion_rows = []

    print(f"Auditing graph topology across {len(by_corpus)} repository corpora...")

    for (repo, base_commit), repo_samples in by_corpus.items():
        chunks_path = manifest_raw.get((repo, base_commit))
        if not chunks_path or not chunks_path.is_file():
            continue

        chunks = read_jsonl(chunks_path)
        file_texts = {}
        for c in chunks:
            p = c.get("path")
            t = c.get("text", "")
            if p and (p not in file_texts or len(t) > len(file_texts[p])):
                file_texts[p] = t

        docs = []
        for p, t in file_texts.items():
            syms, imps = RepoGraph.extract_polyglot_symbols(t[:25000], p)
            docs.append(FileDoc(path=p, content=t[:25000], symbols=syms, imports=imps))

        engine = RepoNeedleEngine.from_documents(docs)
        rg = engine.repo_graph
        G = rg.graph
        num_docs = len(docs)

        # Graph topology metrics
        num_nodes = G.number_of_nodes()
        num_edges = G.number_of_edges()

        if num_nodes == 0:
            continue

        in_degrees = [d for n, d in G.in_degree()]
        out_degrees = [d for n, d in G.out_degree()]
        total_degrees = [d for n, d in G.degree()]

        max_in_deg = max(in_degrees) if in_degrees else 0
        max_out_deg = max(out_degrees) if out_degrees else 0
        max_tot_deg = max(total_degrees) if total_degrees else 0

        p50_deg = float(np.percentile(total_degrees, 50))
        p90_deg = float(np.percentile(total_degrees, 90))
        p95_deg = float(np.percentile(total_degrees, 95))
        p99_deg = float(np.percentile(total_degrees, 99))

        isolated_nodes = len(list(nx.isolates(G)))
        
        # Undirected components
        G_undir = G.to_undirected()
        num_components = nx.number_connected_components(G_undir)

        # Hub concentration: fraction of total edge ends owned by top 5% nodes
        sorted_nodes_by_deg = sorted(G.degree(), key=lambda x: -x[1])
        top_5pct_k = max(1, int(0.05 * num_nodes))
        top_5pct_deg_sum = sum(d for n, d in sorted_nodes_by_deg[:top_5pct_k])
        total_deg_sum = sum(total_degrees)
        hub_concentration = top_5pct_deg_sum / total_deg_sum if total_deg_sum > 0 else 0.0

        top_hubs = [f"{n}(deg={d})" for n, d in sorted_nodes_by_deg[:3]]
        top_hubs_str = "; ".join(top_hubs)

        # Record graph hub diagnostic
        graph_hub_rows.append({
            "repo": repo,
            "base_commit": base_commit,
            "num_nodes": num_nodes,
            "num_edges": num_edges,
            "isolated_nodes": isolated_nodes,
            "num_components": num_components,
            "max_in_degree": max_in_deg,
            "max_out_degree": max_out_deg,
            "max_total_degree": max_tot_deg,
            "p50_degree": p50_deg,
            "p90_degree": p90_deg,
            "p95_degree": p95_deg,
            "p99_degree": p99_deg,
            "hub_concentration_top5pct": hub_concentration,
            "top_hubs": top_hubs_str,
        })

        # Score diffusion diagnostics across queries
        doc_paths = [d.path for d in docs]
        path_to_idx = {d.path: i for i, d in enumerate(docs)}

        doc_paths_lower = [p.lower() for p in doc_paths]
        is_doc_file = np.array([
            any(seg in p for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or
            p.endswith((".md", ".rst", ".txt", ".adoc", ".html"))
            for p in doc_paths_lower
        ], dtype=bool)

        for s in repo_samples:
            s_id = s["id"]
            gold = target_gold_files(s)
            q_text = query_text_for_eval(s)

            lex_scores = engine.lexical_index.score(q_text)
            sem_scores = engine.semantic_index.score(q_text)
            struct_scores = engine.repo_graph.pagerank_scores

            # Candidate C base scores
            base_scores = (lex_scores + sem_scores + struct_scores) / 3.0
            base_scores[is_doc_file] *= 0.5

            # Initial ranks before diffusion
            init_ranks = np.argsort(-base_scores)
            init_rank_map = {doc_paths[r]: i + 1 for i, r in enumerate(init_ranks)}

            # Trace Forward, Backward, and Bidirectional Diffusion
            boost_fwd = np.zeros(num_docs, dtype=np.float32)
            boost_bwd = np.zeros(num_docs, dtype=np.float32)
            boost_bidir = np.zeros(num_docs, dtype=np.float32)
            boost_hubnorm = np.zeros(num_docs, dtype=np.float32)

            if G.number_of_edges() > 0:
                combined_hits = lex_scores + sem_scores
                if len(combined_hits) > 0 and float(np.max(combined_hits)) > 0:
                    top_seed_indices = np.argsort(combined_hits)[::-1][:5]
                    
                    for s_idx in top_seed_indices:
                        seed_path = doc_paths[s_idx]
                        seed_val = float(combined_hits[s_idx])
                        if seed_val > 0 and seed_path in G:
                            # Forward: seed -> successors
                            for succ in G.successors(seed_path):
                                if succ in path_to_idx:
                                    n_idx = path_to_idx[succ]
                                    boost_fwd[n_idx] = max(boost_fwd[n_idx], float(seed_val * 0.25))
                                    # Hub normalized: scale by 1 / sqrt(in_degree(succ))
                                    in_deg = max(1, G.in_degree(succ))
                                    norm_factor = 1.0 / np.sqrt(in_deg)
                                    boost_hubnorm[n_idx] = max(boost_hubnorm[n_idx], float(seed_val * 0.25 * norm_factor))

                            # Backward: predecessors -> seed
                            for pred in G.predecessors(seed_path):
                                if pred in path_to_idx:
                                    n_idx = path_to_idx[pred]
                                    boost_bwd[n_idx] = max(boost_bwd[n_idx], float(seed_val * 0.20))
                                    # Hub normalized: scale by 1 / sqrt(out_degree(pred))
                                    out_deg = max(1, G.out_degree(pred))
                                    norm_factor = 1.0 / np.sqrt(out_deg)
                                    boost_hubnorm[n_idx] = max(boost_hubnorm[n_idx], float(seed_val * 0.20 * norm_factor))

            boost_bidir = np.maximum(boost_fwd, boost_bwd)

            scores_fwd = base_scores + 0.15 * boost_fwd
            scores_bwd = base_scores + 0.15 * boost_bwd
            scores_bidir = base_scores + 0.15 * boost_bidir
            scores_hubnorm = base_scores + 0.15 * boost_hubnorm

            ranks_fwd = np.argsort(-scores_fwd)
            ranks_bwd = np.argsort(-scores_bwd)
            ranks_bidir = np.argsort(-scores_bidir)
            ranks_hubnorm = np.argsort(-scores_hubnorm)

            rank_map_fwd = {doc_paths[r]: i + 1 for i, r in enumerate(ranks_fwd)}
            rank_map_bwd = {doc_paths[r]: i + 1 for i, r in enumerate(ranks_bwd)}
            rank_map_bidir = {doc_paths[r]: i + 1 for i, r in enumerate(ranks_bidir)}
            rank_map_hubnorm = {doc_paths[r]: i + 1 for i, r in enumerate(ranks_hubnorm)}

            # Gold files ranking changes
            for g in gold:
                if g in path_to_idx:
                    g_idx = path_to_idx[g]
                    r_init = init_rank_map.get(g, len(doc_paths) + 1)
                    r_fwd = rank_map_fwd.get(g, len(doc_paths) + 1)
                    r_bwd = rank_map_bwd.get(g, len(doc_paths) + 1)
                    r_bidir = rank_map_bidir.get(g, len(doc_paths) + 1)
                    r_hubnorm = rank_map_hubnorm.get(g, len(doc_paths) + 1)

                    # Top hub files in bidir rank
                    top_5_bidir = [doc_paths[r] for r in ranks_bidir[:5]]
                    top_5_hub_degs = [G.degree(p) if p in G else 0 for p in top_5_bidir]
                    max_top5_hub_deg = max(top_5_hub_degs) if top_5_hub_degs else 0

                    diffusion_rows.append({
                        "sample_id": s_id,
                        "repo": repo,
                        "gold_path": g,
                        "init_rank_no_diff": r_init,
                        "rank_fwd_only": r_fwd,
                        "rank_bwd_only": r_bwd,
                        "rank_bidir": r_bidir,
                        "rank_hubnorm": r_hubnorm,
                        "delta_bidir_vs_init": r_bidir - r_init, # > 0 means diffusion degraded rank
                        "delta_hubnorm_vs_bidir": r_bidir - r_hubnorm, # > 0 means hubnorm improved rank
                        "max_top5_hub_degree": max_top5_hub_deg,
                        "gold_in_degree": G.in_degree(g) if g in G else 0,
                        "gold_out_degree": G.out_degree(g) if g in G else 0,
                    })

    # Write GRAPH_HUB_DIAGNOSTICS.csv
    out_hub_csv = STAGE_DIR / "GRAPH_HUB_DIAGNOSTICS.csv"
    with open(out_hub_csv, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "repo", "base_commit", "num_nodes", "num_edges", "isolated_nodes",
            "num_components", "max_in_degree", "max_out_degree", "max_total_degree",
            "p50_degree", "p90_degree", "p95_degree", "p99_degree",
            "hub_concentration_top5pct", "top_hubs"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(graph_hub_rows)

    # Write GRAPH_DIFFUSION_RESULTS.csv
    out_diff_csv = STAGE_DIR / "GRAPH_DIFFUSION_RESULTS.csv"
    with open(out_diff_csv, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "sample_id", "repo", "gold_path", "init_rank_no_diff",
            "rank_fwd_only", "rank_bwd_only", "rank_bidir", "rank_hubnorm",
            "delta_bidir_vs_init", "delta_hubnorm_vs_bidir",
            "max_top5_hub_degree", "gold_in_degree", "gold_out_degree"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(diffusion_rows)

    print(f"\nSaved graph hub diagnostics to {out_hub_csv}")
    print(f"Saved graph diffusion results to {out_diff_csv}")

    # Summary statistics
    deltas = [r["delta_bidir_vs_init"] for r in diffusion_rows]
    degraded = sum(1 for d in deltas if d > 0)
    improved = sum(1 for d in deltas if d < 0)
    unchanged = sum(1 for d in deltas if d == 0)

    print(f"\nDiffusion Impact on Gold Files (N={len(diffusion_rows)} instances):")
    print(f"  Degraded:  {degraded} ({degraded / len(diffusion_rows):.1%})")
    print(f"  Improved:  {improved} ({improved / len(diffusion_rows):.1%})")
    print(f"  Unchanged: {unchanged} ({unchanged / len(diffusion_rows):.1%})")

    # Hubnorm vs Bidir
    hn_deltas = [r["delta_hubnorm_vs_bidir"] for r in diffusion_rows]
    hn_improved = sum(1 for d in hn_deltas if d > 0)
    hn_degraded = sum(1 for d in hn_deltas if d < 0)
    hn_unchanged = sum(1 for d in hn_deltas if d == 0)
    print(f"\nHub Normalization vs Raw Bidirectional Diffusion:")
    print(f"  Improved:  {hn_improved} ({hn_improved / len(diffusion_rows):.1%})")
    print(f"  Degraded:  {hn_degraded} ({hn_degraded / len(diffusion_rows):.1%})")
    print(f"  Unchanged: {hn_unchanged} ({hn_unchanged / len(diffusion_rows):.1%})")

    # Extreme hubs
    all_max_degs = [r["max_total_degree"] for r in graph_hub_rows]
    print(f"\nGraph Connectivity Extremes across repos:")
    print(f"  Max Total Degree observed: {max(all_max_degs)}")
    print(f"  Median Max Degree across repos: {np.median(all_max_degs)}")

    return graph_hub_rows, diffusion_rows


if __name__ == "__main__":
    run_graph_audit()

