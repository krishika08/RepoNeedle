"""
Stage 3.8: Exploration and Validation of Query-Conditioned Structural Propagation.
Tests query-conditioned backward propagation, edge-type awareness, and degree-aware dampening.
"""

import sys
import os
import json
import csv
from pathlib import Path
from collections import defaultdict
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
)
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex


def explore():
    print("=" * 80)
    print("STAGE 3.8: EXPLORE QUERY-CONDITIONED PROPAGATION ACROSS ALL N=345 QUERIES")
    print("=" * 80)

    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    manifest_raw = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            manifest_raw[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]

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

    mrrs = defaultdict(list)
    r20s = defaultdict(list)
    h20s = defaultdict(list)

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
        sem = SubwordSemanticIndex().fit(docs)
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

        for s in repo_samples:
            gold = target_gold_files(s)
            hard_neg = hard_negative_files(s)
            q_text = query_text_for_eval(s)
            t_type = s["_subset_name"]

            lex = bm25.score(q_text)
            sm = sem.score(q_text)

            base = (lex + sm) / 2.0
            base[is_doc_file] *= 0.5

            hits = lex + sm
            max_hit = float(np.max(hits)) if len(hits) > 0 else 1.0
            if max_hit == 0.0:
                max_hit = 1.0

            # 1. EXP-384: Reference EXP-378
            boost_384 = np.zeros(num_docs, dtype=np.float32)

            # 2. EXP-385: Query-Conditioned Backward Propagation
            boost_385 = np.zeros(num_docs, dtype=np.float32)

            # 3. EXP-386: Query-Conditioned Edge-Type-Aware Propagation
            boost_386 = np.zeros(num_docs, dtype=np.float32)

            # 4. EXP-387: Degree-Aware Query-Conditioned Propagation (Leapfrog Dampened)
            boost_387 = np.zeros(num_docs, dtype=np.float32)

            # 5. EXP-388: Combined Query-Conditioned Propagation
            boost_388 = np.zeros(num_docs, dtype=np.float32)

            q_lower = q_text.lower()
            query_is_test_seeking = ("test" in q_lower or "assert" in q_lower or "spec" in q_lower or "fixture" in q_lower) and t_type != "trace2code"

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

                            # EXP-385: Query-conditioned backward propagation
                            # Affine scaling by query match of predecessor
                            pred_affinity = float(hits[n_idx]) / max_hit
                            bwd_385 = bwd_raw * (0.20 + 0.80 * pred_affinity)
                            boost_385[n_idx] = max(boost_385[n_idx], bwd_385)

                            # EXP-386: Edge-type-aware propagation
                            edge_mult = 1.0
                            if is_manifest_file[n_idx]:
                                edge_mult = 0.05
                            elif not query_is_test_seeking and is_test_file[n_idx] and not is_test_file[s_idx]:
                                edge_mult = 0.15 # Attenuate test predecessor for code query
                            elif query_is_test_seeking and is_test_file[n_idx]:
                                edge_mult = 1.25 # Boost test predecessor for test query
                            bwd_386 = bwd_raw * edge_mult
                            boost_386[n_idx] = max(boost_386[n_idx], bwd_386)

                            # EXP-387: Degree-aware leapfrog dampening
                            margin = max(0.0, float(base[s_idx] - base[n_idx]))
                            bwd_387 = min(bwd_raw, margin)
                            boost_387[n_idx] = max(boost_387[n_idx], bwd_387)

                            # EXP-388: Combined query-conditioned propagation
                            bwd_388 = min(bwd_raw * (0.20 + 0.80 * pred_affinity) * edge_mult, margin)
                            boost_388[n_idx] = max(boost_388[n_idx], bwd_388)

            configs = [
                ("EXP-384", base + 0.15 * boost_384),
                ("EXP-385", base + 0.15 * boost_385),
                ("EXP-386", base + 0.15 * boost_386),
                ("EXP-387", base + 0.15 * boost_387),
                ("EXP-388", base + 0.15 * boost_388),
            ]

            gold_set = set(gold)
            for cid, sc_vec in configs:
                r_indices = np.argsort(-sc_vec)
                r_paths = [doc_paths[i] for i in r_indices]
                ranked_chunks = []
                seen = set()
                for p in r_paths:
                    if p in path_to_chunks and p not in seen:
                        ranked_chunks.extend(path_to_chunks[p])
                        seen.add(p)
                for p, chs in path_to_chunks.items():
                    if p not in seen:
                        ranked_chunks.extend(chs)
                        seen.add(p)

                m = sample_metrics(gold, ranked_chunks, context_budget=8000, hard_negative_files=hard_neg)
                r20 = recall_at(gold_set, r_paths, 20)
                hit20 = 1.0 if any(p in gold_set for p in r_paths[:20]) else 0.0

                mrrs[cid].append(m["MRR"])
                r20s[cid].append(r20)
                h20s[cid].append(hit20)

    print("\nResults Across All N=345 ARB v2 Samples:")
    print(f"{'Exp ID':<9} | {'MRR':<7} | {'Recall@20':<10} | {'Hit@20':<7}")
    print("-" * 45)
    for cid in ["EXP-384", "EXP-385", "EXP-386", "EXP-387", "EXP-388"]:
        print(f"{cid:<9} | {np.mean(mrrs[cid]):.4f}  | {np.mean(r20s[cid]):.4f}     | {np.mean(h20s[cid]):.4f}")


if __name__ == "__main__":
    explore()

