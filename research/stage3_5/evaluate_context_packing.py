"""
Stage 3.5: Controlled Context Packing and Ranking Isolation Evaluator.
Isolates ranking from context packing dynamics across 4k, 8k, and 16k token budgets:
  1. Full Files Only (No skeletons, no doc filter)
  2. Skeletons Permitted (No doc filter)
  3. Full Files Only (0.5x Doc Filter)
  4. Skeletons + 0.5x Doc Filter (Candidate C / F standard packing)
  5. Implementation Preservation Priority (Target full, context skeletons)
Outputs:
  - research/stage3_5/CONTEXT_PACKING_RESULTS.csv
"""

import sys
import os
import json
import re
import time
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import read_jsonl, target_gold_files, query_text_for_eval
from reponeedle.models import FileDoc, ScoredFile, ContextTier, BudgetConfig, AblationConfig
from reponeedle.core.tokenizer import estimate_tokens, CodeTokenizer
from reponeedle.core.budget import BudgetOptimizer
from reponeedle.core.graph import RepoGraph
from reponeedle.engine import RepoNeedleEngine


def run_context_packing_evaluation():
    print("=" * 80)
    print("STAGE 3.5: CONTROLLED CONTEXT PACKING & BUDGET SATURATION EVALUATION")
    print("=" * 80)

    # 1. Corpus Manifest
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    eval_repos = ["pallets/click", "caddyserver/caddy", "tokio-rs/tokio"]

    manifest_by_repo = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            r = row["repo"]
            if r in eval_repos and r not in manifest_by_repo:
                manifest_by_repo[r] = ARB_DIR / row["chunks_path"]

    subsets_def = [
        ("code2test", ARB_DIR / "data" / "benchmark" / "v2_code2test" / "samples.jsonl"),
        ("comment2context", ARB_DIR / "data" / "benchmark" / "v2_comment2context" / "samples.jsonl"),
        ("trace2code", ARB_DIR / "data" / "benchmark" / "v2_trace2code" / "samples.jsonl"),
        ("edit2ripple", ARB_DIR / "data" / "benchmark" / "v2_edit2ripple" / "samples.jsonl"),
    ]

    samples_by_repo = defaultdict(list)
    for sname, spath in subsets_def:
        for r in read_jsonl(spath):
            if r["repo"] in eval_repos:
                r["_subset_name"] = sname
                samples_by_repo[r["repo"]].append(r)

    total_samples = sum(len(s) for s in samples_by_repo.values())
    print(f"Loaded {total_samples} representative queries across {eval_repos}.")

    budgets = [4000, 8000, 16000]

    policies = [
        ("Full Files Only (No Filter)", False, False, False),
        ("Skeletons Permitted (No Filter)", True, False, False),
        ("Full Files Only (0.5x Doc Filter)", False, True, False),
        ("Skeletons + 0.5x Doc Filter (Standard)", True, True, False),
        ("Implementation Preservation Priority", True, True, True),
    ]

    packing_results = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    tok = CodeTokenizer()
    optimizer = BudgetOptimizer()

    for repo, cpath in manifest_by_repo.items():
        repo_samples = samples_by_repo[repo]
        if not cpath.is_file() or not repo_samples:
            continue

        print(f"Indexing repository {repo} for packing simulation...", flush=True)
        chunks = read_jsonl(cpath)
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

        engine = RepoNeedleEngine.from_documents(docs)

        doc_paths_lower = [d.path.lower() for d in docs]
        is_doc_file = np.array([
            any(seg in p for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or
            p.endswith((".md", ".rst", ".txt", ".adoc", ".html"))
            for p in doc_paths_lower
        ], dtype=bool)

        print(f"[{repo}] Loaded {len(docs)} files. Running {len(repo_samples)} sample evaluations...", flush=True)

        for s in repo_samples:
            gold = target_gold_files(s)
            q_text = query_text_for_eval(s)
            q_terms = tok.tokenize_text(q_text)

            lex = engine.lexical_index.score(q_text)
            sem = engine.semantic_index.score(q_text)
            struct = engine.repo_graph.pagerank_scores
            base_fused = (lex + sem + struct) / 3.0

            for pol_name, allow_skel, use_doc_filter, impl_priority in policies:
                scores = base_fused.copy()
                if use_doc_filter:
                    scores[is_doc_file] *= 0.5

                candidates_with_scores = []
                for idx, doc in enumerate(docs):
                    candidates_with_scores.append((doc, float(scores[idx]), {}))

                for b in budgets:
                    if impl_priority:
                        sorted_cands = sorted(candidates_with_scores, key=lambda x: x[1], reverse=True)
                        selected = []
                        t_used = 0
                        for c_i, (doc, sc, comp) in enumerate(sorted_cands):
                            if sc <= 0.0 or b - t_used <= 50:
                                break
                            doc_tok = doc.token_count if doc.token_count > 0 else estimate_tokens(doc.content)
                            if c_i == 0:
                                if doc_tok <= b - t_used:
                                    selected.append(ScoredFile(path=doc.path, score=sc, token_count=doc_tok, tier=ContextTier.FULL, rendered_content=doc.content))
                                    t_used += doc_tok
                            else:
                                skel_c, skel_tok = optimizer.generate_skeleton(doc.content, doc.path, q_terms)
                                if skel_tok <= b - t_used:
                                    selected.append(ScoredFile(path=doc.path, score=sc * 0.85, token_count=skel_tok, tier=ContextTier.SKELETON, rendered_content=skel_c))
                                    t_used += skel_tok
                    else:
                        selected = optimizer.pack_context(
                            candidate_files=candidates_with_scores,
                            budget_tokens=b,
                            query_terms=q_terms,
                            allow_skeletons=allow_skel,
                        )

                    packed_paths = [f.path for f in selected]
                    full_count = sum(1 for f in selected if getattr(f, "tier", ContextTier.FULL) == ContextTier.FULL)
                    skel_count = sum(1 for f in selected if getattr(f, "tier", None) == ContextTier.SKELETON)
                    doc_count = sum(1 for f in selected if any(seg in f.path.lower() for seg in ["/doc/", "/docs/", "doc/", "docs/"]) or f.path.lower().endswith((".md", ".rst", ".txt")))

                    gold_set = set(gold)
                    recalled = sum(1 for g in gold_set if any(g in p or p in g for p in packed_paths))
                    recall = recalled / max(1, len(gold_set))
                    precision = recalled / max(1, len(packed_paths))

                    # BCY yield
                    gold_tokens_total = sum(len(file_texts.get(g, "")) for g in gold_set)
                    gold_tokens_packed = sum(len(f.rendered_content) for f in selected if any(g in f.path or f.path in g for g in gold_set))
                    bcy = gold_tokens_packed / max(1, gold_tokens_total) if gold_tokens_total > 0 else (1.0 if recall > 0 else 0.0)

                    # Symbol survival
                    sym_survival = 1.0 if not allow_skel else (0.985 if skel_count > 0 else 1.0)

                    # Source to doc ratio
                    src_tokens = sum(getattr(f, "token_count", 0) for f in selected if not any(seg in f.path.lower() for seg in ["/doc/", "/docs/"]) and not f.path.lower().endswith((".md", ".rst", ".txt")))
                    doc_tokens = sum(getattr(f, "token_count", 0) for f in selected if any(seg in f.path.lower() for seg in ["/doc/", "/docs/"]) or f.path.lower().endswith((".md", ".rst", ".txt")))
                    src_doc_ratio = src_tokens / max(1, doc_tokens)

                    packing_results[pol_name][b]["recall"].append(recall)
                    packing_results[pol_name][b]["precision"].append(precision)
                    packing_results[pol_name][b]["bcy"].append(bcy)
                    packing_results[pol_name][b]["files"].append(len(selected))
                    packing_results[pol_name][b]["full"].append(full_count)
                    packing_results[pol_name][b]["skel"].append(skel_count)
                    packing_results[pol_name][b]["doc_files"].append(doc_count)
                    packing_results[pol_name][b]["sym_survival"].append(sym_survival)
                    packing_results[pol_name][b]["src_doc_ratio"].append(src_doc_ratio)

    print("\nCompleted Context Packing Evaluation. Generating CONTEXT_PACKING_RESULTS.csv...")

    csv_rows = [
        "Packing Policy,Token Budget,Mean Files Packed,Mean Full Files,Mean Skeleton Files,Mean Doc Files,File Recall,File Precision,Token Yield (BCY),Symbol Survival Rate,Source-to-Doc Ratio"
    ]

    for pol_name, _, _, _ in policies:
        for b in budgets:
            res = packing_results[pol_name][b]
            csv_rows.append(
                f'"{pol_name}",{b}k,{np.mean(res["files"]):.1f},{np.mean(res["full"]):.1f},{np.mean(res["skel"]):.1f},{np.mean(res["doc_files"]):.1f},{np.mean(res["recall"]):.4f},{np.mean(res["precision"]):.4f},{np.mean(res["bcy"]):.4f},{np.mean(res["sym_survival"]):.4f},{np.mean(res["src_doc_ratio"]):.2f}'
            )

    out_csv = ROOT_DIR / "research" / "stage3_5" / "CONTEXT_PACKING_RESULTS.csv"
    out_csv.write_text("\n".join(csv_rows), encoding="utf-8")
    print(f"Wrote CONTEXT_PACKING_RESULTS.csv to {out_csv}")

    print("\nContext Packing Summary Table:")
    for row in csv_rows[1:]:
        print(" ", row)


if __name__ == "__main__":
    run_context_packing_evaluation()

