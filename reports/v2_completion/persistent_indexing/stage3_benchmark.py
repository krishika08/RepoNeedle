"""
V2 Stage 3 benchmark: Stage 2 (``0b273814``, semantic index recomputed by the Stage 2 per-pair loops) versus Stage 3
(the exact single-pass reconstruction) on the Stage 1 workload generator. Measurement only: every phase runs in a
fresh process, and rounds alternate which code runs first.

    git worktree add <dir> 0b273814ba6b31ffa7aa1f13d612057ce0cfa7b9      # the Stage 2 baseline
    python reports/v2_completion/persistent_indexing/stage3_benchmark.py --stage2-root <dir> \
        --files 1000 2500 --profile realistic --rounds 3 --verify --out stage3_benchmark.json

Per round, size and code version, on a pristine copy of the seeded corpus (stage1_benchmark.generate, seed 7):
uncached build; cold cached build; unchanged warm restart; then, each followed by a restart: a one-file feature edit,
a one-file addition, a one-file deletion, 1% of the Python files modified, 10% modified, a vocabulary-cutoff
transition (a file repeating the words ranked just outside the ``max_features`` cutoff), a full discovery-order
change and its restoration; then an in-process ``refresh()`` after a one-file edit and after reverting it. The same
mutations are applied to each version's own copy of the corpus.

Every phase records: seconds to a ready engine, the wall time of every semantic ``fit()`` call (all routes), the
engine's own timings and work counters (Stage 3 adds semantic sub-stage timings), peak working set, peak committed
memory, physical memory available at the start (a phase whose committed memory exceeded it is "paging_suspected"),
peak WAL size; plus database statistics. ``semantic_fit_memory`` measures, for each version, the transient
tracemalloc peak of one warm semantic fit on the corpus (numpy reports its buffers to tracemalloc).

With --upgrade, each workload also measures the one-time cost of upgrading: a cache written by Stage 2, opened by
Stage 3 (every semantic artifact is re-extracted because its extractor fingerprint changed; every other artifact is
reused), then a Stage 3 restart.

With --verify, the final state of every round is checked: the Stage 3 warm restart, the Stage 3 uncached build AND
the Stage 2 uncached build, each in its own process with PYTHONHASHSEED=0, must produce the same canonical digest of
the complete index state and of retrieval for a query sample.
"""

import argparse
import json
import os
import platform
import random
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import stage1_benchmark as s1  # noqa: E402  (the Stage 1 generator and database statistics)
import stage2_benchmark as s2  # noqa: E402  (the Stage 2 child: memory watchdog, WAL watcher, digest)

# The Stage 2 child, plus a timer around every semantic fit (installed before the engine is imported).
FIT_TIMER = r'''
import sys as _sys, time as _time
_sys.path.insert(0, _sys.argv[1])
from reponeedle.core import semantic as _semantic
_fit_calls = []
_real_fit = _semantic.SubwordSemanticIndex.fit
def _timed_fit(self, docs):
    _t = _time.perf_counter()
    try:
        return _real_fit(self, docs)
    finally:
        _fit_calls.append({"s": round(_time.perf_counter() - _t, 3), "documents": len(docs),
                           "stats": dict(getattr(self, "fit_stats", {}) or {})})
_semantic.SubwordSemanticIndex.fit = _timed_fit
'''
CHILD = FIT_TIMER + s2.CHILD.replace(
    "print(json.dumps(out))",
    "out['semantic_fit_calls'] = _fit_calls\nprint(json.dumps(out))")

MEMORY_CHILD = r'''
import gc, json, sys, tracemalloc, time
code_root, repo = sys.argv[1], sys.argv[2]
sys.path.insert(0, code_root)
from reponeedle.core.semantic import SubwordSemanticIndex
from reponeedle.engine import _build_file_doc, _scan_repository
from reponeedle.models import AblationConfig
from reponeedle.core.graph import RepoGraph
abl = AblationConfig()
docs = _scan_repository(repo, None, 10 ** 7, 10 * 1024 * 1024,
                        lambda rel, ext, content: _build_file_doc(rel, ext, content, abl)).docs
for d in docs:
    if abl.enable_polyglot_symbols and not d.symbols and not d.imports:
        syms, imps = RepoGraph.extract_polyglot_symbols(d.content, d.path)
        if syms or imps:
            d.symbols, d.imports = syms, imps
sem = SubwordSemanticIndex()
sem.fit(docs)                                 # extraction (fills the per-document cache)
out = {"documents": len(docs), "warm_fit_s": []}
for _ in range(3):
    t = time.perf_counter(); sem.fit(docs); out["warm_fit_s"].append(round(time.perf_counter() - t, 3))
gc.collect()
tracemalloc.start()
before = tracemalloc.get_traced_memory()[0]
sem.fit(docs)
cur, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
out["transient_peak_bytes"] = peak - before
out["retained_delta_bytes"] = cur - before
print(json.dumps(out))
'''

CUTOFF_CHILD = r'''
import json, sys
code_root, repo, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, code_root)
from reponeedle.engine import RepoNeedleEngine
engine = RepoNeedleEngine.from_directory(repo, max_files=10 ** 7)
sem = engine.semantic_index
df = {}
for p in sem.doc_paths:
    for f in sem._doc_feature_cache[p][1]:
        df[f] = df.get(f, 0) + 1
ranked = sorted(df.items(), key=lambda x: (x[1], len(x[0])), reverse=True)
outside = [f for f, _ in ranked[sem.max_features:sem.max_features + 400]
           if f.isidentifier() and "<" not in f and ">" not in f][:40]
json.dump({"words": outside, "cutoff_df": ranked[sem.max_features - 1][1] if len(ranked) >= sem.max_features else None,
           "features": len(df)}, open(out_path, "w"))
'''


def run_child(code: str, code_root: Path, args, timeout=None, env=None) -> dict:
    full_env = {**os.environ, **(env or {})}
    full_env.pop("PYTHONPATH", None)
    proc = subprocess.Popen([sys.executable, "-c", code, str(code_root), *map(str, args)], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=full_env, cwd=str(code_root))
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        s1._kill_tree(proc)
        proc.communicate()
        return {"aborted": f"exceeded the time limit of {timeout} s"}
    lines = stdout.strip().splitlines()
    if lines:
        try:
            return json.loads(lines[-1])
        except ValueError:
            pass
    return {"failed": f"exit {proc.returncode}: {stderr[-1500:]}"}


def run_phase(code_root: Path, repo: Path, cache_dir: Path, mode: str, limit: int, timeout, env=None) -> dict:
    return run_child(CHILD, code_root, [repo, cache_dir, mode, limit], timeout, env)


# ------------------------------------------------------------------------------------------------- mutations

def _py_files(repo: Path):
    return sorted(p for p in repo.rglob("*.py") if p.is_file())


def mutate(repo: Path, name: str, cutoff_words) -> str:
    files = _py_files(repo)
    if name == "feature_edit":
        p = files[len(files) // 3]
        p.write_text(p.read_text(encoding="utf-8") + "\n\ndef quarterly_ledger_reconciliation_x7(entries):\n"
                     "    return entries\n", encoding="utf-8", newline="\n")
        return p.relative_to(repo).as_posix()
    if name == "add_file":
        (repo / "zz_added").mkdir(exist_ok=True)
        (repo / "zz_added" / "added_module.py").write_text(
            "def added_semantic_feature_one(value):\n    return value\n", encoding="utf-8", newline="\n")
        return "zz_added/added_module.py"
    if name == "delete_file":
        p = files[len(files) // 4]
        p.unlink()
        return p.relative_to(repo).as_posix()
    if name in ("modify_1pct", "modify_10pct"):
        k = max(1, len(files) // (100 if name == "modify_1pct" else 10))
        rng = random.Random(name)
        for i, p in enumerate(rng.sample(files, k)):
            p.write_text(p.read_text(encoding="utf-8") + f"\n\ndef bulk_edit_{name}_{i}(value):\n    return value\n",
                         encoding="utf-8", newline="\n")
        return f"{k} Python files"
    if name == "vocabulary_cutoff":
        (repo / "zz_added").mkdir(exist_ok=True)
        words = " ".join(cutoff_words or ["placeholder"])
        for i in range(3):
            (repo / "zz_added" / f"cutoff_{i}.md").write_text(f"{words}\n", encoding="utf-8", newline="\n")
        return f"3 files repeating {len(cutoff_words or [])} words ranked just outside the cutoff"
    raise ValueError(name)


SERIES = ["feature_edit", "add_file", "delete_file", "modify_1pct", "modify_10pct", "vocabulary_cutoff"]
SHORT_SERIES = ["feature_edit", "add_file", "modify_1pct"]


def db_stats(cache_dir: Path) -> dict:
    return s2.db_stats(cache_dir)


def one_round(pristine: Path, work: Path, stage2_root: Path, stage3_root: Path, limit: int, timeout, first: str,
              verify: bool, series, cutoff_words, refresh: bool) -> dict:
    out = {"stage2": {}, "stage3": {}, "mutations": {}}
    order = ["stage2", "stage3"] if first == "stage2" else ["stage3", "stage2"]
    for variant in order:
        repo, cache = work / f"{variant}_repo", work / f"{variant}_cache"
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(cache, ignore_errors=True)
        shutil.copytree(pristine, repo)
        code = stage2_root if variant == "stage2" else stage3_root
        ph = out[variant]
        ph["semantic_fit_memory"] = run_child(MEMORY_CHILD, code, [repo], timeout)
        for phase, mode in (("uncached", "uncached"), ("cold_cached", "cached"), ("warm_restart", "cached")):
            ph[phase] = r = run_phase(code, repo, cache, mode, limit, timeout)
            if "aborted" in r or "failed" in r:
                return out
            if phase == "cold_cached":
                ph["database_after_cold"] = db_stats(cache)
        for name in series:
            out["mutations"][name] = mutate(repo, name, cutoff_words)
            ph[f"restart_after_{name}"] = r = run_phase(code, repo, cache, "cached", limit, timeout)
            if "aborted" in r or "failed" in r:
                return out
        ph["restart_after_discovery_order_change"] = run_phase(code, repo, cache, "cached", limit, timeout,
                                                               env={"BENCH_REVERSE_WALK": "1"})
        ph["restart_original_order_again"] = run_phase(code, repo, cache, "cached", limit, timeout)
        if refresh:
            edit = _py_files(repo)[len(_py_files(repo)) // 7].relative_to(repo).as_posix()
            ph["in_process_refresh"] = run_phase(code, repo, cache, "cached", limit, timeout,
                                                 env={"BENCH_REFRESH_EDIT": edit})
        ph["database_after_series"] = db_stats(cache)
        if verify:
            env = {"BENCH_VERIFY": "1", "PYTHONHASHSEED": "0"}
            ph["verification_digests"] = {
                "warm": run_phase(code, repo, cache, "cached", limit, timeout, env=env).get("state_digest"),
                "uncached": run_phase(code, repo, cache, "uncached", limit, timeout, env=env).get("state_digest")}
    if verify and out["stage2"].get("verification_digests") and out["stage3"].get("verification_digests"):
        d2, d3 = out["stage2"]["verification_digests"], out["stage3"]["verification_digests"]
        out["verification"] = {"stage3_warm": d3["warm"], "stage3_uncached": d3["uncached"],
                               "stage2_uncached": d2["uncached"], "stage2_warm": d2["warm"],
                               "identical": bool(d3["warm"]) and len({d3["warm"], d3["uncached"], d2["uncached"],
                                                                      d2["warm"]}) == 1}
    return out


def upgrade(pristine: Path, work: Path, stage2_root: Path, stage3_root: Path, limit: int, timeout) -> dict:
    """The one-time cost of upgrading: a cache written by Stage 2, then opened by Stage 3 (semantic artifacts are
    re-extracted because their extractor fingerprint changed), then a Stage 3 restart."""
    repo, cache = work / "upgrade_repo", work / "upgrade_cache"
    shutil.rmtree(repo, ignore_errors=True)
    shutil.rmtree(cache, ignore_errors=True)
    shutil.copytree(pristine, repo)
    out = {"stage2_cold_cached": run_phase(stage2_root, repo, cache, "cached", limit, timeout),
           "stage2_warm_restart": run_phase(stage2_root, repo, cache, "cached", limit, timeout)}
    out["stage3_first_build_over_stage2_cache"] = run_phase(stage3_root, repo, cache, "cached", limit, timeout)
    out["stage3_warm_restart_after_upgrade"] = run_phase(stage3_root, repo, cache, "cached", limit, timeout)
    return out


def _semantic_s(val: dict):
    calls = val.get("semantic_fit_calls") or []
    return calls[0]["s"] if calls else None


def summarise(runs: list) -> dict:
    """Median and range per (variant, phase) over the rounds: time to a ready engine and the semantic fit."""
    out = {}
    for variant in ("stage2", "stage3"):
        phases = {}
        for r in runs:
            for phase, val in r.get(variant, {}).items():
                if isinstance(val, dict) and "seconds_to_ready_engine" in val:
                    phases.setdefault(phase, []).append(val)
        summary = {}
        for p, vals in phases.items():
            sem = [s for s in (_semantic_s(v) for v in vals) if s is not None]
            summary[p] = {"median_s": round(statistics.median(v["seconds_to_ready_engine"] for v in vals), 3),
                          "min_s": min(v["seconds_to_ready_engine"] for v in vals),
                          "max_s": max(v["seconds_to_ready_engine"] for v in vals), "rounds": len(vals),
                          "semantic_fit_median_s": round(statistics.median(sem), 3) if sem else None,
                          "paging_suspected_rounds": sum(1 for v in vals if v.get("paging_suspected"))}
        mem = [r[variant]["semantic_fit_memory"] for r in runs
               if "transient_peak_bytes" in r.get(variant, {}).get("semantic_fit_memory", {})]
        if mem:
            summary["semantic_fit_memory"] = {
                "transient_peak_mb_median": round(statistics.median(m["transient_peak_bytes"] for m in mem) / 2 ** 20, 1),
                "warm_fit_s_median": round(statistics.median(min(m["warm_fit_s"]) for m in mem), 3)}
        out[variant] = summary
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, nargs="+", required=True)
    ap.add_argument("--profile", choices=("realistic", "reduced"), default="realistic")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--stage2-root", required=True, help="checkout of the Stage 2 baseline (git worktree)")
    ap.add_argument("--memory-limit-gb", type=float, default=12.0)
    ap.add_argument("--phase-timeout-s", type=float, default=None)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--series", choices=("full", "short"), default="full",
                    help="short: feature edit, addition, 1% modified; no cutoff search, no in-process refresh")
    ap.add_argument("--upgrade", action="store_true",
                    help="also measure a Stage 3 start over a cache written by Stage 2 (one-time re-extraction)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    stage2_root = Path(args.stage2_root).resolve()
    result = {"environment": {"python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
                              "platform": platform.platform(), "cpus": os.cpu_count(),
                              "memory_limit_gb": args.memory_limit_gb, "stage2_code": "0b27381 (Stage 2 baseline)",
                              "stage3_code": "this checkout"}, "runs": {}}
    try:
        import numpy
        import scipy
        result["environment"].update(numpy=numpy.__version__, scipy=scipy.__version__)
    except ImportError:
        pass
    if args.out and Path(args.out).exists():
        result = json.loads(Path(args.out).read_text(encoding="utf-8"))
    limit = int(args.memory_limit_gb * 1024 ** 3)
    full = args.series == "full"
    for n in args.files:
        key = f"{args.profile} {n} files"
        work = Path(tempfile.mkdtemp(prefix=f"rn_s3_{args.profile}_{n}_"))
        try:
            pristine = work / "pristine"
            t = time.perf_counter()
            workload = s1.generate(pristine, n, args.profile)
            workload["generation_seconds"] = round(time.perf_counter() - t, 1)
            cutoff = {}
            if full:
                path = work / "cutoff.json"
                res = run_child(CUTOFF_CHILD, ROOT, [pristine, path], args.phase_timeout_s)
                cutoff = json.loads(path.read_text()) if path.exists() else {"failed": res}
            workload["cutoff_words"] = cutoff
            runs = []
            for r in range(args.rounds):
                first = "stage2" if r % 2 == 0 else "stage3"
                runs.append(one_round(pristine, work, stage2_root, ROOT, limit, args.phase_timeout_s, first,
                                      args.verify, SERIES if full else SHORT_SERIES, cutoff.get("words"), full))
                print(key, "round", r + 1, json.dumps(summarise(runs[-1:]))[:800], flush=True)
                result["runs"][key] = {"workload": workload, "rounds": runs, "summary": summarise(runs)}
                if args.out:
                    Path(args.out).write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
            if args.upgrade:
                result["runs"][key]["upgrade"] = upgrade(pristine, work, stage2_root, ROOT, limit,
                                                         args.phase_timeout_s)
                print(key, "upgrade", json.dumps({k: v.get("seconds_to_ready_engine") for k, v in
                                                  result["runs"][key]["upgrade"].items()}), flush=True)
                if args.out:
                    Path(args.out).write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
        finally:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
