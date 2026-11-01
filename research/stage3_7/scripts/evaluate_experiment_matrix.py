"""
Stage 3.7: Controlled Experiment Matrix Evaluator.
Executes the pre-registered 8-configuration ablation matrix (EXP-371 through EXP-378)
under the canonical unconstrained candidate-generation protocol across all N=345 ARB v2 samples.

Configurations:
  EXP-371: CAND-C (Previous-stage control: Lexical + Subword + PageRank + 0.5x Doc Filter)
  EXP-372: CAND-F (Previous-stage control: Coupled BM25 + Subword + PageRank + Doc Filter + Unbounded Bidir Diffusion)
  EXP-373: CAND-F-NO-DIFF (Candidate F with graph diffusion disabled)
  EXP-374: CAND-F-DECOUPLED (Candidate F with decoupled BM25 symbol length)
  EXP-375: CAND-F-FWD-ONLY (Candidate F with forward-only diffusion: alpha_fwd=0.25, alpha_bwd=0.0)
  EXP-376: CAND-F-BWD-ONLY (Candidate F with backward-only diffusion: alpha_fwd=0.0, alpha_bwd=0.20)
  EXP-377: CAND-F-HUBNORM (Candidate F with degree-normalized graph diffusion)
  EXP-378: CAND-COMBINED (Evidence-supported combination: Decoupled BM25 + Doc Filter + Hub-Normalized Diffusion)

Outputs:
  - research/stage3_7/RANKING_RESULTS.csv
  - research/stage3_7/PER_QUERY_RESULTS.jsonl
  - research/stage3_7/EXPERIMENT_REGISTRY.jsonl
"""

import sys
import os
import json
import csv
import time
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np

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
    sample_metrics,
    recall_at,
    reciprocal_rank,
    gold_coverage_at_budget,
)
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.core.tokenizer import estimate_tokens
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex


def run_experiment_matrix():
    print("=" * 80)
    print("STAGE 3.7: CONTROLLED EXPERIMENT MATRIX EVALUATION (EXP-371 TO EXP-378)")
    print("=" * 80)

    # 1. Corpus Manifest
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    manifest_raw = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            manifest_raw[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]

    # 2. Benchmark Subsets (Positive N=345)
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

    # Experiment definitions
    experiments = [
        {
            "id": "EXP-371",
            "name": "CAND-C",
            "desc": "Candidate C control: Lexical (decoupled) + Subword + PageRank + 0.5x Doc Filter (no symbols, no diffusion)",
        },
        {
            "id": "EXP-372",
            "name": "CAND-F",
            "desc": "Candidate F control: Coupled BM25 + Subword + PageRank + Doc Filter + Polyglot Symbols + Unbounded Bidir Diffusion",
        },
        {
            "id": "EXP-373",
            "name": "CAND-F-NO-DIFF",
            "desc": "Candidate F with graph diffusion disabled",
        },
        {
            "id": "EXP-374",
            "name": "CAND-F-DECOUPLED",
            "desc": "Candidate F with decoupled BM25 symbol length",
        },
        {
            "id": "EXP-375",
            "name": "CAND-F-FWD-ONLY",
            "desc": "Candidate F with forward-only diffusion (alpha_fwd=0.25, alpha_bwd=0.0)",
        },
        {
            "id": "EXP-376",
            "name": "CAND-F-BWD-ONLY",
            "desc": "Candidate F with backward-only diffusion (alpha_fwd=0.0, alpha_bwd=0.20)",
        },
        {
            "id": "EXP-377",
            "name": "CAND-F-HUBNORM",
            "desc": "Candidate F with degree-normalized graph diffusion (1/sqrt(degree))",
        },
        {
            "id": "EXP-378",
            "name": "CAND-COMBINED",
            "desc": "Combined candidate: Decoupled BM25 + Subword + Doc Filter + Hub-Normalized Diffusion (No PageRank)",
        },
    ]

    # Data structures for accumulation
    per_query_records = []
    exp_summary_metrics = defaultdict(lambda: defaultdict(list))
    exp_latencies = defaultdict(list)

    corpus_idx = 0
    total_corpora = len(by_corpus)

    for (repo, base_commit), repo_samples in by_corpus.items():
        corpus_idx += 1
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

        path_to_chunks = defaultdict(list)
        for c in chunks:
            p = c.get("path")
            if p:
                path_to_chunks[p].append(c)

        # Build docs:
        # 1. With polyglot symbols
        docs_with_symbols = []
        # 2. Pure (without symbols, for Cand C)
        docs_pure = []
        for p, t in file_texts.items():
            content = t[:25000]
            syms, imps = RepoGraph.extract_polyglot_symbols(content, p)
            docs_with_symbols.append(FileDoc(path=p, content=content, symbols=syms, imports=imps))
            docs_pure.append(FileDoc(path=p, content=content, symbols=[], imports=[]))

        num_docs = len(docs_with_symbols)
        doc_paths = [d.path for d in docs_with_symbols]
        path_to_idx = {d.path: i for i, d in enumerate(docs_with_symbols)}

        # Build indices
        # BM25 coupled symbols (Cand F default)
        bm25_coupled = BM25Index(decouple_symbols=False).fit(docs_with_symbols)
        # BM25 decoupled symbols (Decoupled Cand F / Cand C)
        bm25_decoupled = BM25Index(decouple_symbols=True).fit(docs_with_symbols)
        # BM25 pure (Cand C)
        bm25_pure = BM25Index(decouple_symbols=True).fit(docs_pure)

        # Semantic index
        semantic_index = SubwordSemanticIndex().fit(docs_with_symbols)

        # RepoGraph
        rg = RepoGraph().fit(docs_with_symbols)
        G = rg.graph
        pagerank_scores = rg.pagerank_scores

        # Doc filter mask
        doc_paths_lower = [p.lower() for p in doc_paths]
        is_doc_file = np.array([
            any(seg in p for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or
            p.endswith((".md", ".rst", ".txt", ".adoc", ".html"))
            for p in doc_paths_lower
        ], dtype=bool)

        # Helper to compute official metrics for a ranked score vector
        def eval_scores(scores_vec, gold_files, hard_neg_files, budget_tokens=8000):
            ranked_indices = np.argsort(-scores_vec)
            ranked_paths = [doc_paths[i] for i in ranked_indices]
            ranked_chunks = []
            seen = set()
            for p in ranked_paths:
                if p in path_to_chunks and p not in seen:
                    ranked_chunks.extend(path_to_chunks[p])
                    seen.add(p)
            for p, chs in path_to_chunks.items():
                if p not in seen:
                    ranked_chunks.extend(chs)
                    seen.add(p)

            gold_set = set(gold_files)
            # Official ARB sample metrics (uses fractional recall for multi-gold)
            m = sample_metrics(gold_files, ranked_chunks, context_budget=budget_tokens, hard_negative_files=hard_neg_files)
            
            # Hit@K definitions (1.0 if at least one gold in top K, else 0.0)
            hit1 = 1.0 if any(p in gold_set for p in ranked_paths[:1]) else 0.0
            hit5 = 1.0 if any(p in gold_set for p in ranked_paths[:5]) else 0.0
            hit10 = 1.0 if any(p in gold_set for p in ranked_paths[:10]) else 0.0
            hit20 = 1.0 if any(p in gold_set for p in ranked_paths[:20]) else 0.0

            r1 = recall_at(gold_set, ranked_paths, 1)
            r5 = recall_at(gold_set, ranked_paths, 5)
            r10 = recall_at(gold_set, ranked_paths, 10)
            r20 = recall_at(gold_set, ranked_paths, 20)

            # First rank
            first_rank = -1
            for r_i, p in enumerate(ranked_paths):
                if p in gold_set:
                    first_rank = r_i + 1
                    break

            bcy_4k = gold_coverage_at_budget(gold_set, ranked_chunks, 4000)
            bcy_8k = m["gold_coverage@8k"]
            bcy_16k = gold_coverage_at_budget(gold_set, ranked_chunks, 16000)

            return {
                "mrr": m["MRR"],
                "r1": r1,
                "r5": r5,
                "r10": r10,
                "r20": r20,
                "hit1": hit1,
                "hit5": hit5,
                "hit10": hit10,
                "hit20": hit20,
                "p5": m["Precision@5"],
                "p10": m["Precision@10"],
                "p20": m["Precision@20"],
                "bcy_4k": bcy_4k,
                "bcy_8k": bcy_8k,
                "bcy_16k": bcy_16k,
                "first_rank": first_rank,
                "top_paths": ranked_paths[:5],
                "coverage": 1.0 if first_rank > 0 else 0.0,
            }

        # Language of repository
        ext_counts = Counter(p.split(".")[-1].lower() for p in file_texts.keys() if "." in p)
        top_ext = ext_counts.most_common(1)[0][0] if ext_counts else "unknown"
        lang_map = {"py": "python", "rs": "rust", "go": "go", "ts": "typescript", "js": "javascript", "tsx": "typescript", "jsx": "javascript"}
        repo_lang = lang_map.get(top_ext, top_ext)

        # Evaluate queries for this repo
        for s in repo_samples:
            s_id = s["id"]
            gold = target_gold_files(s)
            hard_neg = hard_negative_files(s)
            q_text = query_text_for_eval(s)
            t_type = s["_subset_name"]

            # Compute foundational scores
            t_start = time.perf_counter()
            lex_pure = bm25_pure.score(q_text)
            lex_coup = bm25_coupled.score(q_text)
            lex_decoup = bm25_decoupled.score(q_text)
            sem = semantic_index.score(q_text)

            # Base hybrid scores
            # Cand C base
            base_c = (lex_pure + sem + pagerank_scores) / 3.0
            base_c[is_doc_file] *= 0.5

            # Cand F base (coupled)
            base_f_coup = (lex_coup + sem + pagerank_scores) / 3.0
            base_f_coup[is_doc_file] *= 0.5

            # Cand F base (decoupled)
            base_f_decoup = (lex_decoup + sem + pagerank_scores) / 3.0
            base_f_decoup[is_doc_file] *= 0.5

            # Combined base (lexical decoupled + semantic, without PageRank)
            base_combined = (lex_decoup + sem) / 2.0
            base_combined[is_doc_file] *= 0.5

            # Graph diffusion calculations from coupled hits
            boost_fwd_coup = np.zeros(num_docs, dtype=np.float32)
            boost_bwd_coup = np.zeros(num_docs, dtype=np.float32)
            boost_hubnorm_coup = np.zeros(num_docs, dtype=np.float32)

            # Graph diffusion calculations from decoupled hits (for EXP-374 & EXP-378)
            boost_bidir_decoup = np.zeros(num_docs, dtype=np.float32)
            boost_hubnorm_decoup = np.zeros(num_docs, dtype=np.float32)

            if G.number_of_edges() > 0:
                # 1. Using coupled hits (Cand F standard)
                combined_hits_coup = lex_coup + sem
                if len(combined_hits_coup) > 0 and float(np.max(combined_hits_coup)) > 0:
                    top_seeds = np.argsort(combined_hits_coup)[::-1][:5]
                    for s_idx in top_seeds:
                        seed_p = doc_paths[s_idx]
                        seed_val = float(combined_hits_coup[s_idx])
                        if seed_val > 0 and seed_p in G:
                            for succ in G.successors(seed_p):
                                if succ in path_to_idx:
                                    n_idx = path_to_idx[succ]
                                    boost_fwd_coup[n_idx] = max(boost_fwd_coup[n_idx], float(seed_val * 0.25))
                                    in_deg = max(1, G.in_degree(succ))
                                    boost_hubnorm_coup[n_idx] = max(boost_hubnorm_coup[n_idx], float(seed_val * 0.25 / np.sqrt(in_deg)))
                            for pred in G.predecessors(seed_p):
                                if pred in path_to_idx:
                                    n_idx = path_to_idx[pred]
                                    boost_bwd_coup[n_idx] = max(boost_bwd_coup[n_idx], float(seed_val * 0.20))
                                    out_deg = max(1, G.out_degree(pred))
                                    boost_hubnorm_coup[n_idx] = max(boost_hubnorm_coup[n_idx], float(seed_val * 0.20 / np.sqrt(out_deg)))

                # 2. Using decoupled hits (for EXP-374 & EXP-378)
                combined_hits_decoup = lex_decoup + sem
                if len(combined_hits_decoup) > 0 and float(np.max(combined_hits_decoup)) > 0:
                    top_seeds_d = np.argsort(combined_hits_decoup)[::-1][:5]
                    for s_idx in top_seeds_d:
                        seed_p = doc_paths[s_idx]
                        seed_val = float(combined_hits_decoup[s_idx])
                        if seed_val > 0 and seed_p in G:
                            for succ in G.successors(seed_p):
                                if succ in path_to_idx:
                                    n_idx = path_to_idx[succ]
                                    boost_bidir_decoup[n_idx] = max(boost_bidir_decoup[n_idx], float(seed_val * 0.25))
                                    in_deg = max(1, G.in_degree(succ))
                                    boost_hubnorm_decoup[n_idx] = max(boost_hubnorm_decoup[n_idx], float(seed_val * 0.25 / np.sqrt(in_deg)))
                            for pred in G.predecessors(seed_p):
                                if pred in path_to_idx:
                                    n_idx = path_to_idx[pred]
                                    boost_bidir_decoup[n_idx] = max(boost_bidir_decoup[n_idx], float(seed_val * 0.20))
                                    out_deg = max(1, G.out_degree(pred))
                                    boost_hubnorm_decoup[n_idx] = max(boost_hubnorm_decoup[n_idx], float(seed_val * 0.20 / np.sqrt(out_deg)))

            boost_bidir_coup = np.maximum(boost_fwd_coup, boost_bwd_coup)

            # Assemble configurations
            # EXP-371: Cand C
            scores_371 = base_c
            # EXP-372: Cand F (coupled + bidir)
            scores_372 = base_f_coup + 0.15 * boost_bidir_coup
            # EXP-373: Cand F no diffusion
            scores_373 = base_f_coup
            # EXP-374: Cand F decoupled (decoupled BM25 + bidir)
            scores_374 = base_f_decoup + 0.15 * boost_bidir_decoup
            # EXP-375: Cand F fwd only
            scores_375 = base_f_coup + 0.15 * boost_fwd_coup
            # EXP-376: Cand F bwd only
            scores_376 = base_f_coup + 0.15 * boost_bwd_coup
            # EXP-377: Cand F hub-norm
            scores_377 = base_f_coup + 0.15 * boost_hubnorm_coup
            # EXP-378: Combined (Decoupled BM25 + Subword + Doc Filter + Hub-norm diffusion, no PR)
            scores_378 = base_combined + 0.15 * boost_hubnorm_decoup

            exp_scores = [
                ("EXP-371", scores_371),
                ("EXP-372", scores_372),
                ("EXP-373", scores_373),
                ("EXP-374", scores_374),
                ("EXP-375", scores_375),
                ("EXP-376", scores_376),
                ("EXP-377", scores_377),
                ("EXP-378", scores_378),
            ]

            elapsed_query_ms = (time.perf_counter() - t_start) * 1000.0

            for exp_id, sc in exp_scores:
                res = eval_scores(sc, gold, hard_neg)
                res["latency_ms"] = elapsed_query_ms / len(exp_scores)
                res["query_id"] = s_id
                res["repo"] = repo
                res["task_type"] = t_type
                res["language"] = repo_lang
                res["experiment_id"] = exp_id
                res["gold_files"] = gold

                per_query_records.append(res)
                for k in ["mrr", "r1", "r5", "r10", "r20", "hit1", "hit5", "hit10", "hit20", "bcy_4k", "bcy_8k", "bcy_16k", "coverage"]:
                    exp_summary_metrics[exp_id][k].append(res[k])
                exp_latencies[exp_id].append(res["latency_ms"])

        if corpus_idx % 5 == 0 or corpus_idx == total_corpora:
            print(f"Evaluated {corpus_idx}/{total_corpora} corpora ({len(per_query_records)} per-query rows generated)...", flush=True)

    # 1. Write PER_QUERY_RESULTS.jsonl
    out_jsonl = STAGE_DIR / "PER_QUERY_RESULTS.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for r in per_query_records:
            f.write(json.dumps(r) + "\n")
    print(f"\nWrote full PER_QUERY_RESULTS.jsonl to {out_jsonl} ({len(per_query_records)} records).")

    # 2. Write RANKING_RESULTS.csv
    out_rank_csv = STAGE_DIR / "RANKING_RESULTS.csv"
    rank_headers = [
        "experiment_id", "system_name", "description",
        "mrr", "recall_at_1", "recall_at_5", "recall_at_10", "recall_at_20",
        "hit_at_1", "hit_at_5", "hit_at_10", "hit_at_20",
        "candidate_coverage", "candidate_generation_failure_rate",
        "bcy_at_4k", "bcy_at_8k", "bcy_at_16k",
        "latency_median_ms", "latency_p95_ms"
    ]

    exp_dict = {e["id"]: e for e in experiments}
    ranking_rows = []

    print("\n" + "=" * 80)
    print("STAGE 3.7 ABLATION MATRIX SUMMARY LEADERBOARD (N=345 positive ARB v2 samples)")
    print("=" * 80)
    print(f"{'Exp ID':<9} | {'System':<18} | {'MRR':<7} | {'R@1':<7} | {'R@5':<7} | {'R@10':<7} | {'R@20':<7} | {'Hit@20':<7} | {'BCY@8k':<7}")
    print("-" * 88)

    for exp in experiments:
        eid = exp["id"]
        sm = exp_summary_metrics[eid]
        lats = exp_latencies[eid]

        mrr_val = float(np.mean(sm["mrr"]))
        r1_val = float(np.mean(sm["r1"]))
        r5_val = float(np.mean(sm["r5"]))
        r10_val = float(np.mean(sm["r10"]))
        r20_val = float(np.mean(sm["r20"]))
        h1_val = float(np.mean(sm["hit1"]))
        h5_val = float(np.mean(sm["hit5"]))
        h10_val = float(np.mean(sm["hit10"]))
        h20_val = float(np.mean(sm["hit20"]))
        cov_val = float(np.mean(sm["coverage"]))
        fail_rate = 1.0 - cov_val
        bcy4 = float(np.mean(sm["bcy_4k"]))
        bcy8 = float(np.mean(sm["bcy_8k"]))
        bcy16 = float(np.mean(sm["bcy_16k"]))
        lat_med = float(np.median(lats))
        lat_p95 = float(np.percentile(lats, 95))

        print(f"{eid:<9} | {exp['name']:<18} | {mrr_val:.4f}  | {r1_val:.4f}  | {r5_val:.4f}  | {r10_val:.4f}  | {r20_val:.4f}  | {h20_val:.4f}  | {bcy8:.4f}")

        ranking_rows.append({
            "experiment_id": eid,
            "system_name": exp["name"],
            "description": exp["desc"],
            "mrr": f"{mrr_val:.6f}",
            "recall_at_1": f"{r1_val:.6f}",
            "recall_at_5": f"{r5_val:.6f}",
            "recall_at_10": f"{r10_val:.6f}",
            "recall_at_20": f"{r20_val:.6f}",
            "hit_at_1": f"{h1_val:.6f}",
            "hit_at_5": f"{h5_val:.6f}",
            "hit_at_10": f"{h10_val:.6f}",
            "hit_at_20": f"{h20_val:.6f}",
            "candidate_coverage": f"{cov_val:.6f}",
            "candidate_generation_failure_rate": f"{fail_rate:.6f}",
            "bcy_at_4k": f"{bcy4:.6f}",
            "bcy_at_8k": f"{bcy8:.6f}",
            "bcy_at_16k": f"{bcy16:.6f}",
            "latency_median_ms": f"{lat_med:.2f}",
            "latency_p95_ms": f"{lat_p95:.2f}",
        })

    with open(out_rank_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rank_headers)
        writer.writeheader()
        writer.writerows(ranking_rows)

    print(f"\nSaved RANKING_RESULTS.csv to {out_rank_csv}")

    # 3. Write EXPERIMENT_REGISTRY.jsonl
    out_reg_jsonl = STAGE_DIR / "EXPERIMENT_REGISTRY.jsonl"
    with open(out_reg_jsonl, "w", encoding="utf-8") as f:
        for r_row in ranking_rows:
            reg_entry = {
                "experiment_id": r_row["experiment_id"],
                "system_name": r_row["system_name"],
                "stage": "Stage 3.7",
                "commit": "f61c6be",
                "branch": "research/stage3_7",
                "benchmark": "ARB v2 Unconstrained (N=345)",
                "description": r_row["description"],
                "metrics": {
                    "mrr": float(r_row["mrr"]),
                    "recall_at_1": float(r_row["recall_at_1"]),
                    "recall_at_5": float(r_row["recall_at_5"]),
                    "recall_at_10": float(r_row["recall_at_10"]),
                    "recall_at_20": float(r_row["recall_at_20"]),
                    "hit_at_1": float(r_row["hit_at_1"]),
                    "hit_at_5": float(r_row["hit_at_5"]),
                    "hit_at_10": float(r_row["hit_at_10"]),
                    "hit_at_20": float(r_row["hit_at_20"]),
                    "candidate_coverage": float(r_row["candidate_coverage"]),
                    "bcy_at_8k": float(r_row["bcy_at_8k"]),
                    "latency_median_ms": float(r_row["latency_median_ms"]),
                    "latency_p95_ms": float(r_row["latency_p95_ms"]),
                }
            }
            f.write(json.dumps(reg_entry) + "\n")

    print(f"Saved EXPERIMENT_REGISTRY.jsonl to {out_reg_jsonl}")


if __name__ == "__main__":
    run_experiment_matrix()

