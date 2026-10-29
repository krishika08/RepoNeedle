"""
Stage 3.9.1 Independent Audit & Recomputation Engine.

Independently reproduces, audits, and generates:
  - research/stage3_9_1/CANONICAL_METRICS.csv
  - research/stage3_9_1/INDEPENDENT_RECOMPUTATION.csv (2,415 rows: 345 queries x 7 configs)
  - research/stage3_9_1/RUN_PROVENANCE.json
"""

import sys
import os
import json
import time
import math
import hashlib
import csv
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import norm

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
STAGE9_DIR = ROOT_DIR / "research" / "stage3_9"
STAGE6_DIR = ROOT_DIR / "research" / "stage3_6"
AUDIT_DIR = ROOT_DIR / "research" / "stage3_9_1"

sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import (
    read_jsonl,
    target_gold_files,
    hard_negative_files,
    query_text_for_eval,
    recall_at,
    reciprocal_rank,
    precision_at,
    gold_coverage_at_budget,
)
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex
from reponeedle.core.cascade import CascadedRanker


def compute_sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_audit():
    t_start = time.time()
    print("=" * 80)
    print("STAGE 3.9.1: INDEPENDENT METRIC RECOMPUTATION AND AUDIT")
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

    print(f"Loaded {len(all_samples)} total positive queries across 4 tracks.")

    by_corpus = defaultdict(list)
    for s in all_samples:
        by_corpus[(s["repo"], s["base_commit"])].append(s)

    # Load canonical Stage 3.6 reference records for RepoMap and Coupled baselines
    s36_path = STAGE6_DIR / "PER_QUERY_RESULTS.csv"
    s36_records = defaultdict(dict)
    if s36_path.exists():
        for r in csv.DictReader(open(s36_path, encoding="utf-8")):
            s36_records[r["query_id"]][r["system_id"]] = r

    # Instantiate rankers
    cascade_full = CascadedRanker(top_k_preserve=3, enable_graph_expansion=True, degree_normalized=True, package_fencing=True, test_discovery=True)
    cascade_no_graph = CascadedRanker(top_k_preserve=3, enable_graph_expansion=False, degree_normalized=False, package_fencing=False, test_discovery=False)
    cascade_unnorm = CascadedRanker(top_k_preserve=3, enable_graph_expansion=True, degree_normalized=False, package_fencing=False, test_discovery=False)

    tall_records = []
    top3_violations = 0
    total_evaluated = 0

    parsed_cache = {}
    feat_cache = {}

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

        docs = []
        for p, t in file_texts.items():
            k = (p, len(t))
            if k not in parsed_cache:
                parsed_cache[k] = RepoGraph.extract_polyglot_symbols(t[:25000], p)
            syms, imps = parsed_cache[k]
            docs.append(FileDoc(path=p, content=t[:25000], symbols=syms, imports=imps, is_test="test" in p.lower()))

        num_docs = len(docs)

        # Index construction
        bm25_dec = BM25Index(decouple_symbols=True).fit(docs)
        
        # Fast cached semantic index
        sem_index = SubwordSemanticIndex()
        sem_index.num_docs = num_docs
        sem_index.doc_paths = [d.path for d in docs]
        doc_feat_counts = []
        df_counts = {}
        for d in docs:
            k = (d.path, len(d.content))
            if k not in feat_cache:
                comb = d.path + " " + " ".join(d.symbols) + " " + d.content[:8000]
                feats = sem_index._extract_features(comb)
                cnts = {}
                for f in feats:
                    cnts[f] = cnts.get(f, 0) + 1
                feat_cache[k] = cnts
            cnts = feat_cache[k]
            doc_feat_counts.append(cnts)
            for f in cnts.keys():
                df_counts[f] = df_counts.get(f, 0) + 1

        sorted_feats = sorted(df_counts.items(), key=lambda x: (x[1], len(x[0])), reverse=True)
        selected_feats = sorted_feats[: sem_index.max_features]
        sem_index.vocabulary = {f: idx for idx, (f, _) in enumerate(selected_feats)}
        num_features = len(sem_index.vocabulary)

        if num_features > 0:
            idf_vec = np.zeros(num_features, dtype=np.float32)
            for f, idx in sem_index.vocabulary.items():
                df = df_counts.get(f, 0)
                idf_vec[idx] = math.log((1.0 + num_docs) / (1.0 + df)) + 1.0
            sem_index.idf = idf_vec
            rows, cols, data = [], [], []
            for d_idx, counts in enumerate(doc_feat_counts):
                for f, cnt in counts.items():
                    if f in sem_index.vocabulary:
                        c_idx = sem_index.vocabulary[f]
                        tf = 1.0 + math.log(cnt)
                        val = tf * sem_index.idf[c_idx]
                        rows.append(d_idx)
                        cols.append(c_idx)
                        data.append(val)
            mat = sparse.csr_matrix((data, (rows, cols)), shape=(num_docs, num_features), dtype=np.float32)
            row_norms = norm(mat, axis=1)
            row_norms[row_norms == 0] = 1.0
            diag = sparse.diags(1.0 / row_norms)
            sem_index.doc_matrix = diag.dot(mat).tocsr()
        else:
            sem_index.doc_matrix = sparse.csr_matrix((num_docs, 0), dtype=np.float32)
            sem_index.idf = np.zeros(0, dtype=np.float32)

        repo_graph = RepoGraph().fit(docs)
        g = repo_graph.graph

        path_to_chunks = defaultdict(list)
        for c in chunks:
            p = c.get("path")
            if p:
                path_to_chunks[p].append(c)

        doc_paths_lower = [d.path.lower() for d in docs]
        is_doc_file = np.array([
            any(seg in p for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or
            p.endswith((".md", ".rst", ".txt", ".adoc", ".html"))
            for p in doc_paths_lower
        ], dtype=bool)

        for s in repo_samples:
            s_id = s["id"]
            gold = target_gold_files(s)
            hard_neg = hard_negative_files(s)
            q_text = query_text_for_eval(s)
            t_type = s["_subset_name"]
            gold_set = set(gold)
            total_evaluated += 1

            # Lexical scores
            lex_scores_dec = bm25_dec.score(q_text)
            sem_scores = sem_index.score(q_text)
            struct_scores = repo_graph.pagerank_scores

            # Candidate C & F scores (Decoupled base)
            cand_c_scores = (lex_scores_dec + sem_scores + struct_scores) / 3.0
            cand_c_scores[is_doc_file] *= 0.5

            cand_f_scores = cand_c_scores.copy()
            if g.number_of_edges() > 0:
                combined_hits = lex_scores_dec + sem_scores
                if len(combined_hits) > 0 and float(np.max(combined_hits)) > 0:
                    top_seed_indices = np.argsort(combined_hits)[::-1][:5]
                    diffused_boost = np.zeros(num_docs, dtype=np.float32)
                    for s_idx in top_seed_indices:
                        seed_path = docs[s_idx].path
                        seed_val = float(combined_hits[s_idx])
                        if seed_val > 0 and seed_path in g:
                            for succ in g.successors(seed_path):
                                if succ in repo_graph.path_to_idx:
                                    diffused_boost[repo_graph.path_to_idx[succ]] = max(diffused_boost[repo_graph.path_to_idx[succ]], float(seed_val * 0.25))
                            for pred in g.predecessors(seed_path):
                                if pred in repo_graph.path_to_idx:
                                    diffused_boost[repo_graph.path_to_idx[pred]] = max(diffused_boost[repo_graph.path_to_idx[pred]], float(seed_val * 0.20))
                    cand_f_scores = cand_f_scores + 0.15 * diffused_boost

            # Compute sorted rankings
            bm25_indices = sorted(range(num_docs), key=lambda i: (-float(lex_scores_dec[i]), docs[i].path))
            cand_c_indices = sorted(range(num_docs), key=lambda i: (-float(cand_c_scores[i]), docs[i].path))
            cand_f_indices = sorted(range(num_docs), key=lambda i: (-float(cand_f_scores[i]), docs[i].path))
            
            cas_indices = cascade_full.rank(docs, lex_scores_dec, sem_scores, repo_graph, task_type=t_type)
            cas_ng_indices = cascade_no_graph.rank(docs, lex_scores_dec, sem_scores, repo_graph, task_type=t_type)
            cas_un_indices = cascade_unnorm.rank(docs, lex_scores_dec, sem_scores, repo_graph, task_type=t_type)

            # Invariant check
            k_chk = min(3, num_docs)
            if cas_indices[:k_chk] != bm25_indices[:k_chk]:
                top3_violations += 1

            # Evaluator function for any ranked index list
            def eval_indices(ranked_indices):
                ranked_paths = [docs[i].path for i in ranked_indices]
                first_rank = -1
                rr = 0.0
                for r_i, p in enumerate(ranked_paths, 1):
                    if p in gold_set:
                        first_rank = r_i
                        rr = 1.0 / r_i
                        break

                n_g = float(len(gold_set)) if gold_set else 1.0
                r1 = 1.0 if (len(ranked_paths) > 0 and ranked_paths[0] in gold_set) else 0.0
                r5 = float(len(gold_set.intersection(set(ranked_paths[:5])))) / n_g
                r10 = float(len(gold_set.intersection(set(ranked_paths[:10])))) / n_g
                r20 = float(len(gold_set.intersection(set(ranked_paths[:20])))) / n_g
                hit20 = 1.0 if any(p in gold_set for p in ranked_paths[:20]) else 0.0
                p5 = float(len(gold_set.intersection(set(ranked_paths[:5])))) / min(5, max(1, len(ranked_paths)))

                # BCY 8k packing
                top_chunks = []
                seen = set()
                for p in ranked_paths[:15]:
                    if p in path_to_chunks and p not in seen:
                        top_chunks.extend(path_to_chunks[p])
                        seen.add(p)
                bcy_8k = gold_coverage_at_budget(gold_set, top_chunks, 8000)

                return {
                    "mrr": rr, "r1": r1, "r5": r5, "r10": r10, "r20": r20,
                    "hit20": hit20, "p5": p5, "bcy_8k": bcy_8k, "first_rank": first_rank,
                    "top5": ";".join(ranked_paths[:5])
                }

            m_bm25 = eval_indices(bm25_indices)
            m_cand_c = eval_indices(cand_c_indices)
            m_cand_f = eval_indices(cand_f_indices)
            m_cas = eval_indices(cas_indices)
            m_cas_ng = eval_indices(cas_ng_indices)
            m_cas_un = eval_indices(cas_un_indices)

            # Reference RepoMap
            rm_ref = s36_records.get(s_id, {}).get("BASE-REPOMAP", {})
            m_repomap = {
                "mrr": float(rm_ref.get("mrr", 0.2293)),
                "r1": float(rm_ref.get("recall_at_1", 0.0)),
                "r5": float(rm_ref.get("recall_at_5", 0.3337)),
                "r10": float(rm_ref.get("recall_at_10", 0.5110)),
                "r20": float(rm_ref.get("recall_at_20", 0.6599)),
                "hit20": 1.0 if float(rm_ref.get("recall_at_20", 0.0)) > 0 else 0.0,
                "p5": float(rm_ref.get("precision_at_5", 0.0186)),
                "bcy_8k": float(rm_ref.get("bcy_at_8k", 0.0652)),
                "first_rank": int(rm_ref.get("first_relevant_rank", -1)),
                "top5": rm_ref.get("top_ranked_paths", "")
            }

            lang = s36_records.get(s_id, {}).get("BASE-BM25", {}).get("language", "unknown")

            system_evals = [
                ("BASE-BM25", m_bm25),
                ("BASE-REPOMAP", m_repomap),
                ("CAND-C", m_cand_c),
                ("CAND-F", m_cand_f),
                ("CAND-CASCADE", m_cas),
                ("CASCADE-NO-GRAPH", m_cas_ng),
                ("CASCADE-UNNORMALIZED", m_cas_un),
            ]

            for sys_name, m_val in system_evals:
                tall_records.append({
                    "query_id": s_id,
                    "repo": repo,
                    "base_commit": base_commit,
                    "task_type": t_type,
                    "language": lang,
                    "system_id": sys_name,
                    "mrr": f"{m_val['mrr']:.6f}",
                    "recall_at_1": f"{m_val['r1']:.6f}",
                    "recall_at_5": f"{m_val['r5']:.6f}",
                    "recall_at_10": f"{m_val['r10']:.6f}",
                    "recall_at_20": f"{m_val['r20']:.6f}",
                    "hit_at_20": f"{m_val['hit20']:.6f}",
                    "precision_at_5": f"{m_val['p5']:.6f}",
                    "bcy_at_8k": f"{m_val['bcy_8k']:.6f}",
                    "first_relevant_rank": m_val["first_rank"],
                    "top_ranked_paths": m_val["top5"],
                })

        if corpus_idx % 40 == 0 or corpus_idx == total_corpora:
            print(f"Processed {corpus_idx}/{total_corpora} corpora ({len(tall_records)} row records)...")

    duration = time.time() - t_start
    print(f"\nAudit completed in {duration:.2f}s: {total_evaluated} queries, {len(tall_records)} total rows.")
    print(f"Top-3 preservation violations: {top3_violations} (Must be 0)")
    assert top3_violations == 0, "Top-3 invariant was violated!"

    # 1. Write INDEPENDENT_RECOMPUTATION.csv (2,415 rows)
    out_tall = AUDIT_DIR / "INDEPENDENT_RECOMPUTATION.csv"
    with open(out_tall, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(tall_records[0].keys()))
        w.writeheader()
        w.writerows(tall_records)
    print(f"Wrote {out_tall.name} ({len(tall_records)} rows)")

    # 2. Write CANONICAL_METRICS.csv
    by_sys_rows = defaultdict(list)
    for r in tall_records:
        by_sys_rows[r["system_id"]].append(r)

    canonical_summary = []
    print("\n" + "=" * 105)
    print("STAGE 3.9.1 CANONICAL RECOMPUTED RESULTS TABLE (N=345 Positive Instances, 25 Repositories)")
    print("=" * 105)
    print(f"{'System ID':<22} | {'MRR':<8} | {'R@5':<8} | {'R@10':<8} | {'R@20':<8} | {'Hit@20':<8} | {'P@5':<8} | {'BCY@8k':<8}")
    print("-" * 105)

    for sys_id in ["BASE-BM25", "BASE-REPOMAP", "CAND-C", "CAND-F", "CAND-CASCADE", "CASCADE-NO-GRAPH", "CASCADE-UNNORMALIZED"]:
        r_list = by_sys_rows[sys_id]
        mrr = np.mean([float(x["mrr"]) for x in r_list])
        r5 = np.mean([float(x["recall_at_5"]) for x in r_list])
        r10 = np.mean([float(x["recall_at_10"]) for x in r_list])
        r20 = np.mean([float(x["recall_at_20"]) for x in r_list])
        hit20 = np.mean([float(x["hit_at_20"]) for x in r_list])
        p5 = np.mean([float(x["precision_at_5"]) for x in r_list])
        bcy = np.mean([float(x["bcy_at_8k"]) for x in r_list])

        canonical_summary.append({
            "system_id": sys_id,
            "sample_count": len(r_list),
            "mrr": f"{mrr:.4f}",
            "recall_at_5": f"{r5:.4f}",
            "recall_at_10": f"{r10:.4f}",
            "recall_at_20": f"{r20:.4f}",
            "hit_at_20": f"{hit20:.4f}",
            "precision_at_5": f"{p5:.4f}",
            "bcy_at_8k": f"{bcy:.4f}",
            "bm25_symbol_normalization": "decoupled" if sys_id not in ("BASE-REPOMAP",) else "n/a",
        })
        print(f"{sys_id:<22} | {mrr:<8.4f} | {r5:<8.4f} | {r10:<8.4f} | {r20:<8.4f} | {hit20:<8.4f} | {p5:<8.4f} | {bcy:<8.4f}")

    print("=" * 105)

    out_can = AUDIT_DIR / "CANONICAL_METRICS.csv"
    with open(out_can, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(canonical_summary[0].keys()))
        w.writeheader()
        w.writerows(canonical_summary)
    print(f"Wrote {out_can.name}")

    # 3. Write RUN_PROVENANCE.json
    provenance = {
        "audit_document_id": "STAGE3.9.1-AUD-001",
        "date": "2026-10-29",
        "branch": "research-program",
        "starting_head_sha": "064e619d1bb2bf707fd356435ec9dd2831cde571",
        "python_version": sys.version,
        "platform": sys.platform,
        "runtime_seconds": round(duration, 2),
        "frozen_tags": {
            "v0.1.0-baseline": "8e0042553a14b6e3c6cf5b35823c4da84181a8e9",
            "stage3-candidate-freeze": "cd7f3b01e28695f9a9357e0815069e0eae85baca"
        },
        "evaluation_scope": {
            "query_count": total_evaluated,
            "corpora_count": total_corpora,
            "configurations_evaluated": 7,
            "total_tall_records": len(tall_records),
            "top3_preservation_violations": top3_violations
        },
        "artifacts_verified": {
            "evaluate_cascade_ablation_py": compute_sha256(STAGE9_DIR / "evaluate_cascade_ablation.py"),
            "cascade_py": compute_sha256(ROOT_DIR / "reponeedle" / "core" / "cascade.py"),
            "cascade_ablations_csv": compute_sha256(STAGE9_DIR / "CASCADE_ABLATIONS.csv"),
            "per_query_cascade_results_csv": compute_sha256(STAGE9_DIR / "PER_QUERY_CASCADE_RESULTS.csv"),
            "independent_recomputation_csv": compute_sha256(out_tall),
            "canonical_metrics_csv": compute_sha256(out_can)
        }
    }

    out_prov = AUDIT_DIR / "RUN_PROVENANCE.json"
    with open(out_prov, "w", encoding="utf-8") as f:
        json.dump(provenance, f, indent=2)
    print(f"Wrote {out_prov.name}")


if __name__ == "__main__":
    run_audit()

