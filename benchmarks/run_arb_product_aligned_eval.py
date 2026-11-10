"""
SUPPLEMENTAL product-aligned evaluation on ARB v2 positives (N=345).

NOT an official ARB score. The official evaluation (`benchmarks/run_complete_arb_evaluation.py`,
`benchmarks/run_arb_current_engine.py`) and the ARB metric definitions are unchanged. Outputs go to
`reports/experimental/phase1_product_aligned_evaluation/`.

Protocol (fixed before any results were computed; also written to config.json)
--------------------------------------------------------------------------------
Retrieval unit         FILE for every system. Candidate universe U = every path that has at least one
                       chunk in the snapshot's ARB chunk file. Gold = ARB `target_gold_files`.
Representations        fragment   = the single longest ARB chunk for the path (what the official
                                    harness gives RepoNeedle; truncated at 25,000 chars, which never
                                    binds because ARB chunks are capped at 8,000 chars).
                       wholefile  = the path's `file` chunk header lines before the first symbol,
                                    followed by every `symbol` chunk in line order
                                    (`run_arb_evaluator_audit.reconstruct_file`).
Systems (full ranking) rn_fragment      RepoNeedle engine, fragment documents
                       rn_wholefile     RepoNeedle engine, whole-file documents
                       bm25_fragment    ARB BM25 over one fragment document per file
                       bm25_wholefile   ARB BM25 over one whole-file document per file
                       bm25_chunks      ARB BM25 over all chunks (the official baseline). Chunk scores
                                        map to files by MAX (best chunk), i.e. first occurrence in the
                                        score-sorted chunk list; this is ARB's own `unique_ranked_paths`
                                        rule, not a choice made here.
RepoNeedle ranking     The complete ranking the engine passes to CUD-Pack (all files, fused score).
Ties                   Score descending, then path ascending (both engines' native order; asserted).
Metrics                File-level MRR, Recall@5/10/20 with ARB `reciprocal_rank` / `recall_at`, plus an
                       independent re-implementation that must agree on every query.
Packed context         CUD-Pack output at 8,000 tokens (task label passed, as in the official harness):
                       gold coverage, success (>=1 gold packed), utilisation, files packed, unselected
                       file count. Unselected files get NO positions.
Official sequence      Packed files then corpus order. Recorded ONLY for fidelity against the official
                       current-engine run; never used as a full-ranking metric.
Statistics             Paired differences per query; repository-clustered bootstrap (resample
                       repositories with replacement), 10,000 resamples, seed 20261109, 95% percentile CI.

Usage
-----
    python benchmarks/run_arb_product_aligned_eval.py --shard 0 --num-shards 4      # x4 in parallel
    python benchmarks/run_arb_product_aligned_eval.py --merge
    python benchmarks/run_arb_product_aligned_eval.py --check-determinism 4         # re-run 4 snapshots
"""

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
OUT_DIR = ROOT_DIR / "reports" / "experimental" / "phase1_product_aligned_evaluation"
CURRENT_DIR = ROOT_DIR / "reports" / "arb_v2_current_engine"
HIST_DIR = ROOT_DIR / "reports" / "full_arb_validation"
PHASE0_DIR = ROOT_DIR / "reports" / "experimental" / "phase0_evaluator_audit"
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

SUBSETS = ["code2test", "comment2context", "trace2code", "edit2ripple"]
SYSTEMS = ["rn_fragment", "rn_wholefile", "bm25_fragment", "bm25_wholefile", "bm25_chunks"]
METRICS = ["mrr", "recall@5", "recall@10", "recall@20"]
KS = (5, 10, 20)
BUDGET = 8000
TOP_N_STORED = 100
BOOT_N = 10_000
BOOT_SEED = 20261109
COMPARISONS = [
    ("rn_wholefile", "rn_fragment", "Representation effect on RepoNeedle"),
    ("bm25_wholefile", "bm25_fragment", "Representation effect on BM25"),
    ("rn_fragment", "bm25_fragment", "RepoNeedle vs BM25, matched fragment input"),
    ("rn_wholefile", "bm25_wholefile", "RepoNeedle vs BM25, matched whole-file input"),
    ("rn_wholefile", "bm25_chunks", "RepoNeedle whole-file vs official chunk BM25 (different BM25 unit)"),
]

CONFIG = {
    "evaluation": "supplemental product-aligned full-ranking evaluation (NOT an official ARB score)",
    "dataset": "ARB v2 positive split: v2_code2test, v2_comment2context, v2_trace2code, v2_edit2ripple",
    "corpus_manifest": "data/corpus/v2_selective_mixed/corpus_manifest.jsonl",
    "retrieval_unit": "file",
    "candidate_universe": "paths with >=1 chunk in the snapshot chunk file",
    "representations": {
        "fragment": "longest ARB chunk per path, [:25000]",
        "wholefile": "file-chunk header lines before first symbol + all symbol chunks in line order",
    },
    "systems": SYSTEMS,
    "chunk_to_file_rule": "max (best chunk score) = ARB unique_ranked_paths order",
    "tie_rule": "score desc, path asc",
    "metrics": METRICS + ["reciprocal_rank", "gold_positions"],
    "packed_context_budget_tokens": BUDGET,
    "task_label_passed_to_engine": True,
    "stored_ranking_depth": TOP_N_STORED,
    "bootstrap": {"type": "paired, repository-clustered percentile", "resamples": BOOT_N, "seed": BOOT_SEED, "ci": 0.95},
    "comparisons": [{"a": a, "b": b, "label": l} for a, b, l in COMPARISONS],
}


# ---------------------------------------------------------------------------
# Pure helpers (importable without ARB data; unit-tested)
# ---------------------------------------------------------------------------

def rank_files(scored):
    """[(path, score)] -> paths ordered by score desc, path asc (documented tie rule)."""
    return [p for p, _ in sorted(scored, key=lambda x: (-x[1], x[0]))]


def collapse_chunks_max(scored_chunks):
    """[(path, score)] chunk scores -> [(path, max score)] file scores."""
    best = {}
    for p, s in scored_chunks:
        if p not in best or s > best[p]:
            best[p] = s
    return list(best.items())


def file_metrics(gold, ranked_paths):
    """Independent implementation of file-level MRR and Recall@K (cross-checked against ARB)."""
    g = set(gold)
    rr = 0.0
    for i, p in enumerate(ranked_paths, start=1):
        if p in g:
            rr = 1.0 / i
            break
    out = {"mrr": rr}
    for k in KS:
        out[f"recall@{k}"] = len(g & set(ranked_paths[:k])) / len(g) if g else 0.0
    return out


def gold_positions(gold, ranked_paths):
    pos = {p: i for i, p in enumerate(ranked_paths, start=1)}
    return {g: pos.get(g) for g in gold}


def clustered_bootstrap_ci(diffs, clusters, n_boot=BOOT_N, seed=BOOT_SEED):
    """Paired repository-clustered percentile CI of the mean difference."""
    rng = np.random.default_rng(seed)
    by = defaultdict(list)
    for d, c in zip(diffs, clusters):
        by[c].append(d)
    groups = [np.asarray(v, dtype=float) for _, v in sorted(by.items())]
    k = len(groups)
    boots = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.integers(0, k, size=k)
        boots[b] = np.concatenate([groups[i] for i in pick]).mean()
    return [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]


class PrecomputedBM25:
    """ARB `rank_chunks_bm25_with_scores`, with tokenisation hoisted out of the per-query loop.
    Arithmetic is replicated term for term; equality with ARB's function is asserted at runtime."""

    def __init__(self, chunks, tokenize, chunk_text, k1, b):
        self.chunks, self.tokenize, self.k1, self.b = chunks, tokenize, k1, b
        self.doc_tokens = [tokenize(chunk_text(c)) for c in chunks]
        self.lengths = [len(t) for t in self.doc_tokens]
        self.avg = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        self.df = Counter()
        for t in self.doc_tokens:
            self.df.update(set(t))
        self.tf = [Counter(t) for t in self.doc_tokens]
        self.total = max(1, len(chunks))

    def rank(self, query_text):
        q = self.tokenize(query_text)
        if not q:
            return [(0.0, c) for c in self.chunks]
        qc = Counter(q)
        scored = []
        for chunk, tc, dl in zip(self.chunks, self.tf, self.lengths):
            score = 0.0
            for token, query_count in qc.items():
                tf = tc.get(token, 0)
                if not tf:
                    continue
                df = self.df[token]
                idf = math.log(1.0 + (self.total - df + 0.5) / (df + 0.5))
                length_norm = 1.0 - self.b
                if self.avg > 0:
                    length_norm += self.b * (dl / self.avg)
                denominator = tf + self.k1 * length_norm
                score += query_count * idf * ((tf * (self.k1 + 1.0)) / denominator)
            scored.append((score, str(chunk.get("path", "")), str(chunk.get("chunk_id", "")), chunk))
        scored.sort(key=lambda item: (-item[0], item[1], item[2]))
        return [(item[0], item[3]) for item in scored]


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def _load():
    from agent_retrieval_bench.baseline import read_jsonl
    manifest = {}
    for row in _jsonl(ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"):
        manifest[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]
    by_corpus = defaultdict(list)
    for name in SUBSETS:
        for r in read_jsonl(ARB_DIR / "data" / "benchmark" / f"v2_{name}" / "samples.jsonl"):
            r["_subset_name"] = name
            by_corpus[(r["repo"], r["base_commit"])].append(r)
    return manifest, by_corpus


def _engine_ranking(engine, query, task_enum, universe):
    """Run retrieve(); return (full ranking [(path, fused)], packed paths, result, latency_ms)."""
    captured = {}
    original = engine.budget_optimizer.pack_context

    def capture(candidate_files, *a, **kw):
        captured["r"] = [(d.path, float(s)) for d, s, _ in candidate_files]
        return original(candidate_files, *a, **kw)

    engine.budget_optimizer.pack_context = capture
    try:
        t0 = time.perf_counter()
        res = engine.retrieve(query=query, budget_tokens=BUDGET, task_type=task_enum)
        latency = (time.perf_counter() - t0) * 1000
    finally:
        engine.budget_optimizer.pack_context = original
    ranking = captured.get("r", [])
    assert [p for p, _ in ranking] == rank_files(ranking), "engine order violates documented tie rule"
    assert {p for p, _ in ranking} <= universe, "engine ranked a path outside the snapshot"
    packed = [sf.path for sf in res.selected_files if sf.path in universe]
    return ranking, packed, res, latency


def evaluate_snapshot(key, group, manifest):
    from agent_retrieval_bench.baseline import (
        read_jsonl, target_gold_files, query_text_for_eval, unique_ranked_paths,
        rank_chunks_bm25_with_scores, recall_at, reciprocal_rank, tokenize, chunk_text, BM25_K1, BM25_B,
    )
    from run_arb_evaluator_audit import reconstruct_file
    from reponeedle.engine import RepoNeedleEngine
    from reponeedle.models import FileDoc, TaskType

    chunks = read_jsonl(manifest[key])
    p2c = defaultdict(list)
    for c in chunks:
        if c.get("path"):
            p2c[c["path"]].append(c)
    universe = set(p2c)
    corpus_order = list(p2c)
    fragment, wholefile = {}, {}
    for c in chunks:
        p, t = c.get("path"), c.get("text", "")
        if p and (p not in fragment or len(t) > len(fragment[p])):
            fragment[p] = t
    assert max((len(t) for t in fragment.values()), default=0) <= 25000, "fragment truncation would bind"
    for p, cs in p2c.items():
        wholefile[p] = reconstruct_file(cs)

    def make_engine(texts, cut):
        return RepoNeedleEngine.from_documents(
            [FileDoc(path=p, content=(t[:25000] if cut else t), is_test="test" in p.lower()) for p, t in texts.items()])

    eng_frag, eng_whole = make_engine(fragment, True), make_engine(wholefile, False)
    bm_chunks = PrecomputedBM25(chunks, tokenize, chunk_text, BM25_K1, BM25_B)
    bm_frag = PrecomputedBM25([{"path": p, "chunk_id": p, "text": t} for p, t in fragment.items()], tokenize, chunk_text, BM25_K1, BM25_B)
    bm_whole = PrecomputedBM25([{"path": p, "chunk_id": p, "text": t} for p, t in wholefile.items()], tokenize, chunk_text, BM25_K1, BM25_B)
    enum = {"code2test": TaskType.CODE2TEST, "trace2code": TaskType.TRACE2CODE, "edit2ripple": TaskType.EDIT2RIPPLE}
    first = True

    for s in group:
        gold = target_gold_files(s)
        if not gold:
            continue
        task = s.get("task_type", s["_subset_name"])
        q = query_text_for_eval(s)
        t_enum = enum.get(task, TaskType.COMMENT2CONTEXT)

        rank_frag, packed_frag, res_frag, lat_frag = _engine_ranking(eng_frag, q, t_enum, universe)
        rank_whole, packed_whole, res_whole, lat_whole = _engine_ranking(eng_whole, q, t_enum, universe)

        timings = {}
        bm25_paths = {}
        for name, idx in [("bm25_chunks", bm_chunks), ("bm25_fragment", bm_frag), ("bm25_wholefile", bm_whole)]:
            t0 = time.perf_counter()
            ranked = idx.rank(q)
            timings[name] = (time.perf_counter() - t0) * 1000
            bm25_paths[name] = unique_ranked_paths([c for _, c in ranked])
            if first:  # exactness of the hoisted BM25 against ARB's own implementation
                ref_chunks = idx.chunks
                ref = rank_chunks_bm25_with_scores(q, ref_chunks)
                assert [(round(a, 12), str(c.get("chunk_id"))) for a, c in ref] == \
                       [(round(a, 12), str(c.get("chunk_id"))) for a, c in ranked], f"BM25 mismatch: {name}"
        first = False

        rankings = {
            "rn_fragment": [p for p, _ in rank_frag],
            "rn_wholefile": [p for p, _ in rank_whole],
            **bm25_paths,
        }
        for name, paths in rankings.items():
            assert len(paths) == len(set(paths)) and set(paths) <= universe, f"{name}: invalid ranking"

        metrics, independent_ok = {}, True
        for name, paths in rankings.items():
            m = file_metrics(gold, paths)
            arb = {"mrr": reciprocal_rank(set(gold), paths), **{f"recall@{k}": recall_at(set(gold), paths, k) for k in KS}}
            independent_ok &= all(abs(m[k] - arb[k]) < 1e-15 for k in METRICS)
            metrics[name] = arb

        official_seq = packed_frag + [p for p in corpus_order if p not in set(packed_frag)]

        def packed_stats(packed, res):
            gs, ps = set(gold), set(packed)
            return {"n_files": len(packed), "tokens": int(res.total_tokens), "utilisation": res.total_tokens / BUDGET,
                    "gold_coverage": len(gs & ps) / len(gs), "success": bool(gs & ps),
                    "gold_packed": sorted(gs & ps), "unselected_files": len(universe) - len(ps)}

        record = {
            "sample_id": s["id"], "task_type": task, "repo": key[0], "base_commit": key[1],
            "n_candidate_files": len(universe), "gold_files": gold,
            "metrics": metrics,
            "reciprocal_rank": {n: metrics[n]["mrr"] for n in rankings},
            "gold_positions": {n: gold_positions(gold, p) for n, p in rankings.items()},
            "packed": {"fragment": packed_stats(packed_frag, res_frag), "wholefile": packed_stats(packed_whole, res_whole)},
            "official_sequence_fidelity_only": {"mrr": reciprocal_rank(set(gold), official_seq),
                                                **{f"recall@{k}": recall_at(set(gold), official_seq, k) for k in KS}},
            "latency_ms": {"rn_fragment_retrieve": lat_frag, "rn_wholefile_retrieve": lat_whole, **timings},
            "independent_metrics_agree": independent_ok,
            "ranking_hash": {n: hashlib.sha256("\n".join(p).encode()).hexdigest()[:16] for n, p in rankings.items()},
        }
        ranking_record = {"sample_id": s["id"], "top": {n: p[:TOP_N_STORED] for n, p in rankings.items()},
                          "rn_scores_top": {"rn_fragment": [round(x, 6) for _, x in rank_frag[:TOP_N_STORED]],
                                            "rn_wholefile": [round(x, 6) for _, x in rank_whole[:TOP_N_STORED]]}}
        yield record, ranking_record


def run(shard, num_shards, keys_filter=None, out_dir=OUT_DIR):
    manifest, by_corpus = _load()
    (out_dir / "per_query").mkdir(parents=True, exist_ok=True)
    (out_dir / "rankings").mkdir(parents=True, exist_ok=True)
    if not (out_dir / "config.json").exists():
        (out_dir / "config.json").write_text(json.dumps(CONFIG, indent=2), encoding="utf-8")
    keys = sorted(by_corpus) if keys_filter is None else keys_filter
    mine = [k for i, k in enumerate(keys) if i % num_shards == shard]
    pq = out_dir / "per_query" / f"shard_{shard}_of_{num_shards}.jsonl"
    rk = out_dir / "rankings" / f"shard_{shard}_of_{num_shards}.jsonl"
    done = {r["sample_id"] for r in _jsonl(pq)} if pq.exists() else set()
    t0 = time.time()
    with open(pq, "a", encoding="utf-8") as fq, open(rk, "a", encoding="utf-8") as fr:
        for n, key in enumerate(mine, start=1):
            group = [s for s in by_corpus[key] if s["id"] not in done]
            if not group or not manifest.get(key) or not manifest[key].is_file():
                continue
            for rec, rrec in evaluate_snapshot(key, group, manifest):
                fq.write(json.dumps(rec) + "\n")
                fr.write(json.dumps(rrec) + "\n")
            fq.flush(); fr.flush()
            print(f"[phase1 {shard}/{num_shards}] {n}/{len(mine)} snapshots, {time.time() - t0:.0f}s", file=sys.stderr, flush=True)


def check_determinism(n_snapshots):
    """Re-run the first n snapshots into a scratch directory and compare ranking hashes."""
    import tempfile
    manifest, by_corpus = _load()
    keys = sorted(by_corpus)[:n_snapshots]
    tmp = Path(tempfile.mkdtemp(prefix="phase1_det_"))
    run(0, 1, keys_filter=keys, out_dir=tmp)
    new = {r["sample_id"]: r for r in _jsonl(tmp / "per_query" / "shard_0_of_1.jsonl")}
    old = {}
    for p in (OUT_DIR / "per_query").glob("shard_*.jsonl"):
        for r in _jsonl(p):
            old[r["sample_id"]] = r
    same = sum(new[i]["ranking_hash"] == old[i]["ranking_hash"] and new[i]["metrics"] == old[i]["metrics"]
               for i in new if i in old)
    result = {"snapshots": len(keys), "queries": len(new), "compared": sum(i in old for i in new), "identical": same}
    (OUT_DIR / "determinism_check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def merge():
    rows = {}
    dupes = 0
    for p in sorted((OUT_DIR / "per_query").glob("shard_*.jsonl")):
        for r in _jsonl(p):
            dupes += r["sample_id"] in rows
            rows[r["sample_id"]] = r
    from agent_retrieval_bench.baseline import read_jsonl, target_gold_files
    expected = {}
    for name in SUBSETS:
        for s in read_jsonl(ARB_DIR / "data" / "benchmark" / f"v2_{name}" / "samples.jsonl"):
            if target_gold_files(s):
                expected[s["id"]] = (name, s["repo"])
    ids = sorted(rows)

    official_ref = {r["sample_id"]: r for p in CURRENT_DIR.glob("shard_*.jsonl") for r in _jsonl(p)}
    hist = {r["sample_id"]: r for r in _jsonl(HIST_DIR / "checkpoint_positive.jsonl")}
    p0_frag = {r["sample_id"]: r for p in PHASE0_DIR.glob("shard_*.jsonl") for r in _jsonl(p)}
    p0_whole = {r["sample_id"]: r for p in list((PHASE0_DIR / "reconstructed_docs").glob("shard_*.jsonl"))
                + list(PHASE0_DIR.glob("c2c_fast_*/reconstructed_docs/traces.jsonl")) for r in _jsonl(p)}
    eq = lambda a, b: all(abs(a[k] - b[k]) < 1e-12 for k in METRICS)
    fidelity = {
        "queries_expected": len(expected), "queries_present": len(ids),
        "missing": sorted(set(expected) - set(rows)), "unexpected": sorted(set(rows) - set(expected)),
        "duplicate_rows": dupes,
        "missing_gold_labels": sum(1 for i in ids if not rows[i]["gold_files"]),
        "task_counts": dict(Counter(rows[i]["task_type"] for i in ids)),
        "task_and_repo_match_dataset": sum(1 for i in ids if expected.get(i) == (rows[i]["task_type"], rows[i]["repo"])),
        "independent_metric_agreement": sum(1 for i in ids if rows[i]["independent_metrics_agree"]),
        "official_sequence_vs_official_current_engine_run": sum(
            1 for i in ids if i in official_ref and eq(rows[i]["official_sequence_fidelity_only"], official_ref[i])),
        "bm25_chunks_vs_historical_official_bm25": sum(
            1 for i in ids if i in hist and eq(rows[i]["metrics"]["bm25_chunks"], hist[i]["bm25"])),
        "rn_fragment_vs_phase0_audit": f"{sum(1 for i in ids if i in p0_frag and eq(rows[i]['metrics']['rn_fragment'], p0_frag[i]['rn_full']))}/{sum(1 for i in ids if i in p0_frag)}",
        "rn_wholefile_vs_phase0_audit": f"{sum(1 for i in ids if i in p0_whole and eq(rows[i]['metrics']['rn_wholefile'], p0_whole[i]['rn_full']))}/{sum(1 for i in ids if i in p0_whole)}",
        "bm25_wholefile_vs_phase0_audit": f"{sum(1 for i in ids if i in p0_whole and eq(rows[i]['metrics']['bm25_wholefile'], p0_whole[i]['bm25_file_reconstructed']))}/{sum(1 for i in ids if i in p0_whole)}",
        "bm25_fragment_vs_phase0_audit": f"{sum(1 for i in ids if i in p0_whole and eq(rows[i]['metrics']['bm25_fragment'], p0_whole[i]['bm25_file_longest_chunk']))}/{sum(1 for i in ids if i in p0_whole)}",
    }

    def agg(sel):
        out = {"n_queries": len(sel), "n_repositories": len({rows[i]["repo"] for i in sel})}
        for s in SYSTEMS:
            out[s] = {k: float(np.mean([rows[i]["metrics"][s][k] for i in sel])) for k in METRICS}
        for rep in ["fragment", "wholefile"]:
            out[f"packed_{rep}"] = {k: float(np.mean([float(rows[i]["packed"][rep][k]) for i in sel]))
                                    for k in ["n_files", "utilisation", "gold_coverage", "success", "unselected_files"]}
        lat = lambda k: [rows[i]["latency_ms"][k] for i in sel]
        out["latency_ms"] = {k: {"mean": float(np.mean(lat(k))), "p50": float(np.median(lat(k)))}
                             for k in ["rn_fragment_retrieve", "rn_wholefile_retrieve", "bm25_chunks", "bm25_fragment", "bm25_wholefile"]}
        return out

    def cis(sel):
        repos = [rows[i]["repo"] for i in sel]
        res = []
        for a, b, label in COMPARISONS:
            for k in METRICS:
                d = np.array([rows[i]["metrics"][a][k] - rows[i]["metrics"][b][k] for i in sel])
                ci = clustered_bootstrap_ci(d, repos)
                res.append({"a": a, "b": b, "label": label, "metric": k, "mean_diff": float(d.mean()),
                            "wins": int((d > 0).sum()), "ties": int((d == 0).sum()), "losses": int((d < 0).sum()),
                            "ci95": ci, "excludes_zero": bool(ci[0] > 0 or ci[1] < 0)})
        return res

    groups = {"overall": ids, **{t: [i for i in ids if rows[i]["task_type"] == t] for t in SUBSETS}}
    aggregate = {g: agg(sel) for g, sel in groups.items()}
    intervals = {g: cis(sel) for g, sel in groups.items()}
    (OUT_DIR / "fidelity.json").write_text(json.dumps(fidelity, indent=2), encoding="utf-8")
    (OUT_DIR / "aggregate.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    (OUT_DIR / "confidence_intervals.json").write_text(json.dumps(intervals, indent=2), encoding="utf-8")
    meta = {
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True).stdout.strip(),
        "working_tree_dirty": bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT_DIR, capture_output=True, text=True).stdout.strip()),
        "python": sys.version.split()[0], "numpy": np.__version__, "platform": platform.platform(),
        "merged_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    try:
        import reponeedle
        meta["reponeedle_version"] = reponeedle.__version__
    except Exception:
        pass
    (OUT_DIR / "run_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return fidelity, aggregate, intervals


def main(argv=None):
    ap = argparse.ArgumentParser(description="Supplemental product-aligned ARB v2 evaluation (not official).")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--num-shards", type=int, default=1)
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--check-determinism", type=int, default=0, metavar="N_SNAPSHOTS")
    args = ap.parse_args(argv)
    if not (ARB_DIR / "src").exists():
        print(f"Missing ARB checkout at {ARB_DIR}", file=sys.stderr)
        return 2
    if args.merge:
        fidelity, _, _ = merge()
        print(json.dumps(fidelity, indent=2))
    elif args.check_determinism:
        print(json.dumps(check_determinism(args.check_determinism), indent=2))
    else:
        run(args.shard, args.num_shards)
    return 0


if __name__ == "__main__":
    sys.exit(main())
