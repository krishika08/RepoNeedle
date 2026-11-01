"""
Stage 3.8: Complete Experiment Evaluator & Repository-Level Analyzer.
Evaluates the 5 registered configurations:
  - EXP-384: Exact EXP-378 reproduction
  - EXP-385: Query-conditioned backward propagation
  - EXP-386: Query-conditioned edge-type-aware propagation
  - EXP-387: Degree-aware query-conditioned propagation (leapfrog dampened)
  - EXP-388: Best individually supported combined configuration (Edge-Gated + Degree-Attenuated)

Outputs:
  - research/stage3_8/RANKING_RESULTS.csv
  - research/stage3_8/PER_QUERY_RESULTS.jsonl
  - research/stage3_8/EXPERIMENT_REGISTRY.jsonl
  - research/stage3_8/REPOSITORY_LEVEL_RESULTS.csv
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
STAGE_DIR = ROOT_DIR / "research" / "stage3_8"
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


def run_stage3_8_evaluation():
    print("=" * 80)
    print("STAGE 3.8: QUERY-CONDITIONED STRUCTURAL RETRIEVAL EVALUATION")
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
                raise ValueError(f"Duplicate query ID detected: {qid}")
            seen_qids.add(qid)
            r["_subset_name"] = sname
            all_samples.append(r)

    print(f"Loaded and verified {len(all_samples)} positive samples across 4 tracks.")

    by_corpus = defaultdict(list)
    for s in all_samples:
        by_corpus[(s["repo"], s["base_commit"])].append(s)

    experiments = [
        {
            "id": "EXP-384",
            "name": "EXP-384-REF-REPRO",
            "desc": "Exact EXP-378 reproduction (Decoupled BM25 + Subword + DocFilter + HubNorm Diffusion)",
        },
        {
            "id": "EXP-385",
            "name": "EXP-385-QUERY-AFFINITY",
            "desc": "Query-conditioned backward propagation (affine scaling by predecessor query relevance)",
        },
        {
            "id": "EXP-386",
            "name": "EXP-386-EDGE-TYPE-GATED",
            "desc": "Query-conditioned edge-type-aware propagation (attenuates test predecessors for code queries)",
        },
        {
            "id": "EXP-387",
            "name": "EXP-387-DEGREE-DAMPENED",
            "desc": "Degree-aware query-conditioned propagation (leapfrog margin dampening)",
        },
        {
            "id": "EXP-388",
            "name": "EXP-388-COMBINED-QC",
            "desc": "Best combined query-conditioned propagation (Edge-Gated + Degree-Attenuated)",
        },
    ]

    per_query_jsonl_records = defaultdict(lambda: {"systems": {}})
    exp_summary = defaultdict(lambda: defaultdict(list))
    exp_latencies = defaultdict(list)
    repo_metrics = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

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

        docs = []
        for p, t in file_texts.items():
            content = t[:25000]
            syms, imps = RepoGraph.extract_polyglot_symbols(content, p)
            docs.append(FileDoc(path=p, content=content, symbols=syms, imports=imps))

        num_docs = len(docs)
        doc_paths = [d.path for d in docs]
        path_to_idx = {d.path: i for i, d in enumerate(docs)}

        bm25 = BM25Index(decouple_symbols=True).fit(docs)
        semantic_index = SubwordSemanticIndex().fit(docs)
        rg = RepoGraph().fit(docs)
        G = rg.graph

        doc_paths_lower = [p.lower() for p in doc_paths]
        is_doc_file = np.array([
            any(seg in p for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or
            p.endswith((".md", ".rst", ".txt", ".adoc", ".html"))
            for p in doc_paths_lower
        ], dtype=bool)

        is_test_file = np.array([
            "test" in p or "spec" in p or p.startswith("tests/")
            for p in doc_paths_lower
        ], dtype=bool)

        is_manifest_file = np.array([
            p.endswith(("cargo.toml", "pyproject.toml", "package.json", "go.mod", "setup.py"))
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

            lex = bm25.score(q_text)
            sm = semantic_index.score(q_text)

            base = (lex + sm) / 2.0
            base[is_doc_file] *= 0.5

            hits = lex + sm
            max_hit = float(np.max(hits)) if len(hits) > 0 else 1.0
            if max_hit == 0.0:
                max_hit = 1.0

            boost_384 = np.zeros(num_docs, dtype=np.float32)
            boost_385 = np.zeros(num_docs, dtype=np.float32)
            boost_386 = np.zeros(num_docs, dtype=np.float32)
            boost_387 = np.zeros(num_docs, dtype=np.float32)
            boost_388 = np.zeros(num_docs, dtype=np.float32)

            q_lower = q_text.lower()
            query_is_test_seeking = ("test" in q_lower or "assert" in q_lower or "spec" in q_lower) and t_type != "trace2code"

            if G.number_of_edges() > 0 and len(hits) > 0 and float(np.max(hits)) > 0:
                top_seeds = np.argsort(hits)[::-1][:5]
                for s_idx in top_seeds:
                    sp = doc_paths[s_idx]
                    sv = float(hits[s_idx])
                    if sv <= 0 or sp not in G:
                        continue

                    # Forward: seed -> successors
                    for succ in G.successors(sp):
                        if succ in path_to_idx:
                            n_idx = path_to_idx[succ]
                            in_deg = max(1, G.in_degree(succ))
                            fwd_raw = float(sv * 0.25 / np.sqrt(in_deg))
                            boost_384[n_idx] = max(boost_384[n_idx], fwd_raw)

                    # Backward: predecessors -> seed
                    for pred in G.predecessors(sp):
                        if pred in path_to_idx:
                            n_idx = path_to_idx[pred]
                            out_deg = max(1, G.out_degree(pred))
                            bwd_raw = float(sv * 0.20 / np.sqrt(out_deg))
                            boost_384[n_idx] = max(boost_384[n_idx], bwd_raw)

                            # EXP-385: Query affinity
                            pred_affinity = float(hits[n_idx]) / max_hit
                            bwd_385 = bwd_raw * (0.20 + 0.80 * pred_affinity)
                            boost_385[n_idx] = max(boost_385[n_idx], bwd_385)

                            # EXP-386: Edge-type-aware gating
                            edge_mult = 1.0
                            if is_manifest_file[n_idx]:
                                edge_mult = 0.05
                            elif not query_is_test_seeking and is_test_file[n_idx] and not is_test_file[s_idx]:
                                edge_mult = 0.15 # Suppress test predecessor for code query
                            elif query_is_test_seeking and is_test_file[n_idx]:
                                edge_mult = 1.25 # Enhance test predecessor for test query
                            bwd_386 = bwd_raw * edge_mult
                            boost_386[n_idx] = max(boost_386[n_idx], bwd_386)

                            # EXP-387: Degree-aware leapfrog margin dampening
                            margin = max(0.0, float(base[s_idx] - base[n_idx]))
                            bwd_387 = min(bwd_raw, margin)
                            boost_387[n_idx] = max(boost_387[n_idx], bwd_387)

                            # EXP-388: Edge-type gating with query affinity and degree margin dampening
                            bwd_388 = min(bwd_raw * (0.20 + 0.80 * pred_affinity) * edge_mult, margin)
                            boost_388[n_idx] = max(boost_388[n_idx], bwd_388)

            configs = [
                ("EXP-384", base + 0.15 * boost_384),
                ("EXP-385", base + 0.15 * boost_385),
                ("EXP-386", base + 0.15 * boost_386),
                ("EXP-387", base + 0.15 * boost_387),
                ("EXP-388", base + 0.15 * boost_388),
            ]

            elapsed_query_ms = (time.perf_counter() - t_start) * 1000.0

            for exp_id, sc_vec in configs:
                res = eval_ranking(sc_vec, gold, hard_neg)
                res["latency_ms"] = elapsed_query_ms / len(configs)
                res["query_id"] = s_id
                res["repo"] = repo
                res["task_type"] = t_type
                res["language"] = repo_lang
                res["experiment_id"] = exp_id
                res["gold_files"] = gold

                per_query_jsonl_records[s_id]["systems"][exp_id] = res

                for k in ["mrr", "r1", "r5", "r10", "r20", "hit1", "hit5", "hit10", "hit20", "bcy_4k", "bcy_8k", "bcy_16k", "coverage"]:
                    exp_summary[exp_id][k].append(res[k])
                    repo_metrics[repo][exp_id][k].append(res[k])
                exp_latencies[exp_id].append(res["latency_ms"])

        if corpus_idx % 5 == 0 or corpus_idx == total_corpora:
            print(f"Evaluated {corpus_idx}/{total_corpora} corpora ({len(per_query_jsonl_records)} queries processed)...", flush=True)

    # 1. Write PER_QUERY_RESULTS.jsonl
    out_jsonl = STAGE_DIR / "PER_QUERY_RESULTS.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for qid in sorted(per_query_jsonl_records.keys()):
            f.write(json.dumps(per_query_jsonl_records[qid]) + "\n")
    print(f"\nWrote full PER_QUERY_RESULTS.jsonl to {out_jsonl} ({len(per_query_jsonl_records)} records).")

    # 2. Summary Leaderboard and RANKING_RESULTS.csv
    print("\n" + "=" * 90)
    print("STAGE 3.8 CANONICAL SUMMARY LEADERBOARD (N=345 ARB v2 Samples)")
    print("=" * 90)
    print(f"{'Exp ID':<9} | {'System Name':<25} | {'MRR':<7} | {'R@1':<7} | {'R@5':<7} | {'R@10':<7} | {'R@20':<7} | {'Hit@20':<7} | {'BCY@8k':<7}")
    print("-" * 90)

    ranking_rows = []
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
        bcy4 = float(np.mean(sm["bcy_4k"]))
        bcy8 = float(np.mean(sm["bcy_8k"]))
        bcy16 = float(np.mean(sm["bcy_16k"]))
        lat_med = float(np.median(lats))
        lat_p95 = float(np.percentile(lats, 95))

        print(f"{eid:<9} | {exp['name']:<25} | {mrr_val:.4f}  | {r1_val:.4f}  | {r5_val:.4f}  | {r10_val:.4f}  | {r20_val:.4f}  | {h20_val:.4f}  | {bcy8:.4f}")

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
            "bcy_at_4k": f"{bcy4:.6f}",
            "bcy_at_8k": f"{bcy8:.6f}",
            "bcy_at_16k": f"{bcy16:.6f}",
            "latency_median_ms": f"{lat_med:.2f}",
            "latency_p95_ms": f"{lat_p95:.2f}",
        })

    out_rank_csv = STAGE_DIR / "RANKING_RESULTS.csv"
    with open(out_rank_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(ranking_rows[0].keys()))
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
                "stage": "Stage 3.8",
                "commit": "f61c6be",
                "branch": "research/stage3_8",
                "benchmark": "ARB v2 Unconstrained (N=345)",
                "description": r_row["description"],
                "metrics": {
                    "mrr": float(r_row["mrr"]),
                    "recall_at_1": float(r_row["recall_at_1"]),
                    "recall_at_5": float(r_row["recall_at_5"]),
                    "recall_at_10": float(r_row["recall_at_10"]),
                    "recall_at_20": float(r_row["recall_at_20"]),
                    "hit_at_20": float(r_row["hit_at_20"]),
                    "bcy_at_8k": float(r_row["bcy_at_8k"]),
                }
            }
            f.write(json.dumps(reg_entry) + "\n")
    print(f"Saved EXPERIMENT_REGISTRY.jsonl to {out_reg_jsonl}")

    # 4. Write REPOSITORY_LEVEL_RESULTS.csv (Reporting all 25 repositories individually)
    repo_rows = []
    for r_name in sorted(repo_metrics.keys()):
        num_q = len(repo_metrics[r_name]["EXP-384"]["mrr"])
        mrr_384 = float(np.mean(repo_metrics[r_name]["EXP-384"]["mrr"]))
        mrr_386 = float(np.mean(repo_metrics[r_name]["EXP-386"]["mrr"]))
        r20_384 = float(np.mean(repo_metrics[r_name]["EXP-384"]["r20"]))
        r20_386 = float(np.mean(repo_metrics[r_name]["EXP-386"]["r20"]))
        delta_mrr = mrr_386 - mrr_384
        delta_r20 = r20_386 - r20_384

        repo_rows.append({
            "repo": r_name,
            "query_count": num_q,
            "mrr_exp384_ref": f"{mrr_384:.4f}",
            "mrr_exp386_edge_gated": f"{mrr_386:.4f}",
            "delta_mrr": f"{delta_mrr:+.4f}",
            "r20_exp384_ref": f"{r20_384:.4f}",
            "r20_exp386_edge_gated": f"{r20_386:.4f}",
            "delta_r20": f"{delta_r20:+.4f}",
        })

    out_repo_csv = STAGE_DIR / "REPOSITORY_LEVEL_RESULTS.csv"
    with open(out_repo_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(repo_rows[0].keys()))
        writer.writeheader()
        writer.writerows(repo_rows)
    print(f"Saved REPOSITORY_LEVEL_RESULTS.csv to {out_repo_csv} ({len(repo_rows)} repositories).")


if __name__ == "__main__":
    run_stage3_8_evaluation()
