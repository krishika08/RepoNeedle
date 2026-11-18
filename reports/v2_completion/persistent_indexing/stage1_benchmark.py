"""
Stage 1 persistent-index benchmark. Measurement only; every number comes from fresh processes.

    python reports/v2_completion/persistent_indexing/stage1_benchmark.py --files 2500 10000 --profile realistic
    python reports/v2_completion/persistent_indexing/stage1_benchmark.py --files 10000 30000 100000 --profile reduced
        [--memory-limit-gb 12] [--out stage1_benchmark.json]

Workload generator (deterministic, seeded):
- "realistic": file sizes are log-normal with the median (6.4 KB) and spread (p90 17.7 KB) measured on this
  repository's pinned snapshot (snapshot_file_set.json), capped at 200 KB; language mix py 45%, ts 15%, md 15%,
  json 8%, go 7%, rs 5%, java 5%. Identifiers are drawn from a Zipf-distributed pool of synthetic words (s=1.1,
  60,000 words) plus file-specific names, so vocabulary grows with the corpus; Python/TS/Go files import other
  generated modules, so both graphs have cross-file edges.
- "reduced": the same generator with every file 1/6 of the realistic size (median about 1.1 KB). It exists only
  because RepoNeedle's IN-MEMORY index (not the cache) needs roughly 70x the source size in RAM, so realistic
  corpora of 30,000+ files do not fit on the measurement machine. Its sizes are NOT representative of file sizes;
  it measures database growth and SQLite behaviour at large file counts.

Phases, each in a fresh process: uncached build; cold cached build (writes the cache); warm restart; restart after
modifying 1% of the files. A watchdog aborts any phase whose working set exceeds --memory-limit-gb and records it.
"""

import argparse
import json
import math
import os
import platform
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LANGS = [("py", 45), ("ts", 15), ("md", 15), ("json", 8), ("go", 7), ("rs", 5), ("java", 5)]
COMMON = ("the value data result item list index config request response user order cache total count name path "
          "error state update create delete load save parse render build check handle process return default "
          "options buffer stream event queue token session record field schema model service client server").split()


class Pool:
    """Zipf-distributed synthetic identifier words (deterministic)."""

    def __init__(self, rng, size=60_000, s=1.1):
        syll = ["ka", "lo", "mi", "ra", "te", "su", "vo", "ne", "pi", "da", "xo", "qu", "zen", "tor", "bel", "fin"]
        self.words = ["".join(rng.choice(syll) for _ in range(rng.randint(2, 4))) + str(i % 97) for i in range(size)]
        weights = [1 / (k ** s) for k in range(1, size + 1)]
        total = sum(weights)
        acc, self.cdf = 0.0, []
        for w in weights:
            acc += w / total
            self.cdf.append(acc)
        self.rng = rng

    def word(self):
        import bisect
        return self.words[min(len(self.words) - 1, bisect.bisect_left(self.cdf, self.rng.random()))]


def _ident(pool, rng):
    return "_".join(pool.word() for _ in range(rng.randint(1, 3)))


def _python(i, size, pool, rng, modules):
    lines = [f'"""Module {i}: {" ".join(rng.choice(COMMON) for _ in range(8))}."""', "import os"]
    for m in rng.sample(modules, min(len(modules), rng.randint(0, 4))):
        lines.append(f"from {m} import {pool.word()}")
    while sum(len(x) + 1 for x in lines) < size:
        if rng.random() < 0.2:
            lines += [f"class {pool.word().title()}{i}:", f"    def {_ident(pool, rng)}(self, {pool.word()}):",
                      f"        return self.{pool.word()} + {rng.randint(0, 99)}", ""]
        else:
            name = _ident(pool, rng)
            lines += [f"def {name}_{i}({pool.word()}, {pool.word()}=None):",
                      f"    # {' '.join(rng.choice(COMMON) for _ in range(6))}",
                      f"    {pool.word()} = {_ident(pool, rng)}({pool.word()})",
                      f"    return {pool.word()}", ""]
    return "\n".join(lines) + "\n"


def _code(i, size, pool, rng, lang):
    lines = {"ts": [f"import {{ {pool.word()} }} from './mod{rng.randrange(max(1, i))}';"],
             "go": ["package main", 'import "fmt"'], "rs": ["use std::collections::HashMap;"],
             "java": [f"package com.example.m{i % 50};"]}[lang]
    while sum(len(x) + 1 for x in lines) < size:
        n = f"{_ident(pool, rng)}{i}"
        if lang == "ts":
            lines += [f"export function {n}({pool.word()}: number): number {{", f"  return {pool.word()} * 2; // {rng.choice(COMMON)}", "}"]
        elif lang == "go":
            lines += [f"func {n.title()}({pool.word()} int) int {{", f'\tfmt.Println("{rng.choice(COMMON)}")', f"\treturn {pool.word()}", "}"]
        elif lang == "rs":
            lines += [f"pub fn {n}({pool.word()}: u32) -> u32 {{", f"    {pool.word()} + {rng.randint(0, 9)}", "}"]
        else:
            lines += [f"public class C{i}{len(lines)} {{ public int {n}(int {pool.word()}) {{ return {pool.word()}; }} }}"]
    return "\n".join(lines) + "\n"


def _markdown(i, size, pool, rng):
    lines = [f"# {pool.word().title()} {i}"]
    while sum(len(x) + 1 for x in lines) < size:
        lines.append(" ".join(rng.choice(COMMON) if rng.random() < 0.7 else pool.word() for _ in range(14)) + ".")
    return "\n".join(lines) + "\n"


def _json(i, size, pool, rng):
    items, total = {}, 0
    while total < size:
        k, v = _ident(pool, rng), pool.word()
        items[k] = v
        total += len(k) + len(v) + 6
    return json.dumps(items, indent=1) + "\n"


def generate(root: Path, n_files: int, profile: str, seed: int = 7) -> dict:
    rng = random.Random(seed)
    pool = Pool(rng)
    scale = 1.0 if profile == "realistic" else 1 / 6
    langs = [lang for lang, w in LANGS for _ in range(w)]
    mu, sigma = math.log(6442 * scale), 0.79
    modules, sizes = [], []
    for i in range(n_files):
        lang = rng.choice(langs)
        size = int(min(200_000 * scale, max(150, rng.lognormvariate(mu, sigma))))
        pkg = f"pkg{i % 200}/sub{(i // 200) % 20}"
        if lang == "py":
            text, rel = _python(i, size, pool, rng, modules[-500:]), f"{pkg}/mod{i}.py"
            modules.append(f"{pkg.replace('/', '.')}.mod{i}")
        elif lang == "md":
            text, rel = _markdown(i, size, pool, rng), f"{pkg}/notes{i}.md"
        elif lang == "json":
            text, rel = _json(i, size, pool, rng), f"{pkg}/data{i}.json"
        else:
            text, rel = _code(i, size, pool, rng, lang), f"{pkg}/mod{i}.{lang}"
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
        sizes.append(len(text.encode("utf-8")))
    sizes.sort()
    q = lambda p: sizes[min(len(sizes) - 1, int(p * len(sizes)))]  # noqa: E731
    return {"files": n_files, "source_bytes": sum(sizes), "mean": sum(sizes) // n_files, "p10": q(.1),
            "p50": q(.5), "p90": q(.9), "p99": q(.99), "max": sizes[-1]}


CHILD = r'''
import json, os, sys, threading, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import IndexCacheConfig
repo, cache_dir, phase, limit = sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])


def own_peak(committed=False):
    """Peak working set, or with committed=True the peak committed private memory (pagefile usage)."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t)] + [
                (f"f{i}", ctypes.c_size_t) for i in range(6)]
        k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return c.f5 if committed else c.PeakWorkingSetSize   # f5 = PeakPagefileUsage
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def watchdog():
    # Both measures: when physical memory is exhausted the working set stays capped while committed memory grows
    # (paging), so the working set alone cannot detect it.
    while True:
        if own_peak() > limit or own_peak(committed=True) > limit:
            print(json.dumps({"aborted": f"working set or committed memory exceeded {limit / 1024 ** 3:.0f} GB",
                              "peak_rss_bytes": own_peak(),
                              "peak_committed_bytes": own_peak(committed=True)}), flush=True)
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
t = time.perf_counter()
cfg = None if phase == "uncached" else IndexCacheConfig(cache_dir=cache_dir, max_db_bytes=64 * 1024 ** 3,
                                                        max_total_bytes=64 * 1024 ** 3)
engine = RepoNeedleEngine.from_directory(repo, max_files=10 ** 7, index_cache=cfg)
elapsed = time.perf_counter() - t
stop.set()
out = {"seconds_to_ready_engine": round(elapsed, 3), "files": len(engine.docs), "peak_wal_bytes": peak_wal[0],
       "peak_rss_bytes": own_peak(), "peak_committed_bytes": own_peak(committed=True)}
if cfg is not None:
    r = engine.index_cache_diagnostics["last_update"]
    out["report"] = {k: r[k] for k in ("state", "reason", "generation", "files_reused", "files_extracted",
                                       "artifacts_written", "artifacts_reused", "artifacts_collected", "timings_ms")}
print(json.dumps(out))
'''


PHASE_TIMEOUT_S = [None]


def _kill_tree(proc: subprocess.Popen) -> None:
    """On Windows a venv's python.exe is a launcher that starts the real interpreter: kill the whole tree."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.kill()


def run_phase(repo: Path, cache_dir: Path, phase: str, limit_bytes: int) -> dict:
    """
    One phase in a fresh process; the child measures its own peak working set and aborts itself at the memory limit,
    and the parent aborts it at the time limit (--phase-timeout-s).
    """
    proc = subprocess.Popen([sys.executable, "-c", CHILD, str(ROOT), str(repo), str(cache_dir), phase,
                             str(limit_bytes)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        stdout, stderr = proc.communicate(timeout=PHASE_TIMEOUT_S[0])
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        proc.communicate()
        return {"aborted": f"phase exceeded the time limit of {PHASE_TIMEOUT_S[0]} s"}
    proc = subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
    lines = proc.stdout.strip().splitlines()
    if lines:
        try:
            return json.loads(lines[-1])
        except ValueError:
            pass
    return {"failed": f"exit {proc.returncode}: {proc.stderr[-1500:]}"}


def db_stats(cache_dir: Path) -> dict:
    db = next(cache_dir.glob("*.sqlite3"))
    conn = sqlite3.connect(str(db))
    try:
        stats = {"database_file_bytes": db.stat().st_size,
                 "page_size": conn.execute("PRAGMA page_size").fetchone()[0],
                 "page_count": conn.execute("PRAGMA page_count").fetchone()[0],
                 "freelist_pages": conn.execute("PRAGMA freelist_count").fetchone()[0]}
        stats["artifacts"] = {k: {"rows": n, "payload_bytes": b} for k, n, b in conn.execute(
            "SELECT kind, count(*), sum(length(payload)) FROM artifacts GROUP BY kind")}
        stats["manifest_rows"] = conn.execute("SELECT count(*) FROM manifest").fetchone()[0]
        stats["file_artifacts_rows"] = conn.execute("SELECT count(*) FROM file_artifacts").fetchone()[0]
        stats["artifact_metadata_bytes"] = conn.execute(
            "SELECT sum(length(artifact_key) + length(extractor_fp) + length(path) + length(input_sig) + "
            "length(codec) + length(checksum)) FROM artifacts").fetchone()[0]
        wal = Path(str(db) + "-wal")
        stats["wal_bytes_after"] = wal.stat().st_size if wal.exists() else 0
        return stats
    finally:
        conn.close()


def bench(n_files: int, profile: str, limit_bytes: int) -> dict:
    work = Path(tempfile.mkdtemp(prefix=f"rn_s1_{profile}_{n_files}_"))
    try:
        repo, cache_dir = work / "repo", work / "cache"
        t = time.perf_counter()
        workload = generate(repo, n_files, profile)
        workload["generation_seconds"] = round(time.perf_counter() - t, 1)
        out = {"workload": workload, "phases": {}}
        for phase in ("uncached", "cold_cached", "warm_restart"):
            out["phases"][phase] = r = run_phase(repo, cache_dir, phase, limit_bytes)
            if "aborted" in r or "failed" in r:
                return out
            if phase == "cold_cached":
                out["database_after_cold"] = db_stats(cache_dir)
        rng = random.Random(11)
        changed = rng.sample(sorted(p for p in repo.rglob("*") if p.is_file()), max(1, n_files // 100))
        for p in changed:
            with open(p, "a", encoding="utf-8", newline="\n") as fh:
                fh.write("\n" if p.suffix in (".md", ".json") else "\n// edit\n" if p.suffix != ".py" else "\n# edit\n")
        out["phases"]["restart_after_1pct_modified"] = run_phase(repo, cache_dir, "modified", limit_bytes)
        out["database_after_modification"] = db_stats(cache_dir)
        u, w = out["phases"]["uncached"], out["phases"]["warm_restart"]
        out["warm_restart_speedup_vs_uncached"] = round(u["seconds_to_ready_engine"] / w["seconds_to_ready_engine"], 3)
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, nargs="+", required=True)
    ap.add_argument("--profile", choices=("realistic", "reduced"), default="realistic")
    ap.add_argument("--memory-limit-gb", type=float, default=12.0)
    ap.add_argument("--phase-timeout-s", type=float, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    import sqlite3 as _s
    result = {"environment": {"python": sys.version.split()[0], "sqlite": _s.sqlite_version,
                              "platform": platform.platform(), "cpus": os.cpu_count(),
                              "memory_limit_gb": args.memory_limit_gb}, "profile": args.profile, "runs": {}}
    if args.out and Path(args.out).exists():
        result = json.loads(Path(args.out).read_text(encoding="utf-8"))
    PHASE_TIMEOUT_S[0] = args.phase_timeout_s
    blocked = None
    for n in args.files:
        key = f"{args.profile} {n} files"
        if blocked:
            result["runs"][key] = {"not_run": f"a smaller size ({blocked}) already hit a resource limit"}
            continue
        result["runs"][key] = bench(n, args.profile, int(args.memory_limit_gb * 1024 ** 3))
        if any("aborted" in ph or "failed" in ph for ph in result["runs"][key].get("phases", {}).values()):
            blocked = key
        print(key, json.dumps(result["runs"][key])[:400], flush=True)
        if args.out:
            Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
