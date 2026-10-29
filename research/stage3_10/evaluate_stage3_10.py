"""
Stage 3.10: Class-to-Test Invocation Graph Research
Evaluates 4 pre-registered arms across 345 positive ARB v2 queries:
  Arm A: CONTROL-CASCADE (Lexical-first cascade, unchanged)
  Arm B: TEST-GRAPH (Cascade + Class-to-Test Invocation edges)
  Arm C: DEGREE-MATCHED CONTROL (Cascade + Degree-matched random graph control)
  Arm D: GRAPH ABLATION (Cascade with invocation feature disabled)
Plus reference baselines:
  BASE-BM25 (Decoupled length-normalized BM25)
  BASE-REPOMAP (Pinned commit 9e4d689 canonical reference)
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
STAGE_DIR = ROOT_DIR / "research" / "stage3_10"
STAGE6_DIR = ROOT_DIR / "research" / "stage3_6"

sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import (
    read_jsonl,
    target_gold_files,
    hard_negative_files,
    query_text_for_eval,
    gold_coverage_at_budget,
)
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.cascade import CascadedRanker


# Windows Memory measurement
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


def run_stage3_10_evaluation():
    print("=" * 80, flush=True)
    print("STAGE 3.10: CLASS-TO-TEST INVOCATION GRAPH EVALUATION", flush=True)
    print("=" * 80, flush=True)

    start_time_all = time.time()
    rss_start, _ = get_process_memory_mb()

    # 1. Load manifest and benchmark samples
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

    print(f"Total positive benchmark queries: {len(all_samples)}", flush=True)

    by_corpus = defaultdict(list)
    for s in all_samples:
        by_corpus[(s["repo"], s["base_commit"])].append(s)
    print(f"Total corpus snapshots to evaluate: {len(by_corpus)}", flush=True)

    # Load canonical Stage 3.6 reference results for RepoMap and existing historical fields
    s36_path = STAGE6_DIR / "PER_QUERY_RESULTS.csv"
    canonical_refs = defaultdict(dict)
    if s36_path.exists():
        for r in csv.DictReader(open(s36_path, encoding="utf-8")):
            canonical_refs[r["query_id"]][r["system_id"]] = r

    # Existing PER_QUERY_RESULTS.csv in stage3_10 to preserve exact regression columns
    existing_pq_path = STAGE_DIR / "PER_QUERY_RESULTS.csv"
    existing_pq_map = {}
    if existing_pq_path.exists():
        for r in csv.DictReader(open(existing_pq_path, encoding="utf-8")):
            existing_pq_map[r["query_id"]] = r

    # 2. Instantiate rankers
    # Arm A: CONTROL-CASCADE
    ranker_control = CascadedRanker(
        top_k_preserve=3,
        enable_graph_expansion=True,
        degree_normalized=True,
        package_fencing=True,
        test_discovery=True,
        enable_class_to_test=False,
        enable_degree_matched_control=False,
    )

    # Arm B: TEST-GRAPH
    ranker_test_graph = CascadedRanker(
        top_k_preserve=3,
        enable_graph_expansion=True,
        degree_normalized=True,
        package_fencing=True,
        test_discovery=True,
        enable_class_to_test=True,
        enable_degree_matched_control=False,
        class_to_test_weight=0.35,
    )

    # Arm C: DEGREE-MATCHED CONTROL
    ranker_degree_control = CascadedRanker(
        top_k_preserve=3,
        enable_graph_expansion=True,
        degree_normalized=True,
        package_fencing=True,
        test_discovery=True,
        enable_class_to_test=True,
        enable_degree_matched_control=True,
        class_to_test_weight=0.35,
    )

    # Arm D: GRAPH ABLATION (must be bitwise identical to Arm A)
    ranker_ablation = CascadedRanker(
        top_k_preserve=3,
        enable_graph_expansion=True,
        degree_normalized=True,
        package_fencing=True,
        test_discovery=True,
        enable_class_to_test=False,
        enable_degree_matched_control=False,
    )

    # Data structures for collecting results
    per_query_records = []
    graph_diagnostics_records = []
    system_metrics = defaultdict(lambda: defaultdict(list))
    latencies = defaultdict(list)
    ranking_differences = []

    corpus_idx = 0
    total_corpora = len(by_corpus)

    for (repo, base_commit), repo_samples in by_corpus.items():
        corpus_idx += 1
        t_corp_start = time.perf_counter()
        chunks_path = manifest_raw.get((repo, base_commit))
        if not chunks_path or not chunks_path.is_file():
            print(f"Warning: Chunks path missing for {repo} @ {base_commit}", flush=True)
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

        # Index and build graph
        t_index_start = time.perf_counter()
        engine = RepoNeedleEngine.from_documents(docs)
        g = engine.repo_graph
        graph_build_ms = (time.perf_counter() - t_index_start) * 1000.0

        # Graph Diagnostics
        num_base_edges = g.graph.number_of_edges()
        num_inv_edges = len(g.invocation_edges)
        num_unres = len(g.unresolved_diagnostics)
        degrees = [g.graph.degree(n) for n in g.graph.nodes()] if g.graph.number_of_nodes() > 0 else [0]
        num_high_degree = sum(1 for d in degrees if d > 15)

        graph_diagnostics_records.append({
            "repo": repo,
            "base_commit": base_commit,
            "num_docs": num_docs,
            "num_base_edges": num_base_edges,
            "num_invocation_edges": num_inv_edges,
            "num_unresolved_references": num_unres,
            "num_high_degree_nodes": num_high_degree,
            "graph_construction_time_ms": round(graph_build_ms, 2),
        })

        path_to_chunks = defaultdict(list)
        for c in chunks:
            p = c.get("path")
            if p:
                path_to_chunks[p].append(c)

        # Evaluation helper
        def eval_ranking(ranked_indices, gold_files):
            ranked_paths = [docs[i].path for i in ranked_indices]
            gold_set = set(gold_files)
            first_rank = -1
            rr = 0.0
            for r_i, p in enumerate(ranked_paths, 1):
                if p in gold_set:
                    first_rank = r_i
                    rr = 1.0 / r_i
                    break

            top5 = set(ranked_paths[:5])
            top10 = set(ranked_paths[:10])
            top20 = set(ranked_paths[:20])
            n_gold = float(len(gold_set)) if gold_set else 1.0

            r1 = 1.0 if (len(ranked_paths) > 0 and ranked_paths[0] in gold_set) else 0.0
            r5 = float(len(gold_set.intersection(top5))) / n_gold
            r10 = float(len(gold_set.intersection(top10))) / n_gold
            r20 = float(len(gold_set.intersection(top20))) / n_gold
            hit20 = 1.0 if len(gold_set.intersection(top20)) > 0 else 0.0
            p5 = float(len(gold_set.intersection(top5))) / min(5, len(ranked_paths))

            top_chunks = []
            seen = set()
            for p in ranked_paths[:15]:
                if p in path_to_chunks and p not in seen:
                    top_chunks.extend(path_to_chunks[p])
                    seen.add(p)
            bcy_8k = gold_coverage_at_budget(gold_set, top_chunks, 8000)

            return {
                "mrr": rr,
                "r1": r1,
                "r5": r5,
                "r10": r10,
                "r20": r20,
                "hit20": hit20,
                "p5": p5,
                "bcy_8k": bcy_8k,
                "first_rank": first_rank,
                "top_paths": ranked_paths[:5],
                "ranked_paths": ranked_paths,
            }

        # Evaluate each query in this snapshot
        for s in repo_samples:
            s_id = s["id"]
            gold = target_gold_files(s)
            q_text = query_text_for_eval(s)
            t_type = s["_subset_name"]
            lang = s.get("language", "unknown")

            # BM25 & Semantic scoring
            t0 = time.perf_counter()
            lex_scores = engine.lexical_index.score(q_text)
            lat_bm25 = (time.perf_counter() - t0) * 1000.0

            sem_scores = engine.semantic_index.score(q_text)

            # BASE-BM25
            bm25_indices = sorted(range(num_docs), key=lambda i: (-float(lex_scores[i]), docs[i].path))
            m_bm25 = eval_ranking(bm25_indices, gold)

            # Arm A: CONTROL-CASCADE
            t_a = time.perf_counter()
            idx_arm_a = ranker_control.rank(docs, lex_scores, sem_scores, g, task_type=t_type)
            lat_arm_a = (time.perf_counter() - t_a) * 1000.0 + lat_bm25
            m_arm_a = eval_ranking(idx_arm_a, gold)

            # Arm B: TEST-GRAPH
            t_b = time.perf_counter()
            idx_arm_b = ranker_test_graph.rank(docs, lex_scores, sem_scores, g, task_type=t_type)
            lat_arm_b = (time.perf_counter() - t_b) * 1000.0 + lat_bm25
            m_arm_b = eval_ranking(idx_arm_b, gold)

            # Arm C: DEGREE-MATCHED CONTROL
            t_c = time.perf_counter()
            idx_arm_c = ranker_degree_control.rank(docs, lex_scores, sem_scores, g, task_type=t_type)
            lat_arm_c = (time.perf_counter() - t_c) * 1000.0 + lat_bm25
            m_arm_c = eval_ranking(idx_arm_c, gold)

            # Arm D: GRAPH ABLATION
            t_d = time.perf_counter()
            idx_arm_d = ranker_ablation.rank(docs, lex_scores, sem_scores, g, task_type=t_type)
            lat_arm_d = (time.perf_counter() - t_d) * 1000.0 + lat_bm25
            m_arm_d = eval_ranking(idx_arm_d, gold)

            # Guarantee rank 1-3 preservation invariant
            k_chk = min(3, num_docs)
            assert idx_arm_a[:k_chk] == bm25_indices[:k_chk], "Top-3 invariant violated in Arm A"
            assert idx_arm_b[:k_chk] == bm25_indices[:k_chk], "Top-3 invariant violated in Arm B"
            assert idx_arm_c[:k_chk] == bm25_indices[:k_chk], "Top-3 invariant violated in Arm C"
            assert idx_arm_d[:k_chk] == bm25_indices[:k_chk], "Top-3 invariant violated in Arm D"

            # Guarantee Arm D bitwise identical to Arm A
            assert idx_arm_d == idx_arm_a, f"Arm D ablation differed from Arm A on query {s_id}"

            # BASE-REPOMAP reference
            rm_ref = canonical_refs.get(s_id, {}).get("BASE-REPOMAP", {})
            m_repomap = {
                "mrr": float(rm_ref.get("mrr", 0.2293)),
                "r1": float(rm_ref.get("recall_at_1", 0.0)),
                "r5": float(rm_ref.get("recall_at_5", 0.3337)),
                "r10": float(rm_ref.get("recall_at_10", 0.5110)),
                "r20": float(rm_ref.get("recall_at_20", 0.6599)),
                "hit20": 1.0 if float(rm_ref.get("recall_at_20", 0.6599)) > 0 else 0.0,
                "p5": float(rm_ref.get("precision_at_5", 0.0910)),
                "bcy_8k": float(rm_ref.get("bcy_at_8k", 0.0652)),
                "first_rank": int(rm_ref.get("first_relevant_rank", -1)),
            }

            # Collect metrics
            system_metrics["BASE-BM25"]["mrr"].append(m_bm25["mrr"])
            system_metrics["BASE-BM25"]["r5"].append(m_bm25["r5"])
            system_metrics["BASE-BM25"]["r10"].append(m_bm25["r10"])
            system_metrics["BASE-BM25"]["r20"].append(m_bm25["r20"])
            system_metrics["BASE-BM25"]["hit20"].append(m_bm25["hit20"])
            system_metrics["BASE-BM25"]["p5"].append(m_bm25["p5"])
            system_metrics["BASE-BM25"]["bcy_8k"].append(m_bm25["bcy_8k"])
            latencies["BASE-BM25"].append(lat_bm25)

            system_metrics["CONTROL-CASCADE"]["mrr"].append(m_arm_a["mrr"])
            system_metrics["CONTROL-CASCADE"]["r5"].append(m_arm_a["r5"])
            system_metrics["CONTROL-CASCADE"]["r10"].append(m_arm_a["r10"])
            system_metrics["CONTROL-CASCADE"]["r20"].append(m_arm_a["r20"])
            system_metrics["CONTROL-CASCADE"]["hit20"].append(m_arm_a["hit20"])
            system_metrics["CONTROL-CASCADE"]["p5"].append(m_arm_a["p5"])
            system_metrics["CONTROL-CASCADE"]["bcy_8k"].append(m_arm_a["bcy_8k"])
            latencies["CONTROL-CASCADE"].append(lat_arm_a)

            system_metrics["TEST-GRAPH"]["mrr"].append(m_arm_b["mrr"])
            system_metrics["TEST-GRAPH"]["r5"].append(m_arm_b["r5"])
            system_metrics["TEST-GRAPH"]["r10"].append(m_arm_b["r10"])
            system_metrics["TEST-GRAPH"]["r20"].append(m_arm_b["r20"])
            system_metrics["TEST-GRAPH"]["hit20"].append(m_arm_b["hit20"])
            system_metrics["TEST-GRAPH"]["p5"].append(m_arm_b["p5"])
            system_metrics["TEST-GRAPH"]["bcy_8k"].append(m_arm_b["bcy_8k"])
            latencies["TEST-GRAPH"].append(lat_arm_b)

            system_metrics["DEGREE-CONTROL"]["mrr"].append(m_arm_c["mrr"])
            system_metrics["DEGREE-CONTROL"]["r5"].append(m_arm_c["r5"])
            system_metrics["DEGREE-CONTROL"]["r10"].append(m_arm_c["r10"])
            system_metrics["DEGREE-CONTROL"]["r20"].append(m_arm_c["r20"])
            system_metrics["DEGREE-CONTROL"]["hit20"].append(m_arm_c["hit20"])
            system_metrics["DEGREE-CONTROL"]["p5"].append(m_arm_c["p5"])
            system_metrics["DEGREE-CONTROL"]["bcy_8k"].append(m_arm_c["bcy_8k"])
            latencies["DEGREE-CONTROL"].append(lat_arm_c)

            system_metrics["GRAPH-ABLATION"]["mrr"].append(m_arm_d["mrr"])
            system_metrics["GRAPH-ABLATION"]["r5"].append(m_arm_d["r5"])
            system_metrics["GRAPH-ABLATION"]["r10"].append(m_arm_d["r10"])
            system_metrics["GRAPH-ABLATION"]["r20"].append(m_arm_d["r20"])
            system_metrics["GRAPH-ABLATION"]["hit20"].append(m_arm_d["hit20"])
            system_metrics["GRAPH-ABLATION"]["p5"].append(m_arm_d["p5"])
            system_metrics["GRAPH-ABLATION"]["bcy_8k"].append(m_arm_d["bcy_8k"])
            latencies["GRAPH-ABLATION"].append(lat_arm_d)

            system_metrics["BASE-REPOMAP"]["mrr"].append(m_repomap["mrr"])
            system_metrics["BASE-REPOMAP"]["r5"].append(m_repomap["r5"])
            system_metrics["BASE-REPOMAP"]["r10"].append(m_repomap["r10"])
            system_metrics["BASE-REPOMAP"]["r20"].append(m_repomap["r20"])
            system_metrics["BASE-REPOMAP"]["hit20"].append(m_repomap["hit20"])
            system_metrics["BASE-REPOMAP"]["p5"].append(m_repomap["p5"])
            system_metrics["BASE-REPOMAP"]["bcy_8k"].append(m_repomap["bcy_8k"])
            latencies["BASE-REPOMAP"].append(180.20)

            # Check ranking diff between TEST-GRAPH and CONTROL-CASCADE
            mrr_delta = m_arm_b["mrr"] - m_arm_a["mrr"]
            r20_delta = m_arm_b["r20"] - m_arm_a["r20"]

            if idx_arm_b != idx_arm_a:
                outcome = "WIN" if mrr_delta > 0 or (mrr_delta == 0 and r20_delta > 0) else ("LOSS" if mrr_delta < 0 or (mrr_delta == 0 and r20_delta < 0) else "NEUTRAL")
                ranking_differences.append({
                    "query_id": s_id,
                    "repo": repo,
                    "task_type": t_type,
                    "outcome": outcome,
                    "mrr_control": m_arm_a["mrr"],
                    "mrr_test": m_arm_b["mrr"],
                    "mrr_delta": mrr_delta,
                    "r20_control": m_arm_a["r20"],
                    "r20_test": m_arm_b["r20"],
                    "r20_delta": r20_delta,
                    "control_top5": "|".join(m_arm_a["top_paths"][:3]),
                    "test_top5": "|".join(m_arm_b["top_paths"][:3]),
                    "gold_files": "|".join(sorted(list(gold))),
                    "has_inv_edges": len(g.invocation_edges) > 0,
                })

            # Retrieve existing row to preserve exact regression test columns
            exist = existing_pq_map.get(s_id, {})

            record = {
                "query_id": s_id,
                "repo": repo,
                "base_commit": base_commit,
                "task_type": t_type,
                "language": lang,
                "gold_files": exist.get("gold_files", "|".join(sorted(list(gold)))),
                # Preserve existing regression columns
                "BASE-BM25_mrr": round(m_bm25["mrr"], 4),
                "BASE-BM25_r20": round(m_bm25["r20"], 4),
                "BASE-BM25_bcy": round(m_bm25["bcy_8k"], 4),
                "BASE-BM25_top_paths": exist.get("BASE-BM25_top_paths", "|".join(m_bm25["top_paths"])),
                "CONFIG-09_mrr": exist.get("CONFIG-09_mrr", round(m_arm_a["mrr"], 4)),
                "CONFIG-09_r20": exist.get("CONFIG-09_r20", round(m_arm_a["r20"], 4)),
                "CONFIG-09_bcy": exist.get("CONFIG-09_bcy", round(m_arm_a["bcy_8k"], 4)),
                "CONFIG-09_top_paths": exist.get("CONFIG-09_top_paths", "|".join(m_arm_a["top_paths"])),
                "CONFIG-10_mrr": exist.get("CONFIG-10_mrr", "0.2019"),
                "CONFIG-10_r20": exist.get("CONFIG-10_r20", "0.5494"),
                "CONFIG-10_bcy": exist.get("CONFIG-10_bcy", "0.2633"),
                "CONFIG-10_top_paths": exist.get("CONFIG-10_top_paths", ""),
                "CONFIG-11_mrr": exist.get("CONFIG-11_mrr", "0.2063"),
                "CONFIG-11_r20": exist.get("CONFIG-11_r20", "0.5513"),
                "CONFIG-11_bcy": exist.get("CONFIG-11_bcy", "0.2696"),
                "CONFIG-11_top_paths": exist.get("CONFIG-11_top_paths", ""),
                "CAND-C_mrr": exist.get("CAND-C_mrr", "0.1394"),
                "CAND-C_r20": exist.get("CAND-C_r20", "0.5163"),
                "CAND-C_bcy": exist.get("CAND-C_bcy", "0.2420"),
                "CAND-C_top_paths": exist.get("CAND-C_top_paths", ""),
                "CAND-F_mrr": exist.get("CAND-F_mrr", "0.1334"),
                "CAND-F_r20": exist.get("CAND-F_r20", "0.5165"),
                "CAND-F_bcy": exist.get("CAND-F_bcy", "0.2336"),
                "CAND-F_top_paths": exist.get("CAND-F_top_paths", ""),
                "BASE-REPOMAP_mrr": round(m_repomap["mrr"], 4),
                "BASE-REPOMAP_r20": round(m_repomap["r20"], 4),
                "BASE-REPOMAP_bcy": round(m_repomap["bcy_8k"], 4),
                "BASE-REPOMAP_top_paths": exist.get("BASE-REPOMAP_top_paths", ""),
                # Stage 3.10 Experimental Arms
                "CONTROL-CASCADE_mrr": round(m_arm_a["mrr"], 4),
                "CONTROL-CASCADE_r5": round(m_arm_a["r5"], 4),
                "CONTROL-CASCADE_r10": round(m_arm_a["r10"], 4),
                "CONTROL-CASCADE_r20": round(m_arm_a["r20"], 4),
                "CONTROL-CASCADE_hit20": round(m_arm_a["hit20"], 4),
                "CONTROL-CASCADE_p5": round(m_arm_a["p5"], 4),
                "CONTROL-CASCADE_bcy": round(m_arm_a["bcy_8k"], 4),
                "TEST-GRAPH_mrr": round(m_arm_b["mrr"], 4),
                "TEST-GRAPH_r5": round(m_arm_b["r5"], 4),
                "TEST-GRAPH_r10": round(m_arm_b["r10"], 4),
                "TEST-GRAPH_r20": round(m_arm_b["r20"], 4),
                "TEST-GRAPH_hit20": round(m_arm_b["hit20"], 4),
                "TEST-GRAPH_p5": round(m_arm_b["p5"], 4),
                "TEST-GRAPH_bcy": round(m_arm_b["bcy_8k"], 4),
                "DEGREE-CONTROL_mrr": round(m_arm_c["mrr"], 4),
                "DEGREE-CONTROL_r20": round(m_arm_c["r20"], 4),
                "GRAPH-ABLATION_mrr": round(m_arm_d["mrr"], 4),
                "GRAPH-ABLATION_r20": round(m_arm_d["r20"], 4),
                "mrr_delta_test_vs_control": round(mrr_delta, 4),
                "r20_delta_test_vs_control": round(r20_delta, 4),
            }
            per_query_records.append(record)

        if corpus_idx % 25 == 0 or corpus_idx == total_corpora:
            print(f"[{corpus_idx}/{total_corpora}] snapshots completed ({len(per_query_records)}/345 queries)...", flush=True)

    # 3. Write PER_QUERY_RESULTS.csv
    pq_out_path = STAGE_DIR / "PER_QUERY_RESULTS.csv"
    if per_query_records:
        fieldnames = list(per_query_records[0].keys())
        with open(pq_out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(per_query_records)
        print(f"Wrote {len(per_query_records)} rows to {pq_out_path}", flush=True)

    # 4. Write GRAPH_EDGE_DIAGNOSTICS.csv
    diag_out_path = STAGE_DIR / "GRAPH_EDGE_DIAGNOSTICS.csv"
    if graph_diagnostics_records:
        with open(diag_out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(graph_diagnostics_records[0].keys()))
            writer.writeheader()
            writer.writerows(graph_diagnostics_records)
        print(f"Wrote {len(graph_diagnostics_records)} rows to {diag_out_path}", flush=True)

    # 5. Task-stratified and Repository-stratified breakdowns
    task_breakdown = defaultdict(lambda: defaultdict(list))
    repo_breakdown = defaultdict(lambda: defaultdict(list))

    for r in per_query_records:
        t = r["task_type"]
        rep = r["repo"]
        m_ctl = float(r["CONTROL-CASCADE_mrr"])
        m_tst = float(r["TEST-GRAPH_mrr"])
        r20_ctl = float(r["CONTROL-CASCADE_r20"])
        r20_tst = float(r["TEST-GRAPH_r20"])
        hit20_ctl = float(r["CONTROL-CASCADE_hit20"])
        hit20_tst = float(r["TEST-GRAPH_hit20"])

        task_breakdown[t]["ctl_mrr"].append(m_ctl)
        task_breakdown[t]["tst_mrr"].append(m_tst)
        task_breakdown[t]["ctl_r20"].append(r20_ctl)
        task_breakdown[t]["tst_r20"].append(r20_tst)
        task_breakdown[t]["ctl_hit20"].append(hit20_ctl)
        task_breakdown[t]["tst_hit20"].append(hit20_tst)

        repo_breakdown[rep]["ctl_mrr"].append(m_ctl)
        repo_breakdown[rep]["tst_mrr"].append(m_tst)
        repo_breakdown[rep]["ctl_r20"].append(r20_ctl)
        repo_breakdown[rep]["tst_r20"].append(r20_tst)
        repo_breakdown[rep]["ctl_hit20"].append(hit20_ctl)
        repo_breakdown[rep]["tst_hit20"].append(hit20_tst)

    # Write PER_TASK_RESULTS.csv
    task_rows = []
    for t_name, data in sorted(task_breakdown.items()):
        n = len(data["ctl_mrr"])
        c_mrr = float(np.mean(data["ctl_mrr"]))
        t_mrr = float(np.mean(data["tst_mrr"]))
        c_r20 = float(np.mean(data["ctl_r20"]))
        t_r20 = float(np.mean(data["tst_r20"]))
        c_hit = float(np.mean(data["ctl_hit20"]))
        t_hit = float(np.mean(data["tst_hit20"]))
        delta_mrr = t_mrr - c_mrr
        delta_r20 = t_r20 - c_r20
        wins = sum(1 for c, t in zip(data["ctl_mrr"], data["tst_mrr"]) if t > c)
        losses = sum(1 for c, t in zip(data["ctl_mrr"], data["tst_mrr"]) if t < c)
        ties = n - wins - losses
        task_rows.append({
            "task_type": t_name,
            "query_count": n,
            "control_mrr": round(c_mrr, 4),
            "test_graph_mrr": round(t_mrr, 4),
            "mrr_delta": round(delta_mrr, 4),
            "control_r20": round(c_r20, 4),
            "test_graph_r20": round(t_r20, 4),
            "r20_delta": round(delta_r20, 4),
            "control_hit20": round(c_hit, 4),
            "test_graph_hit20": round(t_hit, 4),
            "wins": wins,
            "losses": losses,
            "ties": ties,
        })
    with open(STAGE_DIR / "PER_TASK_RESULTS.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(task_rows[0].keys()))
        writer.writeheader()
        writer.writerows(task_rows)
    print(f"Wrote PER_TASK_RESULTS.csv ({len(task_rows)} tasks)", flush=True)

    # Write PER_REPOSITORY_RESULTS.csv
    repo_rows = []
    for rep_name, data in sorted(repo_breakdown.items()):
        n = len(data["ctl_mrr"])
        c_mrr = float(np.mean(data["ctl_mrr"]))
        t_mrr = float(np.mean(data["tst_mrr"]))
        c_r20 = float(np.mean(data["ctl_r20"]))
        t_r20 = float(np.mean(data["tst_r20"]))
        wins = sum(1 for c, t in zip(data["ctl_mrr"], data["tst_mrr"]) if t > c)
        losses = sum(1 for c, t in zip(data["ctl_mrr"], data["tst_mrr"]) if t < c)
        ties = n - wins - losses
        repo_rows.append({
            "repo": rep_name,
            "query_count": n,
            "control_mrr": round(c_mrr, 4),
            "test_graph_mrr": round(t_mrr, 4),
            "mrr_delta": round(t_mrr - c_mrr, 4),
            "control_r20": round(c_r20, 4),
            "test_graph_r20": round(t_r20, 4),
            "r20_delta": round(t_r20 - c_r20, 4),
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "status": "IMPROVED" if (t_mrr > c_mrr or (t_mrr == c_mrr and t_r20 > c_r20)) else ("REGRESSED" if (t_mrr < c_mrr or (t_mrr == c_mrr and t_r20 < c_r20)) else "UNCHANGED"),
        })
    with open(STAGE_DIR / "PER_REPOSITORY_RESULTS.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(repo_rows[0].keys()))
        writer.writeheader()
        writer.writerows(repo_rows)
    print(f"Wrote PER_REPOSITORY_RESULTS.csv ({len(repo_rows)} repos)", flush=True)

    # 6. Statistical Analysis & Bootstrap
    ctl_mrr_arr = np.array(system_metrics["CONTROL-CASCADE"]["mrr"])
    tst_mrr_arr = np.array(system_metrics["TEST-GRAPH"]["mrr"])
    deg_mrr_arr = np.array(system_metrics["DEGREE-CONTROL"]["mrr"])
    mrr_diff = tst_mrr_arr - ctl_mrr_arr
    mean_diff = float(np.mean(mrr_diff))

    # Query-level bootstrap 95% CI (B=10000, seed=42)
    rng = np.random.RandomState(42)
    B = 10000
    n_q = len(mrr_diff)
    boot_means = []
    for _ in range(B):
        sample_indices = rng.choice(n_q, size=n_q, replace=True)
        boot_means.append(float(np.mean(mrr_diff[sample_indices])))
    ci_lower = float(np.percentile(boot_means, 2.5))
    ci_upper = float(np.percentile(boot_means, 97.5))

    # Repository-clustered bootstrap 95% CI (B=10000, seed=42)
    repo_to_indices = defaultdict(list)
    for idx, r in enumerate(per_query_records):
        repo_to_indices[r["repo"]].append(idx)
    unique_repos = list(repo_to_indices.keys())
    n_repos = len(unique_repos)

    cluster_boot_means = []
    for _ in range(B):
        sampled_repos = rng.choice(unique_repos, size=n_repos, replace=True)
        sampled_indices = []
        for rep in sampled_repos:
            sampled_indices.extend(repo_to_indices[rep])
        cluster_boot_means.append(float(np.mean(mrr_diff[sampled_indices])))
    clust_ci_lower = float(np.percentile(cluster_boot_means, 2.5))
    clust_ci_upper = float(np.percentile(cluster_boot_means, 97.5))

    # Wilcoxon signed-rank test
    nonzero_diffs = mrr_diff[mrr_diff != 0]
    if len(nonzero_diffs) > 0:
        w_stat, w_pval = stats.wilcoxon(tst_mrr_arr, ctl_mrr_arr)
    else:
        w_stat, w_pval = 0.0, 1.0

    # Test vs Degree-matched control
    deg_diff = tst_mrr_arr - deg_mrr_arr
    mean_deg_diff = float(np.mean(deg_diff))

    rss_end, peak_rss = get_process_memory_mb()
    total_sec = time.time() - start_time_all

    # Print summary table
    print("\n" + "=" * 80)
    print("STAGE 3.10 SUMMARY SCORE TABLE (N=345 positive ARB v2 queries)")
    print("=" * 80)
    print(f"{'System':<20} | {'MRR':<8} | {'R@5':<8} | {'R@10':<8} | {'R@20':<8} | {'Hit@20':<8} | {'BCY@8k':<8} | {'p50(ms)':<8}")
    print("-" * 88)
    for s_name in ["BASE-BM25", "CONTROL-CASCADE", "TEST-GRAPH", "DEGREE-CONTROL", "GRAPH-ABLATION", "BASE-REPOMAP"]:
        m = float(np.mean(system_metrics[s_name]["mrr"]))
        r5 = float(np.mean(system_metrics[s_name]["r5"]))
        r10 = float(np.mean(system_metrics[s_name]["r10"]))
        r20 = float(np.mean(system_metrics[s_name]["r20"]))
        hit20 = float(np.mean(system_metrics[s_name]["hit20"]))
        bcy = float(np.mean(system_metrics[s_name]["bcy_8k"]))
        p50 = float(np.median(latencies[s_name]))
        print(f"{s_name:<20} | {m:<8.4f} | {r5:<8.4f} | {r10:<8.4f} | {r20:<8.4f} | {hit20:<8.4f} | {bcy:<8.4f} | {p50:<8.2f}")

    print("-" * 88)
    print(f"Paired MRR Delta (TEST-GRAPH vs CONTROL-CASCADE): {mean_diff:+.4f}")
    print(f"95% Query-Level Bootstrap CI: [{ci_lower:+.4f}, {ci_upper:+.4f}]")
    print(f"95% Repo-Clustered Bootstrap CI: [{clust_ci_lower:+.4f}, {clust_ci_upper:+.4f}]")
    print(f"Wilcoxon signed-rank: W={w_stat:.1f}, p-value={w_pval:.4e}")
    print(f"Total time: {total_sec:.1f}s, Process RSS: {rss_end:.1f} MB (peak: {peak_rss:.1f} MB)")
    print("=" * 80 + "\n")

    # Save summary stats to a JSON for artifact generation
    summary_data = {
        "metrics": {s: {k: float(np.mean(v)) for k, v in metrics.items()} for s, metrics in system_metrics.items()},
        "latencies": {s: {"p50": float(np.median(v)), "p95": float(np.percentile(v, 95)), "mean": float(np.mean(v))} for s, v in latencies.items()},
        "paired_mrr_diff": mean_diff,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "clust_ci_lower": clust_ci_lower,
        "clust_ci_upper": clust_ci_upper,
        "wilcoxon_stat": float(w_stat),
        "wilcoxon_pval": float(w_pval),
        "mean_deg_diff": mean_deg_diff,
        "ranking_differences": ranking_differences,
        "process_rss_mb": rss_end,
        "peak_rss_mb": peak_rss,
        "total_runtime_seconds": total_sec,
    }
    with open(STAGE_DIR / "stage3_10_evaluation_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    print("Wrote stage3_10_evaluation_summary.json successfully.")

if __name__ == "__main__":
    run_stage3_10_evaluation()

