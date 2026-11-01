"""
RepoNeedle Stage 3.9.4: Controlled Retrieval Pilot Runner & Statistical Analyzer.
Evaluates:
  - EXP-386: Query-conditioned edge-type-aware file graph (Reference Architecture)
  - EXP-392a: Hybrid (EXP-386 + Raw Unweighted Python LFCG on 13 Python repos)
  - EXP-392b: Hybrid (EXP-386 + Ambiguity-Penalized Python LFCG on 13 Python repos)

Population:
  - All 345 canonical positive ARB v2 queries across all 25 repositories and 218 active corpus splits.
  - LFCG enabled strictly on the 13 primary Python repositories.
  - Remaining 12 non-Python repositories use exact EXP-386.

Outputs:
  - research/stage3_9/PER_QUERY_PILOT_RESULTS.jsonl
  - research/stage3_9/PILOT_STATISTICAL_RESULTS.md
  - research/stage3_9/RUNTIME_COMPARISON.csv
  - research/stage3_9/CONTROLLED_PILOT_REPORT.md
"""

import sys
import os
import json
import csv
import time
import math
import tracemalloc
import ctypes
from ctypes import wintypes
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
STAGE_DIR = ROOT_DIR / "research" / "stage3_9"

sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(STAGE_DIR / "prototypes"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import (
    read_jsonl,
    target_gold_files,
    hard_negative_files,
    query_text_for_eval,
    sample_metrics,
    recall_at,
    gold_coverage_at_budget,
)
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex
from python_lfcg import PythonLFCGEngine

# Win32 Memory Monitoring
class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
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
    ]

def get_process_rss_mb() -> float:
    try:
        psapi = ctypes.windll.psapi
        GetProcessMemoryInfo = psapi.GetProcessMemoryInfo
        GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        GetProcessMemoryInfo.restype = wintypes.BOOL
        pmc = PROCESS_MEMORY_COUNTERS()
        pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
            return round(pmc.WorkingSetSize / (1024 * 1024), 2)
    except Exception:
        pass
    return 0.0

PYTHON_REPOS = {
    "HypothesisWorks/hypothesis",
    "fastapi/fastapi",
    "huggingface/diffusers",
    "huggingface/transformers",
    "ipython/ipython",
    "numpy/numpy",
    "pallets/click",
    "pydantic/pydantic",
    "pypa/pip",
    "pytest-dev/pytest",
    "python/mypy",
    "scrapy/scrapy",
    "tox-dev/tox",
}

def run_pilot():
    print("=" * 80)
    print("REPO NEEDLE — STAGE 3.9.4: CONTROLLED RETRIEVAL PILOT")
    print("=" * 80)

    # 1. Corpus Manifest
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    manifest_raw = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            manifest_raw[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]

    # 2. Benchmark Subsets (Positive N=345)
    subsets_def = [
        ("code2test", ARB_DIR / "data" / "benchmark" / "v2_code2test" / "samples.jsonl"),
        ("comment2context", ARB_DIR / "data" / "benchmark" / "v2_comment2context" / "samples.jsonl"),
        ("trace2code", ARB_DIR / "data" / "benchmark" / "v2_trace2code" / "samples.jsonl"),
        ("edit2ripple", ARB_DIR / "data" / "benchmark" / "v2_edit2ripple" / "samples.jsonl"),
    ]

    all_samples = []
    seen_qids = set()
    for sname, spath in subsets_def:
        for r in read_jsonl(spath):
            qid = r["id"]
            if qid in seen_qids:
                raise ValueError(f"Duplicate query ID detected: {qid}")
            seen_qids.add(qid)
            r["_subset_name"] = sname
            all_samples.append(r)

    print(f"Loaded and verified {len(all_samples)} positive samples across 4 tracks.")

    by_corpus = defaultdict(list)
    for s in all_samples:
        by_corpus[(s["repo"], s["base_commit"])].append(s)

    per_query_records = {}
    exp_ids = ["EXP-386", "EXP-392a", "EXP-392b"]

    # Tracking metrics per system
    system_metrics = {exp_id: defaultdict(list) for exp_id in exp_ids}
    system_latencies = {exp_id: [] for exp_id in exp_ids}
    repo_system_mrr = defaultdict(lambda: defaultdict(list))

    # Runtime tracking
    runtime_stats = {
        "EXP-386": {"index_ms": 0.0, "peak_heap_mb": 0.0, "rss_start_mb": get_process_rss_mb(), "rss_peak_mb": 0.0, "nodes": 0, "edges": 0, "serial_kb": 0.0},
        "EXP-392a": {"index_ms": 0.0, "peak_heap_mb": 0.0, "rss_start_mb": get_process_rss_mb(), "rss_peak_mb": 0.0, "nodes": 0, "edges": 0, "serial_kb": 0.0},
        "EXP-392b": {"index_ms": 0.0, "peak_heap_mb": 0.0, "rss_start_mb": get_process_rss_mb(), "rss_peak_mb": 0.0, "nodes": 0, "edges": 0, "serial_kb": 0.0},
    }

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
            kind = c.get("kind", "")
            if kind == "file":
                file_texts[p] = t
            elif p and (p not in file_texts or len(t) > len(file_texts[p])):
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

        # Fit Baseline EXP-386 Indices
        t_base_0 = time.perf_counter()
        tracemalloc.start()
        bm25 = BM25Index(decouple_symbols=True).fit(docs)
        semantic_index = SubwordSemanticIndex().fit(docs)
        rg = RepoGraph().fit(docs)
        G = rg.graph
        t_base_idx = (time.perf_counter() - t_base_0) * 1000.0
        _, base_peak_heap = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        runtime_stats["EXP-386"]["index_ms"] += t_base_idx
        runtime_stats["EXP-386"]["peak_heap_mb"] = max(runtime_stats["EXP-386"]["peak_heap_mb"], base_peak_heap / (1024*1024))
        runtime_stats["EXP-386"]["nodes"] += G.number_of_nodes()
        runtime_stats["EXP-386"]["edges"] += G.number_of_edges()

        # Build Python LFCG if Python repo
        is_python_repo = repo in PYTHON_REPOS
        lfcg_engine = None
        lfcg_file_to_funcs = defaultdict(list)
        lfcg_calls_edges = []
        lfcg_edge_weights_a = {}
        lfcg_edge_weights_b = {}

        if is_python_repo:
            t_lfcg_0 = time.perf_counter()
            tracemalloc.start()
            lfcg_engine = PythonLFCGEngine(repo_name=repo)
            for p, t in file_texts.items():
                if p.endswith(".py"):
                    lfcg_engine.parse_source(p, t)
            lfcg_engine.resolve_all_calls()
            t_lfcg_idx = (time.perf_counter() - t_lfcg_0) * 1000.0
            _, lfcg_peak_heap = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            # Record runtime
            runtime_stats["EXP-392a"]["index_ms"] += (t_base_idx + t_lfcg_idx)
            runtime_stats["EXP-392b"]["index_ms"] += (t_base_idx + t_lfcg_idx)
            runtime_stats["EXP-392a"]["peak_heap_mb"] = max(runtime_stats["EXP-392a"]["peak_heap_mb"], (base_peak_heap + lfcg_peak_heap) / (1024*1024))
            runtime_stats["EXP-392b"]["peak_heap_mb"] = max(runtime_stats["EXP-392b"]["peak_heap_mb"], (base_peak_heap + lfcg_peak_heap) / (1024*1024))

            # Index LFCG structures
            for fn in lfcg_engine.function_nodes.values():
                lfcg_file_to_funcs[fn.file_uri].append(fn.uri)

            for e in lfcg_engine.edges:
                if e.edge_type == "CALLS":
                    lfcg_calls_edges.append((e.source_uri, e.target_uri))
                    lfcg_edge_weights_a[(e.source_uri, e.target_uri)] = 1.0
                    lfcg_edge_weights_b[(e.source_uri, e.target_uri)] = e.ambiguity_penalty

            runtime_stats["EXP-392a"]["nodes"] += (G.number_of_nodes() + len(lfcg_engine.function_nodes))
            runtime_stats["EXP-392a"]["edges"] += (G.number_of_edges() + len(lfcg_calls_edges))
            runtime_stats["EXP-392b"]["nodes"] += (G.number_of_nodes() + len(lfcg_engine.function_nodes))
            runtime_stats["EXP-392b"]["edges"] += (G.number_of_edges() + len(lfcg_calls_edges))
        else:
            runtime_stats["EXP-392a"]["index_ms"] += t_base_idx
            runtime_stats["EXP-392b"]["index_ms"] += t_base_idx
            runtime_stats["EXP-392a"]["nodes"] += G.number_of_nodes()
            runtime_stats["EXP-392a"]["edges"] += G.number_of_edges()
            runtime_stats["EXP-392b"]["nodes"] += G.number_of_nodes()
            runtime_stats["EXP-392b"]["edges"] += G.number_of_edges()

        # Doc classification masks
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

        def eval_ranking(scores_vec, gold_files, hard_neg_files, budget_tokens=8000):
            ranked_indices = np.argsort(-scores_vec)
            ranked_paths = [doc_paths[i] for i in ranked_indices]
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

            gold_set = set(gold_files)
            m = sample_metrics(gold_files, ranked_chunks, context_budget=budget_tokens, hard_negative_files=hard_neg_files)

            hit1 = 1.0 if any(p in gold_set for p in ranked_paths[:1]) else 0.0
            hit5 = 1.0 if any(p in gold_set for p in ranked_paths[:5]) else 0.0
            hit10 = 1.0 if any(p in gold_set for p in ranked_paths[:10]) else 0.0
            hit20 = 1.0 if any(p in gold_set for p in ranked_paths[:20]) else 0.0

            r1 = recall_at(gold_set, ranked_paths, 1)
            r5 = recall_at(gold_set, ranked_paths, 5)
            r10 = recall_at(gold_set, ranked_paths, 10)
            r20 = recall_at(gold_set, ranked_paths, 20)

            first_rank = -1
            for r_i, p in enumerate(ranked_paths):
                if p in gold_set:
                    first_rank = r_i + 1
                    break

            bcy_8k = m["gold_coverage@8k"]

            return {
                "mrr": m["MRR"],
                "r1": r1,
                "r5": r5,
                "r10": r10,
                "r20": r20,
                "hit1": hit1,
                "hit5": hit5,
                "hit10": hit10,
                "hit20": hit20,
                "p5": m["Precision@5"],
                "p10": m["Precision@10"],
                "p20": m["Precision@20"],
                "bcy_8k": bcy_8k,
                "first_rank": first_rank,
                "top_paths": ranked_paths[:5],
                "coverage": 1.0 if first_rank > 0 else 0.0,
            }

        # Ext counts for language
        ext_counts = Counter(p.split(".")[-1].lower() for p in file_texts.keys() if "." in p)
        top_ext = ext_counts.most_common(1)[0][0] if ext_counts else "unknown"
        lang_map = {"py": "python", "rs": "rust", "go": "go", "ts": "typescript", "js": "javascript", "tsx": "typescript", "jsx": "javascript"}
        repo_lang = lang_map.get(top_ext, top_ext)

        # Adjacency for LFCG propagation
        lfcg_succs = defaultdict(list)
        lfcg_preds = defaultdict(list)
        if is_python_repo and lfcg_calls_edges:
            for s_uri, t_uri in lfcg_calls_edges:
                lfcg_succs[s_uri].append(t_uri)
                lfcg_preds[t_uri].append(s_uri)

        for s in repo_samples:
            s_id = s["id"]
            gold = target_gold_files(s)
            hard_neg = hard_negative_files(s)
            q_text = query_text_for_eval(s)
            t_type = s["_subset_name"]

            per_query_records[s_id] = {
                "query_id": s_id,
                "repo": repo,
                "task_type": t_type,
                "language": repo_lang,
                "gold_files": gold,
                "is_python": is_python_repo,
                "systems": {},
            }

            t_query_0 = time.perf_counter()

            # Lexical and semantic
            lex = bm25.score(q_text)
            sm = semantic_index.score(q_text)
            base = (lex + sm) / 2.0
            base[is_doc_file] *= 0.5

            hits = lex + sm
            max_hit = float(np.max(hits)) if len(hits) > 0 else 1.0
            if max_hit == 0.0:
                max_hit = 1.0

            q_lower = q_text.lower()
            query_is_test_seeking = ("test" in q_lower or "assert" in q_lower or "spec" in q_lower) and t_type != "trace2code"

            # 1. EXP-386 Boost (File Graph)
            boost_386 = np.zeros(num_docs, dtype=np.float32)
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
                            boost_386[n_idx] = max(boost_386[n_idx], fwd_raw)

                    # Backward: predecessors -> seed
                    for pred in G.predecessors(sp):
                        if pred in path_to_idx:
                            n_idx = path_to_idx[pred]
                            out_deg = max(1, G.out_degree(pred))
                            bwd_raw = float(sv * 0.20 / np.sqrt(out_deg))
                            edge_mult = 1.0
                            if is_manifest_file[n_idx]:
                                edge_mult = 0.05
                            elif not query_is_test_seeking and is_test_file[n_idx] and not is_test_file[s_idx]:
                                edge_mult = 0.15
                            elif query_is_test_seeking and is_test_file[n_idx]:
                                edge_mult = 1.25
                            bwd_386 = bwd_raw * edge_mult
                            boost_386[n_idx] = max(boost_386[n_idx], bwd_386)

            score_386 = base + 0.15 * boost_386

            # 2. LFCG Symbol Boost (for EXP-392a and EXP-392b)
            boost_lfcg_a = np.zeros(num_docs, dtype=np.float32)
            boost_lfcg_b = np.zeros(num_docs, dtype=np.float32)

            if is_python_repo and lfcg_calls_edges and len(hits) > 0 and float(np.max(hits)) > 0:
                top_seeds = np.argsort(hits)[::-1][:5]
                
                # Function activation maps
                act_a = defaultdict(float)
                act_b = defaultdict(float)

                for s_idx in top_seeds:
                    sp = doc_paths[s_idx]
                    sv = float(hits[s_idx])
                    if sv <= 0:
                        continue
                    sp_uri = lfcg_engine.make_file_uri(sp)
                    seed_funcs = lfcg_file_to_funcs.get(sp_uri, [])
                    if not seed_funcs:
                        continue
                    initial_val = sv / len(seed_funcs)
                    for fn_uri in seed_funcs:
                        act_a[fn_uri] = max(act_a[fn_uri], initial_val)
                        act_b[fn_uri] = max(act_b[fn_uri], initial_val)

                # Hop 1
                hop1_a = defaultdict(float)
                hop1_b = defaultdict(float)
                for fn_uri, val in act_a.items():
                    for succ in lfcg_succs.get(fn_uri, []):
                        w_a = lfcg_edge_weights_a.get((fn_uri, succ), 1.0)
                        hop1_a[succ] = max(hop1_a[succ], val * 0.25 * w_a)
                    for pred in lfcg_preds.get(fn_uri, []):
                        w_a = lfcg_edge_weights_a.get((pred, fn_uri), 1.0)
                        hop1_a[pred] = max(hop1_a[pred], val * 0.20 * w_a)

                for fn_uri, val in act_b.items():
                    for succ in lfcg_succs.get(fn_uri, []):
                        w_b = lfcg_edge_weights_b.get((fn_uri, succ), 1.0)
                        hop1_b[succ] = max(hop1_b[succ], val * 0.25 * w_b)
                    for pred in lfcg_preds.get(fn_uri, []):
                        w_b = lfcg_edge_weights_b.get((pred, fn_uri), 1.0)
                        hop1_b[pred] = max(hop1_b[pred], val * 0.20 * w_b)

                # Hop 2
                hop2_a = defaultdict(float)
                hop2_b = defaultdict(float)
                for fn_uri, val in hop1_a.items():
                    for succ in lfcg_succs.get(fn_uri, []):
                        w_a = lfcg_edge_weights_a.get((fn_uri, succ), 1.0)
                        hop2_a[succ] = max(hop2_a[succ], val * 0.50 * 0.25 * w_a)
                    for pred in lfcg_preds.get(fn_uri, []):
                        w_a = lfcg_edge_weights_a.get((pred, fn_uri), 1.0)
                        hop2_a[pred] = max(hop2_a[pred], val * 0.50 * 0.20 * w_a)

                for fn_uri, val in hop1_b.items():
                    for succ in lfcg_succs.get(fn_uri, []):
                        w_b = lfcg_edge_weights_b.get((fn_uri, succ), 1.0)
                        hop2_b[succ] = max(hop2_b[succ], val * 0.50 * 0.25 * w_b)
                    for pred in lfcg_preds.get(fn_uri, []):
                        w_b = lfcg_edge_weights_b.get((pred, fn_uri), 1.0)
                        hop2_b[pred] = max(hop2_b[pred], val * 0.50 * 0.20 * w_b)

                # Combine activations
                all_act_a = defaultdict(float)
                all_act_b = defaultdict(float)
                for d in (act_a, hop1_a, hop2_a):
                    for k, v in d.items():
                        all_act_a[k] = max(all_act_a[k], v)
                for d in (act_b, hop1_b, hop2_b):
                    for k, v in d.items():
                        all_act_b[k] = max(all_act_b[k], v)

                # Max-Pooling Projection to FileNode
                for i, p in enumerate(doc_paths):
                    p_uri = lfcg_engine.make_file_uri(p)
                    funcs = lfcg_file_to_funcs.get(p_uri, [])
                    if funcs:
                        boost_lfcg_a[i] = max([all_act_a.get(f_uri, 0.0) for f_uri in funcs])
                        boost_lfcg_b[i] = max([all_act_b.get(f_uri, 0.0) for f_uri in funcs])

                # Max hit normalization
                max_la = float(np.max(boost_lfcg_a))
                if max_la > 0:
                    boost_lfcg_a = (boost_lfcg_a / max_la) * max_hit

                max_lb = float(np.max(boost_lfcg_b))
                if max_lb > 0:
                    boost_lfcg_b = (boost_lfcg_b / max_lb) * max_hit

            # Hybrid Score Fusion: lambda = 0.15
            score_392a = score_386 + 0.15 * boost_lfcg_a
            score_392b = score_386 + 0.15 * boost_lfcg_b

            elapsed_query_ms = (time.perf_counter() - t_query_0) * 1000.0

            configs = [
                ("EXP-386", score_386),
                ("EXP-392a", score_392a),
                ("EXP-392b", score_392b),
            ]

            for exp_id, sc_vec in configs:
                res = eval_ranking(sc_vec, gold, hard_neg)
                res["latency_ms"] = elapsed_query_ms / 3.0
                res["query_id"] = s_id
                res["repo"] = repo
                res["task_type"] = t_type
                res["language"] = repo_lang
                res["experiment_id"] = exp_id
                res["gold_files"] = gold

                per_query_records[s_id]["systems"][exp_id] = res

                for k in ["mrr", "r1", "r5", "r10", "r20", "hit1", "hit5", "hit10", "hit20", "bcy_8k", "coverage"]:
                    system_metrics[exp_id][k].append(res[k])
                repo_system_mrr[repo][exp_id].append(res["mrr"])
                system_latencies[exp_id].append(res["latency_ms"])

        if corpus_idx % 10 == 0 or corpus_idx == total_corpora:
            print(f"Evaluated {corpus_idx}/{total_corpora} corpora ({len(per_query_records)} queries processed)...", flush=True)

    # 1. Output PER_QUERY_PILOT_RESULTS.jsonl
    out_jsonl = STAGE_DIR / "PER_QUERY_PILOT_RESULTS.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for qid, qdata in sorted(per_query_records.items()):
            f.write(json.dumps(qdata) + "\n")
    print(f"\nWrote per-query pilot results to {out_jsonl}")

    # 2. Paired Statistical Analysis (10,000 Clustered Bootstrap Resamples, seed 42)
    print("\nRunning 10,000 Paired Repository-Clustered Bootstrap Resamples (seed 42)...")
    np.random.seed(42)

    # Collect query pairs
    all_queries = list(per_query_records.values())
    py_queries = [q for q in all_queries if q["is_python"]]

    # Unique repositories
    all_repos = sorted(list(set(q["repo"] for q in all_queries)))
    py_repos = sorted(list(set(q["repo"] for q in py_queries)))

    queries_by_repo_all = defaultdict(list)
    for q in all_queries:
        queries_by_repo_all[q["repo"]].append(q)

    def clustered_bootstrap(target_repos, queries_dict, sys_test, sys_ref, metric_key="mrr", B=10000):
        observed_diffs = []
        for r in target_repos:
            for q in queries_dict[r]:
                val_test = q["systems"][sys_test][metric_key]
                val_ref = q["systems"][sys_ref][metric_key]
                observed_diffs.append(val_test - val_ref)
        mean_observed = float(np.mean(observed_diffs))

        # Bootstrap
        n_clusters = len(target_repos)
        boot_means = []
        for _ in range(B):
            sampled_repos = np.random.choice(target_repos, size=n_clusters, replace=True)
            resampled_diffs = []
            for r in sampled_repos:
                for q in queries_dict[r]:
                    val_test = q["systems"][sys_test][metric_key]
                    val_ref = q["systems"][sys_ref][metric_key]
                    resampled_diffs.append(val_test - val_ref)
            boot_means.append(float(np.mean(resampled_diffs)))

        ci_lower = float(np.percentile(boot_means, 2.5))
        ci_upper = float(np.percentile(boot_means, 97.5))
        p_val = float(np.mean(np.array(boot_means) <= 0.0)) if mean_observed > 0 else float(np.mean(np.array(boot_means) >= 0.0))
        return mean_observed, ci_lower, ci_upper, p_val

    # Run bootstrap for overall and python subset
    stats_overall_392a_mrr = clustered_bootstrap(all_repos, queries_by_repo_all, "EXP-392a", "EXP-386", "mrr")
    stats_overall_392a_r5 = clustered_bootstrap(all_repos, queries_by_repo_all, "EXP-392a", "EXP-386", "r5")
    stats_overall_392a_r10 = clustered_bootstrap(all_repos, queries_by_repo_all, "EXP-392a", "EXP-386", "r10")
    stats_overall_392a_r20 = clustered_bootstrap(all_repos, queries_by_repo_all, "EXP-392a", "EXP-386", "r20")
    stats_overall_392a_hit20 = clustered_bootstrap(all_repos, queries_by_repo_all, "EXP-392a", "EXP-386", "hit20")
    stats_overall_392a_bcy8k = clustered_bootstrap(all_repos, queries_by_repo_all, "EXP-392a", "EXP-386", "bcy_8k")

    stats_py_392a_mrr = clustered_bootstrap(py_repos, queries_by_repo_all, "EXP-392a", "EXP-386", "mrr")
    stats_py_392a_r5 = clustered_bootstrap(py_repos, queries_by_repo_all, "EXP-392a", "EXP-386", "r5")
    stats_py_392a_r10 = clustered_bootstrap(py_repos, queries_by_repo_all, "EXP-392a", "EXP-386", "r10")
    stats_py_392a_r20 = clustered_bootstrap(py_repos, queries_by_repo_all, "EXP-392a", "EXP-386", "r20")
    stats_py_392a_hit20 = clustered_bootstrap(py_repos, queries_by_repo_all, "EXP-392a", "EXP-386", "hit20")
    stats_py_392a_bcy8k = clustered_bootstrap(py_repos, queries_by_repo_all, "EXP-392a", "EXP-386", "bcy_8k")

    stats_overall_392b_mrr = clustered_bootstrap(all_repos, queries_by_repo_all, "EXP-392b", "EXP-386", "mrr")
    stats_py_392b_mrr = clustered_bootstrap(py_repos, queries_by_repo_all, "EXP-392b", "EXP-386", "mrr")

    # Win/Tie/Loss Counts
    def count_wins(q_list, sys_test, sys_ref, key="mrr"):
        wins, ties, losses = 0, 0, 0
        for q in q_list:
            diff = q["systems"][sys_test][key] - q["systems"][sys_ref][key]
            if diff > 1e-5:
                wins += 1
            elif diff < -1e-5:
                losses += 1
            else:
                ties += 1
        return wins, ties, losses

    w_all_a, t_all_a, l_all_a = count_wins(all_queries, "EXP-392a", "EXP-386")
    w_py_a, t_py_a, l_py_a = count_wins(py_queries, "EXP-392a", "EXP-386")
    w_all_b, t_all_b, l_all_b = count_wins(all_queries, "EXP-392b", "EXP-386")
    w_py_b, t_py_b, l_py_b = count_wins(py_queries, "EXP-392b", "EXP-386")

    # 3. Output PILOT_STATISTICAL_RESULTS.md
    out_stat_md = STAGE_DIR / "PILOT_STATISTICAL_RESULTS.md"
    with open(out_stat_md, "w", encoding="utf-8") as f:
        f.write("# RepoNeedle Stage 3.9.4: Pilot Statistical Analysis Report\n\n")
        f.write("> **Evaluation Population:** 345 canonical positive ARB v2 queries across 25 repositories (104 queries in 13 Python repos).\n")
        f.write("> **Inferential Method:** 10,000 Paired Repository-Clustered Bootstrap Resamples (Seed 42).\n")
        f.write("> **Significance Criteria:** Mean difference $\\ge +0.0050$ and 95% Clustered CI lower bound $> 0.0$.\n\n")

        f.write("## 1. Overall Benchmark Results (All 345 Queries)\n\n")
        f.write("| Experiment | MRR | Recall@5 | Recall@10 | Recall@20 | Hit@20 | BCY@8k | Wins / Ties / Losses vs EXP-386 |\n")
        f.write("|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|\n")
        for exp_id in exp_ids:
            m = system_metrics[exp_id]
            f.write(f"| **{exp_id}** | {np.mean(m['mrr']):.4f} | {np.mean(m['r5']):.4f} | {np.mean(m['r10']):.4f} | {np.mean(m['r20']):.4f} | {np.mean(m['hit20']):.4f} | {np.mean(m['bcy_8k']):.4f} | ")
            if exp_id == "EXP-386":
                f.write("Reference Baseline |\n")
            elif exp_id == "EXP-392a":
                f.write(f"{w_all_a} / {t_all_a} / {l_all_a} |\n")
            elif exp_id == "EXP-392b":
                f.write(f"{w_all_b} / {t_all_b} / {l_all_b} |\n")

        f.write("\n### Paired Inferential Differences (EXP-392a vs EXP-386 Reference)\n\n")
        f.write("| Metric | Mean Diff (\\Delta) | 95% Clustered CI | p-value | Minimum Meaningful Effect (+0.0050) | Statistically Significant? |\n")
        f.write("|---|:---:|:---:|:---:|:---:|:---:|\n")
        f.write(f"| **MRR** | {stats_overall_392a_mrr[0]:+.4f} | [{stats_overall_392a_mrr[1]:+.4f}, {stats_overall_392a_mrr[2]:+.4f}] | {stats_overall_392a_mrr[3]:.4f} | {'MET' if stats_overall_392a_mrr[0] >= 0.0050 else 'NOT MET'} | {'YES' if stats_overall_392a_mrr[1] > 0 else 'NO'} |\n")
        f.write(f"| **Recall@5** | {stats_overall_392a_r5[0]:+.4f} | [{stats_overall_392a_r5[1]:+.4f}, {stats_overall_392a_r5[2]:+.4f}] | {stats_overall_392a_r5[3]:.4f} | — | {'YES' if stats_overall_392a_r5[1] > 0 else 'NO'} |\n")
        f.write(f"| **Recall@10** | {stats_overall_392a_r10[0]:+.4f} | [{stats_overall_392a_r10[1]:+.4f}, {stats_overall_392a_r10[2]:+.4f}] | {stats_overall_392a_r10[3]:.4f} | — | {'YES' if stats_overall_392a_r10[1] > 0 else 'NO'} |\n")
        f.write(f"| **Recall@20** | {stats_overall_392a_r20[0]:+.4f} | [{stats_overall_392a_r20[1]:+.4f}, {stats_overall_392a_r20[2]:+.4f}] | {stats_overall_392a_r20[3]:.4f} | — | {'YES' if stats_overall_392a_r20[1] > 0 else 'NO'} |\n")
        f.write(f"| **Hit@20** | {stats_overall_392a_hit20[0]:+.4f} | [{stats_overall_392a_hit20[1]:+.4f}, {stats_overall_392a_hit20[2]:+.4f}] | {stats_overall_392a_hit20[3]:.4f} | — | {'YES' if stats_overall_392a_hit20[1] > 0 else 'NO'} |\n")
        f.write(f"| **BCY@8k** | {stats_overall_392a_bcy8k[0]:+.4f} | [{stats_overall_392a_bcy8k[1]:+.4f}, {stats_overall_392a_bcy8k[2]:+.4f}] | {stats_overall_392a_bcy8k[3]:.4f} | — | {'YES' if stats_overall_392a_bcy8k[1] > 0 else 'NO'} |\n")

        f.write("\n---\n\n")
        f.write("## 2. Python-Eligible Subset Results (104 Queries across 13 Repositories)\n\n")
        f.write("| Experiment | MRR | Recall@5 | Recall@10 | Recall@20 | Hit@20 | BCY@8k | Wins / Ties / Losses vs EXP-386 |\n")
        f.write("|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|\n")
        for exp_id in exp_ids:
            py_m = defaultdict(list)
            for q in py_queries:
                for k in ["mrr", "r5", "r10", "r20", "hit20", "bcy_8k"]:
                    py_m[k].append(q["systems"][exp_id][k])
            f.write(f"| **{exp_id}** | {np.mean(py_m['mrr']):.4f} | {np.mean(py_m['r5']):.4f} | {np.mean(py_m['r10']):.4f} | {np.mean(py_m['r20']):.4f} | {np.mean(py_m['hit20']):.4f} | {np.mean(py_m['bcy_8k']):.4f} | ")
            if exp_id == "EXP-386":
                f.write("Reference Baseline |\n")
            elif exp_id == "EXP-392a":
                f.write(f"{w_py_a} / {t_py_a} / {l_py_a} |\n")
            elif exp_id == "EXP-392b":
                f.write(f"{w_py_b} / {t_py_b} / {l_py_b} |\n")

        f.write("\n### Paired Inferential Differences (Python Subset: EXP-392a vs EXP-386)\n\n")
        f.write("| Metric | Mean Diff (\\Delta) | 95% Clustered CI | p-value | Minimum Meaningful Effect (+0.0050) | Statistically Significant? |\n")
        f.write("|---|:---:|:---:|:---:|:---:|:---:|\n")
        f.write(f"| **MRR** | {stats_py_392a_mrr[0]:+.4f} | [{stats_py_392a_mrr[1]:+.4f}, {stats_py_392a_mrr[2]:+.4f}] | {stats_py_392a_mrr[3]:.4f} | {'MET' if stats_py_392a_mrr[0] >= 0.0050 else 'NOT MET'} | {'YES' if stats_py_392a_mrr[1] > 0 else 'NO'} |\n")
        f.write(f"| **Recall@5** | {stats_py_392a_r5[0]:+.4f} | [{stats_py_392a_r5[1]:+.4f}, {stats_py_392a_r5[2]:+.4f}] | {stats_py_392a_r5[3]:.4f} | — | {'YES' if stats_py_392a_r5[1] > 0 else 'NO'} |\n")
        f.write(f"| **Recall@10** | {stats_py_392a_r10[0]:+.4f} | [{stats_py_392a_r10[1]:+.4f}, {stats_py_392a_r10[2]:+.4f}] | {stats_py_392a_r10[3]:.4f} | — | {'YES' if stats_py_392a_r10[1] > 0 else 'NO'} |\n")
        f.write(f"| **Recall@20** | {stats_py_392a_r20[0]:+.4f} | [{stats_py_392a_r20[1]:+.4f}, {stats_py_392a_r20[2]:+.4f}] | {stats_py_392a_r20[3]:.4f} | — | {'YES' if stats_py_392a_r20[1] > 0 else 'NO'} |\n")
        f.write(f"| **Hit@20** | {stats_py_392a_hit20[0]:+.4f} | [{stats_py_392a_hit20[1]:+.4f}, {stats_py_392a_hit20[2]:+.4f}] | {stats_py_392a_hit20[3]:.4f} | — | {'YES' if stats_py_392a_hit20[1] > 0 else 'NO'} |\n")
        f.write(f"| **BCY@8k** | {stats_py_392a_bcy8k[0]:+.4f} | [{stats_py_392a_bcy8k[1]:+.4f}, {stats_py_392a_bcy8k[2]:+.4f}] | {stats_py_392a_bcy8k[3]:.4f} | — | {'YES' if stats_py_392a_bcy8k[1] > 0 else 'NO'} |\n")

        f.write("\n---\n\n")
        f.write("## 3. Repository-Level Effects Breakdown\n\n")
        f.write("| Repository | Language | Query Count | EXP-386 MRR | EXP-392a MRR | EXP-392b MRR | \\Delta MRR (392a - 386) |\n")
        f.write("|---|:---:|:---:|:---:|:---:|:---:|:---:|\n")
        for repo_name in sorted(all_repos):
            q_cnt = len(queries_by_repo_all[repo_name])
            m_386 = np.mean(repo_system_mrr[repo_name]["EXP-386"])
            m_392a = np.mean(repo_system_mrr[repo_name]["EXP-392a"])
            m_392b = np.mean(repo_system_mrr[repo_name]["EXP-392b"])
            diff = m_392a - m_386
            is_py = "Python" if repo_name in PYTHON_REPOS else "Other"
            f.write(f"| `{repo_name}` | {is_py} | {q_cnt} | {m_386:.4f} | {m_392a:.4f} | {m_392b:.4f} | {diff:+.4f} |\n")

    print(f"Wrote statistical results to {out_stat_md}")

    # 4. Output RUNTIME_COMPARISON.csv
    out_runtime_csv = STAGE_DIR / "RUNTIME_COMPARISON.csv"
    with open(out_runtime_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "system",
            "total_indexing_time_ms",
            "peak_heap_mb",
            "process_rss_mb",
            "median_query_latency_ms",
            "p95_query_latency_ms",
            "total_nodes",
            "total_edges",
        ])
        for exp_id in exp_ids:
            lats = system_latencies[exp_id]
            writer.writerow([
                exp_id,
                round(runtime_stats[exp_id]["index_ms"], 2),
                round(runtime_stats[exp_id]["peak_heap_mb"], 2),
                round(get_process_rss_mb(), 2),
                round(float(np.median(lats)), 3) if lats else 0.0,
                round(float(np.percentile(lats, 95)), 3) if lats else 0.0,
                runtime_stats[exp_id]["nodes"],
                runtime_stats[exp_id]["edges"],
            ])
    print(f"Wrote runtime comparison to {out_runtime_csv}")

    print("\nControlled Pilot execution and statistical computation complete!")

if __name__ == "__main__":
    run_pilot()

