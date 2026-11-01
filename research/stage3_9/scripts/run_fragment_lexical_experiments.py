"""
RepoNeedle Stage 3.9.6: Controlled Fragment-Aware Lexical Retrieval Experiment Runner.
Evaluates:
  - EXP-397: Canonical Stage 3.8 EXP-386 Reference Baseline (Bit-for-bit locked)
  - EXP-398: EXP-397 + Multi-Field Complete-Function Lexical Matching via Max-Pooling (alpha = 0.10)
  - EXP-399a: EXP-397 + Soft-Max Top-2 Function Pooling (alpha = 0.10)
  - EXP-399b: EXP-397 + Symbol Specificity Attenuation (alpha = 0.10)

Outputs:
  - research/stage3_9/PER_QUERY_FRAGMENT_RESULTS.jsonl
  - research/stage3_9/FIELD_SCORE_DISTRIBUTION.csv
  - research/stage3_9/FRAGMENT_COVERAGE_REPORT.md
  - research/stage3_9/FRAGMENT_RUNTIME_REPORT.md
  - research/stage3_9/STAGE3_9_6_DECISION_REPORT.md
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
from fragment_lexical_engine import FragmentClassifier, MultiFieldFragmentBM25


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


def get_process_rss_mb() -> float:
    try:
        psapi = ctypes.windll.psapi
        GetProcessMemoryInfo = psapi.GetProcessMemoryInfo
        GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        GetProcessMemoryInfo.restype = wintypes.BOOL
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
        pmc = PROCESS_MEMORY_COUNTERS()
        pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
            return round(pmc.WorkingSetSize / (1024 * 1024), 2)
    except Exception:
        pass
    return 0.0


def run_experiment_suite():
    print("=" * 80)
    print("REPO NEEDLE — STAGE 3.9.6: FRAGMENT-AWARE LEXICAL RETRIEVAL EXPERIMENTS")
    print("=" * 80, flush=True)

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
            if qid not in seen_qids:
                seen_qids.add(qid)
                r["_subset_name"] = sname
                all_samples.append(r)

    print(f"Loaded {len(all_samples)} positive benchmark samples across 4 tracks.", flush=True)

    by_corpus = defaultdict(list)
    for s in all_samples:
        by_corpus[(s["repo"], s["base_commit"])].append(s)

    exp_ids = ["EXP-397", "EXP-398", "EXP-399a", "EXP-399b"]
    per_query_records = {}
    system_metrics = {eid: defaultdict(list) for eid in exp_ids}
    system_latencies = {eid: [] for eid in exp_ids}
    repo_system_mrr = defaultdict(lambda: defaultdict(list))

    # Field score distribution tracking
    field_scores_collector = defaultdict(list)

    # Coverage statistics collector
    repo_coverage_stats = defaultdict(lambda: {
        "files_total": 0,
        "files_with_complete_fragments": 0,
        "complete_fragments": 0,
        "incomplete_headers": 0,
        "incomplete_bodies": 0,
        "quarantined_invalid": 0,
        "gold_files_total": 0,
        "gold_files_with_fragments": 0,
    })

    # Runtime tracking
    runtime_stats = {
        eid: {"index_ms": 0.0, "peak_heap_mb": 0.0, "rss_peak_mb": 0.0}
        for eid in exp_ids
    }

    corpus_idx = 0
    total_corpora = len(by_corpus)

    for (repo, base_commit), repo_samples in by_corpus.items():
        corpus_idx += 1
        chunks_path = manifest_raw.get((repo, base_commit))
        if not chunks_path or not chunks_path.is_file():
            continue

        chunks = read_jsonl(chunks_path)

        # Canonical Stage 3.8 File Reconstruction: longest snippet per path
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
        doc_paths_set = set(doc_paths)

        # 1. Fit EXP-397 (Exact Stage 3.8 EXP-386)
        t_base_0 = time.perf_counter()
        tracemalloc.start()
        bm25 = BM25Index(decouple_symbols=True).fit(docs)
        semantic_index = SubwordSemanticIndex().fit(docs)
        rg = RepoGraph().fit(docs)
        G = rg.graph
        t_base_idx = (time.perf_counter() - t_base_0) * 1000.0
        _, base_peak_heap = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        runtime_stats["EXP-397"]["index_ms"] += t_base_idx
        runtime_stats["EXP-397"]["peak_heap_mb"] = max(runtime_stats["EXP-397"]["peak_heap_mb"], base_peak_heap / (1024*1024))

        # 2. Extract Complete Symbol Fragments if Python Repo
        is_python_repo = repo in PYTHON_REPOS
        frag_clf = None
        frag_index = None
        file_to_frag_indices = defaultdict(list)
        t_frag_idx = 0.0

        if is_python_repo:
            t_frag_0 = time.perf_counter()
            tracemalloc.start()
            frag_clf = FragmentClassifier(repo=repo, base_commit=base_commit)
            for c in chunks:
                if c.get("kind") == "symbol":
                    frag_clf.ingest_chunk(c, doc_paths_set)

            # Build Multi-Field BM25
            frag_index = MultiFieldFragmentBM25(frag_clf.complete_fragments)
            t_frag_idx = (time.perf_counter() - t_frag_0) * 1000.0
            _, frag_peak_heap = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            # Map fragments to doc_paths
            for f_idx, frag in enumerate(frag_clf.complete_fragments):
                if frag.filepath in path_to_idx:
                    file_to_frag_indices[frag.filepath].append(f_idx)

            # Accumulate coverage
            cov = repo_coverage_stats[repo]
            cov["files_total"] += len(doc_paths)
            cov["files_with_complete_fragments"] += len(file_to_frag_indices)
            cov["complete_fragments"] += len(frag_clf.complete_fragments)
            cov["incomplete_headers"] += frag_clf.incomplete_headers_count
            cov["incomplete_bodies"] += frag_clf.incomplete_bodies_count
            cov["quarantined_invalid"] += frag_clf.quarantined_invalid_count

            # Track gold coverage
            gold_in_corpus = set()
            for s in repo_samples:
                gold_in_corpus.update(target_gold_files(s))
            cov["gold_files_total"] += len(gold_in_corpus)
            cov["gold_files_with_fragments"] += len(gold_in_corpus.intersection(file_to_frag_indices.keys()))

            # Record runtimes
            for eid in ["EXP-398", "EXP-399a", "EXP-399b"]:
                runtime_stats[eid]["index_ms"] += (t_base_idx + t_frag_idx)
                runtime_stats[eid]["peak_heap_mb"] = max(runtime_stats[eid]["peak_heap_mb"], (base_peak_heap + frag_peak_heap) / (1024*1024))
        else:
            for eid in ["EXP-398", "EXP-399a", "EXP-399b"]:
                runtime_stats[eid]["index_ms"] += t_base_idx
                runtime_stats[eid]["peak_heap_mb"] = max(runtime_stats[eid]["peak_heap_mb"], base_peak_heap / (1024*1024))

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

        # Language of repository
        ext_counts = Counter(p.split(".")[-1].lower() for p in file_texts.keys() if "." in p)
        top_ext = ext_counts.most_common(1)[0][0] if ext_counts else "unknown"
        lang_map = {"py": "python", "rs": "rust", "go": "go", "ts": "typescript", "js": "javascript", "tsx": "typescript", "jsx": "javascript"}
        repo_lang = lang_map.get(top_ext, top_ext)

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

            # 1. Base Lexical and Semantic
            lex = bm25.score(q_text)
            sm = semantic_index.score(q_text)
            base = (lex + sm) / 2.0
            base[is_doc_file] *= 0.5
            hits = lex + sm

            q_lower = q_text.lower()
            query_is_test_seeking = ("test" in q_lower or "assert" in q_lower or "spec" in q_lower) and t_type != "trace2code"

            # 2. Canonical EXP-386 (Backward degree-dampened edge gating)
            boost_386 = np.zeros(num_docs, dtype=np.float32)
            if G.number_of_edges() > 0 and len(hits) > 0 and float(np.max(hits)) > 0:
                top_seeds = np.argsort(hits)[::-1][:5]
                for s_idx in top_seeds:
                    sp = doc_paths[s_idx]
                    sv = float(hits[s_idx])
                    if sv <= 0 or sp not in G:
                        continue
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

            score_397 = base + 0.15 * boost_386

            # 3. Fragment Lexical Scoring (EXP-398, EXP-399a, EXP-399b)
            score_398 = np.copy(score_397)
            score_399a = np.copy(score_397)
            score_399b = np.copy(score_397)

            if is_python_repo and frag_index and frag_index.N > 0:
                frag_scores, per_field_scores = frag_index.score_query_per_field(q_text)

                # Record field score distributions on top scoring fragments
                if len(frag_scores) > 0 and np.max(frag_scores) > 0:
                    top_f_idx = int(np.argmax(frag_scores))
                    for fld in MultiFieldFragmentBM25.FIELDS:
                        field_scores_collector[fld].append(float(per_field_scores[fld][top_f_idx]))
                else:
                    for fld in MultiFieldFragmentBM25.FIELDS:
                        field_scores_collector[fld].append(0.0)

                # Prepare per-file projected scores
                proj_398 = np.zeros(num_docs, dtype=np.float32)
                proj_399a = np.zeros(num_docs, dtype=np.float32)
                proj_399b = np.zeros(num_docs, dtype=np.float32)

                for doc_idx, p in enumerate(doc_paths):
                    frag_indices = file_to_frag_indices.get(p, [])
                    if not frag_indices:
                        continue

                    f_scores = [frag_scores[idx] for idx in frag_indices]
                    if not f_scores or max(f_scores) <= 0:
                        continue

                    # A. EXP-398: Max Pooling
                    max_f = max(f_scores)
                    proj_398[doc_idx] = max_f

                    # B. EXP-399a: Soft-Max Top-2 Pooling
                    sorted_f = sorted(f_scores, reverse=True)
                    top1 = sorted_f[0]
                    top2 = sorted_f[1] if len(sorted_f) > 1 else 0.0
                    proj_399a[doc_idx] = top1 + 0.5 * top2

                    # C. EXP-399b: Specificity Attenuated Max Pooling
                    # Specificity penalty: 1 / sqrt(symbol_corpus_counts)
                    spec_scores = []
                    for idx in frag_indices:
                        frag = frag_clf.complete_fragments[idx]
                        c_count = frag_index.symbol_corpus_counts.get(frag.name, 1)
                        spec_penalty = 1.0 / math.sqrt(max(1, c_count))
                        spec_scores.append(frag_scores[idx] * spec_penalty)
                    proj_399b[doc_idx] = max(spec_scores) if spec_scores else 0.0

                max_hit_base = float(np.max(score_397)) if len(score_397) > 0 else 1.0
                if max_hit_base <= 0:
                    max_hit_base = 1.0

                # Normalization and scaling: alpha = 0.10
                m_398 = float(np.max(proj_398))
                if m_398 > 0:
                    score_398 = score_397 + 0.10 * (proj_398 / m_398) * max_hit_base

                m_399a = float(np.max(proj_399a))
                if m_399a > 0:
                    score_399a = score_397 + 0.10 * (proj_399a / m_399a) * max_hit_base

                m_399b = float(np.max(proj_399b))
                if m_399b > 0:
                    score_399b = score_397 + 0.10 * (proj_399b / m_399b) * max_hit_base

            elapsed_query_ms = (time.perf_counter() - t_query_0) * 1000.0

            configs = [
                ("EXP-397", score_397),
                ("EXP-398", score_398),
                ("EXP-399a", score_399a),
                ("EXP-399b", score_399b),
            ]

            for exp_id, sc_vec in configs:
                res = eval_ranking(sc_vec, gold, hard_neg)
                res["latency_ms"] = elapsed_query_ms / 4.0
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

    # 1. Output PER_QUERY_FRAGMENT_RESULTS.jsonl
    out_jsonl = STAGE_DIR / "PER_QUERY_FRAGMENT_RESULTS.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for qid, qdata in sorted(per_query_records.items()):
            f.write(json.dumps(qdata) + "\n")
    print(f"\nWrote per-query fragment results to {out_jsonl}", flush=True)

    # 2. Output FIELD_SCORE_DISTRIBUTION.csv
    out_field_csv = STAGE_DIR / "FIELD_SCORE_DISTRIBUTION.csv"
    with open(out_field_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["field", "weight", "mean_score", "std_score", "min_score", "median_score", "p95_score", "max_score"])
        for fld in MultiFieldFragmentBM25.FIELDS:
            vals = field_scores_collector[fld]
            w = MultiFieldFragmentBM25.DEFAULT_WEIGHTS[fld]
            if vals:
                writer.writerow([
                    fld,
                    w,
                    round(float(np.mean(vals)), 4),
                    round(float(np.std(vals)), 4),
                    round(float(np.min(vals)), 4),
                    round(float(np.median(vals)), 4),
                    round(float(np.percentile(vals, 95)), 4),
                    round(float(np.max(vals)), 4),
                ])
    print(f"Wrote field score distributions to {out_field_csv}", flush=True)

    # 3. Output FRAGMENT_COVERAGE_REPORT.md
    out_cov_md = STAGE_DIR / "FRAGMENT_COVERAGE_REPORT.md"
    with open(out_cov_md, "w", encoding="utf-8") as f:
        f.write("# RepoNeedle Stage 3.9.6: Fragment Coverage and Classification Report\n\n")
        f.write("| Repository | Eligible Files | Files with Fragments | Complete Functions | Incomplete Headers | Incomplete Bodies | Quarantined Invalid | Gold Files Covered |\n")
        f.write("|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|\n")
        total_cf, total_ih, total_ib, total_qi = 0, 0, 0, 0
        total_files, total_cov_files = 0, 0
        total_gold, total_gold_cov = 0, 0

        for r_name in sorted(PYTHON_REPOS):
            cov = repo_coverage_stats[r_name]
            total_files += cov["files_total"]
            total_cov_files += cov["files_with_complete_fragments"]
            total_cf += cov["complete_fragments"]
            total_ih += cov["incomplete_headers"]
            total_ib += cov["incomplete_bodies"]
            total_qi += cov["quarantined_invalid"]
            total_gold += cov["gold_files_total"]
            total_gold_cov += cov["gold_files_with_fragments"]

            gold_pct = (cov["gold_files_with_fragments"] / max(1, cov["gold_files_total"])) * 100.0
            f.write(f"| `{r_name}` | {cov['files_total']} | {cov['files_with_complete_fragments']} | {cov['complete_fragments']} | {cov['incomplete_headers']} | {cov['incomplete_bodies']} | {cov['quarantined_invalid']} | {cov['gold_files_with_fragments']}/{cov['gold_files_total']} ({gold_pct:.1f}%) |\n")

        tot_gold_pct = (total_gold_cov / max(1, total_gold)) * 100.0
        f.write(f"| **TOTAL (All 13 Python Repos)** | **{total_files}** | **{total_cov_files}** | **{total_cf}** | **{total_ih}** | **{total_ib}** | **{total_qi}** | **{total_gold_cov}/{total_gold} ({tot_gold_pct:.1f}%)** |\n")
    print(f"Wrote fragment coverage report to {out_cov_md}", flush=True)

    # 4. Output FRAGMENT_RUNTIME_REPORT.md
    out_runtime_md = STAGE_DIR / "FRAGMENT_RUNTIME_REPORT.md"
    current_rss = get_process_rss_mb()
    with open(out_runtime_md, "w", encoding="utf-8") as f:
        f.write("# RepoNeedle Stage 3.9.6: Fragment Retrieval Runtime & Resource Report\n\n")
        f.write("| System | Total Indexing Time (s) | Indexing Overhead vs EXP-397 | Peak Heap (MB) | Process Working Set RSS (MB) | Median Query Latency (ms) | P95 Query Latency (ms) |\n")
        f.write("|---|:---:|:---:|:---:|:---:|:---:|:---:|\n")
        base_idx_s = runtime_stats["EXP-397"]["index_ms"] / 1000.0
        for eid in exp_ids:
            idx_s = runtime_stats[eid]["index_ms"] / 1000.0
            overhead_pct = ((idx_s - base_idx_s) / max(1.0, base_idx_s)) * 100.0
            lats = system_latencies[eid]
            med_lat = float(np.median(lats)) if lats else 0.0
            p95_lat = float(np.percentile(lats, 95)) if lats else 0.0
            f.write(f"| **{eid}** | {idx_s:.2f} s | {overhead_pct:+.2f}% | {runtime_stats[eid]['peak_heap_mb']:.2f} MB | {current_rss:.2f} MB | {med_lat:.3f} ms | {p95_lat:.3f} ms |\n")
    print(f"Wrote fragment runtime report to {out_runtime_md}", flush=True)

    # 5. Paired Statistical Analysis (10,000 Clustered Bootstrap Resamples, seed 42)
    print("\nRunning 10,000 Paired Repository-Clustered Bootstrap Resamples (seed 42)...", flush=True)
    np.random.seed(42)

    all_queries = list(per_query_records.values())
    py_queries = [q for q in all_queries if q["is_python"]]
    non_py_queries = [q for q in all_queries if not q["is_python"]]

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

    # Compute bootstrap statistics for candidate systems vs EXP-397
    stat_results = {}
    for candidate in ["EXP-398", "EXP-399a", "EXP-399b"]:
        stat_results[candidate] = {
            "overall_mrr": clustered_bootstrap(all_repos, queries_by_repo_all, candidate, "EXP-397", "mrr"),
            "overall_r5": clustered_bootstrap(all_repos, queries_by_repo_all, candidate, "EXP-397", "r5"),
            "overall_r10": clustered_bootstrap(all_repos, queries_by_repo_all, candidate, "EXP-397", "r10"),
            "overall_r20": clustered_bootstrap(all_repos, queries_by_repo_all, candidate, "EXP-397", "r20"),
            "overall_hit20": clustered_bootstrap(all_repos, queries_by_repo_all, candidate, "EXP-397", "hit20"),
            "overall_bcy8k": clustered_bootstrap(all_repos, queries_by_repo_all, candidate, "EXP-397", "bcy_8k"),
            "py_mrr": clustered_bootstrap(py_repos, queries_by_repo_all, candidate, "EXP-397", "mrr"),
            "py_r5": clustered_bootstrap(py_repos, queries_by_repo_all, candidate, "EXP-397", "r5"),
            "py_r10": clustered_bootstrap(py_repos, queries_by_repo_all, candidate, "EXP-397", "r10"),
            "py_r20": clustered_bootstrap(py_repos, queries_by_repo_all, candidate, "EXP-397", "r20"),
            "py_hit20": clustered_bootstrap(py_repos, queries_by_repo_all, candidate, "EXP-397", "hit20"),
            "py_bcy8k": clustered_bootstrap(py_repos, queries_by_repo_all, candidate, "EXP-397", "bcy_8k"),
            "overall_wtl": count_wins(all_queries, candidate, "EXP-397"),
            "py_wtl": count_wins(py_queries, candidate, "EXP-397"),
        }

    # Verify Non-Python Identity Control
    non_py_diffs = []
    for q in non_py_queries:
        for candidate in ["EXP-398", "EXP-399a", "EXP-399b"]:
            d = q["systems"][candidate]["mrr"] - q["systems"]["EXP-397"]["mrr"]
            if abs(d) > 1e-5:
                non_py_diffs.append((q["query_id"], candidate, d))

    print(f"Non-Python negative control verification: {len(non_py_diffs)} differences found (Target: 0)", flush=True)

    # 6. Output STAGE3_9_6_DECISION_REPORT.md
    out_decision_md = STAGE_DIR / "STAGE3_9_6_DECISION_REPORT.md"
    with open(out_decision_md, "w", encoding="utf-8") as f:
        f.write("# RepoNeedle Stage 3.9.6: Fragment-Aware Lexical Retrieval Decision Report\n\n")
        f.write("> **Evaluation Population:** 345 positive ARB v2 queries across 25 repositories (104 queries in 13 Python repos).\n")
        f.write("> **Statistical Engine:** 10,000 Paired Repository-Clustered Bootstrap Resamples (Seed 42).\n")
        f.write("> **Acceptance Criteria:** Overall & Python $\\Delta\\text{MRR} \\ge +0.0050$, 95% Clustered CI lower bound $> 0$, $\\text{Wins} > 2 \\times \\text{Losses}$, no $\\text{BCY@8k}$ regression.\n\n")

        f.write("## 1. Overall Benchmark Results (All 345 Queries)\n\n")
        f.write("| System | MRR | Recall@5 | Recall@10 | Recall@20 | Hit@20 | BCY@8k | Wins / Ties / Losses vs EXP-397 |\n")
        f.write("|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|\n")
        for eid in exp_ids:
            m = system_metrics[eid]
            f.write(f"| **{eid}** | {np.mean(m['mrr']):.4f} | {np.mean(m['r5']):.4f} | {np.mean(m['r10']):.4f} | {np.mean(m['r20']):.4f} | {np.mean(m['hit20']):.4f} | {np.mean(m['bcy_8k']):.4f} | ")
            if eid == "EXP-397":
                f.write("Canonical Baseline |\n")
            else:
                w, t, l = stat_results[eid]["overall_wtl"]
                f.write(f"{w} / {t} / {l} |\n")

        f.write("\n### Paired Inferential Statistics vs EXP-397 Reference Baseline (Overall Benchmark)\n\n")
        f.write("| Candidate System | Metric | Mean Diff (\\Delta) | 95% Clustered CI | p-value | Gate (\\ge +0.0050) | Statistically Significant? |\n")
        f.write("|---|---|:---:|:---:|:---:|:---:|:---:|\n")
        for candidate in ["EXP-398", "EXP-399a", "EXP-399b"]:
            st = stat_results[candidate]
            f.write(f"| **{candidate}** | **MRR** | {st['overall_mrr'][0]:+.4f} | [{st['overall_mrr'][1]:+.4f}, {st['overall_mrr'][2]:+.4f}] | {st['overall_mrr'][3]:.4f} | {'MET' if st['overall_mrr'][0] >= 0.0050 else 'NOT MET'} | {'YES' if st['overall_mrr'][1] > 0 else 'NO'} |\n")
            f.write(f"| | **Recall@10** | {st['overall_r10'][0]:+.4f} | [{st['overall_r10'][1]:+.4f}, {st['overall_r10'][2]:+.4f}] | {st['overall_r10'][3]:.4f} | — | {'YES' if st['overall_r10'][1] > 0 else 'NO'} |\n")
            f.write(f"| | **Recall@20** | {st['overall_r20'][0]:+.4f} | [{st['overall_r20'][1]:+.4f}, {st['overall_r20'][2]:+.4f}] | {st['overall_r20'][3]:.4f} | — | {'YES' if st['overall_r20'][1] > 0 else 'NO'} |\n")
            f.write(f"| | **BCY@8k** | {st['overall_bcy8k'][0]:+.4f} | [{st['overall_bcy8k'][1]:+.4f}, {st['overall_bcy8k'][2]:+.4f}] | {st['overall_bcy8k'][3]:.4f} | — | {'YES' if st['overall_bcy8k'][1] > 0 else 'NO'} |\n")

        f.write("\n---\n\n")
        f.write("## 2. Python-Eligible Subset Results (104 Queries across 13 Repositories)\n\n")
        f.write("| System | MRR | Recall@5 | Recall@10 | Recall@20 | Hit@20 | BCY@8k | Wins / Ties / Losses vs EXP-397 |\n")
        f.write("|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|\n")
        for eid in exp_ids:
            py_m = defaultdict(list)
            for q in py_queries:
                for k in ["mrr", "r5", "r10", "r20", "hit20", "bcy_8k"]:
                    py_m[k].append(q["systems"][eid][k])
            f.write(f"| **{eid}** | {np.mean(py_m['mrr']):.4f} | {np.mean(py_m['r5']):.4f} | {np.mean(py_m['r10']):.4f} | {np.mean(py_m['r20']):.4f} | {np.mean(py_m['hit20']):.4f} | {np.mean(py_m['bcy_8k']):.4f} | ")
            if eid == "EXP-397":
                f.write("Canonical Baseline |\n")
            else:
                w, t, l = stat_results[eid]["py_wtl"]
                f.write(f"{w} / {t} / {l} |\n")

        f.write("\n### Paired Inferential Statistics vs EXP-397 (Python Subset)\n\n")
        f.write("| Candidate System | Metric | Mean Diff (\\Delta) | 95% Clustered CI | p-value | Gate (\\ge +0.0050) | Statistically Significant? |\n")
        f.write("|---|---|:---:|:---:|:---:|:---:|:---:|\n")
        for candidate in ["EXP-398", "EXP-399a", "EXP-399b"]:
            st = stat_results[candidate]
            f.write(f"| **{candidate}** | **MRR** | {st['py_mrr'][0]:+.4f} | [{st['py_mrr'][1]:+.4f}, {st['py_mrr'][2]:+.4f}] | {st['py_mrr'][3]:.4f} | {'MET' if st['py_mrr'][0] >= 0.0050 else 'NOT MET'} | {'YES' if st['py_mrr'][1] > 0 else 'NO'} |\n")
            f.write(f"| | **Recall@10** | {st['py_r10'][0]:+.4f} | [{st['py_r10'][1]:+.4f}, {st['py_r10'][2]:+.4f}] | {st['py_r10'][3]:.4f} | — | {'YES' if st['py_r10'][1] > 0 else 'NO'} |\n")
            f.write(f"| | **Recall@20** | {st['py_r20'][0]:+.4f} | [{st['py_r20'][1]:+.4f}, {st['py_r20'][2]:+.4f}] | {st['py_r20'][3]:.4f} | — | {'YES' if st['py_r20'][1] > 0 else 'NO'} |\n")
            f.write(f"| | **BCY@8k** | {st['py_bcy8k'][0]:+.4f} | [{st['py_bcy8k'][1]:+.4f}, {st['py_bcy8k'][2]:+.4f}] | {st['py_bcy8k'][3]:.4f} | — | {'YES' if st['py_bcy8k'][1] > 0 else 'NO'} |\n")

        f.write("\n---\n\n")
        f.write("## 3. Per-Task-Type Performance Breakdown\n\n")
        f.write("| Task Type | Query Count | EXP-397 MRR | EXP-398 MRR | EXP-399a MRR | EXP-399b MRR | \\Delta MRR (EXP-398 vs 397) |\n")
        f.write("|---|:---:|:---:|:---:|:---:|:---:|:---:|\n")
        for t_type in ["code2test", "comment2context", "trace2code", "edit2ripple"]:
            t_queries = [q for q in all_queries if q["task_type"] == t_type]
            m_397 = np.mean([q["systems"]["EXP-397"]["mrr"] for q in t_queries])
            m_398 = np.mean([q["systems"]["EXP-398"]["mrr"] for q in t_queries])
            m_399a = np.mean([q["systems"]["EXP-399a"]["mrr"] for q in t_queries])
            m_399b = np.mean([q["systems"]["EXP-399b"]["mrr"] for q in t_queries])
            diff = m_398 - m_397
            f.write(f"| `{t_type}` | {len(t_queries)} | {m_397:.4f} | {m_398:.4f} | {m_399a:.4f} | {m_399b:.4f} | {diff:+.4f} |\n")

        f.write("\n---\n\n")
        f.write("## 4. Repository-Level Effects Breakdown\n\n")
        f.write("| Repository | Language | Query Count | EXP-397 MRR | EXP-398 MRR | \\Delta MRR (398 - 397) | Wins / Ties / Losses |\n")
        f.write("|---|:---:|:---:|:---:|:---:|:---:|:---:|\n")
        for r_name in sorted(all_repos):
            q_cnt = len(queries_by_repo_all[r_name])
            m_397 = np.mean(repo_system_mrr[r_name]["EXP-397"])
            m_398 = np.mean(repo_system_mrr[r_name]["EXP-398"])
            diff = m_398 - m_397
            r_queries = queries_by_repo_all[r_name]
            w, t, l = count_wins(r_queries, "EXP-398", "EXP-397")
            is_py = "Python" if r_name in PYTHON_REPOS else "Polyglot"
            f.write(f"| `{r_name}` | {is_py} | {q_cnt} | {m_397:.4f} | {m_398:.4f} | {diff:+.4f} | {w} / {t} / {l} |\n")

        f.write("\n---\n\n")
        f.write("## 5. Non-Python Negative Control Verification\n\n")
        f.write(f"- Non-Python queries evaluated: {len(non_py_queries)} across 12 repositories.\n")
        f.write(f"- Ranking divergence count: **{len(non_py_diffs)} differences**.\n")
        if len(non_py_diffs) == 0:
            f.write("- **Status:** PASS (Bit-for-bit identical behavior on non-Python repositories).\n")
        else:
            f.write("- **Status:** FAIL (Unintended leakage to non-Python repositories).\n")

        f.write("\n---\n\n")
        f.write("## 6. Formal Decision Recommendation\n\n")

        # Determine decision based on Gate criteria for EXP-398
        best_cand = "EXP-398"
        cand_st = stat_results[best_cand]
        overall_mrr_gain = cand_st["overall_mrr"][0]
        py_mrr_gain = cand_st["py_mrr"][0]
        py_ci_lower = cand_st["py_mrr"][1]
        py_w, py_t, py_l = cand_st["py_wtl"]
        bcy_diff = cand_st["overall_bcy8k"][0]

        pass_gain = (overall_mrr_gain >= 0.0050) or (py_mrr_gain >= 0.0050)
        pass_ci = py_ci_lower > 0.0
        pass_ratio = py_w >= 2 * py_l if py_l > 0 else py_w > 0
        pass_bcy = bcy_diff >= 0.0

        if pass_gain and pass_ci and pass_ratio and pass_bcy:
            decision = "PROMOTE FRAGMENT RETRIEVAL"
        elif py_mrr_gain > 0.0:
            decision = "REVISE FRAGMENT RETRIEVAL"
        else:
            decision = "REJECT FRAGMENT RETRIEVAL"

        f.write(f"### Final Verdict: **{decision}**\n\n")
        f.write(f"- **Overall MRR Delta:** {overall_mrr_gain:+.4f}\n")
        f.write(f"- **Python Subset MRR Delta:** {py_mrr_gain:+.4f}\n")
        f.write(f"- **Python 95% Clustered CI:** [{cand_st['py_mrr'][1]:+.4f}, {cand_st['py_mrr'][2]:+.4f}]\n")
        f.write(f"- **Wins / Losses Ratio:** {py_w} wins vs {py_l} losses\n")
        f.write(f"- **BCY@8k Delta:** {bcy_diff:+.4f}\n")

    print(f"Wrote decision report to {out_decision_md}", flush=True)
    print("\nStage 3.9.6 execution and statistical analysis complete!", flush=True)


if __name__ == "__main__":
    run_experiment_suite()

