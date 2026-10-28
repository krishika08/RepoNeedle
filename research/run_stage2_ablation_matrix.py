"""
Stage 2: Controlled Factorial Ablation Matrix Runner for RepoNeedle.
Evaluates 32 full factorial configurations (5 binary factors) across all 345 positive ARB v2 samples.

Factors:
  Factor A: Lexical ranking signal (BM25)
  Factor B: Semantic/subword ranking signal
  Factor C: Structural repository graph (PageRank & AST test linkage)
  Factor D: Workflow-adaptive routing & score fusion (vs static equal fusion)
  Factor E: Structural skeleton compression during context packing (vs full only)
"""

import os
import sys
import json
import time
import csv
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Tuple, Set
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import (
    read_jsonl,
    target_gold_files,
    hard_negative_files,
    query_text_for_eval,
    sample_metrics,
    unique_ranked_paths,
)
from agent_retrieval_bench.bcy_curve import count_tokens, pack_files, CorpusFileCache
from reponeedle.models import FileDoc, TaskType, Query, BudgetConfig, AblationConfig
from reponeedle.engine import RepoNeedleEngine

CONFIG_DEFS = [
    # (exp_id, name, A, B, C, D, E)
    ("EXP-001", "Full RepoNeedle (Anchor Baseline)", 1, 1, 1, 1, 1),
    ("EXP-002", "Full RepoNeedle w/o Skeletons", 1, 1, 1, 1, 0),
    ("EXP-003", "Static Hybrid w/ Skeletons", 1, 1, 1, 0, 1),
    ("EXP-004", "Static Hybrid Full Only", 1, 1, 1, 0, 0),
    ("EXP-005", "Lexical + Semantic + Router w/ Skel", 1, 1, 0, 1, 1),
    ("EXP-006", "Lexical + Semantic + Router Full", 1, 1, 0, 1, 0),
    ("EXP-007", "Lexical + Semantic Static w/ Skel", 1, 1, 0, 0, 1),
    ("EXP-008", "Lexical + Semantic Static Full", 1, 1, 0, 0, 0),
    ("EXP-009", "Lexical + Graph + Router w/ Skel", 1, 0, 1, 1, 1),
    ("EXP-010", "Lexical + Graph + Router Full", 1, 0, 1, 1, 0),
    ("EXP-011", "Lexical + Graph Static w/ Skel", 1, 0, 1, 0, 1),
    ("EXP-012", "Lexical + Graph Static Full", 1, 0, 1, 0, 0),
    ("EXP-013", "Lexical Only + Router w/ Skel", 1, 0, 0, 1, 1),
    ("EXP-014", "Lexical Only + Router Full", 1, 0, 0, 1, 0),
    ("EXP-015", "Pure BM25 Baseline w/ Skel", 1, 0, 0, 0, 1),
    ("EXP-016", "Pure BM25 Baseline (Standard Full)", 1, 0, 0, 0, 0),
    ("EXP-017", "Semantic + Graph + Router w/ Skel", 0, 1, 1, 1, 1),
    ("EXP-018", "Semantic + Graph + Router Full", 0, 1, 1, 1, 0),
    ("EXP-019", "Semantic + Graph Static w/ Skel", 0, 1, 1, 0, 1),
    ("EXP-020", "Semantic + Graph Static Full", 0, 1, 1, 0, 0),
    ("EXP-021", "Semantic Only + Router w/ Skel", 0, 1, 0, 1, 1),
    ("EXP-022", "Semantic Only + Router Full", 0, 1, 0, 1, 0),
    ("EXP-023", "Pure Semantic Baseline w/ Skel", 0, 1, 0, 0, 1),
    ("EXP-024", "Pure Semantic Baseline Full", 0, 1, 0, 0, 0),
    ("EXP-025", "Graph Only + Router w/ Skel", 0, 0, 1, 1, 1),
    ("EXP-026", "Graph Only + Router Full", 0, 0, 1, 1, 0),
    ("EXP-027", "Pure Graph Baseline w/ Skel", 0, 0, 1, 0, 1),
    ("EXP-028", "Pure Graph Baseline Full", 0, 0, 1, 0, 0),
    ("EXP-029", "Null Signals + Router Boosts w/ Skel", 0, 0, 0, 1, 1),
    ("EXP-030", "Null Signals + Router Boosts Full", 0, 0, 0, 1, 0),
    ("EXP-031", "Null Ranker Prior w/ Skel", 0, 0, 0, 0, 1),
    ("EXP-032", "Null Ranker Prior Full", 0, 0, 0, 0, 0),
]


def run_stage2_ablation():
    t_start = time.time()
    print("=" * 80)
    print("REPONEEDLE STAGE 2: CONTROLLED FACTORIAL ABLATION MATRIX (32 CONFIGS)")
    print("=" * 80)

    # 1. Load Merged Corpus Manifest
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing merged manifest: {manifest_path}")

    manifest_raw = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            manifest_raw[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]

    # 2. Load Positive Benchmark Samples
    subsets_def = [
        ("code2test", ARB_DIR / "data" / "benchmark" / "v2_code2test" / "samples.jsonl"),
        ("comment2context", ARB_DIR / "data" / "benchmark" / "v2_comment2context" / "samples.jsonl"),
        ("trace2code", ARB_DIR / "data" / "benchmark" / "v2_trace2code" / "samples.jsonl"),
        ("edit2ripple", ARB_DIR / "data" / "benchmark" / "v2_edit2ripple" / "samples.jsonl"),
    ]

    positive_samples = []
    for name, path in subsets_def:
        rows = read_jsonl(path)
        for r in rows:
            r["_subset_name"] = name
            positive_samples.append(r)

    print(f"Loaded {len(positive_samples)} positive samples across 4 tracks.")

    # 3. Group samples by corpus snapshot
    samples_by_corpus = defaultdict(list)
    for s in positive_samples:
        key = (s["repo"], s["base_commit"])
        samples_by_corpus[key].append(s)

    total_corpora = len(samples_by_corpus)
    print(f"Grouped into {total_corpora} frozen repository snapshots.")

    # Corpus cache for canonical BCY
    bcy_manifest = {k: Path(v) for k, v in manifest_raw.items()}
    corpus_cache = CorpusFileCache(bcy_manifest)

    # Setup output paths
    out_dir = ROOT_DIR / "research" / "stage2_results"
    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_file = out_dir / "checkpoint_ablations.jsonl"

    completed_sample_ids = set()
    per_sample_records = []

    if checkpoint_file.exists():
        for line in open(checkpoint_file, encoding="utf-8"):
            if line.strip():
                rec = json.loads(line)
                completed_sample_ids.add(rec["sample_id"])
                per_sample_records.append(rec)
        print(f"Loaded {len(per_sample_records)} checkpointed samples.")

    # 16 unique ranking combinations (A, B, C, D)
    ranking_configs = {}
    for exp_id, name, a, b, c, d, e in CONFIG_DEFS:
        key = (a, b, c, d)
        if key not in ranking_configs:
            ranking_configs[key] = []
        ranking_configs[key].append((exp_id, name, e))

    corpus_idx = 0
    t_scoring_total = 0.0

    for (repo, base_commit), samples_in_repo in samples_by_corpus.items():
        corpus_idx += 1
        needed_samples = [s for s in samples_in_repo if s["id"] not in completed_sample_ids]
        if not needed_samples:
            continue

        chunks_path = manifest_raw.get((repo, base_commit))
        if not chunks_path or not chunks_path.is_file():
            print(f"Warning: missing chunks for {repo} @ {base_commit}")
            continue

        chunks = read_jsonl(chunks_path)
        file_texts = {}
        for c in chunks:
            p = c.get("path")
            t = c.get("text", "")
            if p:
                if p not in file_texts or len(t) > len(file_texts[p]):
                    file_texts[p] = t

        docs = [FileDoc(path=p, content=t[:25000], is_test="test" in p.lower()) for p, t in file_texts.items()]
        engine = RepoNeedleEngine.from_documents(docs)

        path_to_chunks = defaultdict(list)
        for c in chunks:
            p = c.get("path")
            if p:
                path_to_chunks[p].append(c)

        num_docs = len(docs)

        if corpus_idx % 20 == 0 or corpus_idx == total_corpora:
            print(f"[{time.strftime('%H:%M:%S')}] Processing corpus {corpus_idx}/{total_corpora}: {repo} ({len(needed_samples)} queries) | Completed: {len(per_sample_records)}/345", flush=True)

        for s in needed_samples:
            sample_id = s["id"]
            task_type_str = s.get("task_type", s["_subset_name"])
            gold = target_gold_files(s)
            hard_neg = hard_negative_files(s)
            q_text = query_text_for_eval(s)
            query_obj = Query(text=q_text)

            t_s0 = time.perf_counter()

            # Precalculate base signals ONCE for this query
            lex_scores = engine.lexical_index.score(q_text)
            sem_scores = engine.semantic_index.score(q_text)
            struct_scores = engine.repo_graph.pagerank_scores

            # Router classification & task boosts
            inferred_task, metadata = engine.router.classify_intent(query_obj)
            router_weights = engine.router.get_fusion_weights(inferred_task)

            # Precalculate workflow boosts
            wf_boost_graph = np.zeros(num_docs, dtype=np.float32)
            wf_boost_nograph = np.zeros(num_docs, dtype=np.float32)

            if inferred_task == TaskType.TRACE2CODE:
                frames = metadata.get("trace_frames", [])
                for frame_path, line_no, func_name in frames:
                    clean_frame = frame_path.replace("\\", "/").lower()
                    for idx, doc in enumerate(docs):
                        doc_lower = doc.path.lower()
                        if clean_frame.endswith(doc_lower) or doc_lower.endswith(clean_frame):
                            wf_boost_graph[idx] = max(wf_boost_graph[idx], 1.0)
                            wf_boost_nograph[idx] = max(wf_boost_nograph[idx], 1.0)
                        elif func_name and func_name in doc.symbols:
                            wf_boost_graph[idx] = max(wf_boost_graph[idx], 0.7)
                            wf_boost_nograph[idx] = max(wf_boost_nograph[idx], 0.7)

            elif inferred_task == TaskType.CODE2TEST:
                top_target_indices = np.argsort(lex_scores + sem_scores)[::-1][:3]
                target_paths = [docs[i].path for i in top_target_indices if not docs[i].is_test]
                test_scores = engine.repo_graph.get_test_scores_for_target(target_paths)
                for idx, doc in enumerate(docs):
                    if doc.is_test:
                        wf_boost_graph[idx] = max(0.4, float(test_scores[idx]))
                        wf_boost_nograph[idx] = 0.4
                    else:
                        wf_boost_graph[idx] = -0.5
                        wf_boost_nograph[idx] = -0.5

            elif inferred_task == TaskType.EDIT2RIPPLE:
                anchors = query_obj.anchor_files or ([docs[int(np.argmax(lex_scores))].path] if len(lex_scores) > 0 else [])
                wf_boost_graph = engine.repo_graph.get_ripple_scores(anchors)
                wf_boost_nograph = np.zeros(num_docs, dtype=np.float32)

            # Dictionary to hold predictions for this sample across all 32 experiments
            sample_evaluations: Dict[str, Any] = {}

            # Evaluate each of the 16 ranking combinations
            for (a, b, c, d), exp_list in ranking_configs.items():
                if d == 1:
                    w_lex = router_weights["lexical"] if a else 0.0
                    w_sem = router_weights["semantic"] if b else 0.0
                    w_struct = router_weights["structural"] if c else 0.0
                    w_boost = router_weights["workflow_boost"]
                    wf_b = wf_boost_graph if c else wf_boost_nograph
                else:
                    active_sig = a + b + c
                    base_w = 1.0 / max(1, active_sig)
                    w_lex = base_w if a else 0.0
                    w_sem = base_w if b else 0.0
                    w_struct = base_w if c else 0.0
                    w_boost = 0.0
                    wf_b = np.zeros(num_docs, dtype=np.float32)

                fused = w_lex * lex_scores + w_sem * sem_scores + w_struct * struct_scores + w_boost * wf_b
                fused = np.maximum(0.0, fused)

                # Rank paths descending
                ranked_indices = np.argsort(-fused)
                ranked_paths = [docs[i].path for i in ranked_indices]

                # Convert to chunks for canonical sample_metrics
                ranked_chunks = []
                seen_p = set()
                for p in ranked_paths:
                    if p in path_to_chunks and p not in seen_p:
                        ranked_chunks.extend(path_to_chunks[p])
                        seen_p.add(p)
                for p, chs in path_to_chunks.items():
                    if p not in seen_p:
                        ranked_chunks.extend(chs)
                        seen_p.add(p)

                m = sample_metrics(gold, ranked_chunks, hard_negative_files=hard_neg)
                top_files = unique_ranked_paths(ranked_chunks)[:20]

                # BCY for full-files (E=0)
                bcy_full = {
                    b: pack_files(repo, base_commit, top_files, set(gold), corpus_cache, b)["bcy"]
                    for b in (4000, 8000, 16000, 32000)
                }

                # BCY with structural skeletons (E=1)
                # When skeletons are allowed: compute internal packing over top candidates
                # Candidates with scores:
                candidates_for_packing = [
                    (docs[i], float(fused[i]), {}) for i in ranked_indices[:50]
                ]
                # Packing under 4k, 8k, 16k, 32k budgets
                bcy_skel = {}
                for b in (4000, 8000, 16000, 32000):
                    packed_res = engine.budget_optimizer.pack_context(
                        candidate_files=candidates_for_packing,
                        budget_tokens=b,
                        query_terms=engine.tokenizer.tokenize_text(q_text),
                        allow_skeletons=True,
                    )
                    packed_paths = {sf.path for sf in packed_res}
                    covered = set(gold) & packed_paths
                    bcy_skel[b] = (len(covered) / len(gold)) if gold else 0.0

                # Store metrics for both E=1 and E=0 configurations
                for exp_id, name, e in exp_list:
                    bcy_eval = bcy_skel if e == 1 else bcy_full
                    sample_evaluations[exp_id] = {
                        "mrr": float(m["MRR"]),
                        "recall@5": float(m["Recall@5"]),
                        "recall@10": float(m["Recall@10"]),
                        "recall@20": float(m["Recall@20"]),
                        "bcy@4k": float(bcy_eval[4000]),
                        "bcy@8k": float(bcy_eval[8000]),
                        "bcy@16k": float(bcy_eval[16000]),
                        "bcy@32k": float(bcy_eval[32000]),
                        "top_files": top_files[:5],
                    }

            t_s1 = time.perf_counter()
            t_scoring_total += (t_s1 - t_s0)

            rec = {
                "sample_id": sample_id,
                "subset": s["_subset_name"],
                "task_type": task_type_str,
                "repo": repo,
                "base_commit": base_commit,
                "gold_files": gold,
                "evaluations": sample_evaluations,
            }
            per_sample_records.append(rec)
            with open(checkpoint_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        # Explicit GC
        del chunks, file_texts, docs, engine, path_to_chunks
        corpus_cache._cache.clear()
        import gc
        gc.collect()

    t_total = time.time() - t_start
    print(f"\n[DONE] Completed evaluation of all {len(per_sample_records)} samples across 32 configurations in {t_total:.1f}s.")

    # Save final raw predictions
    raw_pred_file = out_dir / "PER_SAMPLE_ABLATIONS.jsonl"
    with open(raw_pred_file, "w", encoding="utf-8") as f:
        for r in per_sample_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    return per_sample_records, t_total


if __name__ == "__main__":
    records, total_time = run_stage2_ablation()

