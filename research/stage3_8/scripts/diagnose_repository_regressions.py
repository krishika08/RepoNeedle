"""
Stage 3.8 Phase 2: Forensic Diagnostic Script for Repository Regressions.
Deeply analyzes pallets/click (26 queries) and clap-rs/clap (10 queries)
to determine why EXP-378 degraded relative to Candidate C.
Outputs: research/stage3_8/GRAPH_PROPAGATION_DIAGNOSTICS.csv and console case studies.
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
)
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex


def run_regression_diagnosis():
    print("=" * 80)
    print("STAGE 3.8 PHASE 2: FORENSIC DIAGNOSIS OF CLICK & CLAP REGRESSIONS")
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

    target_repos = ["pallets/click", "clap-rs/clap"]
    repo_samples = defaultdict(list)
    for s in all_samples:
        if s["repo"] in target_repos:
            repo_samples[(s["repo"], s["base_commit"])].append(s)

    diag_rows = []

    for (repo, base_commit), samples in repo_samples.items():
        cpath = manifest_raw.get((repo, base_commit))
        if not cpath or not cpath.is_file():
            continue

        chunks = read_jsonl(cpath)
        file_texts = {}
        for c in chunks:
            p = c.get("path")
            t = c.get("text", "")
            if p and (p not in file_texts or len(t) > len(file_texts[p])):
                file_texts[p] = t

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

        bm25_decoupled = BM25Index(decouple_symbols=True).fit(docs_with_symbols)
        bm25_pure = BM25Index(decouple_symbols=True).fit(docs_pure)
        semantic_index = SubwordSemanticIndex().fit(docs_with_symbols)
        rg = RepoGraph().fit(docs_with_symbols)
        G = rg.graph
        pr_scores = rg.pagerank_scores

        doc_paths_lower = [p.lower() for p in doc_paths]
        is_doc_file = np.array([
            any(seg in p for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or
            p.endswith((".md", ".rst", ".txt", ".adoc", ".html"))
            for p in doc_paths_lower
        ], dtype=bool)

        print(f"\nAnalyzing {repo} ({len(samples)} queries, {num_docs} files, {G.number_of_edges()} edges)...")

        for s in samples:
            s_id = s["id"]
            gold = target_gold_files(s)
            q_text = query_text_for_eval(s)

            # Raw scores
            lex_d = bm25_decoupled.score(q_text)
            lex_p = bm25_pure.score(q_text)
            sem = semantic_index.score(q_text)

            # Candidate C (pure lexical + sem + PR)
            base_c = (lex_p + sem + pr_scores) / 3.0
            base_c[is_doc_file] *= 0.5
            ranks_c = np.argsort(-base_c)
            path_rank_c = {doc_paths[r]: i + 1 for i, r in enumerate(ranks_c)}

            # EXP-378 (decoupled lex + sem + hub-norm diffusion, no PR)
            base_378 = (lex_d + sem) / 2.0
            base_378[is_doc_file] *= 0.5

            boost_hn = np.zeros(num_docs, dtype=np.float32)
            top_seeds = []
            seed_paths = []
            hits = lex_d + sem
            if len(hits) > 0 and float(np.max(hits)) > 0:
                top_seed_indices = np.argsort(hits)[::-1][:5]
                for s_idx in top_seed_indices:
                    sp = doc_paths[s_idx]
                    sv = float(hits[s_idx])
                    if sv > 0 and sp in G:
                        seed_paths.append(sp)
                        for succ in G.successors(sp):
                            if succ in path_to_idx:
                                n_idx = path_to_idx[succ]
                                deg = max(1, G.in_degree(succ))
                                boost_hn[n_idx] = max(boost_hn[n_idx], float(sv * 0.25 / np.sqrt(deg)))
                        for pred in G.predecessors(sp):
                            if pred in path_to_idx:
                                n_idx = path_to_idx[pred]
                                deg = max(1, G.out_degree(pred))
                                boost_hn[n_idx] = max(boost_hn[n_idx], float(sv * 0.20 / np.sqrt(deg)))

            scores_378 = base_378 + 0.15 * boost_hn
            ranks_378 = np.argsort(-scores_378)
            path_rank_378 = {doc_paths[r]: i + 1 for i, r in enumerate(ranks_378)}

            for g in gold:
                if g in path_to_idx:
                    g_idx = path_to_idx[g]
                    r_c = path_rank_c.get(g, num_docs + 1)
                    r_378 = path_rank_378.get(g, num_docs + 1)
                    mrr_c = 1.0 / r_c if r_c > 0 else 0.0
                    mrr_378 = 1.0 / r_378 if r_378 > 0 else 0.0
                    delta_mrr = mrr_378 - mrr_c

                    # Check which file displaced gold
                    displacing_files = [doc_paths[r] for r in ranks_378[:r_378-1] if path_rank_c.get(doc_paths[r], 9999) > r_c]

                    row = {
                        "sample_id": s_id,
                        "repo": repo,
                        "task_type": s["_subset_name"],
                        "query_snippet": q_text[:80].replace("\n", " "),
                        "gold_path": g,
                        "gold_in_degree": G.in_degree(g) if g in G else 0,
                        "gold_out_degree": G.out_degree(g) if g in G else 0,
                        "gold_pagerank": f"{pr_scores[g_idx]:.4f}",
                        "gold_lex_score": f"{lex_d[g_idx]:.4f}",
                        "gold_sem_score": f"{sem[g_idx]:.4f}",
                        "gold_diffusion_boost": f"{boost_hn[g_idx]:.4f}",
                        "rank_cand_c": r_c,
                        "rank_exp_378": r_378,
                        "delta_rank": r_378 - r_c, # > 0 means regressed
                        "mrr_cand_c": f"{mrr_c:.4f}",
                        "mrr_exp_378": f"{mrr_378:.4f}",
                        "delta_mrr": f"{delta_mrr:+.4f}",
                        "seeds": ";".join(seed_paths[:3]),
                        "displacing_top": displacing_files[0] if displacing_files else "",
                    }
                    diag_rows.append(row)

                    if delta_mrr < -0.10:
                        print(f"  REGRESSION: Query {s_id[:8]} | Gold: {g}")
                        print(f"    Ranks: Cand C = #{r_c} (MRR {mrr_c:.4f}) -> EXP-378 = #{r_378} (MRR {mrr_378:.4f}) [Delta: {delta_mrr:+.4f}]")
                        print(f"    Gold PageRank: {pr_scores[g_idx]:.4f} | Lex: {lex_d[g_idx]:.4f} | Sem: {sem[g_idx]:.4f}")
                        print(f"    Displaced by: {displacing_files[:2]}")

    out_csv = STAGE_DIR / "GRAPH_PROPAGATION_DIAGNOSTICS.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(diag_rows[0].keys()))
        writer.writeheader()
        writer.writerows(diag_rows)

    print(f"\nSaved diagnostics to {out_csv} ({len(diag_rows)} gold evaluation rows).")


if __name__ == "__main__":
    run_regression_diagnosis()

