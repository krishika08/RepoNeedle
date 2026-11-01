"""
Stage 3.7: BM25 Document-Length Inflation Diagnostic Audit.
Measures the empirical effect of polyglot symbol extraction on BM25 effective document length,
length normalization penalties, and target ranking degradation across all ARB v2 corpora and queries.
"""

import sys
import os
import json
import csv
import time
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np
import scipy.stats as stats

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
    recall_at,
    reciprocal_rank,
)
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.core.tokenizer import CodeTokenizer
from reponeedle.core.lexical import BM25Index


def run_bm25_audit():
    print("=" * 80)
    print("STAGE 3.7: AUDIT BM25 DOCUMENT-LENGTH INFLATION & NORMALIZATION PENALTIES")
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

    tokenizer = CodeTokenizer()

    # Per-file diagnostics
    file_diag_rows = []
    # Per-repo diagnostics
    repo_diag_rows = []
    # Per-query diagnostics
    query_diag_rows = []

    gold_inflation_list = []
    gold_rank_change_list = []

    print(f"Auditing {len(by_corpus)} repository corpora...")

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

        docs_coupled = []
        docs_decoupled = []
        docs_pure = []

        repo_lex_tokens = []
        repo_sym_tokens = []
        repo_coupled_lens = []
        repo_decoupled_lens = []

        file_stat_map = {}

        for p, t in file_texts.items():
            content = t[:25000]
            syms, imps = RepoGraph.extract_polyglot_symbols(content, p)
            
            p_tokens = tokenizer.tokenize_path(p)
            b_tokens = tokenizer.tokenize_text(content)
            s_tokens = []
            for s in syms:
                s_tokens.extend(tokenizer.tokenize_text(s))

            lex_len = len(b_tokens) + len(p_tokens)
            sym_len = len(s_tokens)
            # Coupled length calculation from BM25Index:
            # sum(weighted_counts.values()) where path=2.5, sym=2.0, body=1.0
            coupled_len = 2.5 * len(p_tokens) + 2.0 * len(s_tokens) + 1.0 * len(b_tokens)
            decoupled_len = max(1.0, float(lex_len))

            inflation_ratio = coupled_len / decoupled_len if decoupled_len > 0 else 1.0

            repo_lex_tokens.append(lex_len)
            repo_sym_tokens.append(sym_len)
            repo_coupled_lens.append(coupled_len)
            repo_decoupled_lens.append(decoupled_len)

            file_stat_map[p] = {
                "lex_len": lex_len,
                "sym_len": sym_len,
                "coupled_len": coupled_len,
                "decoupled_len": decoupled_len,
                "inflation_ratio": inflation_ratio,
                "num_symbols": len(syms),
            }

            # Prepare docs
            docs_coupled.append(FileDoc(path=p, content=content, symbols=syms, imports=imps))
            docs_decoupled.append(FileDoc(path=p, content=content, symbols=syms, imports=imps))
            docs_pure.append(FileDoc(path=p, content=content, symbols=[], imports=[]))

        avg_lex = float(np.mean(repo_lex_tokens)) if repo_lex_tokens else 0.0
        avg_sym = float(np.mean(repo_sym_tokens)) if repo_sym_tokens else 0.0
        avg_coupled_len = float(np.mean(repo_coupled_lens)) if repo_coupled_lens else 0.0
        avg_decoupled_len = float(np.mean(repo_decoupled_lens)) if repo_decoupled_lens else 0.0
        repo_inflation = avg_coupled_len / avg_decoupled_len if avg_decoupled_len > 0 else 1.0

        repo_diag_rows.append({
            "repo": repo,
            "base_commit": base_commit,
            "num_files": len(file_texts),
            "avg_lex_tokens": avg_lex,
            "avg_sym_tokens": avg_sym,
            "avg_coupled_len": avg_coupled_len,
            "avg_decoupled_len": avg_decoupled_len,
            "avg_inflation_ratio": repo_inflation,
        })

        # Fit BM25 indices
        # 1. Pure BM25 (no symbols)
        bm25_pure = BM25Index(decouple_symbols=True).fit(docs_pure)
        # 2. Coupled BM25 (Candidate F default: decouple_symbols=False)
        bm25_coupled = BM25Index(decouple_symbols=False).fit(docs_coupled)
        # 3. Decoupled BM25 (EXP-374: decouple_symbols=True)
        bm25_decoupled = BM25Index(decouple_symbols=True).fit(docs_decoupled)

        doc_paths = [d.path for d in docs_coupled]
        path_to_idx = {p: i for i, p in enumerate(doc_paths)}

        # Evaluate queries for this repo
        for s in repo_samples:
            s_id = s["id"]
            gold = target_gold_files(s)
            q_text = query_text_for_eval(s)

            scores_pure = bm25_pure.score(q_text)
            scores_coupled = bm25_coupled.score(q_text)
            scores_decoupled = bm25_decoupled.score(q_text)

            ranks_pure = np.argsort(-scores_pure)
            ranks_coupled = np.argsort(-scores_coupled)
            ranks_decoupled = np.argsort(-scores_decoupled)

            path_rank_pure = {doc_paths[r]: i + 1 for i, r in enumerate(ranks_pure)}
            path_rank_coupled = {doc_paths[r]: i + 1 for i, r in enumerate(ranks_coupled)}
            path_rank_decoupled = {doc_paths[r]: i + 1 for i, r in enumerate(ranks_decoupled)}

            # Gold file metrics
            for g in gold:
                if g in path_to_idx:
                    g_idx = path_to_idx[g]
                    g_stat = file_stat_map.get(g, {})
                    r_pure = path_rank_pure.get(g, len(doc_paths) + 1)
                    r_coup = path_rank_coupled.get(g, len(doc_paths) + 1)
                    r_decoup = path_rank_decoupled.get(g, len(doc_paths) + 1)
                    
                    s_pure = float(scores_pure[g_idx])
                    s_coup = float(scores_coupled[g_idx])
                    s_decoup = float(scores_decoupled[g_idx])

                    rank_delta = r_coup - r_decoup # > 0 means coupled ranked gold worse
                    score_delta = s_decoup - s_coup # > 0 means decoupled gave higher score

                    query_diag_rows.append({
                        "sample_id": s_id,
                        "repo": repo,
                        "gold_path": g,
                        "lex_len": g_stat.get("lex_len", 0),
                        "sym_len": g_stat.get("sym_len", 0),
                        "coupled_len": g_stat.get("coupled_len", 0),
                        "decoupled_len": g_stat.get("decoupled_len", 0),
                        "inflation_ratio": g_stat.get("inflation_ratio", 1.0),
                        "rank_pure": r_pure,
                        "rank_coupled": r_coup,
                        "rank_decoupled": r_decoup,
                        "rank_delta_coup_vs_decoup": rank_delta,
                        "score_pure": s_pure,
                        "score_coupled": s_coup,
                        "score_decoupled": s_decoup,
                        "score_delta_decoup_minus_coup": score_delta,
                    })

                    gold_inflation_list.append(g_stat.get("inflation_ratio", 1.0))
                    gold_rank_change_list.append(rank_delta)

    # Compute correlation
    corr_p, p_val_p = stats.pearsonr(gold_inflation_list, gold_rank_change_list)
    corr_s, p_val_s = stats.spearmanr(gold_inflation_list, gold_rank_change_list)

    print(f"\nAudit complete across {len(query_diag_rows)} gold instances.")
    print(f"Correlation between Gold Length Inflation & Rank Degradation (Rank_coupled - Rank_decoupled):")
    print(f"  Pearson  r = {corr_p:.4f} (p = {p_val_p:.4e})")
    print(f"  Spearman r = {corr_s:.4f} (p = {p_val_s:.4e})")

    # Find top concrete cases of severe degradation due to length inflation
    query_diag_rows.sort(key=lambda x: -x["rank_delta_coup_vs_decoup"])
    top_degradations = [r for r in query_diag_rows if r["rank_delta_coup_vs_decoup"] > 0][:10]

    print("\nTop Concrete Cases where Coupled BM25 Penalized Gold Files:")
    for row in top_degradations[:5]:
        print(f"  Sample: {row['sample_id']} | Repo: {row['repo']}")
        print(f"    Gold: {row['gold_path']}")
        print(f"    Inflation: {row['inflation_ratio']:.2f}x (Lex: {row['lex_len']}, Sym: {row['sym_len']}, Coupled: {row['coupled_len']:.0f})")
        print(f"    Rank: Decoupled={row['rank_decoupled']} -> Coupled={row['rank_coupled']} (Degradation: +{row['rank_delta_coup_vs_decoup']} positions)")
        print(f"    Score: Decoupled={row['score_decoupled']:.4f} vs Coupled={row['score_coupled']:.4f}")

    # Write BM25_LENGTH_DIAGNOSTICS.csv
    out_csv = STAGE_DIR / "BM25_LENGTH_DIAGNOSTICS.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "sample_id", "repo", "gold_path", "lex_len", "sym_len",
            "coupled_len", "decoupled_len", "inflation_ratio",
            "rank_pure", "rank_coupled", "rank_decoupled",
            "rank_delta_coup_vs_decoup", "score_pure", "score_coupled",
            "score_decoupled", "score_delta_decoup_minus_coup"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(query_diag_rows)

    print(f"\nSaved diagnostics to {out_csv}")
    return query_diag_rows, repo_diag_rows, (corr_p, p_val_p, corr_s, p_val_s)


if __name__ == "__main__":
    run_bm25_audit()

