"""
Extraction performance: Tree-sitter vs the existing regex extractor on the fixture corpora.

Usage:
    python bench_extraction.py [--copies 40] [--repeats 5] [--out results.json]

Corpus: every file under tests/fixtures/tree_sitter/<language>/ replicated ``--copies`` times under
distinct directories (copyN/...). The code is synthetic but realistic in shape; it is not a sample of
real-world repositories, so absolute numbers are indicative only.

Measured:
- startup: fresh-process time to import reponeedle, and to load the Tree-sitter runtime + one grammar;
- per language: extraction time over the corpus (warm parsers), regex vs Tree-sitter, and per-KB cost;
- build_graph: full call-graph construction on the multi-language corpus, both modes, cold (new engine)
  and repeated (same engine; per-file extraction caches hit);
- memory: peak Python allocations (tracemalloc; does not see Tree-sitter's C allocations) and the process's
  peak resident set size before/after the build (run regex first, so the Tree-sitter delta is visible).

Graph edge counts on the replicated corpus are NOT meaningful: every function name occurs ``--copies`` times,
so name-uniqueness resolution cannot fire; only import-bound edges resolve. Edge correctness is covered by
tests/test_tree_sitter_graph.py on the single-copy fixtures.
"""

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from reponeedle.core import tree_sitter_extraction as tse  # noqa: E402
from reponeedle.core.function_graph import FunctionGraphEngine  # noqa: E402
from reponeedle.models import FileDoc  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "tree_sitter"
LANGS = ["typescript", "go", "rust", "java", "cpp"]


def rss_mb():
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1e6
    except ImportError:
        pass
    if sys.platform == "win32":
        import ctypes
        import ctypes.wintypes as wt

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        kernel32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
        kernel32.GetCurrentProcess.restype = wt.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
        psapi.GetProcessMemoryInfo.restype = wt.BOOL
        if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            return float("nan")
        return pmc.PeakWorkingSetSize / 1e6
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e3


def corpus(lang, copies):
    docs = []
    for i in range(copies):
        for p in sorted((FIXTURES / lang).rglob("*")):
            if p.is_file():
                rel = p.relative_to(FIXTURES / lang).as_posix()
                docs.append(FileDoc(path=f"copy{i}/{rel}", content=p.read_text(encoding="utf-8"),
                                    is_test="test" in rel.lower()))
    return docs


def fresh_process_seconds(code):
    times = []
    for _ in range(3):
        t0 = time.perf_counter()
        subprocess.run([sys.executable, "-c", code], check=True, cwd=str(ROOT), capture_output=True)
        times.append(time.perf_counter() - t0)
    return round(statistics.median(times) * 1000, 1)


def timed(fn, repeats):
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return round(statistics.median(samples) * 1000, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--copies", type=int, default=40)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    status = tse.tree_sitter_status()
    if not status["runtime"]["available"]:
        sys.exit("Tree-sitter is not installed: pip install 'reponeedle[treesitter]'")

    results = {
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "processor": platform.processor() or platform.machine(),
            "tree_sitter": status["runtime"]["version"],
            "grammars": {k: v.get("grammar_version") for k, v in status["languages"].items()},
            "copies": args.copies,
            "repeats": args.repeats,
        },
        "startup_ms": {
            "import_reponeedle": fresh_process_seconds("import reponeedle"),
            "import_reponeedle_and_load_runtime_plus_go_grammar": fresh_process_seconds(
                "import reponeedle; from reponeedle.core import tree_sitter_extraction as t; "
                "assert t.load_language('go') is not None"),
            "import_reponeedle_and_load_all_six_grammars": fresh_process_seconds(
                "import reponeedle; from reponeedle.core import tree_sitter_extraction as t; "
                "assert all(v['available'] for v in t.tree_sitter_status()['languages'].values())"),
        },
        "per_language": {},
    }

    regex_engine = FunctionGraphEngine()
    for lang in LANGS:
        docs = [d for d in corpus(lang, args.copies) if tse.detect_language(d.path)]
        kb = sum(len(d.content.encode()) for d in docs) / 1024
        for d in docs:  # warm the parsers
            tse.extract(d.content, d.path, tse.detect_language(d.path), False)

        def run_ts():
            for d in docs:
                tse.extract(d.content, d.path, tse.detect_language(d.path), False)

        def run_regex():
            for d in docs:
                regex_engine.extract_polyglot(d.content, d.path)

        ts_ms, rx_ms = timed(run_ts, args.repeats), timed(run_regex, args.repeats)
        counts = [tse.extract(d.content, d.path, tse.detect_language(d.path), False) for d in docs]
        results["per_language"][lang] = {
            "files": len(docs),
            "kib": round(kb, 1),
            "tree_sitter_ms": ts_ms,
            "regex_ms": rx_ms,
            "tree_sitter_ms_per_kib": round(ts_ms / kb, 3),
            "regex_ms_per_kib": round(rx_ms / kb, 3),
            "tree_sitter_functions": sum(len(c.functions) for c in counts),
            "tree_sitter_calls": sum(len(c.calls) for c in counts),
            "regex_functions": sum(len(regex_engine.extract_polyglot(d.content, d.path)[0]) for d in docs),
            "regex_calls": sum(len(regex_engine.extract_polyglot(d.content, d.path)[1]) for d in docs),
        }

    docs = [d for lang in LANGS for d in corpus(lang, args.copies)]
    graph = {"files": len(docs)}
    for mode in ("regex", "tree_sitter"):
        cold = timed(lambda: FunctionGraphEngine(structural_parser=mode).build_graph(docs), args.repeats)
        engine = FunctionGraphEngine(structural_parser=mode).build_graph(docs)
        repeated = timed(lambda: engine.build_graph(docs), args.repeats)
        rss_before = rss_mb()
        tracemalloc.start()
        built = FunctionGraphEngine(structural_parser=mode).build_graph(docs)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        graph[mode] = {
            "build_graph_cold_ms": cold,
            "build_graph_repeated_ms": repeated,
            "python_peak_alloc_mb": round(peak / 1e6, 2),
            "peak_rss_mb_before_build": round(rss_before, 1),
            "peak_rss_mb_after_build": round(rss_mb(), 1),
            "functions": len(built.functions),
            "call_sites": len(built.call_sites),
            "edges": len(built.edges),
            "edge_types": {t: sum(1 for e in built.edges if e.edge_type == t)
                           for t in sorted({e.edge_type for e in built.edges})},
        }
    results["build_graph"] = graph

    print(json.dumps(results, indent=2, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
