"""
Re-measure the *current* RepoNeedle engine on the ARB v2 positive split (N=345).

Why this exists
---------------
README Part A was produced on 2026-10-28 by `benchmarks/run_complete_arb_evaluation.py` with the
engine at commit 8e00425 (tag `v0.1.0-baseline`). Later engine changes (before the 1.1.0 release)
changed RepoNeedle's rankings, so those numbers do not describe 1.1.0 or later. This script measures
RepoNeedle only, replicating that harness's RepoNeedle path exactly (document construction,
task-type conditioning, budget 8,000, chunk ordering, ARB `sample_metrics` and `pack_files`).
The official BM25 / Lexical / RepoMap baselines do not depend on RepoNeedle code, so their
historical per-sample values are reused for comparison.

Outputs go to a NEW directory (default `reports/arb_v2_current_engine/`). Historical reports in
`reports/full_arb_validation/` are only read, never written.

Usage
-----
    # run shards in parallel (each resumable), then merge
    python benchmarks/run_arb_current_engine.py --shard 0 --num-shards 3
    python benchmarks/run_arb_current_engine.py --shard 1 --num-shards 3
    python benchmarks/run_arb_current_engine.py --shard 2 --num-shards 3
    python benchmarks/run_arb_current_engine.py --merge

Validation: setting REPONEEDLE_CODE_ROOT to a checkout of tag `v0.1.0-baseline` must reproduce the
historical per-sample RepoNeedle metrics exactly (see docs/BENCHMARK_CONFIGURATION.md).
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
HIST_DIR = ROOT_DIR / "reports" / "full_arb_validation"
DEFAULT_OUT = ROOT_DIR / "reports" / "arb_v2_current_engine"
CODE_ROOT = Path(os.environ.get("REPONEEDLE_CODE_ROOT", str(ROOT_DIR)))
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(CODE_ROOT))

SUBSETS = ["code2test", "comment2context", "trace2code", "edit2ripple"]
METRICS = ["mrr", "recall@5", "recall@10", "recall@20", "bcy@4k", "bcy@8k", "bcy@16k", "bcy@32k"]
BCY_BUDGETS = (4000, 8000, 16000, 32000)


def _jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def run_shard(shard: int, num_shards: int, out_dir: Path, limit_snapshots=None) -> None:
    from agent_retrieval_bench.baseline import (
        read_jsonl, target_gold_files, hard_negative_files, query_text_for_eval,
        sample_metrics, unique_ranked_paths,
    )
    from agent_retrieval_bench.bcy_curve import pack_files, CorpusFileCache
    import reponeedle
    from reponeedle.engine import RepoNeedleEngine
    from reponeedle.models import FileDoc, TaskType

    manifest = {}
    for row in _jsonl(ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"):
        manifest[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]
    corpus_cache = CorpusFileCache({k: Path(v) for k, v in manifest.items()})

    samples = []
    for name in SUBSETS:
        for r in read_jsonl(ARB_DIR / "data" / "benchmark" / f"v2_{name}" / "samples.jsonl"):
            r["_subset_name"] = name
            samples.append(r)
    by_corpus = defaultdict(list)
    for s in samples:
        by_corpus[(s["repo"], s["base_commit"])].append(s)
    keys = sorted(by_corpus)[: limit_snapshots or None]
    mine = [k for i, k in enumerate(keys) if i % num_shards == shard]

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"shard_{shard}_of_{num_shards}.jsonl"
    done = {r["sample_id"] for r in _jsonl(out_path)} if out_path.exists() else set()
    enum = {"code2test": TaskType.CODE2TEST, "trace2code": TaskType.TRACE2CODE, "edit2ripple": TaskType.EDIT2RIPPLE}
    version = getattr(reponeedle, "__version__", "unknown")
    t0 = time.time()

    for n, key in enumerate(mine, start=1):
        group = [s for s in by_corpus[key] if s["id"] not in done and target_gold_files(s)]
        cpath = manifest.get(key)
        if not group or not cpath or not cpath.is_file():
            continue
        chunks = read_jsonl(cpath)
        file_texts = {}
        for c in chunks:
            p, t = c.get("path"), c.get("text", "")
            if p and (p not in file_texts or len(t) > len(file_texts[p])):
                file_texts[p] = t
        docs = [FileDoc(path=p, content=t[:25000], is_test="test" in p.lower()) for p, t in file_texts.items()]
        t_idx = time.perf_counter()
        engine = RepoNeedleEngine.from_documents(docs)
        index_ms = (time.perf_counter() - t_idx) * 1000
        path_to_chunks = defaultdict(list)
        for c in chunks:
            if c.get("path"):
                path_to_chunks[c["path"]].append(c)

        with open(out_path, "a", encoding="utf-8") as f:
            for s in group:
                task = s.get("task_type", s["_subset_name"])
                gold = target_gold_files(s)
                t_q = time.perf_counter()
                res = engine.retrieve(query=query_text_for_eval(s), budget_tokens=8000,
                                      task_type=enum.get(task, TaskType.COMMENT2CONTEXT))
                latency_ms = (time.perf_counter() - t_q) * 1000
                ranked, seen = [], set()
                for sf in res.selected_files:
                    if sf.path in path_to_chunks and sf.path not in seen:
                        ranked.extend(path_to_chunks[sf.path])
                        seen.add(sf.path)
                for p, chs in path_to_chunks.items():
                    if p not in seen:
                        ranked.extend(chs)
                        seen.add(p)
                m = sample_metrics(gold, ranked, hard_negative_files=hard_negative_files(s))
                top = unique_ranked_paths(ranked)[:20]
                bcy = {b: pack_files(key[0], key[1], top, set(gold), corpus_cache, b)["bcy"] for b in BCY_BUDGETS}
                f.write(json.dumps({
                    "sample_id": s["id"], "task_type": task, "repo": key[0], "base_commit": key[1],
                    "engine_version": version, "abstained": bool(res.abstained),
                    "mrr": m["MRR"], "recall@5": m["Recall@5"], "recall@10": m["Recall@10"],
                    "recall@20": m["Recall@20"], "bcy@4k": bcy[4000], "bcy@8k": bcy[8000],
                    "bcy@16k": bcy[16000], "bcy@32k": bcy[32000], "top_files": top,
                    "latency_ms": latency_ms, "index_ms": index_ms,
                }) + "\n")
        corpus_cache._cache.clear()
        del engine, docs, chunks, file_texts, path_to_chunks
        print(f"[shard {shard}/{num_shards}] {n}/{len(mine)} snapshots, {time.time() - t0:.0f}s",
              file=sys.stderr, flush=True)


def _boot_ci(diffs, groups, n_boot=5000, seed=0):
    rng = np.random.default_rng(seed)
    diffs = np.asarray(diffs, dtype=float)
    sample = [float(np.mean(rng.choice(diffs, size=len(diffs), replace=True))) for _ in range(n_boot)]
    by = defaultdict(list)
    for d, g in zip(diffs, groups):
        by[g].append(d)
    clusters = list(by.values())
    clustered = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(clusters), size=len(clusters))
        clustered.append(float(np.mean(np.concatenate([clusters[i] for i in pick]))))
    return ([float(np.percentile(sample, 2.5)), float(np.percentile(sample, 97.5))],
            [float(np.percentile(clustered, 2.5)), float(np.percentile(clustered, 97.5))])


def merge(out_dir: Path) -> dict:
    rows = {}
    for p in sorted(out_dir.glob("shard_*.jsonl")):
        for r in _jsonl(p):
            rows[r["sample_id"]] = r
    hist = {r["sample_id"]: r for r in _jsonl(HIST_DIR / "checkpoint_positive.jsonl")}
    ids = sorted(set(rows) & set(hist))
    systems = {
        "reponeedle_current": lambda i: rows[i],
        "reponeedle_2026_10_28": lambda i: hist[i]["reponeedle"],
        "bm25": lambda i: hist[i]["bm25"], "lexical": lambda i: hist[i]["lexical"],
        "repomap": lambda i: hist[i]["repomap"],
    }

    def agg(sel):
        return {s: {m: float(np.mean([get(i)[m] for i in sel])) for m in METRICS} for s, get in systems.items()}

    summary = {
        "n_samples": len(ids), "n_expected": len(hist),
        "engine_versions": sorted({rows[i]["engine_version"] for i in ids}),
        "abstained_count": sum(rows[i]["abstained"] for i in ids),
        "overall": agg(ids),
        "by_task": {t: dict(n=len(sel), **agg(sel)) for t in SUBSETS
                    for sel in [[i for i in ids if rows[i]["task_type"] == t]] if sel},
        "latency_ms": {"mean": float(np.mean([rows[i]["latency_ms"] for i in ids])),
                       "p50": float(np.median([rows[i]["latency_ms"] for i in ids])),
                       "p95": float(np.percentile([rows[i]["latency_ms"] for i in ids], 95))},
        "paired_mrr": {},
        "top20_identical_to_2026_10_28": sum(rows[i]["top_files"] == hist[i]["reponeedle"]["top_files"] for i in ids),
    }
    repos = [rows[i]["repo"] for i in ids]
    cur = np.array([rows[i]["mrr"] for i in ids])
    for other in ["bm25", "lexical", "repomap", "reponeedle_2026_10_28"]:
        o = np.array([systems[other](i)["mrr"] for i in ids])
        d = cur - o
        ci, cci = _boot_ci(d, repos)
        summary["paired_mrr"][other] = {
            "mean_diff": float(d.mean()), "wins": int((d > 0).sum()), "ties": int((d == 0).sum()),
            "losses": int((d < 0).sum()), "sample_ci95": ci, "repo_clustered_ci95": cci,
        }
    (out_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="Re-measure the current RepoNeedle engine on ARB v2 positives.")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--num-shards", type=int, default=1)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--limit-snapshots", type=int, default=None, help="Validation only: first N snapshots.")
    ap.add_argument("--merge", action="store_true", help="Merge shard outputs and write SUMMARY.json.")
    args = ap.parse_args(argv)
    if args.out_dir.resolve() == HIST_DIR.resolve():
        ap.error("refusing to write into the historical report directory")
    if not (ARB_DIR / "src").exists():
        print(f"Missing ARB checkout at {ARB_DIR}", file=sys.stderr)
        return 2
    if args.merge:
        print(json.dumps(merge(args.out_dir), indent=2))
    else:
        run_shard(args.shard, args.num_shards, args.out_dir, args.limit_snapshots)
    return 0


if __name__ == "__main__":
    sys.exit(main())
