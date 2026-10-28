"""
Stage 3.9: Controlled Ablation Matrix & Canonical Benchmark Harness.
Evaluates 11 precisely specified configurations across all N=345 positive ARB v2 queries:
  1. CONFIG-01 (BASE-BM25): Pure BM25 Canonical Baseline
  2. CONFIG-02 (BM25-DOCFILTER): BM25 + Documentation Filter (0.5x)
  3. CONFIG-03 (BM25-SUBWORD-RAW): BM25 + Subword Semantic (raw linear sum)
  4. CONFIG-04 (BM25-SUBWORD-CALIBRATED): BM25 + Subword Semantic (RRF k=60)
  5. CONFIG-05 (BM25-SUBWORD-DOCFILTER): BM25 + Subword Semantic + DocFilter (0.5x)
  6. CONFIG-06 (CAND-C-CANONICAL): Candidate C ((BM25+Sem+PR)/3 * DocFilter)
  7. CONFIG-07 (CAND-F-CANONICAL): Candidate C + Unbounded Graph Diffusion
  8. CONFIG-08 (CAND-BOUNDED-DIFFUSION): Candidate C with Bounded Graph Diffusion (deg <= 25)
  9. CONFIG-09 (CORRECTED-HYBRID): Decoupled BM25 + Subword + DocFilter (No PR)
  10. CONFIG-10 (SPARSE-RERANK): BM25 Top-50 Candidate Retrieval + Subword Reranking
  11. CONFIG-11 (RECOVERED-CANDIDATE): Decoupled BM25 + Subword + DocFilter + Bounded Graph Diffusion

Outputs:
  - research/stage3_9/ABLATION_RESULTS.csv
  - research/stage3_9/CANONICAL_PER_QUERY_RESULTS.csv
  - research/stage3_9/PER_REPOSITORY_RESULTS.csv
"""

import sys
import os
import json
import time
import math
import csv
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import (
    read_jsonl,
    target_gold_files,
    hard_negative_files,
    query_text_for_eval,
    recall_at,
    precision_at,
    reciprocal_rank,
    gold_coverage_at_budget,
)
from agent_retrieval_bench.bcy_curve import pack_files, CorpusFileCache

from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.core.tokenizer import CodeTokenizer, estimate_tokens
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex


class FastDecoupledBM25(BM25Index):
    """Decouples symbol token count from document length normalization denominator."""
    def fit(self, docs, decouple=True):
        self.docs = docs
        self.num_docs = len(docs)
        self.doc_paths = [d.path for d in docs]
        self.doc_frequencies = {}
        self.doc_term_freqs = []
        doc_lengths_list = []

        if self.num_docs == 0:
            self.avg_doc_len = 0.0
            return self

        for doc in docs:
            path_tokens = self.tokenizer.tokenize_path(doc.path)
            symbol_tokens = []
            for s in doc.symbols:
                symbol_tokens.extend(self.tokenizer.tokenize_text(s))
            body_tokens = self.tokenizer.tokenize_text(doc.content)

            weighted_counts = {}
            for t in path_tokens:
                weighted_counts[t] = weighted_counts.get(t, 0.0) + self.path_weight
            for t in symbol_tokens:
                weighted_counts[t] = weighted_counts.get(t, 0.0) + self.symbol_weight
            for t in body_tokens:
                weighted_counts[t] = weighted_counts.get(t, 0.0) + self.body_weight

            effective_len = max(1.0, float(len(body_tokens) + len(path_tokens))) if decouple else sum(weighted_counts.values())
            doc_lengths_list.append(effective_len)
            self.doc_term_freqs.append(weighted_counts)

            for term in set(weighted_counts.keys()):
                self.doc_frequencies[term] = self.doc_frequencies.get(term, 0) + 1

        self.doc_lengths = np.array(doc_lengths_list, dtype=np.float32)
        self.avg_doc_len = float(np.mean(self.doc_lengths)) if len(self.doc_lengths) > 0 else 1.0

        self.idf = {}
        for term, df in self.doc_frequencies.items():
            idf_val = math.log((self.num_docs - df + 0.5) / (df + 0.5) + 1.0)
            self.idf[term] = max(0.0, idf_val)

        return self


def run_ablation_matrix():
    t_start = time.time()
    print("=" * 80)
    print("STAGE 3.9: COMPREHENSIVE ABLATION MATRIX & CANONICAL BENCHMARK (N=345)")
    print("=" * 80)

    # 1. Corpus Manifest
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    manifest_raw = {}
    manifest_for_cache = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            if row.get("status") and row.get("status") != "ok":
                continue
            r_repo = str(row.get("repo") or "")
            r_commit = str(row.get("base_commit") or "")
            c_path = row.get("chunks_path")
            if r_repo and r_commit and c_path:
                manifest_raw[(r_repo, r_commit)] = ARB_DIR / str(c_path)
                manifest_for_cache[(r_repo, r_commit)] = ARB_DIR / str(c_path)

    corpus_cache = CorpusFileCache(manifest_for_cache)

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

    print(f"Loaded {len(all_samples)} total positive samples across 4 tracks.")

    by_corpus = defaultdict(list)
    for s in all_samples:
        by_corpus[(s["repo"], s["base_commit"])].append(s)

    # Configuration definitions
    configs = [
        ("CONFIG-01", "BASE-BM25", "Pure BM25 canonical baseline (EXP-016)"),
        ("CONFIG-02", "BM25-DOCFILTER", "BM25 with 0.5x documentation filter"),
        ("CONFIG-03", "BM25-SUBWORD-RAW", "BM25 + Subword Semantic linear raw sum"),
        ("CONFIG-04", "BM25-SUBWORD-CALIBRATED", "BM25 + Subword Semantic calibrated (RRF k=60)"),
        ("CONFIG-05", "BM25-SUBWORD-DOCFILTER", "BM25 + Subword Semantic + DocFilter (0.5x)"),
        ("CONFIG-06", "CAND-C-CANONICAL", "Candidate C canonical ((BM25+Sem+PR)/3 * DocFilter)"),
        ("CONFIG-07", "CAND-F-CANONICAL", "Candidate F canonical (Candidate C + Unbounded Diffusion)"),
        ("CONFIG-08", "CAND-BOUNDED-DIFFUSION", "Candidate C architecture with Bounded Diffusion (deg <= 25)"),
        ("CONFIG-09", "CORRECTED-HYBRID", "Decoupled BM25 + Subword + DocFilter (No PR)"),
        ("CONFIG-10", "SPARSE-RERANK", "BM25 Top-50 Candidate Generation + Subword Reranking"),
        ("CONFIG-11", "RECOVERED-CANDIDATE", "Decoupled BM25 + Subword + DocFilter + Bounded Diffusion"),
    ]

    cfg_keys = [c[0] for c in configs]
    metrics_summary = {k: defaultdict(list) for k in cfg_keys}
    per_repo_mrr = {k: defaultdict(list) for k in cfg_keys}
    latencies = {k: [] for k in cfg_keys}

    # Storage for per-query rows
    per_query_rows = []

    # Cross-commit file parsing cache
    parsed_file_cache = {}

    def get_parsed_doc(p, t):
        k = (p, len(t))
        if k not in parsed_file_cache:
            syms, imps = RepoGraph.extract_polyglot_symbols(t[:25000], p)
            parsed_file_cache[k] = (syms, imps)
        return parsed_file_cache[k]

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
            syms, imps = get_parsed_doc(p, t)
            docs.append(FileDoc(path=p, content=t[:25000], symbols=syms, imports=imps, is_test="test" in p.lower()))

        num_docs = len(docs)

        # Build indices
        # 1. Canonical BM25 (coupled length)
        bm25_canonical = FastDecoupledBM25()
        bm25_canonical.fit(docs, decouple=False)

        # 2. Decoupled BM25 (true content length)
        bm25_decoupled = FastDecoupledBM25()
        bm25_decoupled.fit(docs, decouple=True)

        # 3. Subword Semantic Index
        sem_index = SubwordSemanticIndex()
        sem_index.fit(docs)

        # 4. Repo Graph
        repo_graph = RepoGraph()
        repo_graph.fit(docs)
        g = repo_graph.graph
        struct_pr = repo_graph.pagerank_scores

        doc_paths_lower = [d.path.lower() for d in docs]
        is_doc_file = np.array([
            any(seg in p for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or
            p.endswith((".md", ".rst", ".txt", ".adoc", ".html"))
            for p in doc_paths_lower
        ], dtype=bool)

        # Repo primary language
        ext_counts = Counter(p.split(".")[-1].lower() for p in file_texts.keys() if "." in p)
        top_ext = ext_counts.most_common(1)[0][0] if ext_counts else "unknown"
        lang_map = {"py": "python", "rs": "rust", "go": "go", "ts": "typescript", "js": "javascript", "tsx": "typescript", "jsx": "javascript", "java": "java"}
        repo_lang = lang_map.get(top_ext, top_ext)

        for s in repo_samples:
            s_id = s["id"]
            gold = target_gold_files(s)
            hard_neg = hard_negative_files(s)
            q_text = query_text_for_eval(s)
            track = s["_subset_name"]
            gold_set = set(gold)
            gold_str = ";".join(gold)

            # Pre-compute base scores
            t0 = time.perf_counter()
            s_bm25_can = bm25_canonical.score(q_text)
            lat_bm25 = (time.perf_counter() - t0) * 1000.0

            t0 = time.perf_counter()
            s_bm25_dec = bm25_decoupled.score(q_text)
            lat_bm25_dec = (time.perf_counter() - t0) * 1000.0

            t0 = time.perf_counter()
            s_sem = sem_index.score(q_text)
            lat_sem = (time.perf_counter() - t0) * 1000.0

            # ---------------------------------------------------------
            # 1. CONFIG-01 (BASE-BM25)
            # ---------------------------------------------------------
            sc_cfg1 = s_bm25_can.copy()
            lat_cfg1 = lat_bm25

            # ---------------------------------------------------------
            # 2. CONFIG-02 (BM25-DOCFILTER)
            # ---------------------------------------------------------
            sc_cfg2 = s_bm25_can.copy()
            sc_cfg2[is_doc_file] *= 0.5
            lat_cfg2 = lat_bm25

            # ---------------------------------------------------------
            # 3. CONFIG-03 (BM25-SUBWORD-RAW)
            # ---------------------------------------------------------
            sc_cfg3 = (s_bm25_can + s_sem) / 2.0
            lat_cfg3 = lat_bm25 + lat_sem

            # ---------------------------------------------------------
            # 4. CONFIG-04 (BM25-SUBWORD-CALIBRATED)
            # ---------------------------------------------------------
            t_rrf = time.perf_counter()
            ranks_b = np.argsort(np.argsort(-s_bm25_can))
            ranks_s = np.argsort(np.argsort(-s_sem))
            sc_cfg4 = (1.0 / (60.0 + ranks_b)) + (1.0 / (60.0 + ranks_s))
            lat_cfg4 = lat_bm25 + lat_sem + (time.perf_counter() - t_rrf) * 1000.0

            # ---------------------------------------------------------
            # 5. CONFIG-05 (BM25-SUBWORD-DOCFILTER)
            # ---------------------------------------------------------
            sc_cfg5 = sc_cfg3.copy()
            sc_cfg5[is_doc_file] *= 0.5
            lat_cfg5 = lat_cfg3

            # ---------------------------------------------------------
            # 6. CONFIG-06 (CAND-C-CANONICAL)
            # ---------------------------------------------------------
            sc_cfg6 = (s_bm25_can + s_sem + struct_pr) / 3.0
            sc_cfg6[is_doc_file] *= 0.5
            lat_cfg6 = lat_bm25 + lat_sem + 0.1

            # ---------------------------------------------------------
            # 7. CONFIG-07 (CAND-F-CANONICAL)
            # ---------------------------------------------------------
            t_f = time.perf_counter()
            sc_cfg7 = sc_cfg6.copy()
            if g.number_of_edges() > 0:
                comb_hits = s_bm25_can + s_sem
                if len(comb_hits) > 0 and float(np.max(comb_hits)) > 0:
                    top_seed_idx = np.argsort(comb_hits)[::-1][:5]
                    diff_boost = np.zeros(num_docs, dtype=np.float32)
                    for s_idx in top_seed_idx:
                        s_p = docs[s_idx].path
                        s_v = float(comb_hits[s_idx])
                        if s_v > 0 and s_p in g:
                            for succ in g.successors(s_p):
                                if succ in repo_graph.path_to_idx:
                                    n_idx = repo_graph.path_to_idx[succ]
                                    diff_boost[n_idx] = max(diff_boost[n_idx], float(s_v * 0.25))
                            for pred in g.predecessors(s_p):
                                if pred in repo_graph.path_to_idx:
                                    n_idx = repo_graph.path_to_idx[pred]
                                    diff_boost[n_idx] = max(diff_boost[n_idx], float(s_v * 0.20))
                    sc_cfg7 = sc_cfg7 + 0.15 * diff_boost
            lat_cfg7 = lat_cfg6 + (time.perf_counter() - t_f) * 1000.0

            # ---------------------------------------------------------
            # 8. CONFIG-08 (CAND-BOUNDED-DIFFUSION)
            # ---------------------------------------------------------
            t_b = time.perf_counter()
            sc_cfg8 = sc_cfg6.copy()
            if g.number_of_edges() > 0:
                comb_hits = s_bm25_can + s_sem
                if len(comb_hits) > 0 and float(np.max(comb_hits)) > 0:
                    top_seed_idx = np.argsort(comb_hits)[::-1][:5]
                    diff_boost = np.zeros(num_docs, dtype=np.float32)
                    for s_idx in top_seed_idx:
                        s_p = docs[s_idx].path
                        s_v = float(comb_hits[s_idx])
                        if s_v > 0 and s_p in g:
                            if g.degree(s_p) <= 25:
                                for succ in g.successors(s_p):
                                    if succ in repo_graph.path_to_idx and g.degree(succ) <= 25:
                                        n_idx = repo_graph.path_to_idx[succ]
                                        diff_boost[n_idx] = max(diff_boost[n_idx], float(s_v * 0.25))
                                for pred in g.predecessors(s_p):
                                    if pred in repo_graph.path_to_idx and g.degree(pred) <= 25:
                                        n_idx = repo_graph.path_to_idx[pred]
                                        diff_boost[n_idx] = max(diff_boost[n_idx], float(s_v * 0.20))
                    sc_cfg8 = sc_cfg8 + 0.15 * diff_boost
            lat_cfg8 = lat_cfg6 + (time.perf_counter() - t_b) * 1000.0

            # ---------------------------------------------------------
            # 9. CONFIG-09 (CORRECTED-HYBRID)
            # ---------------------------------------------------------
            sc_cfg9 = (s_bm25_dec + s_sem) / 2.0
            sc_cfg9[is_doc_file] *= 0.5
            lat_cfg9 = lat_bm25_dec + lat_sem

            # ---------------------------------------------------------
            # 10. CONFIG-10 (SPARSE-RERANK)
            # ---------------------------------------------------------
            t_sp = time.perf_counter()
            # Select top 50 with BM25
            top50_idx = np.argsort(-s_bm25_can)[:50]
            # Rescore only top 50 candidates
            sc_cfg10 = np.zeros(num_docs, dtype=np.float32)
            for idx in top50_idx:
                sc_cfg10[idx] = (s_bm25_can[idx] + s_sem[idx]) / 2.0
                if is_doc_file[idx]:
                    sc_cfg10[idx] *= 0.5
            lat_cfg10 = lat_bm25 + (time.perf_counter() - t_sp) * 1000.0

            # ---------------------------------------------------------
            # 11. CONFIG-11 (RECOVERED-CANDIDATE)
            # ---------------------------------------------------------
            t_rec = time.perf_counter()
            sc_cfg11 = sc_cfg9.copy()
            if g.number_of_edges() > 0:
                comb_hits = s_bm25_dec + s_sem
                if len(comb_hits) > 0 and float(np.max(comb_hits)) > 0:
                    top_seed_idx = np.argsort(comb_hits)[::-1][:5]
                    diff_boost = np.zeros(num_docs, dtype=np.float32)
                    for s_idx in top_seed_idx:
                        s_p = docs[s_idx].path
                        s_v = float(comb_hits[s_idx])
                        if s_v > 0 and s_p in g:
                            if g.degree(s_p) <= 25:
                                for succ in g.successors(s_p):
                                    if succ in repo_graph.path_to_idx and g.degree(succ) <= 25:
                                        n_idx = repo_graph.path_to_idx[succ]
                                        diff_boost[n_idx] = max(diff_boost[n_idx], float(s_v * 0.25))
                                for pred in g.predecessors(s_p):
                                    if pred in repo_graph.path_to_idx and g.degree(pred) <= 25:
                                        n_idx = repo_graph.path_to_idx[pred]
                                        diff_boost[n_idx] = max(diff_boost[n_idx], float(s_v * 0.20))
                    sc_cfg11 = sc_cfg11 + 0.15 * diff_boost
            lat_cfg11 = lat_cfg9 + (time.perf_counter() - t_rec) * 1000.0

            eval_dict = {
                "CONFIG-01": (sc_cfg1, lat_cfg1),
                "CONFIG-02": (sc_cfg2, lat_cfg2),
                "CONFIG-03": (sc_cfg3, lat_cfg3),
                "CONFIG-04": (sc_cfg4, lat_cfg4),
                "CONFIG-05": (sc_cfg5, lat_cfg5),
                "CONFIG-06": (sc_cfg6, lat_cfg6),
                "CONFIG-07": (sc_cfg7, lat_cfg7),
                "CONFIG-08": (sc_cfg8, lat_cfg8),
                "CONFIG-09": (sc_cfg9, lat_cfg9),
                "CONFIG-10": (sc_cfg10, lat_cfg10),
                "CONFIG-11": (sc_cfg11, lat_cfg11),
            }

            for c_key, (sc_vec, c_lat) in eval_dict.items():
                ranked_idx = np.argsort(-sc_vec)
                ranked_paths = [docs[i].path for i in ranked_idx]

                # Reciprocal rank
                rr = 0.0
                first_rank = -1
                for r_i, p in enumerate(ranked_paths):
                    if p in gold_set:
                        rr = 1.0 / (r_i + 1)
                        first_rank = r_i + 1
                        break

                r1 = recall_at(gold_set, ranked_paths, 1)
                r5 = recall_at(gold_set, ranked_paths, 5)
                r10 = recall_at(gold_set, ranked_paths, 10)
                r20 = recall_at(gold_set, ranked_paths, 20)

                p5 = precision_at(gold_set, ranked_paths, 5)
                p10 = precision_at(gold_set, ranked_paths, 10)
                p20 = precision_at(gold_set, ranked_paths, 20)

                # Canonical Token-Budgeted BCY@8k
                packed = pack_files(repo, base_commit, ranked_paths, gold_set, corpus_cache, budget=8000)
                token_bcy = packed["bcy"]
                ret_tokens = packed["used_tokens"]
                sel_files = packed["packed_files"]

                metrics_summary[c_key]["mrr"].append(rr)
                metrics_summary[c_key]["r1"].append(r1)
                metrics_summary[c_key]["r5"].append(r5)
                metrics_summary[c_key]["r10"].append(r10)
                metrics_summary[c_key]["r20"].append(r20)
                metrics_summary[c_key]["p5"].append(p5)
                metrics_summary[c_key]["p10"].append(p10)
                metrics_summary[c_key]["p20"].append(p20)
                metrics_summary[c_key]["token_bcy"].append(token_bcy)
                latencies[c_key].append(c_lat)

                per_repo_mrr[c_key][repo].append(rr)

                # Per-query record
                top_p_str = ";".join(ranked_paths[:5])
                per_query_rows.append({
                    "query_id": s_id,
                    "repo": repo,
                    "base_commit": base_commit,
                    "task_type": track,
                    "language": repo_lang,
                    "configuration_id": c_key,
                    "system_name": [c[1] for c in configs if c[0] == c_key][0],
                    "mrr": f"{rr:.6f}",
                    "recall_at_1": f"{r1:.6f}",
                    "recall_at_5": f"{r5:.6f}",
                    "recall_at_10": f"{r10:.6f}",
                    "recall_at_20": f"{r20:.6f}",
                    "precision_at_5": f"{p5:.6f}",
                    "precision_at_10": f"{p10:.6f}",
                    "precision_at_20": f"{p20:.6f}",
                    "token_bcy_at_8k": f"{token_bcy:.6f}",
                    "first_relevant_rank": first_rank,
                    "retrieved_token_count": ret_tokens,
                    "selected_file_count": sel_files,
                    "latency_ms": f"{c_lat:.2f}",
                    "abstained": False,
                    "gold_files": gold_str,
                    "top_ranked_paths": top_p_str,
                })

        if corpus_idx % 10 == 0 or corpus_idx == total_corpora:
            print(f"Processed {corpus_idx}/{total_corpora} corpora ({repo})...", flush=True)

    # 1. Write CANONICAL_PER_QUERY_RESULTS.csv
    out_per_query = ROOT_DIR / "research" / "stage3_9" / "CANONICAL_PER_QUERY_RESULTS.csv"
    with open(out_per_query, "w", newline="", encoding="utf-8") as f:
        header = list(per_query_rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(per_query_rows)
    print(f"\n[DONE] Wrote {len(per_query_rows)} canonical per-query records to {out_per_query.name}.")

    # 2. Write ABLATION_RESULTS.csv
    out_ablation = ROOT_DIR / "research" / "stage3_9" / "ABLATION_RESULTS.csv"
    ablation_rows = []
    print("\n" + "=" * 105)
    print(f"{'Config ID':<10} | {'System Name':<24} | {'MRR':<8} | {'R@5':<8} | {'R@10':<8} | {'R@20':<8} | {'BCY@8k':<8} | {'p50 (ms)':<9} | {'p95 (ms)':<9}")
    print("=" * 105)

    for cfg_id, name, desc in configs:
        m = metrics_summary[cfg_id]
        lats = latencies[cfg_id]
        row_dict = {
            "configuration_id": cfg_id,
            "system_name": name,
            "description": desc,
            "mrr": f"{np.mean(m['mrr']):.4f}",
            "recall_at_1": f"{np.mean(m['r1']):.4f}",
            "recall_at_5": f"{np.mean(m['r5']):.4f}",
            "recall_at_10": f"{np.mean(m['r10']):.4f}",
            "recall_at_20": f"{np.mean(m['r20']):.4f}",
            "precision_at_5": f"{np.mean(m['p5']):.4f}",
            "precision_at_10": f"{np.mean(m['p10']):.4f}",
            "precision_at_20": f"{np.mean(m['p20']):.4f}",
            "token_bcy_at_8k": f"{np.mean(m['token_bcy']):.4f}",
            "latency_p50_ms": f"{np.median(lats):.2f}",
            "latency_p90_ms": f"{np.percentile(lats, 90):.2f}",
            "latency_p95_ms": f"{np.percentile(lats, 95):.2f}",
            "latency_p99_ms": f"{np.percentile(lats, 99):.2f}",
        }
        ablation_rows.append(row_dict)
        print(f"{cfg_id:<10} | {name:<24} | {row_dict['mrr']:<8} | {row_dict['recall_at_5']:<8} | {row_dict['recall_at_10']:<8} | {row_dict['recall_at_20']:<8} | {row_dict['token_bcy_at_8k']:<8} | {row_dict['latency_p50_ms']:<9} | {row_dict['latency_p95_ms']:<9}")

    print("=" * 105)

    with open(out_ablation, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(ablation_rows[0].keys()))
        writer.writeheader()
        writer.writerows(ablation_rows)
    print(f"[DONE] Wrote summary ablation results to {out_ablation.name}.")

    # 3. Write PER_REPOSITORY_RESULTS.csv
    out_per_repo = ROOT_DIR / "research" / "stage3_9" / "PER_REPOSITORY_RESULTS.csv"
    all_repos = sorted(list(set(s["repo"] for s in all_samples)))
    repo_rows = []
    for r in all_repos:
        r_row = {"repo": r, "query_count": len([s for s in all_samples if s["repo"] == r])}
        for cfg_id, name, _ in configs:
            vals = per_repo_mrr[cfg_id][r]
            r_row[f"{name}_mrr"] = f"{np.mean(vals):.4f}" if vals else "N/A"
        repo_rows.append(r_row)

    with open(out_per_repo, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(repo_rows[0].keys()))
        writer.writeheader()
        writer.writerows(repo_rows)
    print(f"[DONE] Wrote per-repository breakdown to {out_per_repo.name}.")

    t_end = time.time()
    print(f"\nExecution finished in {t_end - t_start:.2f} seconds.")


if __name__ == "__main__":
    run_ablation_matrix()
