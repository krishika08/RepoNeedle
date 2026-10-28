"""
Stage 3.9: Diagnostic & Hypothesis Verification Harness.
Evaluates modular ranking components on the 345 ARB v2 positive queries:
  Hypothesis A: Document-Length Inflation in BM25
  Hypothesis B: Fusion Calibration & Score Distribution Mismatch
  Hypothesis C: Graph Diffusion Dilution & Hub Distortion
  Hypothesis D: Documentation Filtering Impact by Track
  Hypothesis E: Candidate Generation & Ordering
"""

import sys
import os
import json
import time
import math
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
    sample_metrics,
    recall_at,
    precision_at,
    reciprocal_rank,
    gold_coverage_at_budget,
)
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.core.tokenizer import CodeTokenizer
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex


class DecoupledBM25Index(BM25Index):
    """
    BM25 index where doc_len denominator is based ONLY on document body content length
    (or body + path), preventing symbol extraction count from inflating document length.
    """
    def fit(self, docs, decouple_symbols=True, symbol_boost=2.0, path_boost=2.5):
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
                weighted_counts[t] = weighted_counts.get(t, 0.0) + path_boost
            for t in symbol_tokens:
                weighted_counts[t] = weighted_counts.get(t, 0.0) + symbol_boost
            for t in body_tokens:
                weighted_counts[t] = weighted_counts.get(t, 0.0) + self.body_weight

            if decouple_symbols:
                # Denominator uses actual text length (body + path tokens), not inflated by symbol extraction
                effective_len = float(len(body_tokens) + len(path_tokens))
                effective_len = max(1.0, effective_len)
            else:
                effective_len = sum(weighted_counts.values())

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


def run_diagnostics():
    print("=" * 80)
    print("STAGE 3.9: DIAGNOSTIC & HYPOTHESIS TESTING (N=345 POSITIVE QUERIES)")
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

    print(f"Loaded {len(all_samples)} total positive samples across 4 tracks.")

    by_corpus = defaultdict(list)
    for s in all_samples:
        by_corpus[(s["repo"], s["base_commit"])].append(s)

    # Metrics storage across configurations
    # Configurations to test:
    config_names = [
        "1_BM25_CANONICAL",            # Baseline BM25 (Stage 3.6/3.8)
        "2_BM25_DECOUPLED_LEN",        # BM25 with symbol length decoupled from doc_len denominator
        "3_BM25_PURE_BODY_PATH",       # BM25 without any extracted symbols
        "4_FUSION_RAW_SUM",            # (BM25 + Sem + PageRank) / 3 (No doc filter)
        "5_FUSION_NO_PAGERANK",        # (BM25 + Sem) / 2 (No doc filter)
        "6_CAND_C_CANONICAL",          # (BM25 + Sem + PageRank) / 3 * DocFilter(0.5)
        "7_CAND_C_NO_PAGERANK_DOC05",  # (BM25 + Sem) / 2 * DocFilter(0.5)
        "8_FUSION_MINMAX_NORM",        # (MinMax(BM25) + Sem) / 2
        "9_FUSION_RRF_60",             # RRF(BM25, Sem) k=60
        "10_SPARSE_RERANK_TOP50",      # BM25 top 50 candidates reranked by BM25 + Sem
        "11_CAND_F_CANONICAL",         # Candidate F with existing diffusion
        "12_CAND_F_PRUNED_DIFFUSION",  # Candidate F with pruned high-degree hubs
    ]

    results = {cfg: defaultdict(list) for cfg in config_names}
    by_track_mrr = {cfg: defaultdict(list) for cfg in config_names}

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
            syms, imps = RepoGraph.extract_polyglot_symbols(t[:25000], p)
            docs.append(FileDoc(path=p, content=t[:25000], symbols=syms, imports=imps, is_test="test" in p.lower()))

        num_docs = len(docs)

        # Build indices
        # Canonical BM25
        bm25_canonical = BM25Index()
        bm25_canonical.fit(docs)

        # Decoupled BM25
        bm25_decoupled = DecoupledBM25Index()
        bm25_decoupled.fit(docs, decouple_symbols=True)

        # Pure Body+Path BM25
        bm25_pure = BM25Index(symbol_weight=0.0)
        bm25_pure.fit(docs)

        # Semantic Subword index
        sem_index = SubwordSemanticIndex()
        sem_index.fit(docs)

        # Graph
        repo_graph = RepoGraph()
        repo_graph.fit(docs)
        g = repo_graph.graph
        struct_scores = repo_graph.pagerank_scores

        doc_paths_lower = [d.path.lower() for d in docs]
        is_doc_file = np.array([
            any(seg in p for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or
            p.endswith((".md", ".rst", ".txt", ".adoc", ".html"))
            for p in doc_paths_lower
        ], dtype=bool)

        path_to_chunks = defaultdict(list)
        for c in chunks:
            p = c.get("path")
            if p:
                path_to_chunks[p].append(c)

        def eval_scores(scores_vec, gold_files, hard_neg_files):
            ranked_indices = np.argsort(-scores_vec)
            ranked_paths = [docs[i].path for i in ranked_indices]
            gold_set = set(gold_files)
            
            # Reciprocal rank
            rr = 0.0
            for r_i, p in enumerate(ranked_paths):
                if p in gold_set:
                    rr = 1.0 / (r_i + 1)
                    break
            
            r5 = recall_at(gold_set, ranked_paths, 5)
            r10 = recall_at(gold_set, ranked_paths, 10)
            r20 = recall_at(gold_set, ranked_paths, 20)
            p5 = precision_at(gold_set, ranked_paths, 5)

            # BCY@8k
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
            bcy_8k = gold_coverage_at_budget(gold_set, ranked_chunks, 8000)

            return {"mrr": rr, "r5": r5, "r10": r10, "r20": r20, "p5": p5, "bcy_8k": bcy_8k}

        for s in repo_samples:
            gold = target_gold_files(s)
            hard_neg = hard_negative_files(s)
            q_text = query_text_for_eval(s)
            track = s["_subset_name"]

            # 1. Canonical BM25
            s_bm25 = bm25_canonical.score(q_text)

            # 2. Decoupled BM25
            s_decoupled = bm25_decoupled.score(q_text)

            # 3. Pure BM25
            s_pure = bm25_pure.score(q_text)

            # Semantic
            s_sem = sem_index.score(q_text)

            # 4. Raw Sum (BM25 + Sem + PageRank) / 3
            s_raw_sum = (s_bm25 + s_sem + struct_scores) / 3.0

            # 5. Fusion No PageRank (BM25 + Sem) / 2
            s_no_pr = (s_bm25 + s_sem) / 2.0

            # 6. CAND-C Canonical
            s_cand_c = s_raw_sum.copy()
            s_cand_c[is_doc_file] *= 0.5

            # 7. CAND-C No PageRank + DocFilter(0.5)
            s_cand_c_no_pr = s_no_pr.copy()
            s_cand_c_no_pr[is_doc_file] *= 0.5

            # 8. MinMax Norm Fusion
            # Scale BM25 to [0, 1] before adding to Sem
            max_bm25 = float(np.max(s_bm25)) if len(s_bm25) > 0 else 0.0
            min_bm25 = float(np.min(s_bm25)) if len(s_bm25) > 0 else 0.0
            range_bm25 = max_bm25 - min_bm25
            if range_bm25 > 1e-6:
                s_bm25_norm = (s_bm25 - min_bm25) / range_bm25
            else:
                s_bm25_norm = np.zeros_like(s_bm25)
            s_minmax = 0.7 * s_bm25_norm + 0.3 * s_sem

            # 9. RRF Fusion k=60
            ranks_bm25 = np.argsort(np.argsort(-s_bm25))
            ranks_sem = np.argsort(np.argsort(-s_sem))
            s_rrf = (1.0 / (60.0 + ranks_bm25)) + (1.0 / (60.0 + ranks_sem))

            # 10. Sparse Rerank Top 50 (BM25 filter top 50, then score = BM25_norm + 0.5 * Sem)
            top50_indices = np.argsort(-s_bm25)[:50]
            s_sparse = np.zeros_like(s_bm25)
            for idx in top50_indices:
                s_sparse[idx] = s_bm25_norm[idx] + 0.4 * s_sem[idx]

            # 11. CAND-F Canonical Diffusion
            s_cand_f = s_cand_c.copy()
            if g.number_of_edges() > 0:
                combined_hits = s_bm25 + s_sem
                if len(combined_hits) > 0 and float(np.max(combined_hits)) > 0:
                    top_seed_indices = np.argsort(combined_hits)[::-1][:5]
                    diffused_boost = np.zeros(num_docs, dtype=np.float32)
                    for s_idx in top_seed_indices:
                        seed_path = docs[s_idx].path
                        seed_val = float(combined_hits[s_idx])
                        if seed_val > 0 and seed_path in g:
                            for succ in g.successors(seed_path):
                                if succ in repo_graph.path_to_idx:
                                    n_idx = repo_graph.path_to_idx[succ]
                                    diffused_boost[n_idx] = max(diffused_boost[n_idx], float(seed_val * 0.25))
                            for pred in g.predecessors(seed_path):
                                if pred in repo_graph.path_to_idx:
                                    n_idx = repo_graph.path_to_idx[pred]
                                    diffused_boost[n_idx] = max(diffused_boost[n_idx], float(seed_val * 0.20))
                    s_cand_f = s_cand_f + 0.15 * diffused_boost

            # 12. CAND-F Pruned Diffusion (Prune nodes with degree > 25 to prevent hub blowout)
            s_cand_f_pruned = s_cand_c_no_pr.copy()
            if g.number_of_edges() > 0:
                combined_hits = s_bm25 + s_sem
                if len(combined_hits) > 0 and float(np.max(combined_hits)) > 0:
                    top_seed_indices = np.argsort(combined_hits)[::-1][:5]
                    diffused_boost = np.zeros(num_docs, dtype=np.float32)
                    for s_idx in top_seed_indices:
                        seed_path = docs[s_idx].path
                        seed_val = float(combined_hits[s_idx])
                        if seed_val > 0 and seed_path in g:
                            # Skip diffusing into/out of extreme hub files (degree > 25)
                            succs = list(g.successors(seed_path))
                            preds = list(g.predecessors(seed_path))
                            if len(succs) + len(preds) <= 25:
                                for succ in succs:
                                    if succ in repo_graph.path_to_idx and g.degree(succ) <= 25:
                                        n_idx = repo_graph.path_to_idx[succ]
                                        diffused_boost[n_idx] = max(diffused_boost[n_idx], float(seed_val * 0.25))
                                for pred in preds:
                                    if pred in repo_graph.path_to_idx and g.degree(pred) <= 25:
                                        n_idx = repo_graph.path_to_idx[pred]
                                        diffused_boost[n_idx] = max(diffused_boost[n_idx], float(seed_val * 0.20))
                    s_cand_f_pruned = s_cand_f_pruned + 0.15 * diffused_boost

            # Evaluate each
            configs_to_eval = [
                ("1_BM25_CANONICAL", s_bm25),
                ("2_BM25_DECOUPLED_LEN", s_decoupled),
                ("3_BM25_PURE_BODY_PATH", s_pure),
                ("4_FUSION_RAW_SUM", s_raw_sum),
                ("5_FUSION_NO_PAGERANK", s_no_pr),
                ("6_CAND_C_CANONICAL", s_cand_c),
                ("7_CAND_C_NO_PAGERANK_DOC05", s_cand_c_no_pr),
                ("8_FUSION_MINMAX_NORM", s_minmax),
                ("9_FUSION_RRF_60", s_rrf),
                ("10_SPARSE_RERANK_TOP50", s_sparse),
                ("11_CAND_F_CANONICAL", s_cand_f),
                ("12_CAND_F_PRUNED_DIFFUSION", s_cand_f_pruned),
            ]

            for cfg_name, sc_vec in configs_to_eval:
                ev = eval_scores(sc_vec, gold, hard_neg)
                for k, v in ev.items():
                    results[cfg_name][k].append(v)
                by_track_mrr[cfg_name][track].append(ev["mrr"])

        print(f"Processed {corpus_idx}/{total_corpora} corpora ({repo})...", flush=True)

    print("\n" + "=" * 95)
    print(f"{'Configuration':<30} | {'MRR':<8} | {'Recall@5':<9} | {'Recall@10':<9} | {'Recall@20':<9} | {'BCY@8k':<8}")
    print("=" * 95)

    for cfg_name in config_names:
        m = results[cfg_name]
        mrr = np.mean(m["mrr"])
        r5 = np.mean(m["r5"])
        r10 = np.mean(m["r10"])
        r20 = np.mean(m["r20"])
        bcy = np.mean(m["bcy_8k"])
        print(f"{cfg_name:<30} | {mrr:<8.4f} | {r5:<9.4f} | {r10:<9.4f} | {r20:<9.4f} | {bcy:<8.4f}")

    print("=" * 95)

    print("\nTRACK BREAKDOWN (MRR):")
    print(f"{'Configuration':<30} | {'code2test':<10} | {'comment2ctx':<12} | {'trace2code':<10} | {'edit2ripple':<11}")
    print("-" * 80)
    for cfg_name in config_names:
        c2t = np.mean(by_track_mrr[cfg_name]["code2test"])
        c2c = np.mean(by_track_mrr[cfg_name]["comment2context"])
        t2c = np.mean(by_track_mrr[cfg_name]["trace2code"])
        e2r = np.mean(by_track_mrr[cfg_name]["edit2ripple"])
        print(f"{cfg_name:<30} | {c2t:<10.4f} | {c2c:<12.4f} | {t2c:<10.4f} | {e2r:<11.4f}")
    print("-" * 80)


if __name__ == "__main__":
    run_diagnostics()

