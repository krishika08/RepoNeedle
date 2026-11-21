"""
V2 Stage 4 benchmark: large-repository scalability (10,000 reduced, 10,000 realistic, 30,000 reduced files), built on
the Stage 1-3 harnesses (the seeded Stage 1 generator, the Stage 2 child with its memory watchdog, WAL watcher and
digest, and the Stage 3 heartbeat, keep-awake and semantic-fit timer). It compares two code revisions, each phase in a
fresh process, alternating which revision runs first in each round.

    git worktree add <dir> <baseline commit>
    python reports/v2_completion/persistent_indexing/stage4_benchmark.py --baseline-root <dir> \
        --files 10000 --profile reduced --rounds 3 --verify --out stage4_benchmark.json

Per workload: a deterministic corpus (stage1_benchmark.generate, seed 7) with a dataset manifest (generator, seed,
language, size and directory statistics, and a SHA-256 over every file's path and content digest); per round and
revision: uncached build, cold cached build, unchanged warm restart (each with the engine's phase timings, the
semantic-fit timer, peak working set, peak committed memory, available memory at start, peak WAL and a heartbeat
gap), retrieval latency for a fixed query sample on the warm engine, and, once per workload and revision, the
retained memory of each engine component (deep object sizes). With --verify, every round checks that the warm
restart and the uncached build of BOTH revisions produce one digest of the complete index state and of retrieval
(PYTHONHASHSEED=0). Every result records both revisions' commit SHAs and whether their trees were clean.

A phase whose committed memory exceeded the memory available when it started is ``paging_suspected``; one whose
heartbeat gap exceeded 5 s is ``suspended_suspected``; one that started or ended on battery power (Windows
``GetSystemPowerStatus``; a laptop on battery is CPU-throttled) is ``on_battery_suspected``. All stay in the raw data
and are excluded from the summary statistics, which list them. Nothing is extrapolated.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import stage1_benchmark as s1  # noqa: E402  (the seeded workload generator)
import stage2_benchmark as s2  # noqa: E402  (database statistics)
import stage3_benchmark as s3  # noqa: E402  (child process, heartbeat, keep-awake, power events)

GENERATOR_VERSION = "stage1_benchmark.generate/seed-7 + stage4-manifest/1"
SEED = 7                    # stage1_benchmark.generate's default seed
QUERY_SAMPLE = 25           # every 9th query of the frozen 225-query corpus

# The Stage 3 child, plus retrieval latency on the built engine (BENCH_QUERY_LATENCY=1).
LATENCY = r'''
if os.environ.get("BENCH_QUERY_LATENCY") == "1":
    sys.path.insert(0, os.path.join(code_root, "tests"))
    from index_equivalence import load_queries
    lat = []
    for q in load_queries()[::9]:
        t0 = time.perf_counter()
        engine.query(q["text"])
        lat.append(round((time.perf_counter() - t0) * 1000, 3))
    out["query_latency_ms"] = lat
'''
CHILD = s3.CHILD.replace("if os.environ.get(\"BENCH_VERIFY\") == \"1\":", LATENCY + "if os.environ.get(\"BENCH_VERIFY\") == \"1\":", 1)
assert LATENCY in CHILD, "the Stage 3 child changed: latency hook not installed"
# The Stage 2 child reads SC_AVPHYS_PAGES, which macOS lacks: there, available memory is recorded as 0 (unknown),
# which disables the paging check instead of failing the phase.
_AVAIL = 'avail = os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 0'
assert _AVAIL in CHILD, "the Stage 2 child changed: available-memory probe not found"
CHILD = CHILD.replace(_AVAIL, 'try:\n        ' + _AVAIL.split(" if ")[0] +
                      '\n    except (AttributeError, ValueError, OSError):\n        avail = 0', 1)
compile(CHILD, "<stage4 child>", "exec")

# Retained memory per engine component of an uncached build (each object counted once, in this order).
MEMORY_CHILD = s3.HEARTBEAT + r'''
import gc, json, sys, time
code_root, repo = sys.argv[1], sys.argv[2]
sys.path.insert(0, code_root)
import numpy as np
from scipy import sparse
from reponeedle.engine import RepoNeedleEngine
engine = RepoNeedleEngine.from_directory(repo, max_files=10 ** 7)
seen = set()
def deep(obj):
    total, stack = 0, [obj]
    while stack:
        o = stack.pop()
        if id(o) in seen:
            continue
        seen.add(id(o))
        if isinstance(o, np.ndarray):
            total += sys.getsizeof(o)
            continue
        if sparse.issparse(o):
            stack.extend(getattr(o, a) for a in ("data", "indices", "indptr") if hasattr(o, a))
            total += sys.getsizeof(o)
            continue
        if isinstance(o, type):
            continue
        total += sys.getsizeof(o)
        if isinstance(o, dict):
            stack.extend(o.keys()); stack.extend(o.values())
        elif isinstance(o, (list, tuple, set, frozenset)):
            stack.extend(o)
        elif hasattr(o, "__dict__"):
            stack.append(vars(o))
        for klass in type(o).__mro__:
            slots = klass.__dict__.get("__slots__", ())
            for name in (slots,) if isinstance(slots, str) else slots:
                if name not in ("__dict__", "__weakref__") and hasattr(o, name):
                    stack.append(getattr(o, name))
    return total
gc.collect()
sem, lex = engine.semantic_index, engine.lexical_index
parts = [("documents_raw_text", [d.content for d in engine.docs]), ("documents_metadata", engine.docs),
         ("semantic_feature_cache", sem._doc_feature_cache),
         ("semantic_vocabulary_idf_matrix", [sem.vocabulary, sem.idf, sem.doc_matrix]),
         ("lexical_term_cache", getattr(lex, "_doc_term_cache", {})), ("lexical_index_rest", lex),
         ("abstainer", engine.abstainer), ("function_graph", engine.function_graph), ("repo_graph", engine.repo_graph),
         ("engine_rest", engine)]
out = {"documents": len(engine.docs), "component_bytes": {}}
for name, obj in parts:
    out["component_bytes"][name] = deep(obj)
cache = sem._doc_feature_cache
out["semantic_pairs"] = sum(len(c) for _, c in cache.values())
out["semantic_distinct_features"] = len({f for _, c in cache.values() for f in c})
out["semantic_distinct_key_objects"] = len({id(f) for _, c in cache.values() for f in c})
out["source_bytes"] = sum(len(d.content.encode("utf-8", "surrogatepass")) for d in engine.docs)
out["max_heartbeat_gap_s"] = round(_hb["max_gap_s"], 3)
print(json.dumps(out))
'''


# ------------------------------------------------------------------------------------------------- provenance

def git_revision(root: Path) -> dict:
    def run(*args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True).stdout.strip()
    version = None
    init = root / "reponeedle" / "__init__.py"
    if init.exists():
        for line in init.read_text(encoding="utf-8").splitlines():
            if line.startswith("__version__"):
                version = line.split("=", 1)[1].strip().strip("\"'")
    return {"commit": run("rev-parse", "HEAD") or None, "tree_clean": run("status", "--porcelain") == "",
            "package_version": version}


def environment() -> dict:
    # Path arguments are recorded by their last component only: no local directory names in published results.
    argv = [Path(a).name if ("/" in a or "\\" in a) else a for a in sys.argv[1:]]
    env = {"platform": platform.platform(), "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
           "cpu": platform.processor(), "logical_cpus": os.cpu_count(), "argv": argv}
    for mod in ("numpy", "scipy", "networkx", "pydantic", "pathspec"):
        try:
            env[mod] = __import__(mod).__version__
        except ImportError:
            env[mod] = None
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong)] + [
                (f"u{i}", ctypes.c_ulonglong) for i in range(5)]
        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        env.update(ram_total_bytes=m.ullTotalPhys, ram_available_bytes_at_start=m.ullAvailPhys)
    else:
        def conf(name):
            try:
                return os.sysconf(name)
            except (AttributeError, ValueError, OSError):   # macOS has no SC_AVPHYS_PAGES
                return None
        pages, avail, size = conf("SC_PHYS_PAGES"), conf("SC_AVPHYS_PAGES"), conf("SC_PAGE_SIZE")
        env.update(ram_total_bytes=pages * size if pages and size else None,
                   ram_available_bytes_at_start=avail * size if avail and size else None)
    return env


# ------------------------------------------------------------------------------------------------- dataset

def dataset_manifest(root: Path, n_files: int, profile: str, generation: dict) -> dict:
    """Deterministic description of a generated corpus; ``manifest_sha256`` identifies its exact content."""
    files = sorted(p for p in root.rglob("*") if p.is_file())
    h = hashlib.sha256()
    sizes, langs, dirs, depths = [], Counter(), Counter(), []
    tests = imports = 0
    for p in files:
        rel = p.relative_to(root).as_posix()
        data = p.read_bytes()
        h.update(rel.encode("utf-8") + b"\0" + hashlib.sha256(data).hexdigest().encode("ascii") + b"\n")
        sizes.append(len(data))
        langs[p.suffix or "(none)"] += 1
        dirs[p.parent.relative_to(root).as_posix()] += 1
        depths.append(rel.count("/"))
        tests += "test" in p.name.lower()
        imports += sum(1 for line in data.splitlines() if line.startswith((b"import ", b"from ", b"use ")))
    ordered = sorted(sizes)

    def q(f):
        return ordered[min(len(ordered) - 1, int(f * len(ordered)))]
    per_dir = sorted(dirs.values())
    return {
        "dataset_id": f"stage1-generator/{profile}/{n_files}/seed-{SEED}", "generator_version": GENERATOR_VERSION,
        "seed": SEED, "profile": profile, "requested_files": n_files, "file_count": len(files),
        "manifest_sha256": h.hexdigest(), "generated_utc": s3._utc(),
        "generation_seconds": generation.get("generation_seconds"),
        "language_distribution": dict(sorted(langs.items())),
        "size_bytes": {"total": sum(sizes), "mean": sum(sizes) // max(1, len(sizes)), "min": ordered[0],
                       "p10": q(.1), "p50": q(.5), "p90": q(.9), "p99": q(.99), "max": ordered[-1]},
        "directories": {"count": len(dirs), "max_depth": max(depths), "files_per_directory_median": per_dir[len(per_dir) // 2],
                        "files_per_directory_max": per_dir[-1]},
        "test_files": tests, "import_lines": imports,
        "generator_config": {"languages_weighted": s1.LANGS, "realistic_median_bytes": 6442,
                             "size_scale": 1.0 if profile == "realistic" else 1 / 6, "lognormal_sigma": 0.79,
                             "max_file_bytes": int(200_000 * (1.0 if profile == "realistic" else 1 / 6)),
                             "packages": "pkg{i % 200}/sub{(i // 200) % 20}", "identifier_pool": "Zipf s=1.1, 60,000 words"},
    }


# ------------------------------------------------------------------------------------------------- rounds

PHASES = ("uncached", "cold_cached", "warm_restart")


def ac_power():
    """True on mains power, False on battery, None when unknown (non-Windows or no answer)."""
    if sys.platform != "win32":
        return None
    import ctypes

    class _Status(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                    ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                    ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
    st = _Status()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(st)) or st.ACLineStatus not in (0, 1):
        return None
    return st.ACLineStatus == 1


def run_phase(code_root: Path, repo: Path, cache_dir: Path, mode: str, limit: int, timeout, env=None) -> dict:
    before = ac_power()
    out = s3.run_child(CHILD, code_root, [repo, cache_dir, mode, limit], timeout, env)
    after = ac_power()
    out["ac_power"] = [before, after]
    out["on_battery_suspected"] = before is False or after is False
    return out


def variants_of(keys) -> list:
    """Revision names in their fixed order: baseline, the extra revisions (as given), candidate."""
    keys = [k for k in keys if k != "verification"]
    return ["baseline"] + [k for k in keys if k not in ("baseline", "candidate")] + ["candidate"]


def variant_order(roots: dict, round_index: int) -> list:
    """Every revision, rotated so that each round starts with a different one."""
    names = variants_of(roots)
    k = round_index % len(names)
    return names[k:] + names[:k]


def one_round(pristine: Path, work: Path, roots: dict, limit: int, timeout, first, verify: bool) -> dict:
    """``first``: "baseline" or "candidate" (two revisions, as in Stage 4), or the full order to run in."""
    out = {}
    if isinstance(first, str):
        order = ["baseline", "candidate"] if first == "baseline" else ["candidate", "baseline"]
    else:
        order = list(first)
    for variant in order:
        repo, cache = work / f"{variant}_repo", work / f"{variant}_cache"
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(cache, ignore_errors=True)
        shutil.copytree(pristine, repo)
        ph = out[variant] = {}
        for phase in PHASES:
            env = {"BENCH_QUERY_LATENCY": "1"} if phase == "warm_restart" else None
            ph[phase] = r = run_phase(roots[variant], repo, cache, "uncached" if phase == "uncached" else "cached",
                                         limit, timeout, env=env)
            if "aborted" in r or "failed" in r:
                break
            if phase == "cold_cached":
                ph["database_after_cold"] = s2.db_stats(cache)
        if verify and not any("aborted" in x or "failed" in x for x in ph.values() if isinstance(x, dict)):
            env = {"BENCH_VERIFY": "1", "PYTHONHASHSEED": "0"}
            ph["verification_digests"] = {
                "warm": run_phase(roots[variant], repo, cache, "cached", limit, timeout, env=env).get("state_digest"),
                "uncached": run_phase(roots[variant], repo, cache, "uncached", limit, timeout, env=env).get("state_digest")}
    names = variants_of(order)
    if verify and all("verification_digests" in out.get(v, {}) for v in names):
        digests = [out[v]["verification_digests"][k] for v in names for k in ("warm", "uncached")]
        out["verification"] = {"digests": digests, "identical": all(digests) and len(set(digests)) == 1}
    return out


def _clean(x) -> bool:
    return isinstance(x, dict) and "seconds_to_ready_engine" in x and not x.get("paging_suspected") \
        and not x.get("suspended_suspected") and not x.get("on_battery_suspected")


def stats(values) -> dict:
    if not values:
        return {"n": 0}
    return {"n": len(values), "median": round(statistics.median(values), 4), "min": round(min(values), 4),
            "max": round(max(values), 4), "stdev": round(statistics.stdev(values), 4) if len(values) > 1 else 0.0}


def metric_values(rounds, variant, phase, fn):
    return [fn(r[variant][phase]) for r in rounds if _clean(r.get(variant, {}).get(phase)) and fn(r[variant][phase]) is not None]


METRICS = {
    "ready_engine_s": lambda v: v["seconds_to_ready_engine"],
    "semantic_fit_s": lambda v: v["semantic_fit_calls"][0]["s"] if v.get("semantic_fit_calls") else None,
    "peak_working_set_gb": lambda v: v["peak_rss_bytes"] / 2 ** 30,
    "peak_committed_gb": lambda v: v["peak_committed_bytes"] / 2 ** 30,
    "peak_wal_mb": lambda v: v["peak_wal_bytes"] / 2 ** 20,
    "scan_ms": lambda v: v.get("report", {}).get("timings_ms", {}).get("scan_ms"),
    "load_ms": lambda v: v.get("report", {}).get("timings_ms", {}).get("load_ms"),
    "fit_ms": lambda v: v.get("report", {}).get("timings_ms", {}).get("fit_ms"),
    "persist_ms": lambda v: v.get("report", {}).get("timings_ms", {}).get("persist_ms"),
    "query_latency_median_ms": lambda v: statistics.median(v["query_latency_ms"]) if v.get("query_latency_ms") else None,
}


def summarise(rounds) -> dict:
    names = variants_of(rounds[0]) if rounds else ["baseline", "candidate"]
    out = {"excluded_phases": [{"round": i + 1, "variant": v, "phase": p,
                                "paging_suspected": bool(x.get("paging_suspected")),
                                "suspended_suspected": bool(x.get("suspended_suspected")),
                                "on_battery_suspected": bool(x.get("on_battery_suspected")),
                                "seconds_to_ready_engine": x.get("seconds_to_ready_engine")}
                               for i, r in enumerate(rounds) for v in names
                               for p, x in r.get(v, {}).items()
                               if isinstance(x, dict) and (x.get("paging_suspected") or x.get("suspended_suspected")
                                                           or x.get("on_battery_suspected"))],
           "failed_or_aborted": [{"round": i + 1, "variant": v, "phase": p, "detail": x.get("aborted") or x.get("failed")}
                                 for i, r in enumerate(rounds) for v in names
                                 for p, x in r.get(v, {}).items() if isinstance(x, dict) and ("aborted" in x or "failed" in x)]}
    for variant in names:
        out[variant] = {p: {m: stats(metric_values(rounds, variant, p, fn)) for m, fn in METRICS.items()} for p in PHASES}
    for other in names[:-1]:
        out[f"per_round_ratio_{other}_over_candidate"] = {
            p: {m: [round(METRICS[m](r[other][p]) / METRICS[m](r["candidate"][p]), 3)
                    if _clean(r.get(other, {}).get(p)) and _clean(r.get("candidate", {}).get(p))
                    and METRICS[m](r[other][p]) and METRICS[m](r["candidate"][p]) else None for r in rounds]
                for m in ("ready_engine_s", "semantic_fit_s", "peak_working_set_gb", "peak_committed_gb")}
            for p in PHASES}
    out["verification"] = [r.get("verification", {}).get("identical") for r in rounds]
    return out


def markdown(result: dict) -> str:
    """Human-readable summary of the raw JSON (every number is copied from it)."""
    env = result["environment"]
    names = variants_of(result["revisions"])
    revs = "; ".join(f"{v} `{result['revisions'][v]['commit']}` (clean: {result['revisions'][v]['tree_clean']})"
                     for v in names)
    lines = [f"# Stage 4 benchmark summary (generated from `{result.get('json_name', 'stage4_benchmark.json')}`)", "",
             f"Revisions: {revs}.",
             f"{env['platform']}, Python {env['python']}, numpy {env['numpy']}, SciPy {env['scipy']}, "
             f"{env['logical_cpus']} logical CPUs, {(env.get('ram_total_bytes') or 0) / 2 ** 30:.1f} GB RAM "
             f"({(env.get('ram_available_bytes_at_start') or 0) / 2 ** 30:.1f} GB available at start; 0 = unknown).", ""]
    for key, run in result["runs"].items():
        m = run["dataset"]
        lines += [f"## {key}", "",
                  f"Dataset `{m['dataset_id']}`, manifest SHA-256 `{m['manifest_sha256'][:16]}…`, {m['file_count']} files, "
                  f"{m['size_bytes']['total'] / 2 ** 20:.1f} MB; rounds: {len(run['rounds'])}; "
                  f"verification: {run['summary']['verification']}; conditions: {run.get('conditions', {})}", ""]
        lines += ["| Phase | Metric | " + " | ".join(f"{v.capitalize()} median (min–max, sd, n)" for v in names)
                  + " |", "| :--- | :--- | " + " | ".join("---:" for _ in names) + " |"]
        for p in PHASES:
            for metric in METRICS:
                cells = [run["summary"][v][p][metric] for v in names]
                if not any(c.get("n") for c in cells):
                    continue
                fmt = lambda s: (f"{s['median']} ({s['min']}–{s['max']}, sd {s['stdev']}, n {s['n']})" if s.get("n") else "–")  # noqa: E731
                lines.append(f"| {p} | {metric} | " + " | ".join(fmt(c) for c in cells) + " |")
        if run.get("component_memory"):
            lines += ["", "| Component (retained, uncached build) | " + " | ".join(f"{v.capitalize()} MB" for v in names)
                      + " |", "| :--- | " + " | ".join("---:" for _ in names) + " |"]
            cb = run["component_memory"]
            for comp in cb.get("baseline", {}).get("component_bytes", {}):
                vals = [cb.get(v, {}).get("component_bytes", {}).get(comp, 0) / 2 ** 20 for v in names]
                lines.append(f"| {comp} | " + " | ".join(f"{x:.1f}" for x in vals) + " |")
        ex = run["summary"]["excluded_phases"] + run["summary"]["failed_or_aborted"]
        lines += ["", f"Excluded, failed or aborted phases: {ex if ex else 'none'}", ""]
    return "\n".join(lines).rstrip("\n") + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, nargs="+", required=True)
    ap.add_argument("--profile", choices=("realistic", "reduced"), default="reduced")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--baseline-root", required=True, help="checkout of the baseline revision (git worktree)")
    ap.add_argument("--extra-root", action="append", default=[], metavar="NAME=DIR",
                    help="another revision to compare (git worktree), run between baseline and candidate; repeatable")
    ap.add_argument("--memory-limit-gb", type=float, default=12.0)
    ap.add_argument("--phase-timeout-s", type=float, default=None)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--component-memory", action="store_true", help="retained memory per component, once per revision")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    roots = {"baseline": Path(args.baseline_root).resolve()}
    for spec in args.extra_root:
        name, _, path = spec.partition("=")
        if not name.isidentifier() or name in ("baseline", "candidate", "verification") or not path:
            ap.error(f"--extra-root expects NAME=DIR with a new identifier NAME: {spec!r}")
        roots[name] = Path(path).resolve()
    roots["candidate"] = ROOT
    out_path = Path(args.out)
    result = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {"runs": {}}
    result["environment"] = environment()
    result["revisions"] = {k: git_revision(v) for k, v in roots.items()}
    result["json_name"] = out_path.name
    limit = int(args.memory_limit_gb * 1024 ** 3)
    awake = s3.keep_awake(True)
    try:
        for n in args.files:
            key = f"{args.profile} {n} files"
            work = Path(tempfile.mkdtemp(prefix=f"rn_s4_{args.profile}_{n}_"))
            started = s3._utc()
            try:
                pristine = work / "pristine"
                t = time.perf_counter()
                gen = s1.generate(pristine, n, args.profile)
                gen["generation_seconds"] = round(time.perf_counter() - t, 1)
                run = result["runs"][key] = {"dataset": dataset_manifest(pristine, n, args.profile, gen), "rounds": []}
                if args.component_memory:
                    run["component_memory"] = {v: s3.run_child(MEMORY_CHILD, roots[v], [pristine], args.phase_timeout_s)
                                               for v in variants_of(roots)}
                for r in range(args.rounds):
                    order = variant_order(roots, r)
                    run["rounds"].append(one_round(pristine, work, roots, limit, args.phase_timeout_s, order, args.verify))
                    run["summary"] = summarise(run["rounds"])
                    print(key, "round", r + 1, "verification", run["summary"]["verification"], flush=True)
                    out_path.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
                run["conditions"] = {"started_utc": started, "ended_utc": s3._utc(), "keep_awake_requested": awake,
                                     "sleep_or_standby_events_during_workload": s3.power_events_since(started)}
                out_path.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
                out_path.with_suffix(".md").write_text(markdown(result), encoding="utf-8")
                print(key, "done", json.dumps(run["conditions"])[:300], flush=True)
            finally:
                shutil.rmtree(work, ignore_errors=True)
    finally:
        s3.keep_awake(False)


if __name__ == "__main__":
    main()
