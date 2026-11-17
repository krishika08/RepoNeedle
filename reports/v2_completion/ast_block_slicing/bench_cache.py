"""
Cache benchmark for AST block slicing: the digest-keyed, byte-budgeted caches (this tree) against the baseline caches
of main at 90efcd2 (full content in the keys, entry-count limits only).

    python reports/v2_completion/ast_block_slicing/bench_cache.py [--out cache_results.json]

Measurements, each stated with its method:

* time: time.perf_counter, median of --repeats runs;
* "measured retained": tracemalloc, bytes still allocated after gc.collect() by objects created during the
  workload and still reachable from the extractor (the caller's file contents are created *before* tracing, so they
  are not counted unless the cache keeps extra copies);
* "estimated retained": the caches' own accounting (CodeSpanExtractor.block_cache_stats), which this PR adds;
* RSS: the process resident set size (Windows: GetProcessMemoryInfo; Linux: /proc/self/statm), sampled in a fresh
  process per churn variant, for context only - it includes the interpreter, parsers and everything else, and
  the allocator does not necessarily return freed memory to the OS.
"""

import argparse
import gc
import importlib.util
import json
import os
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench_block_slicing import gen_go, gen_python, gen_typescript  # noqa: E402
from reponeedle.core import block_slicing  # noqa: E402
from reponeedle.core import tree_sitter_extraction as tse  # noqa: E402
from reponeedle.core.packer import CodeSpanExtractor  # noqa: E402

BASELINE = "90efcd21821972a63a72d16b4c935debcd90be52"


def rss_bytes():
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                    (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                                   "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                                   "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
            kernel32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
                return None
            return pmc.WorkingSetSize
        with open("/proc/self/statm") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except Exception:
        return None


def load_baseline_extractor():
    """CodeSpanExtractor and block_slicing from the baseline commit, loaded under private module names."""
    def source(rel):
        return subprocess.run(["git", "show", f"{BASELINE}:{rel}"], cwd=ROOT, check=True,
                              capture_output=True).stdout.decode("utf-8")
    bs_mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("_baseline_block_slicing", loader=None))
    sys.modules["_baseline_block_slicing"] = bs_mod
    exec(compile(source("reponeedle/core/block_slicing.py"), "baseline:block_slicing.py", "exec"), bs_mod.__dict__)
    packer_src = source("reponeedle/core/packer.py").replace(
        "from reponeedle.core import block_slicing\n", "import _baseline_block_slicing as block_slicing\n")
    pk_mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("_baseline_packer", loader=None))
    sys.modules["_baseline_packer"] = pk_mod
    exec(compile(packer_src, "baseline:packer.py", "exec"), pk_mod.__dict__)
    return pk_mod.CodeSpanExtractor


def median_ms(fn, repeats):
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    return round(statistics.median(times), 3)


def timing_rows(extractors, repeats):
    """
    Cold / warm / new-query times. The implementations are interleaved within every repeat (baseline, this PR,
    baseline, ...) so that machine-level drift affects both equally; medians are reported. The two costs this PR
    adds on top of the baseline code path (content digest, size estimate) are also timed on their own.
    """
    inputs = [("python, 2,000 functions", "svc.py", gen_python(2000), {"handle_1500"}, {"floor"}),
              ("typescript, 2,000 functions", "svc.ts", gen_typescript(2000), {"handle1500"}, {"round"}),
              ("go, 2,000 functions", "svc.go", gen_go(2000), {"handle1500"}, {"floor"})]
    rows = []
    for name, path, content, q1, q2 in inputs:
        row = {"input": name, "lines": len(content.splitlines()), "bytes": len(content.encode())}
        warm = {label: cls() for label, cls in extractors.items()}
        for w in warm.values():
            w.extract_block_span(content, path, q1)
        samples = {label: {"cold_ms": [], "warm_repeat_ms": [], "new_query_parsed_file_ms": []} for label in extractors}
        for r in range(repeats):
            for label, cls in extractors.items():
                for metric, fn in (("cold_ms", lambda: cls().extract_block_span(content, path, q1)),
                                   ("warm_repeat_ms", lambda: warm[label].extract_block_span(content, path, q1)),
                                   ("new_query_parsed_file_ms",
                                    lambda: warm[label].extract_block_span(content, path, q2 | {f"x{r}"}))):
                    t0 = time.perf_counter()
                    fn()
                    samples[label][metric].append((time.perf_counter() - t0) * 1000)
        for label in extractors:
            row[label] = {m: round(statistics.median(v), 3) for m, v in samples[label].items()}
        structure = block_slicing.analyze_structure(content, path)
        row["this_pr_overheads"] = {
            "sha256_digest_ms": median_ms(lambda: CodeSpanExtractor._content_digest(content), repeats),
            "structure_size_estimate_ms": median_ms(lambda: block_slicing.estimate_structure_bytes(structure),
                                                    repeats),
        }
        rows.append(row)
    return rows


def churn(label, cls, make_files, queries):
    """
    Many different large files through one extractor. Each file's content is generated inside the traced region
    and dropped by the caller after use (as when files change or are re-read), so anything still allocated at the
    end is held by the extractor's caches.
    """
    gc.collect()
    rss_before = rss_bytes()
    tracemalloc.start()
    base = tracemalloc.get_traced_memory()[0]
    ex = cls()
    t0 = time.perf_counter()
    count = 0
    for path, content in make_files():
        for q in queries:
            ex.extract_block_span(content, path, q)
        count += 1
    del content
    elapsed = time.perf_counter() - t0
    ex._span_cache.clear()          # legacy (unbounded, unchanged) caches: excluded from the comparison
    ex._skel_cache.clear()
    ex.tokenizer._cache.clear()
    gc.collect()
    measured = tracemalloc.get_traced_memory()[0] - base
    peak = tracemalloc.get_traced_memory()[1] - base
    tracemalloc.stop()
    out = {"implementation": label, "files": count, "queries_per_file": len(queries),
           "total_s": round(elapsed, 2), "ms_per_file": round(elapsed * 1000 / count, 1),
           "structure_entries": len(ex._structure_cache), "span_entries": len(ex._block_cache),
           "measured_retained_bytes": measured, "traced_peak_bytes": peak,
           "rss_before_bytes": rss_before, "rss_after_bytes": rss_bytes()}
    if hasattr(ex, "block_cache_stats"):
        st = ex.block_cache_stats()
        out["estimated_retained_bytes"] = st["structure"]["estimated_bytes"] + st["span"]["estimated_bytes"]
        out["cache_stats"] = st
    del ex
    gc.collect()
    out["rss_after_release_bytes"] = rss_bytes()
    return out


CHURN_VARIANTS = ("baseline_90efcd2", "this_pr", "this_pr_small_budget")
QUERIES = [{"handle_120", "handle120"}, {"floor", "round"}]
_GENS = (("py", gen_python), ("ts", gen_typescript), ("go", gen_go))


def make_files_factory(n):
    def make_files():
        for i in range(n):
            ext, gen = _GENS[i % 3]
            yield f"pkg{i}/module{i}.{ext}", gen(300 + (i % 7) * 50).replace("Service", f"Svc{i}_")
    return make_files


def run_churn_variant(variant, n_files):
    if variant == "baseline_90efcd2":
        cls, label = load_baseline_extractor(), variant
    elif variant == "this_pr":
        cls, label = CodeSpanExtractor, variant
    else:
        # Same workload under a deliberately small budget: eviction must keep the estimate within it.
        cls = lambda: CodeSpanExtractor(structure_cache_bytes=2 * 2 ** 20, span_cache_bytes=2 ** 20)  # noqa: E731
        label = "this_pr, 2 MiB structure / 1 MiB span budget"
    return churn(label, cls, make_files_factory(n_files), QUERIES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--files", type=int, default=300)
    ap.add_argument("--out", default=None)
    ap.add_argument("--churn-variant", choices=CHURN_VARIANTS, help=argparse.SUPPRESS)
    args = ap.parse_args()
    for lang in tse.GRAMMARS:
        tse.load_language(lang)
    if args.churn_variant:                       # child process: one churn variant, fresh interpreter
        print(json.dumps(run_churn_variant(args.churn_variant, args.files)))
        return
    extractors = {"baseline_90efcd2": load_baseline_extractor(), "this_pr": CodeSpanExtractor}
    timings = timing_rows(extractors, args.repeats)

    content_bytes = sum(len(c.encode()) for _, c in make_files_factory(args.files)())
    queries = QUERIES
    churn_rows = []
    for variant in CHURN_VARIANTS:               # each in its own process, so RSS figures are not shared
        out = subprocess.run([sys.executable, __file__, "--churn-variant", variant, "--files", str(args.files)],
                             check=True, capture_output=True, text=True).stdout
        churn_rows.append(json.loads(out.strip().splitlines()[-1]))
    small = churn_rows.pop()

    result = {
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                        "processor": platform.processor() or platform.machine(), "repeats": args.repeats},
        "timings": timings,
        "churn_workload": {"files": args.files, "lines_per_file": "about 3,000-6,000",
                           "total_content_bytes": content_bytes, "queries_per_file": len(queries)},
        "churn": churn_rows + [small],
    }
    for t in timings:
        print(t["input"], json.dumps({k: v for k, v in t.items() if isinstance(v, dict)}))
    for c in result["churn"]:
        print(json.dumps({k: v for k, v in c.items() if k != "cache_stats"}))
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
