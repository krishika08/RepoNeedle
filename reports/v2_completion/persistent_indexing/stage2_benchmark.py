"""
V2 Stage 2 benchmark: Stage 1 (persistent, globally recomputed) versus Stage 2 (dependency-scoped re-resolution,
incremental bookkeeping) on the Stage 1 workload generator. Measurement only; every number comes from fresh
processes, and every phase reports the engine's own work counters.

    git worktree add <dir> 9cb4c4614014dbdd4c85606d7fd3f91baf623762      # the Stage 1 implementation commit
    python reports/v2_completion/persistent_indexing/stage2_benchmark.py --stage1-root <dir> \
        --files 1000 2500 --profile realistic --rounds 3 --out stage2_benchmark.json

Per round and size, on a pristine copy of the seeded corpus (stage1_benchmark.generate, seed 7):
- Stage 1 code: uncached build; cold cached build; warm restart; restart after a one-file body edit.
- Stage 2 code: uncached build; cold cached build; unchanged warm restart; then, each followed by a restart:
  one-file body edit, one-file addition, deletion of an imported module, rename, a provider change with many
  consumers (a second definition of the most-called uniquely defined function: one definition becoming two), the
  reverse transition (two becoming one), a provider change with no consumers, and a full discovery-order change
  (reversed os.walk order); finally an in-process refresh() after a one-file edit (the partially incremental BM25
  path) and after reverting it.
Rounds alternate which code runs first. With --verify, the final state of every round is checked for exact index
equivalence: a Stage 2 warm restart and a Stage 2 UNCACHED build, each in its own process with PYTHONHASHSEED=0,
must produce the same canonical digest of the complete index state and of retrieval for a query sample.

Memory: each phase records its peak working set, peak committed private memory and the physical memory available
when it started. A phase whose committed memory exceeded the memory that was available is marked
"paging_suspected"; its timings are reported but are not clean comparisons.
"""

import argparse
import json
import os
import platform
import random
import re
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

CHILD = r'''
import hashlib, json, os, sys, threading, time
from pathlib import Path
code_root = sys.argv[1]
sys.path.insert(0, code_root)
repo, cache_dir, mode, limit = sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
if os.environ.get("BENCH_REVERSE_WALK") == "1":
    import reponeedle.engine as em
    real_walk = os.walk
    def walk(top, *a, **k):
        for root, dirs, files in real_walk(top, *a, **k):
            dirs.reverse(); files.reverse()
            yield root, dirs, files
    em.os.walk = walk
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import IndexCacheConfig


def memory():
    """(peak working set, peak committed private bytes, available physical bytes now)."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t)] + [
                (f"f{i}", ctypes.c_size_t) for i in range(6)]

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong)] + [
                (f"u{i}", ctypes.c_ulonglong) for i in range(5)]
        k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        c = PMC(); c.cb = ctypes.sizeof(PMC)
        psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        m = MS(); m.dwLength = ctypes.sizeof(MS)
        k32.GlobalMemoryStatusEx(ctypes.byref(m))
        return c.PeakWorkingSetSize, c.f5, m.ullAvailPhys
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    avail = os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 0
    return peak, peak, avail


available_at_start = memory()[2]


def watchdog():
    while True:
        rss, committed, _ = memory()
        if rss > limit or committed > limit:
            print(json.dumps({"aborted": f"memory exceeded {limit / 1024 ** 3:.0f} GB", "peak_rss_bytes": rss,
                              "peak_committed_bytes": committed}), flush=True)
            os._exit(3)
        time.sleep(0.2)


threading.Thread(target=watchdog, daemon=True).start()
peak_wal = [0]
stop = threading.Event()


def watch_wal():
    while not stop.is_set():
        for f in Path(cache_dir).glob("*.sqlite3-wal"):
            try:
                peak_wal[0] = max(peak_wal[0], f.stat().st_size)
            except OSError:
                pass
        time.sleep(0.05)


threading.Thread(target=watch_wal, daemon=True).start()


def digest(engine):
    """Canonical digest of the complete index state and of retrieval for a query sample (exact, ordered)."""
    sys.path.insert(0, os.path.join(code_root, "tests"))
    import numpy as np
    from index_equivalence import capture_index_state, capture_retrieval, load_queries
    h = hashlib.sha256()

    def feed(x):
        if isinstance(x, dict):
            h.update(b"{")
            for k, v in x.items():
                feed(k); feed(v)
            h.update(b"}")
        elif isinstance(x, (list, tuple)):
            h.update(b"[")
            for v in x:
                feed(v)
            h.update(b"]")
        elif isinstance(x, (set, frozenset)):
            h.update(b"<")
            for v in sorted(map(repr, x)):
                h.update(v.encode("utf-8", "surrogatepass"))
            h.update(b">")
        elif isinstance(x, np.ndarray):
            h.update(str(x.dtype).encode() + str(x.shape).encode() + x.tobytes())
        elif isinstance(x, float):
            h.update(x.hex().encode())
        else:
            h.update(repr(x).encode("utf-8", "surrogatepass"))
    feed(capture_index_state(engine))
    feed(capture_retrieval(engine, load_queries()[::25]))
    return h.hexdigest()


t = time.perf_counter()
cfg = None if mode == "uncached" else IndexCacheConfig(cache_dir=cache_dir, max_db_bytes=64 * 1024 ** 3,
                                                       max_total_bytes=64 * 1024 ** 3)
engine = RepoNeedleEngine.from_directory(repo, max_files=10 ** 7, index_cache=cfg)
elapsed = time.perf_counter() - t
out = {"seconds_to_ready_engine": round(elapsed, 3), "files": len(engine.docs)}


def summarise(r):
    keep = ("state", "reason", "generation", "files_reused", "files_extracted", "artifacts_written",
            "artifacts_reused", "artifacts_collected", "timings_ms", "global_structures", "fallbacks",
            "work_counters", "added", "deleted", "renamed", "modified")
    s = {k: r[k] for k in keep if k in r}
    for k in ("added", "deleted", "modified"):
        if k in s:
            s[k] = len(s[k])
    if "renamed" in s:
        s["renamed"] = len(s["renamed"])
    return s


if cfg is not None:
    out["report"] = summarise(engine.index_cache_diagnostics["last_update"])
edit = os.environ.get("BENCH_REFRESH_EDIT")
if edit:
    p = os.path.join(repo, edit)
    with open(p, encoding="utf-8", newline="") as fh:
        original = fh.read()
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(original + "\n# refreshed edit marker\n")
    t = time.perf_counter()
    r1 = engine.refresh()
    out["refresh_after_edit_seconds"] = round(time.perf_counter() - t, 3)
    out["refresh_after_edit"] = summarise(r1.model_dump())
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(original)
    t = time.perf_counter()
    r2 = engine.refresh()
    out["refresh_after_revert_seconds"] = round(time.perf_counter() - t, 3)
    out["refresh_after_revert"] = summarise(r2.model_dump())
if os.environ.get("BENCH_VERIFY") == "1":
    out["state_digest"] = digest(engine)
stop.set()
rss, committed, _ = memory()
out.update({"peak_wal_bytes": peak_wal[0], "peak_rss_bytes": rss, "peak_committed_bytes": committed,
            "available_physical_bytes_at_start": available_at_start,
            "paging_suspected": bool(available_at_start and committed > available_at_start)})
print(json.dumps(out))
'''


def run_phase(code_root: Path, repo: Path, cache_dir: Path, mode: str, limit: int, timeout, env=None) -> dict:
    full_env = {**os.environ, **(env or {})}
    full_env.pop("PYTHONPATH", None)
    proc = subprocess.Popen([sys.executable, "-c", CHILD, str(code_root), str(repo), str(cache_dir), mode,
                             str(limit)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=full_env,
                            cwd=str(code_root))
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        s1._kill_tree(proc)
        proc.communicate()
        return {"aborted": f"phase exceeded the time limit of {timeout} s"}
    lines = stdout.strip().splitlines()
    if lines:
        try:
            return json.loads(lines[-1])
        except ValueError:
            pass
    return {"failed": f"exit {proc.returncode}: {stderr[-1500:]}"}


# ------------------------------------------------------------------------------------------------- mutations

def _py_files(repo: Path):
    return sorted(p for p in repo.rglob("*.py") if p.is_file())


def analyse(repo: Path) -> dict:
    """Names for the provider mutations, found by the same patterns the extractor uses for Python files."""
    defs, calls = {}, {}
    for p in _py_files(repo):
        text = p.read_text(encoding="utf-8")
        for name in re.findall(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text, re.MULTILINE):
            defs[name] = defs.get(name, 0) + 1
        for name in re.findall(r"=\s*([A-Za-z_][A-Za-z0-9_]*)\(", text):
            calls[name] = calls.get(name, 0) + 1
    unique_called = sorted((n for n in calls if defs.get(n) == 1), key=lambda n: (-calls[n], n))
    return {"dup_name": unique_called[0] if unique_called else None,
            "dup_name_calls": calls.get(unique_called[0], 0) if unique_called else 0}


def mutate(repo: Path, name: str, info: dict) -> str:
    rng = random.Random(name)
    files = _py_files(repo)
    if name == "body_edit":
        p = files[len(files) // 3]
        p.write_text(p.read_text(encoding="utf-8") + "\n# body-only edit\n", encoding="utf-8", newline="\n")
        return p.relative_to(repo).as_posix()
    if name == "add_file":
        target = files[len(files) // 2]
        mod = ".".join(target.relative_to(repo).with_suffix("").parts)
        (repo / "zz_added").mkdir(exist_ok=True)
        (repo / "zz_added" / "added_module.py").write_text(
            f"from {mod} import *\n\n\ndef added_function_one(x):\n    return x\n", encoding="utf-8", newline="\n")
        return "zz_added/added_module.py"
    if name == "delete_file":
        p = files[len(files) // 4]
        p.unlink()
        return p.relative_to(repo).as_posix()
    if name == "rename_file":
        p = files[(2 * len(files)) // 3]
        new = p.with_name("renamed_" + p.name)
        p.rename(new)
        return f"{p.relative_to(repo).as_posix()} -> {new.relative_to(repo).as_posix()}"
    if name in ("provider_many_consumers", "provider_two_become_one"):
        target = repo / "zz_added" / "duplicate_definition.py"
        if name == "provider_many_consumers":
            target.parent.mkdir(exist_ok=True)
            target.write_text(f"def {info['dup_name']}(value=None):\n    return value\n", encoding="utf-8",
                              newline="\n")
        else:
            target.unlink()
        return f"{info['dup_name']} ({info['dup_name_calls']} call sites)"
    if name == "provider_no_consumers":
        p = files[len(files) // 5]
        p.write_text(p.read_text(encoding="utf-8") + "\n\ndef never_called_function_q9(x):\n    return x\n",
                     encoding="utf-8", newline="\n")
        return p.relative_to(repo).as_posix()
    raise ValueError(name)


STAGE2_SERIES = ["body_edit", "add_file", "delete_file", "rename_file", "provider_many_consumers",
                 "provider_two_become_one", "provider_no_consumers"]
SHORT_SERIES = ["body_edit", "add_file", "provider_many_consumers", "provider_two_become_one"]


def db_stats(cache_dir: Path) -> dict:
    stats = s1.db_stats(cache_dir)
    db = next(cache_dir.glob("*.sqlite3"))
    conn = sqlite3.connect(str(db))
    try:
        stats["global_state_bytes"] = conn.execute("SELECT sum(length(payload)) FROM global_state").fetchone()[0]
    finally:
        conn.close()
    return stats


def one_round(pristine: Path, work: Path, n_files: int, stage1_root, stage2_root: Path, limit: int, timeout,
              first: str, verify: bool, series=STAGE2_SERIES) -> dict:
    out = {"stage1": {}, "stage2": {}, "mutations": {}}
    order = ["stage1", "stage2"] if first == "stage1" else ["stage2", "stage1"]
    for variant in order:
        if variant == "stage1" and stage1_root is None:
            continue
        repo, cache = work / f"{variant}_repo", work / f"{variant}_cache"
        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(cache, ignore_errors=True)
        shutil.copytree(pristine, repo)
        code = stage1_root if variant == "stage1" else stage2_root
        ph = out[variant]
        for phase, mode in (("uncached", "uncached"), ("cold_cached", "cached"), ("warm_restart", "cached")):
            ph[phase] = r = run_phase(code, repo, cache, mode, limit, timeout)
            if "aborted" in r or "failed" in r:
                return out
            if phase == "cold_cached":
                ph["database_after_cold"] = db_stats(cache)
        info = analyse(repo)
        if variant == "stage1":
            out["mutations"]["body_edit"] = mutate(repo, "body_edit", info)
            ph["restart_after_body_edit"] = run_phase(code, repo, cache, "cached", limit, timeout)
            continue
        for name in series:
            out["mutations"][name] = mutate(repo, name, info)
            ph[f"restart_after_{name}"] = r = run_phase(code, repo, cache, "cached", limit, timeout)
            if "aborted" in r or "failed" in r:
                return out
        ph["restart_after_discovery_order_change"] = run_phase(code, repo, cache, "cached", limit, timeout,
                                                               env={"BENCH_REVERSE_WALK": "1"})
        ph["restart_original_order_again"] = run_phase(code, repo, cache, "cached", limit, timeout)
        edit = _py_files(repo)[len(_py_files(repo)) // 7].relative_to(repo).as_posix()
        ph["in_process_refresh"] = run_phase(code, repo, cache, "cached", limit, timeout,
                                             env={"BENCH_REFRESH_EDIT": edit})
        ph["database_after_series"] = db_stats(cache)
        if verify:
            env = {"BENCH_VERIFY": "1", "PYTHONHASHSEED": "0"}
            warm = run_phase(code, repo, cache, "cached", limit, timeout, env=env)
            ref = run_phase(code, repo, cache, "uncached", limit, timeout, env=env)
            ph["verification"] = {"cached_digest": warm.get("state_digest"), "uncached_digest": ref.get("state_digest"),
                                  "identical": bool(warm.get("state_digest")) and
                                  warm.get("state_digest") == ref.get("state_digest")}
    return out


def summarise(runs: list) -> dict:
    """Median and range of seconds_to_ready_engine per (variant, phase) over the rounds."""
    out = {}
    for variant in ("stage1", "stage2"):
        phases = {}
        for r in runs:
            for phase, val in r.get(variant, {}).items():
                if isinstance(val, dict) and "seconds_to_ready_engine" in val:
                    phases.setdefault(phase, []).append(val)
        out[variant] = {p: {"median_s": round(statistics.median(v["seconds_to_ready_engine"] for v in vals), 3),
                            "min_s": min(v["seconds_to_ready_engine"] for v in vals),
                            "max_s": max(v["seconds_to_ready_engine"] for v in vals), "rounds": len(vals),
                            "paging_suspected_rounds": sum(1 for v in vals if v.get("paging_suspected"))}
                        for p, vals in phases.items()}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, nargs="+", required=True)
    ap.add_argument("--profile", choices=("realistic", "reduced"), default="realistic")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--stage1-root", default=None, help="checkout of the Stage 1 commit (git worktree)")
    ap.add_argument("--memory-limit-gb", type=float, default=12.0)
    ap.add_argument("--phase-timeout-s", type=float, default=None)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--series", choices=("full", "short"), default="full",
                    help="short: body edit, addition, the two provider transitions (for very large corpora)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    stage1_root = Path(args.stage1_root).resolve() if args.stage1_root else None
    result = {"environment": {"python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
                              "platform": platform.platform(), "cpus": os.cpu_count(),
                              "memory_limit_gb": args.memory_limit_gb, "stage1_code": "9cb4c46 (Stage 1)",
                              "stage2_code": "this checkout"}, "runs": {}}
    if args.out and Path(args.out).exists():
        result = json.loads(Path(args.out).read_text(encoding="utf-8"))
    limit = int(args.memory_limit_gb * 1024 ** 3)
    for n in args.files:
        key = f"{args.profile} {n} files"
        work = Path(tempfile.mkdtemp(prefix=f"rn_s2_{args.profile}_{n}_"))
        try:
            pristine = work / "pristine"
            t = time.perf_counter()
            workload = s1.generate(pristine, n, args.profile)
            workload["generation_seconds"] = round(time.perf_counter() - t, 1)
            runs = []
            for r in range(args.rounds):
                first = "stage1" if r % 2 == 0 else "stage2"
                runs.append(one_round(pristine, work, n, stage1_root, ROOT, limit, args.phase_timeout_s, first,
                                      args.verify, STAGE2_SERIES if args.series == "full" else SHORT_SERIES))
                print(key, "round", r + 1, json.dumps(summarise(runs[-1:]))[:600], flush=True)
                result["runs"][key] = {"workload": workload, "rounds": runs, "summary": summarise(runs)}
                if args.out:
                    Path(args.out).write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
        finally:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
