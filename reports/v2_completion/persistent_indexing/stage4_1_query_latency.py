"""
V2 Stage 4.1 query-latency investigation. For each revision: one cold cached build, then ``--processes`` warm-restart
processes per revision (interleaved across revisions), each answering the Stage 4 query sample (every 9th query of
the frozen corpus) ``--reps`` times with the garbage collector enabled, then ``--reps`` times with it disabled. The
first pass of each process is reported separately (query-vector caches are empty then). Per revision: median, p90
and p99 over all samples, the per-query medians, and process-level facts (GC-tracked objects, a full collection's
time). The engine's per-query semantic cache is cleared before every query so every repetition does the same work.

    python reports/v2_completion/persistent_indexing/stage4_1_query_latency.py --files 10000 --profile reduced \
        --rev stage3=<worktree> --rev intern=<worktree> --rev candidate=. --out stage4_1_query_latency.json
"""

import argparse
import json
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage1_benchmark as s1  # noqa: E402
import stage3_benchmark as s3  # noqa: E402
import stage4_benchmark as s4  # noqa: E402

CHILD = s3.HEARTBEAT + r'''
import gc, json, os, statistics, sys, time
code_root, repo, cache_dir, reps = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
sys.path.insert(0, code_root)
sys.path.insert(0, os.path.join(code_root, "tests"))
from index_equivalence import load_queries
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import IndexCacheConfig

cfg = IndexCacheConfig(cache_dir=cache_dir, max_db_bytes=64 * 1024 ** 3, max_total_bytes=64 * 1024 ** 3)
t = time.perf_counter()
engine = RepoNeedleEngine.from_directory(repo, max_files=10 ** 7, index_cache=cfg)
ready = time.perf_counter() - t
queries = [q["text"] for q in load_queries()[::9]]


def one_pass():
    lat = []
    for q in queries:
        engine.semantic_index._query_cache.clear()
        t0 = time.perf_counter()
        engine.query(q)
        lat.append((time.perf_counter() - t0) * 1000)
    return lat


first = one_pass()
gc_on = [x for _ in range(reps) for x in one_pass()]
gc.disable()
gc_off = [x for _ in range(reps) for x in one_pass()]
gc.enable()
t = time.perf_counter()
gc.collect()
out = {"ready_s": round(ready, 3), "first_pass_ms": first, "gc_enabled_ms": gc_on, "gc_disabled_ms": gc_off,
       "gc_tracked_objects": len(gc.get_objects()), "gc_collect_s": round(time.perf_counter() - t, 3),
       "max_heartbeat_gap_s": round(_hb["max_gap_s"], 3)}
print(json.dumps(out))
'''

BUILD = r'''
import sys
sys.path.insert(0, sys.argv[1])
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import IndexCacheConfig
cfg = IndexCacheConfig(cache_dir=sys.argv[3], max_db_bytes=64 * 1024 ** 3, max_total_bytes=64 * 1024 ** 3)
RepoNeedleEngine.from_directory(sys.argv[2], max_files=10 ** 7, index_cache=cfg)
print("{}")
'''


def pct(values, q):
    v = sorted(values)
    return round(v[min(len(v) - 1, int(round(q * (len(v) - 1))))], 3) if v else None


def summary(samples):
    return {"n": len(samples), "median": round(statistics.median(samples), 3), "p90": pct(samples, 0.9),
            "p99": pct(samples, 0.99), "max": round(max(samples), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, required=True)
    ap.add_argument("--profile", choices=("realistic", "reduced"), default="reduced")
    ap.add_argument("--rev", action="append", required=True, metavar="NAME=DIR")
    ap.add_argument("--processes", type=int, default=3)
    ap.add_argument("--reps", type=int, default=4)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    revs = {}
    for spec in args.rev:
        name, _, path = spec.partition("=")
        revs[name] = Path(path).resolve()
    work = Path(tempfile.mkdtemp(prefix="rn_s41_latency_"))
    started = s3._utc()
    awake = s3.keep_awake(True)
    result = {"environment": s4.environment(), "revisions": {k: s4.git_revision(v) for k, v in revs.items()},
              "processes_per_revision": args.processes, "reps": args.reps, "runs": {k: [] for k in revs}}
    result["environment"]["argv"] = [Path(a).name if ("/" in a or "\\" in a) else a for a in sys.argv]
    try:
        repo = work / "repo"
        s1.generate(repo, args.files, args.profile)
        result["dataset"] = s4.dataset_manifest(repo, args.files, args.profile, {})
        for name, root in revs.items():
            s3.run_child(BUILD, root, [repo, work / f"cache_{name}"], None)
        for p in range(args.processes):
            names = list(revs)
            k = p % len(names)
            for name in names[k:] + names[:k]:
                r = s3.run_child(CHILD, revs[name], [repo, work / f"cache_{name}", args.reps], None)
                r["process"] = p + 1
                result["runs"][name].append(r)
                print(name, p + 1, {k: r.get(k) for k in ("ready_s", "gc_tracked_objects", "failed")}, flush=True)
    finally:
        s3.keep_awake(False)
        shutil.rmtree(work, ignore_errors=True)
    result["conditions"] = {"started_utc": started, "ended_utc": s3._utc(), "keep_awake_requested": awake,
                            "sleep_or_standby_events": s3.power_events_since(started),
                            "max_heartbeat_gap_s": max((r.get("max_heartbeat_gap_s") or 0)
                                                       for rs in result["runs"].values() for r in rs)}
    result["summary"] = {}
    for name, rs in result["runs"].items():
        ok = [r for r in rs if "gc_enabled_ms" in r]
        if not ok:
            continue
        on = [x for r in ok for x in r["gc_enabled_ms"]]
        off = [x for r in ok for x in r["gc_disabled_ms"]]
        first = [x for r in ok for x in r["first_pass_ms"]]
        n_q = len(ok[0]["first_pass_ms"])
        per_query = [round(statistics.median([r["gc_enabled_ms"][i + j * n_q] for r in ok for j in range(args.reps)]),
                           3) for i in range(n_q)]
        result["summary"][name] = {"gc_enabled": summary(on), "gc_disabled": summary(off), "first_pass": summary(first),
                                   "per_query_median_ms": per_query,
                                   "per_process_median_ms": [round(statistics.median(r["gc_enabled_ms"]), 3) for r in ok],
                                   "gc_tracked_objects": [r["gc_tracked_objects"] for r in ok],
                                   "warm_ready_s": [r["ready_s"] for r in ok]}
    Path(args.out).write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=1)[:3000])


if __name__ == "__main__":
    main()
