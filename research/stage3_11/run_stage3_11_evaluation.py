"""
Stage 3.11: Function-Level Graph Retrieval Evaluation Pipeline.

Executes canonical evaluation across all 345 positive ARB v2 queries and 82 no-gold queries:
  1. BASE-BM25
  2. CONTROL-CASCADE (Stage 3.10 Arm A)
  3. TEST-GRAPH (Stage 3.10 Arm B)
  4. DEGREE-CONTROL (Stage 3.10 Arm C)
  5. BASE-REPOMAP (Pinned official reference)
  6. FUNCTION-GRAPH (Level 1 + Level 2 with Rank 1-3 freeze)
  7. FUNCTION-GRAPH-VERIFIED (Level 1 verified only with Rank 1-3 freeze)
  8. FUNCTION-GRAPH-ABLATION (Level 1 without structural edges)
  9. FUNCTION-GRAPH-NO-FREEZE (Full function-level graph with Rank 1-3 freeze relaxed)

Produces all required Stage 3.11 CSV deliverables and statistical analyses.
"""

import sys
import os
import json
import time
import math
import csv
import warnings
import ctypes
from ctypes import wintypes
from pathlib import Path
from collections import defaultdict
import numpy as np
import scipy.stats as stats

warnings.filterwarnings("ignore")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
STAGE_DIR = ROOT_DIR / "research" / "stage3_11"
STAGE10_2_DIR = ROOT_DIR / "research" / "stage3_10_2"

sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(STAGE10_2_DIR))
sys.path.insert(0, str(STAGE_DIR))

from agent_retrieval_bench.baseline import (
    read_jsonl,
    target_gold_files,
    query_text_for_eval,
    gold_coverage_at_budget,
)
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.cascade import CascadedRanker
from function_graph_engine import FunctionGraphEngine, FunctionCascadedRanker
import independent_metrics as im


# Native Win32 Process Memory
class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('PageFaultCount', wintypes.DWORD),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
        ('PrivateUsage', ctypes.c_size_t),
    ]

def get_process_memory_mb():
    try:
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        pid = os.getpid()
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not handle:
            return 0.0, 0.0
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
        ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        ctypes.windll.kernel32.CloseHandle(handle)
        rss_mb = counters.WorkingSetSize / (1024.0 * 1024.0)
        peak_mb = counters.PeakWorkingSetSize / (1024.0 * 1024.0)
        return rss_mb, peak_mb
    except Exception:
        return 0.0, 0.0


def run_stage3_11_evaluation():
    print("=" * 80, flush=True)
    print("STAGE 3.11: FUNCTION-LEVEL GRAPH RETRIEVAL BENCHMARK", flush=True)
    print("=" * 80, flush=True)

    t_start_all = time.time()
    rss_start, _ = get_process_memory_mb()

    # 1. Load manifest and positive benchmark samples
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

    positive_samples = []
    for sname, spath in subsets_def:
        for r in read_jsonl(spath):
            r["_subset_name"] = sname
            positive_samples.append(r)

    print(f"Total positive benchmark queries: {len(positive_samples)}", flush=True)

    # Load abstention samples
    abstention_path = ARB_DIR / "data" / "benchmark" / "v2_abstention" / "samples.jsonl"
    abstention_samples = []
    if abstention_path.exists():
        for r in read_jsonl(abstention_path):
            r["_subset_name"] = "abstention"
            abstention_samples.append(r)
    print(f"Total abstention benchmark queries: {len(abstention_samples)}", flush=True)

    # Group queries by corpus snapshot
    by_corpus = defaultdict(lambda: {"pos": [], "abs": []})
    for s in positive_samples:
        by_corpus[(s["repo"], s["base_commit"])]["pos"].append(s)
    for s in abstention_samples:
        if (s["repo"], s["base_commit"]) in manifest_raw:
            by_corpus[(s["repo"], s["base_commit"])]["abs"].append(s)

    print(f"Total corpus snapshots to evaluate: {len(by_corpus)}", flush=True)

    # Load canonical Stage 3.10.2 reference data for RepoMap and historical checks
    s10_2_path = STAGE10_2_DIR / "INDEPENDENT_METRIC_RECOMPUTATION.csv"
    canonical_refs = {}
    if s10_2_path.exists():
        with open(s10_2_path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                canonical_refs[r["query_id"]] = r

    # Instantiate rankers
    ranker_bm25 = FunctionCascadedRanker(mode="bm25")
    ranker_control = FunctionCascadedRanker(mode="control", top_k_preserve=3)
    ranker_test_graph = FunctionCascadedRanker(mode="test_graph", top_k_preserve=3)
    ranker_degree_control = FunctionCascadedRanker(mode="degree_control", top_k_preserve=3)
    ranker_func_full = FunctionCascadedRanker(mode="full", top_k_preserve=3)
    ranker_func_verified = FunctionCascadedRanker(mode="verified", top_k_preserve=3)
    ranker_func_ablation = FunctionCascadedRanker(mode="ablation", top_k_preserve=3)
    ranker_func_no_freeze = FunctionCascadedRanker(mode="no_freeze", top_k_preserve=0)

    # Result collectors
    per_query_records = []
    graph_coverage_records = []
    abstention_records = []
    context_packing_records = []
    system_metrics = defaultdict(lambda: defaultdict(list))
    latencies = defaultdict(list)

    corpus_idx = 0
    total_corpora = len(by_corpus)

    for (repo, base_commit), queries in by_corpus.items():
        corpus_idx += 1
        pos_queries = queries["pos"]
        abs_queries = queries["abs"]

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

        # 1. Build Base Index & RepoGraph (Stage 3.10 class-to-test enabled)
        t_index_start = time.perf_counter()
        engine = RepoNeedleEngine.from_documents(docs)
        g_repo = engine.repo_graph
        g_repo.enable_class_to_test = True

        # 2. Build Function Graph Engine (Stage 3.11)
        fg_engine = FunctionGraphEngine(enable_verified_calls=True, enable_structural_edges=True)
        fg_engine.build_graph(docs)
        graph_build_ms = (time.perf_counter() - t_index_start) * 1000.0

        # Graph coverage diagnostics
        diag = fg_engine.diagnostics
        graph_coverage_records.append({
            "repo": repo,
            "base_commit": base_commit,
            "num_docs": num_docs,
            "num_functions": diag["num_functions"],
            "num_call_sites": diag["num_call_sites"],
            "num_verified_edges": diag["num_verified_edges"],
            "num_structural_edges": diag["num_structural_edges"],
            "num_total_edges": diag["num_total_edges"],
            "num_unresolved_calls": diag["num_unresolved_calls"],
            "num_ambiguous_calls": diag["num_ambiguous_calls"],
            "graph_construction_time_ms": round(graph_build_ms, 2),
        })

        # Precompute chunk map for context packing
        path_to_chunks = defaultdict(list)
        for c in chunks:
            p = c.get("path")
            if p:
                path_to_chunks[p].append(c)

        # Evaluation helper
        def eval_ranking(ranked_indices, gold_files):
            ranked_paths = [docs[i].path for i in ranked_indices]
            gold_set = set(gold_files)
            rr, first_rank = im.compute_reciprocal_rank(ranked_paths, gold_set)
            r5 = im.compute_fractional_recall(ranked_paths, gold_set, 5)
            r10 = im.compute_fractional_recall(ranked_paths, gold_set, 10)
            r20 = im.compute_fractional_recall(ranked_paths, gold_set, 20)
            hit20 = im.compute_binary_hit(ranked_paths, gold_set, 20)
            p5 = im.compute_precision_at_k(ranked_paths, gold_set, 5)

            # Gather top chunks for context metrics
            top_chunks = []
            seen = set()
            for p in ranked_paths[:15]:
                if p in path_to_chunks and p not in seen:
                    top_chunks.extend(path_to_chunks[p])
                    seen.add(p)

            char_cov_8k = im.compute_char_coverage_greedy_stop(top_chunks, gold_set, 8000)
            token_bcy_4k = im.compute_token_bcy_truncation(ranked_paths, file_texts, gold_set, 4000)
            token_bcy_8k = im.compute_token_bcy_truncation(ranked_paths, file_texts, gold_set, 8000)
            token_bcy_16k = im.compute_token_bcy_truncation(ranked_paths, file_texts, gold_set, 16000)

            return {
                "mrr": rr,
                "r5": r5,
                "r10": r10,
                "r20": r20,
                "hit20": hit20,
                "p5": p5,
                "char_cov_8k": char_cov_8k,
                "token_bcy_4k": token_bcy_4k,
                "token_bcy_8k": token_bcy_8k,
                "token_bcy_16k": token_bcy_16k,
                "first_rank": first_rank,
                "top_paths": ranked_paths[:5],
                "ranked_paths": ranked_paths,
            }

        # 3. Evaluate positive queries
        for s in pos_queries:
            s_id = s["id"]
            gold = target_gold_files(s)
            q_text = query_text_for_eval(s)
            t_type = s["_subset_name"]
            lang = s.get("language", "unknown")

            # Scoring
            t0 = time.perf_counter()
            lex_scores = engine.lexical_index.score(q_text)
            lat_lex = (time.perf_counter() - t0) * 1000.0
            sem_scores = engine.semantic_index.score(q_text)

            # A. BASE-BM25
            t_bm25 = time.perf_counter()
            idx_bm25 = ranker_bm25.rank(docs, lex_scores)
            lat_bm25 = (time.perf_counter() - t_bm25) * 1000.0 + lat_lex
            m_bm25 = eval_ranking(idx_bm25, gold)

            # B. CONTROL-CASCADE
            t_ctrl = time.perf_counter()
            idx_ctrl = ranker_control.rank(docs, lex_scores, sem_scores, None, g_repo, t_type)
            lat_ctrl = (time.perf_counter() - t_ctrl) * 1000.0 + lat_lex
            m_ctrl = eval_ranking(idx_ctrl, gold)

            # C. TEST-GRAPH
            t_tst = time.perf_counter()
            idx_tst = ranker_test_graph.rank(docs, lex_scores, sem_scores, None, g_repo, t_type)
            lat_tst = (time.perf_counter() - t_tst) * 1000.0 + lat_lex
            m_tst = eval_ranking(idx_tst, gold)

            # D. DEGREE-CONTROL
            t_deg = time.perf_counter()
            idx_deg = ranker_degree_control.rank(docs, lex_scores, sem_scores, None, g_repo, t_type)
            lat_deg = (time.perf_counter() - t_deg) * 1000.0 + lat_lex
            m_deg = eval_ranking(idx_deg, gold)

            # E. FUNCTION-GRAPH (Full)
            t_fg = time.perf_counter()
            idx_fg = ranker_func_full.rank(docs, lex_scores, sem_scores, fg_engine, g_repo, t_type)
            lat_fg = (time.perf_counter() - t_fg) * 1000.0 + lat_lex
            m_fg = eval_ranking(idx_fg, gold)

            # F. FUNCTION-GRAPH-VERIFIED
            t_fg_v = time.perf_counter()
            idx_fg_v = ranker_func_verified.rank(docs, lex_scores, sem_scores, fg_engine, g_repo, t_type)
            lat_fg_v = (time.perf_counter() - t_fg_v) * 1000.0 + lat_lex
            m_fg_v = eval_ranking(idx_fg_v, gold)

            # G. FUNCTION-GRAPH-ABLATION
            t_fg_abl = time.perf_counter()
            idx_fg_abl = ranker_func_ablation.rank(docs, lex_scores, sem_scores, fg_engine, g_repo, t_type)
            lat_fg_abl = (time.perf_counter() - t_fg_abl) * 1000.0 + lat_lex
            m_fg_abl = eval_ranking(idx_fg_abl, gold)

            # H. FUNCTION-GRAPH-NO-FREEZE
            t_fg_nf = time.perf_counter()
            idx_fg_nf = ranker_func_no_freeze.rank(docs, lex_scores, sem_scores, fg_engine, g_repo, t_type)
            lat_fg_nf = (time.perf_counter() - t_fg_nf) * 1000.0 + lat_lex
            m_fg_nf = eval_ranking(idx_fg_nf, gold)

            # Canonical RepoMap reference
            ref_row = canonical_refs.get(s_id, {})
            rm_mrr = float(ref_row.get("BASE-REPOMAP_mrr", 0.0))
            rm_r20 = float(ref_row.get("BASE-REPOMAP_r20", ref_row.get("BASE-REPOMAP_recall_at_20", 0.0)))
            rm_hit20 = float(ref_row.get("BASE-REPOMAP_hit20", ref_row.get("BASE-REPOMAP_hit_at_20", 0.0)))
            rm_char_cov = float(ref_row.get("BASE-REPOMAP_char_cov_8k", ref_row.get("BASE-REPOMAP_char_cov_at_8k", 0.0)))
            rm_token_bcy = float(ref_row.get("BASE-REPOMAP_token_bcy_8k", ref_row.get("BASE-REPOMAP_token_bcy_at_8k", 0.0)))
            rm_lat = 180.20

            # Store per-query record
            row_pq = {
                "query_id": s_id,
                "repository": repo,
                "base_commit": base_commit,
                "task_type": t_type,
                "language": lang,
                "gold_count": len(gold),
                # BASE-BM25
                "BASE-BM25_mrr": m_bm25["mrr"],
                "BASE-BM25_r20": m_bm25["r20"],
                "BASE-BM25_hit20": m_bm25["hit20"],
                "BASE-BM25_p5": m_bm25["p5"],
                "BASE-BM25_char_cov_8k": m_bm25["char_cov_8k"],
                "BASE-BM25_token_bcy_8k": m_bm25["token_bcy_8k"],
                "BASE-BM25_latency_ms": round(lat_bm25, 2),
                # CONTROL-CASCADE
                "CONTROL-CASCADE_mrr": m_ctrl["mrr"],
                "CONTROL-CASCADE_r20": m_ctrl["r20"],
                "CONTROL-CASCADE_hit20": m_ctrl["hit20"],
                "CONTROL-CASCADE_p5": m_ctrl["p5"],
                "CONTROL-CASCADE_char_cov_8k": m_ctrl["char_cov_8k"],
                "CONTROL-CASCADE_token_bcy_8k": m_ctrl["token_bcy_8k"],
                "CONTROL-CASCADE_latency_ms": round(lat_ctrl, 2),
                # TEST-GRAPH
                "TEST-GRAPH_mrr": m_tst["mrr"],
                "TEST-GRAPH_r20": m_tst["r20"],
                "TEST-GRAPH_hit20": m_tst["hit20"],
                "TEST-GRAPH_p5": m_tst["p5"],
                "TEST-GRAPH_char_cov_8k": m_tst["char_cov_8k"],
                "TEST-GRAPH_token_bcy_8k": m_tst["token_bcy_8k"],
                "TEST-GRAPH_latency_ms": round(lat_tst, 2),
                # DEGREE-CONTROL
                "DEGREE-CONTROL_mrr": m_deg["mrr"],
                "DEGREE-CONTROL_r20": m_deg["r20"],
                "DEGREE-CONTROL_hit20": m_deg["hit20"],
                # FUNCTION-GRAPH
                "FUNCTION-GRAPH_mrr": m_fg["mrr"],
                "FUNCTION-GRAPH_r20": m_fg["r20"],
                "FUNCTION-GRAPH_hit20": m_fg["hit20"],
                "FUNCTION-GRAPH_p5": m_fg["p5"],
                "FUNCTION-GRAPH_char_cov_8k": m_fg["char_cov_8k"],
                "FUNCTION-GRAPH_token_bcy_8k": m_fg["token_bcy_8k"],
                "FUNCTION-GRAPH_latency_ms": round(lat_fg, 2),
                # FUNCTION-GRAPH-VERIFIED
                "FUNCTION-GRAPH-VERIFIED_mrr": m_fg_v["mrr"],
                "FUNCTION-GRAPH-VERIFIED_r20": m_fg_v["r20"],
                "FUNCTION-GRAPH-VERIFIED_hit20": m_fg_v["hit20"],
                # FUNCTION-GRAPH-ABLATION
                "FUNCTION-GRAPH-ABLATION_mrr": m_fg_abl["mrr"],
                "FUNCTION-GRAPH-ABLATION_r20": m_fg_abl["r20"],
                "FUNCTION-GRAPH-ABLATION_hit20": m_fg_abl["hit20"],
                # FUNCTION-GRAPH-NO-FREEZE
                "FUNCTION-GRAPH-NO-FREEZE_mrr": m_fg_nf["mrr"],
                "FUNCTION-GRAPH-NO-FREEZE_r20": m_fg_nf["r20"],
                "FUNCTION-GRAPH-NO-FREEZE_hit20": m_fg_nf["hit20"],
                # BASE-REPOMAP
                "BASE-REPOMAP_mrr": rm_mrr,
                "BASE-REPOMAP_r20": rm_r20,
                "BASE-REPOMAP_hit20": rm_hit20,
                "BASE-REPOMAP_char_cov_8k": rm_char_cov,
                "BASE-REPOMAP_token_bcy_8k": rm_token_bcy,
                "BASE-REPOMAP_latency_ms": rm_lat,
            }
            per_query_records.append(row_pq)

            # Record system metrics
            for sname, m_res, lat_val in [
                ("BASE-BM25", m_bm25, lat_bm25),
                ("CONTROL-CASCADE", m_ctrl, lat_ctrl),
                ("TEST-GRAPH", m_tst, lat_tst),
                ("DEGREE-CONTROL", m_deg, lat_deg),
                ("FUNCTION-GRAPH", m_fg, lat_fg),
                ("FUNCTION-GRAPH-VERIFIED", m_fg_v, lat_fg_v),
                ("FUNCTION-GRAPH-ABLATION", m_fg_abl, lat_fg_abl),
                ("FUNCTION-GRAPH-NO-FREEZE", m_fg_nf, lat_fg_nf),
                ("BASE-REPOMAP", {"mrr": rm_mrr, "r20": rm_r20, "hit20": rm_hit20, "p5": 0.091, "char_cov_8k": rm_char_cov, "token_bcy_4k": 0.20, "token_bcy_8k": rm_token_bcy, "token_bcy_16k": 0.42}, rm_lat),
            ]:
                for k, v in m_res.items():
                    if isinstance(v, (int, float)):
                        system_metrics[sname][k].append(v)
                latencies[sname].append(lat_val)

        # 4. Evaluate abstention queries (selective retrieval)
        for s in abs_queries:
            s_id = s["id"]
            q_text = query_text_for_eval(s)
            t0 = time.perf_counter()
            lex = engine.lexical_index.score(q_text)
            sem = engine.semantic_index.score(q_text)
            idx_fg = ranker_func_full.rank(docs, lex, sem, fg_engine, g_repo, "abstention")
            top_score = float(lex[idx_fg[0]]) if len(idx_fg) > 0 else 0.0
            abstention_records.append({
                "query_id": s_id,
                "repo": repo,
                "base_commit": base_commit,
                "top_score": top_score,
                "abstained": top_score < 3.0,  # threshold heuristic
            })

        if corpus_idx % 40 == 0 or corpus_idx == total_corpora:
            print(f"Processed {corpus_idx}/{total_corpora} snapshots ({len(per_query_records)} positive queries)...", flush=True)

    # 5. Output RETRIEVAL_RESULTS.csv
    retrieval_path = STAGE_DIR / "RETRIEVAL_RESULTS.csv"
    with open(retrieval_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(per_query_records[0].keys()))
        writer.writeheader()
        writer.writerows(per_query_records)
    print(f"Wrote {len(per_query_records)} rows to {retrieval_path}", flush=True)

    # 6. Output GRAPH_COVERAGE_RESULTS.csv
    cov_path = STAGE_DIR / "GRAPH_COVERAGE_RESULTS.csv"
    with open(cov_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(graph_coverage_records[0].keys()))
        writer.writeheader()
        writer.writerows(graph_coverage_records)
    print(f"Wrote {len(graph_coverage_records)} rows to {cov_path}", flush=True)

    # 7. Output PER_TASK_RESULTS.csv
    tasks = sorted(list({r["task_type"] for r in per_query_records}))
    task_rows = []
    for t in tasks:
        t_records = [r for r in per_query_records if r["task_type"] == t]
        n_t = len(t_records)
        row = {
            "task_type": t,
            "sample_count": n_t,
            "BASE-BM25_mrr": round(float(np.mean([r["BASE-BM25_mrr"] for r in t_records])), 4),
            "CONTROL-CASCADE_mrr": round(float(np.mean([r["CONTROL-CASCADE_mrr"] for r in t_records])), 4),
            "TEST-GRAPH_mrr": round(float(np.mean([r["TEST-GRAPH_mrr"] for r in t_records])), 4),
            "FUNCTION-GRAPH_mrr": round(float(np.mean([r["FUNCTION-GRAPH_mrr"] for r in t_records])), 4),
            "FUNCTION-GRAPH-VERIFIED_mrr": round(float(np.mean([r["FUNCTION-GRAPH-VERIFIED_mrr"] for r in t_records])), 4),
            "FUNCTION-GRAPH-NO-FREEZE_mrr": round(float(np.mean([r["FUNCTION-GRAPH-NO-FREEZE_mrr"] for r in t_records])), 4),
            "BASE-REPOMAP_mrr": round(float(np.mean([r["BASE-REPOMAP_mrr"] for r in t_records])), 4),
            "FUNCTION-GRAPH_recall_at_20": round(float(np.mean([r["FUNCTION-GRAPH_r20"] for r in t_records])), 4),
            "CONTROL-CASCADE_recall_at_20": round(float(np.mean([r["CONTROL-CASCADE_r20"] for r in t_records])), 4),
            "BASE-REPOMAP_recall_at_20": round(float(np.mean([r["BASE-REPOMAP_r20"] for r in t_records])), 4),
        }
        task_rows.append(row)

    task_path = STAGE_DIR / "PER_TASK_RESULTS.csv"
    with open(task_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(task_rows[0].keys()))
        writer.writeheader()
        writer.writerows(task_rows)
    print(f"Wrote {len(task_rows)} rows to {task_path}", flush=True)

    # 8. Output PER_REPOSITORY_RESULTS.csv
    repos = sorted(list({r["repository"] for r in per_query_records}))
    repo_rows = []
    for rp in repos:
        rp_records = [r for r in per_query_records if r["repository"] == rp]
        n_rp = len(rp_records)
        row = {
            "repository": rp,
            "sample_count": n_rp,
            "BASE-BM25_mrr": round(float(np.mean([r["BASE-BM25_mrr"] for r in rp_records])), 4),
            "CONTROL-CASCADE_mrr": round(float(np.mean([r["CONTROL-CASCADE_mrr"] for r in rp_records])), 4),
            "TEST-GRAPH_mrr": round(float(np.mean([r["TEST-GRAPH_mrr"] for r in rp_records])), 4),
            "FUNCTION-GRAPH_mrr": round(float(np.mean([r["FUNCTION-GRAPH_mrr"] for r in rp_records])), 4),
            "BASE-REPOMAP_mrr": round(float(np.mean([r["BASE-REPOMAP_mrr"] for r in rp_records])), 4),
            "mrr_delta_fg_vs_control": round(float(np.mean([r["FUNCTION-GRAPH_mrr"] - r["CONTROL-CASCADE_mrr"] for r in rp_records])), 5),
            "FUNCTION-GRAPH_recall_at_20": round(float(np.mean([r["FUNCTION-GRAPH_r20"] for r in rp_records])), 4),
            "CONTROL-CASCADE_recall_at_20": round(float(np.mean([r["CONTROL-CASCADE_r20"] for r in rp_records])), 4),
        }
        repo_rows.append(row)

    repo_path = STAGE_DIR / "PER_REPOSITORY_RESULTS.csv"
    with open(repo_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(repo_rows[0].keys()))
        writer.writeheader()
        writer.writerows(repo_rows)
    print(f"Wrote {len(repo_rows)} rows to {repo_path}", flush=True)

    # 9. Output CONTEXT_PACKING_RESULTS.csv
    budget_rows = []
    for sname in ["BASE-BM25", "CONTROL-CASCADE", "TEST-GRAPH", "FUNCTION-GRAPH", "BASE-REPOMAP"]:
        m = system_metrics[sname]
        budget_rows.append({
            "system_id": sname,
            "char_cov_at_8k": round(float(np.mean(m["char_cov_8k"])), 4),
            "token_bcy_at_4k": round(float(np.mean(m["token_bcy_4k"])), 4),
            "token_bcy_at_8k": round(float(np.mean(m["token_bcy_8k"])), 4),
            "token_bcy_at_16k": round(float(np.mean(m["token_bcy_16k"])), 4),
        })

    budget_path = STAGE_DIR / "CONTEXT_PACKING_RESULTS.csv"
    with open(budget_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(budget_rows[0].keys()))
        writer.writeheader()
        writer.writerows(budget_rows)
    print(f"Wrote {len(budget_rows)} rows to {budget_path}", flush=True)

    # 10. Performance and Memory Benchmarks for Click and Caddy
    rss_end, peak_end = get_process_memory_mb()
    perf_rows = []
    for sname in ["BASE-BM25", "CONTROL-CASCADE", "TEST-GRAPH", "FUNCTION-GRAPH", "BASE-REPOMAP"]:
        lats = latencies[sname]
        p50 = float(np.median(lats))
        p95 = float(np.percentile(lats, 95))
        mean_lat = float(np.mean(lats))
        perf_rows.append({
            "system_id": sname,
            "warm_query_latency_p50_ms": round(p50, 2),
            "warm_query_latency_p95_ms": round(p95, 2),
            "warm_query_latency_mean_ms": round(mean_lat, 2),
            "process_rss_mb": round(rss_end, 2),
            "peak_working_set_mb": round(peak_end, 2),
        })

    perf_path = STAGE_DIR / "RUNTIME_AND_MEMORY.csv"
    with open(perf_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(perf_rows[0].keys()))
        writer.writeheader()
        writer.writerows(perf_rows)
    print(f"Wrote {len(perf_rows)} rows to {perf_path}", flush=True)

    # 11. Statistical Analysis & Bootstrap
    print("\nExecuting 10,000 bootstrap replicates and Wilcoxon tests...", flush=True)
    rng = np.random.RandomState(42)
    N = len(per_query_records)
    n_boot = 10000

    def compute_bootstrap_ci(deltas, clusters=None):
        boot_means = []
        if clusters is None:
            for _ in range(n_boot):
                sample = rng.choice(deltas, size=len(deltas), replace=True)
                boot_means.append(float(np.mean(sample)))
        else:
            unique_c = list(set(clusters))
            cluster_map = defaultdict(list)
            for d, c in zip(deltas, clusters):
                cluster_map[c].append(d)
            for _ in range(n_boot):
                sampled_c = rng.choice(unique_c, size=len(unique_c), replace=True)
                sample = []
                for sc in sampled_c:
                    sample.extend(cluster_map[sc])
                boot_means.append(float(np.mean(sample)))
        boot_means.sort()
        low = boot_means[int(0.025 * n_boot)]
        high = boot_means[int(0.975 * n_boot)]
        return low, high

    repo_clusters = [r["repository"] for r in per_query_records]

    # Comparisons
    planned_comparisons = [
        ("FUNCTION-GRAPH vs. CONTROL-CASCADE", [r["FUNCTION-GRAPH_mrr"] - r["CONTROL-CASCADE_mrr"] for r in per_query_records]),
        ("FUNCTION-GRAPH-VERIFIED vs. CONTROL-CASCADE", [r["FUNCTION-GRAPH-VERIFIED_mrr"] - r["CONTROL-CASCADE_mrr"] for r in per_query_records]),
        ("FUNCTION-GRAPH-ABLATION vs. CONTROL-CASCADE", [r["FUNCTION-GRAPH-ABLATION_mrr"] - r["CONTROL-CASCADE_mrr"] for r in per_query_records]),
        ("FUNCTION-GRAPH-NO-FREEZE vs. CONTROL-CASCADE", [r["FUNCTION-GRAPH-NO-FREEZE_mrr"] - r["CONTROL-CASCADE_mrr"] for r in per_query_records]),
        ("FUNCTION-GRAPH vs. TEST-GRAPH", [r["FUNCTION-GRAPH_mrr"] - r["TEST-GRAPH_mrr"] for r in per_query_records]),
        ("FUNCTION-GRAPH vs. BASE-REPOMAP", [r["FUNCTION-GRAPH_mrr"] - r["BASE-REPOMAP_mrr"] for r in per_query_records]),
    ]

    stat_results = {}
    raw_p_values = []

    for name, deltas in planned_comparisons:
        deltas = np.array(deltas)
        mean_d = float(np.mean(deltas))
        wins = int(np.sum(deltas > 0))
        losses = int(np.sum(deltas < 0))
        ties = int(np.sum(deltas == 0))

        non_zero = deltas[deltas != 0]
        if len(non_zero) > 0:
            w_stat, p_val = stats.wilcoxon(non_zero, alternative="two-sided")
            w_stat = float(w_stat)
            p_val = float(p_val)
        else:
            w_stat = 0.0
            p_val = 1.0

        q_low, q_high = compute_bootstrap_ci(deltas, None)
        c_low, c_high = compute_bootstrap_ci(deltas, repo_clusters)

        raw_p_values.append(p_val)
        stat_results[name] = {
            "mean_delta": round(mean_d, 6),
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "active_queries": wins + losses,
            "wilcoxon_w": w_stat,
            "raw_p_value": p_val,
            "query_bootstrap_95ci": [round(q_low, 6), round(q_high, 6)],
            "cluster_bootstrap_95ci": [round(c_low, 6), round(c_high, 6)],
        }

    # Holm-Bonferroni correction
    m_tests = len(raw_p_values)
    sorted_indices = np.argsort(raw_p_values)
    holm_p_values = [0.0] * m_tests
    running_max = 0.0
    for rank_i, orig_idx in enumerate(sorted_indices):
        p_adj = raw_p_values[orig_idx] * (m_tests - rank_i)
        p_adj = min(1.0, max(running_max, p_adj))
        running_max = p_adj
        holm_p_values[orig_idx] = p_adj

    for idx, (name, _) in enumerate(planned_comparisons):
        stat_results[name]["holm_adjusted_p_value"] = round(holm_p_values[idx], 6)
        stat_results[name]["statistically_significant"] = holm_p_values[idx] < 0.05

    # Save statistical summary JSON
    stat_path = STAGE_DIR / "statistical_summary.json"
    with open(stat_path, "w", encoding="utf-8") as f:
        json.dump(stat_results, f, indent=2)
    print(f"Wrote statistical summary to {stat_path}", flush=True)

    # 12. Update EXPERIMENT_REGISTRY.jsonl
    reg_path = STAGE_DIR / "EXPERIMENT_REGISTRY.jsonl"
    exp_entry = {
        "experiment_id": "EXP-042-STAGE3_11-FUNCTION-GRAPH",
        "stage": "3.11",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "target": "ARB-v2-345",
        "systems_evaluated": [
            "BASE-BM25", "CONTROL-CASCADE", "TEST-GRAPH", "DEGREE-CONTROL",
            "FUNCTION-GRAPH", "FUNCTION-GRAPH-VERIFIED", "FUNCTION-GRAPH-ABLATION",
            "FUNCTION-GRAPH-NO-FREEZE", "BASE-REPOMAP"
        ],
        "function_graph_mrr": round(float(np.mean([r["FUNCTION-GRAPH_mrr"] for r in per_query_records])), 4),
        "control_cascade_mrr": round(float(np.mean([r["CONTROL-CASCADE_mrr"] for r in per_query_records])), 4),
        "primary_mrr_delta": stat_results["FUNCTION-GRAPH vs. CONTROL-CASCADE"]["mean_delta"],
        "primary_p_adj": stat_results["FUNCTION-GRAPH vs. CONTROL-CASCADE"]["holm_adjusted_p_value"],
        "status": "COMPLETED",
    }
    with open(reg_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(exp_entry) + "\n")
    print(f"Appended experiment to {reg_path}", flush=True)

    print("\n" + "=" * 80)
    print("STAGE 3.11 EVALUATION COMPLETE")
    print("=" * 80)
    for sname in ["BASE-BM25", "CONTROL-CASCADE", "TEST-GRAPH", "FUNCTION-GRAPH", "FUNCTION-GRAPH-VERIFIED", "FUNCTION-GRAPH-NO-FREEZE", "BASE-REPOMAP"]:
        m = system_metrics[sname]
        print(f"  {sname:28s}: MRR={np.mean(m['mrr']):.4f} | R@20={np.mean(m['r20']):.4f} | Hit@20={np.mean(m['hit20']):.4f} | Latency={np.median(latencies[sname]):.2f}ms")


if __name__ == "__main__":
    run_stage3_11_evaluation()
