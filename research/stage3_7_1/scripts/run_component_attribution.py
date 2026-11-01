"""
Stage 3.7.1: Controlled Component Attribution & Drop-One Ablation Harness.
Evaluates the 5 single-factor drop-one variants around EXP-378:
  - EXP-378: Reference (Decoupled BM25 + Subword + DocFilter + HubNorm Diffusion, No PageRank)
  - EXP-379: Restore PageRank (Base = (Lex + Sem + PR)/3.0)
  - EXP-380: Restore Coupled BM25 Length (decouple_symbols=False)
  - EXP-381: Remove Hub-Normalized Diffusion (No graph diffusion)
  - EXP-382: Remove Documentation Filtering (No doc penalty)
  - EXP-383: Remove Subword Retrieval (Lexical only)

Outputs:
  - research/stage3_7_1/COMPONENT_ATTRIBUTION_RESULTS.csv
  - research/stage3_7_1/PER_QUERY_RESULTS.jsonl
  - research/stage3_7_1/EXPERIMENT_REGISTRY.jsonl
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
STAGE_DIR = ROOT_DIR / "research" / "stage3_7_1"
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import (
    read_jsonl,
    target_gold_files,
    hard_negative_files,
    query_text_for_eval,
    sample_metrics,
    recall_at,
    gold_coverage_at_budget,
)
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex


def run_attribution_experiments():
    print("=" * 80)
    print("STAGE 3.7.1: COMPONENT ATTRIBUTION DROP-ONE EXPERIMENTS AROUND EXP-378")
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
    seen_qids = set()
    for sname, spath in subsets_def:
        for r in read_jsonl(spath):
            qid = r["id"]
            if qid in seen_qids:
                raise ValueError(f"Duplicate query ID detected in benchmark: {qid}")
            seen_qids.add(qid)
            r["_subset_name"] = sname
            all_samples.append(r)

    print(f"Verified {len(all_samples)} unique positive samples across 4 tracks. Zero duplicates.")

    by_corpus = defaultdict(list)
    for s in all_samples:
        by_corpus[(s["repo"], s["base_commit"])].append(s)

    experiments = [
        {
            "id": "EXP-378",
            "name": "EXP-378-REF",
            "desc": "EXP-378 Reference: Decoupled BM25 + Subword + DocFilter + HubNorm Diffusion (No PR)",
        },
        {
            "id": "EXP-379",
            "name": "EXP-379-RESTORE-PR",
            "desc": "Drop-One: Restore Static PageRank (base = (lex + sem + pr)/3.0)",
        },
        {
            "id": "EXP-380",
            "name": "EXP-380-COUPLED-BM25",
            "desc": "Drop-One: Restore Coupled BM25 Symbol Length (decouple_symbols=False)",
        },
        {
            "id": "EXP-381",
            "name": "EXP-381-NO-DIFFUSION",
            "desc": "Drop-One: Remove Hub-Normalized Diffusion (No graph diffusion)",
        },
        {
            "id": "EXP-382",
            "name": "EXP-382-NO-DOC-FILTER",
            "desc": "Drop-One: Remove Documentation Filtering (No 0.5x penalty)",
        },
        {
            "id": "EXP-383",
            "name": "EXP-383-NO-SUBWORD",
            "desc": "Drop-One: Remove Subword Semantic Retrieval (Lexical only)",
        },
        {
            "id": "EXP-371",
            "name": "CAND-C-CONTROL",
            "desc": "Candidate C Control (Pure Lexical + Subword + PageRank + 0.5x DocFilter)",
        },
    ]

    # Data structures
    per_query_jsonl_records = defaultdict(lambda: {"systems": {}})
    exp_summary = defaultdict(lambda: defaultdict(list))
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

        # Docs with polyglot symbols
        docs_with_symbols = []
        docs_pure = []
        for p, t in file_texts.items():
            content = t[:25000]
            syms, imps = RepoGraph.extract_polyglot_symbols(content, p)
            docs_with_symbols.append(FileDoc(path=p, content=content, symbols=syms, imports=imps))
            docs_pure.append(FileDoc(path=p, content=content, symbols=[], imports=[]))

        num_docs = len(docs_with_symbols)
        doc_paths = [d.path for d in docs_with_symbols]
        path_to_idx = {d.path: i for i, d in enumerate(docs_with_symbols)}

        # Indices
        # 1. Decoupled BM25 (EXP-378 reference)
        bm25_decoupled = BM25Index(decouple_symbols=True).fit(docs_with_symbols)
        # 2. Coupled BM25 (EXP-380 drop-one)
        bm25_coupled = BM25Index(decouple_symbols=False).fit(docs_with_symbols)
        # 3. Pure BM25 without symbols (Candidate C)
        bm25_pure = BM25Index(decouple_symbols=True).fit(docs_pure)

        # Semantic Subword Index
        semantic_index = SubwordSemanticIndex().fit(docs_with_symbols)

        # Graph
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

        def eval_ranking(scores_vec, gold_files, hard_neg_files, budget_tokens=8000):
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
            m = sample_metrics(gold_files, ranked_chunks, context_budget=budget_tokens, hard_negative_files=hard_neg_files)

            hit1 = 1.0 if any(p in gold_set for p in ranked_paths[:1]) else 0.0
            hit5 = 1.0 if any(p in gold_set for p in ranked_paths[:5]) else 0.0
            hit10 = 1.0 if any(p in gold_set for p in ranked_paths[:10]) else 0.0
            hit20 = 1.0 if any(p in gold_set for p in ranked_paths[:20]) else 0.0

            r1 = recall_at(gold_set, ranked_paths, 1)
            r5 = recall_at(gold_set, ranked_paths, 5)
            r10 = recall_at(gold_set, ranked_paths, 10)
            r20 = recall_at(gold_set, ranked_paths, 20)

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

        # Language
        ext_counts = Counter(p.split(".")[-1].lower() for p in file_texts.keys() if "." in p)
        top_ext = ext_counts.most_common(1)[0][0] if ext_counts else "unknown"
        lang_map = {"py": "python", "rs": "rust", "go": "go", "ts": "typescript", "js": "javascript", "tsx": "typescript", "jsx": "javascript"}
        repo_lang = lang_map.get(top_ext, top_ext)

        for s in repo_samples:
            s_id = s["id"]
            gold = target_gold_files(s)
            hard_neg = hard_negative_files(s)
            q_text = query_text_for_eval(s)
            t_type = s["_subset_name"]

            per_query_jsonl_records[s_id]["query_id"] = s_id
            per_query_jsonl_records[s_id]["repo"] = repo
            per_query_jsonl_records[s_id]["task_type"] = t_type
            per_query_jsonl_records[s_id]["language"] = repo_lang
            per_query_jsonl_records[s_id]["gold_files"] = gold

            t_start = time.perf_counter()

            # Base scoring signals
            lex_decoup = bm25_decoupled.score(q_text)
            lex_coup = bm25_coupled.score(q_text)
            lex_pure = bm25_pure.score(q_text)
            sem = semantic_index.score(q_text)

            # Compute hub-normalized diffusion from decoupled seeds (reference)
            boost_hubnorm_decoup = np.zeros(num_docs, dtype=np.float32)
            boost_hubnorm_coup = np.zeros(num_docs, dtype=np.float32)
            boost_hubnorm_lex_only = np.zeros(num_docs, dtype=np.float32)

            if G.number_of_edges() > 0:
                # Combined decoupled hits
                hits_d = lex_decoup + sem
                if len(hits_d) > 0 and float(np.max(hits_d)) > 0:
                    top_seeds_d = np.argsort(hits_d)[::-1][:5]
                    for s_idx in top_seeds_d:
                        seed_p = doc_paths[s_idx]
                        seed_val = float(hits_d[s_idx])
                        if seed_val > 0 and seed_p in G:
                            for succ in G.successors(seed_p):
                                if succ in path_to_idx:
                                    n_idx = path_to_idx[succ]
                                    deg = max(1, G.in_degree(succ))
                                    boost_hubnorm_decoup[n_idx] = max(boost_hubnorm_decoup[n_idx], float(seed_val * 0.25 / np.sqrt(deg)))
                            for pred in G.predecessors(seed_p):
                                if pred in path_to_idx:
                                    n_idx = path_to_idx[pred]
                                    deg = max(1, G.out_degree(pred))
                                    boost_hubnorm_decoup[n_idx] = max(boost_hubnorm_decoup[n_idx], float(seed_val * 0.20 / np.sqrt(deg)))

                # Combined coupled hits (for EXP-380)
                hits_c = lex_coup + sem
                if len(hits_c) > 0 and float(np.max(hits_c)) > 0:
                    top_seeds_c = np.argsort(hits_c)[::-1][:5]
                    for s_idx in top_seeds_c:
                        seed_p = doc_paths[s_idx]
                        seed_val = float(hits_c[s_idx])
                        if seed_val > 0 and seed_p in G:
                            for succ in G.successors(seed_p):
                                if succ in path_to_idx:
                                    n_idx = path_to_idx[succ]
                                    deg = max(1, G.in_degree(succ))
                                    boost_hubnorm_coup[n_idx] = max(boost_hubnorm_coup[n_idx], float(seed_val * 0.25 / np.sqrt(deg)))
                            for pred in G.predecessors(seed_p):
                                if pred in path_to_idx:
                                    n_idx = path_to_idx[pred]
                                    deg = max(1, G.out_degree(pred))
                                    boost_hubnorm_coup[n_idx] = max(boost_hubnorm_coup[n_idx], float(seed_val * 0.20 / np.sqrt(deg)))

                # Lexical-only hits (for EXP-383)
                if len(lex_decoup) > 0 and float(np.max(lex_decoup)) > 0:
                    top_seeds_l = np.argsort(lex_decoup)[::-1][:5]
                    for s_idx in top_seeds_l:
                        seed_p = doc_paths[s_idx]
                        seed_val = float(lex_decoup[s_idx])
                        if seed_val > 0 and seed_p in G:
                            for succ in G.successors(seed_p):
                                if succ in path_to_idx:
                                    n_idx = path_to_idx[succ]
                                    deg = max(1, G.in_degree(succ))
                                    boost_hubnorm_lex_only[n_idx] = max(boost_hubnorm_lex_only[n_idx], float(seed_val * 0.25 / np.sqrt(deg)))
                            for pred in G.predecessors(seed_p):
                                if pred in path_to_idx:
                                    n_idx = path_to_idx[pred]
                                    deg = max(1, G.out_degree(pred))
                                    boost_hubnorm_lex_only[n_idx] = max(boost_hubnorm_lex_only[n_idx], float(seed_val * 0.20 / np.sqrt(deg)))

            # -------------------------------------------------------------
            # Configurations:
            # -------------------------------------------------------------
            # EXP-378 Reference:
            base_378 = (lex_decoup + sem) / 2.0
            base_378[is_doc_file] *= 0.5
            scores_378 = base_378 + 0.15 * boost_hubnorm_decoup

            # EXP-379: Restore PageRank into base score
            base_379 = (lex_decoup + sem + pagerank_scores) / 3.0
            base_379[is_doc_file] *= 0.5
            scores_379 = base_379 + 0.15 * boost_hubnorm_decoup

            # EXP-380: Restore Coupled BM25 length
            base_380 = (lex_coup + sem) / 2.0
            base_380[is_doc_file] *= 0.5
            scores_380 = base_380 + 0.15 * boost_hubnorm_coup

            # EXP-381: Remove Hub-Normalized Diffusion (No graph diffusion)
            scores_381 = base_378.copy()

            # EXP-382: Remove Documentation Filtering (No doc penalty)
            base_382 = (lex_decoup + sem) / 2.0
            scores_382 = base_382 + 0.15 * boost_hubnorm_decoup

            # EXP-383: Remove Subword Retrieval (Lexical only)
            base_383 = lex_decoup.copy()
            base_383[is_doc_file] *= 0.5
            scores_383 = base_383 + 0.15 * boost_hubnorm_lex_only

            # EXP-371: Candidate C Control
            base_371 = (lex_pure + sem + pagerank_scores) / 3.0
            base_371[is_doc_file] *= 0.5
            scores_371 = base_371

            evaluated_configs = [
                ("EXP-378", scores_378),
                ("EXP-379", scores_379),
                ("EXP-380", scores_380),
                ("EXP-381", scores_381),
                ("EXP-382", scores_382),
                ("EXP-383", scores_383),
                ("EXP-371", scores_371),
            ]

            elapsed_query_ms = (time.perf_counter() - t_start) * 1000.0

            for exp_id, sc in evaluated_configs:
                res = eval_ranking(sc, gold, hard_neg)
                res["latency_ms"] = elapsed_query_ms / len(evaluated_configs)
                res["query_id"] = s_id
                res["repo"] = repo
                res["task_type"] = t_type
                res["language"] = repo_lang
                res["experiment_id"] = exp_id
                res["gold_files"] = gold

                per_query_jsonl_records[s_id]["systems"][exp_id] = res

                for k in ["mrr", "r1", "r5", "r10", "r20", "hit1", "hit5", "hit10", "hit20", "bcy_4k", "bcy_8k", "bcy_16k", "coverage"]:
                    exp_summary[exp_id][k].append(res[k])
                exp_latencies[exp_id].append(res["latency_ms"])

        if corpus_idx % 5 == 0 or corpus_idx == total_corpora:
            print(f"Evaluated {corpus_idx}/{total_corpora} corpora ({len(per_query_jsonl_records)} queries processed)...", flush=True)

    # 1. Write PER_QUERY_RESULTS.jsonl
    out_jsonl = STAGE_DIR / "PER_QUERY_RESULTS.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for qid in sorted(per_query_jsonl_records.keys()):
            f.write(json.dumps(per_query_jsonl_records[qid]) + "\n")
    print(f"\nWrote full PER_QUERY_RESULTS.jsonl to {out_jsonl} ({len(per_query_jsonl_records)} query records).")

    # 2. Compute paired differences and bootstrap CIs vs EXP-378 reference
    rng = np.random.default_rng(42)
    repos_list = list(by_corpus.keys())
    num_repos = len(repos_list)
    n_boot = 10000

    repo_to_qids = defaultdict(list)
    for qid, q_data in per_query_jsonl_records.items():
        repo_to_qids[q_data["repo"]].append(qid)
    unique_repos = list(repo_to_qids.keys())
    num_clusters = len(unique_repos)

    print("\n" + "=" * 90)
    print("STAGE 3.7.1 COMPONENT ATTRIBUTION LEADERBOARD & DROP-ONE IMPACT (N=345 ARB v2 Samples)")
    print("=" * 90)
    print(f"{'Exp ID':<9} | {'System Name':<22} | {'MRR':<7} | {'R@5':<7} | {'R@10':<7} | {'R@20':<7} | {'Hit@20':<7} | {'Delta MRR vs 378':<17}")
    print("-" * 90)

    attribution_rows = []

    mrr_378_queries = np.array([per_query_jsonl_records[q]["systems"]["EXP-378"]["mrr"] for q in sorted(per_query_jsonl_records.keys())])
    all_q_sorted = sorted(per_query_jsonl_records.keys())

    for exp in experiments:
        eid = exp["id"]
        sm = exp_summary[eid]
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
        bcy8k_val = float(np.mean(sm["bcy_8k"]))
        lat_med = float(np.median(lats))
        lat_p95 = float(np.percentile(lats, 95))

        # Paired delta vs EXP-378
        mrr_cur_queries = np.array([per_query_jsonl_records[q]["systems"][eid]["mrr"] for q in all_q_sorted])
        diff_queries = mrr_cur_queries - mrr_378_queries
        mean_diff = float(np.mean(diff_queries))

        wins = int(np.sum(diff_queries > 1e-6))
        losses = int(np.sum(diff_queries < -1e-6))
        ties = int(np.sum(np.abs(diff_queries) <= 1e-6))

        # Cluster bootstrap CI for delta vs EXP-378
        boot_diffs = []
        for _ in range(n_boot):
            sampled_r_indices = rng.choice(num_clusters, size=num_clusters, replace=True)
            sampled_q_diffs = []
            for r_idx in sampled_r_indices:
                r_name = unique_repos[r_idx]
                for q in repo_to_qids[r_name]:
                    sampled_q_diffs.append(per_query_jsonl_records[q]["systems"][eid]["mrr"] - per_query_jsonl_records[q]["systems"]["EXP-378"]["mrr"])
            boot_diffs.append(np.mean(sampled_q_diffs))

        boot_diffs = np.array(boot_diffs)
        ci_lower = float(np.percentile(boot_diffs, 2.5))
        ci_upper = float(np.percentile(boot_diffs, 97.5))

        # Marginal impact description
        marginal_impact = f"{mean_diff:+.4f} [{ci_lower:+.4f}, {ci_upper:+.4f}]" if eid != "EXP-378" else "REFERENCE (0.0)"

        print(f"{eid:<9} | {exp['name']:<22} | {mrr_val:.4f}  | {r5_val:.4f}  | {r10_val:.4f}  | {r20_val:.4f}  | {h20_val:.4f}  | {marginal_impact}")

        attribution_rows.append({
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
            "bcy_at_8k": f"{bcy8k_val:.6f}",
            "delta_mrr_vs_exp378": f"{mean_diff:+.6f}",
            "ci_lower_95": f"{ci_lower:+.6f}",
            "ci_upper_95": f"{ci_upper:+.6f}",
            "wins_vs_378": wins,
            "ties_vs_378": ties,
            "losses_vs_378": losses,
            "candidate_coverage": f"{cov_val:.6f}",
            "latency_median_ms": f"{lat_med:.2f}",
            "latency_p95_ms": f"{lat_p95:.2f}",
        })

    # Write COMPONENT_ATTRIBUTION_RESULTS.csv
    out_attr_csv = STAGE_DIR / "COMPONENT_ATTRIBUTION_RESULTS.csv"
    with open(out_attr_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(attribution_rows[0].keys()))
        writer.writeheader()
        writer.writerows(attribution_rows)
    print(f"\nSaved COMPONENT_ATTRIBUTION_RESULTS.csv to {out_attr_csv}")

    # Write EXPERIMENT_REGISTRY.jsonl
    out_reg = STAGE_DIR / "EXPERIMENT_REGISTRY.jsonl"
    with open(out_reg, "w", encoding="utf-8") as f:
        for r_row in attribution_rows:
            reg_entry = {
                "experiment_id": r_row["experiment_id"],
                "system_name": r_row["system_name"],
                "stage": "Stage 3.7.1",
                "commit": "f61c6be",
                "branch": "research/stage3_7",
                "benchmark": "ARB v2 Unconstrained (N=345)",
                "description": r_row["description"],
                "metrics": {
                    "mrr": float(r_row["mrr"]),
                    "recall_at_5": float(r_row["recall_at_5"]),
                    "recall_at_10": float(r_row["recall_at_10"]),
                    "recall_at_20": float(r_row["recall_at_20"]),
                    "hit_at_20": float(r_row["hit_at_20"]),
                    "bcy_at_8k": float(r_row["bcy_at_8k"]),
                    "delta_mrr_vs_exp378": float(r_row["delta_mrr_vs_exp378"]),
                    "ci_95_cluster": [float(r_row["ci_lower_95"]), float(r_row["ci_upper_95"])],
                }
            }
            f.write(json.dumps(reg_entry) + "\n")
    print(f"Saved EXPERIMENT_REGISTRY.jsonl to {out_reg}")


if __name__ == "__main__":
    run_attribution_experiments()

