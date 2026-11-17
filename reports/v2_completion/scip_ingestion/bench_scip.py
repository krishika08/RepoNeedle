"""
SCIP ingestion performance on synthetic indexes of increasing size, plus the real scip-typescript fixture.

Usage:
    python bench_scip.py [--sizes 10 100 1000 5000] [--functions 20] [--repeats 3] [--out results.json]

Each synthetic repository has N files with F functions each. Every function has one definition occurrence
(with an enclosing range) and one reference to the same-numbered function of the next file, so a document
has 2*F occurrences. Files are written to a temporary directory, so path containment checks run as they do
in practice. Every size runs in a fresh interpreter, so earlier sizes do not affect memory or timing.
"""

import argparse
import json
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import google.protobuf  # noqa: E402
from google.protobuf.internal import api_implementation  # noqa: E402

from reponeedle.core._scip import scip_pb2 as pb  # noqa: E402
from reponeedle.core.function_graph import FunctionGraphEngine  # noqa: E402
from reponeedle.core.scip_ingestion import ScipIndex  # noqa: E402
from reponeedle.models import FileDoc  # noqa: E402


def peak_rss_mb():
    if sys.platform == "win32":
        import ctypes
        import ctypes.wintypes as wt

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("a", ctypes.c_size_t), ("b", ctypes.c_size_t),
                        ("c", ctypes.c_size_t), ("d", ctypes.c_size_t), ("e", ctypes.c_size_t), ("f", ctypes.c_size_t)]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
        k32.GetCurrentProcess.restype = wt.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
        psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return pmc.PeakWorkingSetSize / 1e6
    import resource
    scale = 1e6 if sys.platform == "darwin" else 1e3
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / scale


def make_repo(root: Path, n_files: int, n_funcs: int):
    """Writes the files and returns (FileDocs, serialized index)."""
    index = pb.Index()
    index.metadata.tool_info.name, index.metadata.tool_info.version = "bench-synthetic", "1.0"
    index.metadata.project_root = root.as_uri()
    docs = []
    for i in range(n_files):
        nxt = (i + 1) % n_files
        lines = [f"export function f{i}_{j}() {{ return f{nxt}_{j}(); }}" for j in range(n_funcs)]
        content = "\n".join(lines) + "\n"
        path = f"pkg{i // 100}/m{i}.ts"
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(content, encoding="utf-8", newline="\n")
        docs.append(FileDoc(path=path, content=content))
        d = index.documents.add(relative_path=path, language="typescript",
                                position_encoding=pb.UTF8CodeUnitOffsetFromLineStart)
        for j, line in enumerate(lines):
            name, ref = f"f{i}_{j}", f"f{nxt}_{j}"
            sym = f"bench npm repo 1.0 m{i}/{name}()."
            d_start = line.index(name)
            o = d.occurrences.add(symbol=sym, symbol_roles=pb.Definition)
            o.single_line_range.line, o.single_line_range.start_character, o.single_line_range.end_character = \
                j, d_start, d_start + len(name)
            o.single_line_enclosing_range.line = j
            o.single_line_enclosing_range.start_character = 0
            o.single_line_enclosing_range.end_character = len(line)
            r_start = line.index(ref, d_start + len(name))
            r = d.occurrences.add(symbol=f"bench npm repo 1.0 m{nxt}/{ref}().")
            r.single_line_range.line, r.single_line_range.start_character, r.single_line_range.end_character = \
                j, r_start, r_start + len(ref)
            d.symbols.add(symbol=sym, kind=pb.SymbolInformation.Function, display_name=name)
    return docs, index.SerializeToString()


def median_ms(fn, repeats):
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return round(statistics.median(samples) * 1000, 2)


def measure_size(n, functions, repeats):
    tmp = Path(tempfile.mkdtemp(prefix="scipbench"))
    try:
        docs, data = make_repo(tmp, n, functions)
        index_path = tmp / "index.scip"
        index_path.write_bytes(data)

        # Timing, without a tracer. "Cold" is the first load/resolve in this fresh interpreter.
        t0 = time.perf_counter()
        index = ScipIndex.load(str(index_path))
        load_ms = (time.perf_counter() - t0) * 1000
        index.validate_root(str(tmp))
        t1 = time.perf_counter()
        res = index.resolve(docs)
        resolve_cold_ms = (time.perf_counter() - t1) * 1000
        resolve_repeat_ms = median_ms(lambda: index.resolve(docs), repeats)
        load_repeat_ms = median_ms(lambda: ScipIndex.load(str(index_path)), repeats)
        graph_plain_ms = median_ms(lambda: FunctionGraphEngine().build_graph(docs), repeats)

        def with_scip():
            fg = FunctionGraphEngine()
            fg.scip_index = index
            return fg.build_graph(docs)

        graph_scip_ms = median_ms(with_scip, repeats)
        fg = with_scip()

        # Memory last (tracemalloc slows Python down several times).
        rss_before = peak_rss_mb()
        tracemalloc.start()
        mem_index = ScipIndex.load(str(index_path))
        mem_index.validate_root(str(tmp))
        mem_index.resolve(docs)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        d = res.diagnostics
        return {
            "documents": n,
            "occurrences": d["occurrences"]["total"],
            "index_bytes": len(data),
            "load_parse_ms_cold": round(load_ms, 2),
            "load_parse_ms_repeated": load_repeat_ms,
            "resolve_ms_cold": round(resolve_cold_ms, 2),
            "resolve_ms_repeated": resolve_repeat_ms,
            "us_per_occurrence_resolve_repeated": round(resolve_repeat_ms * 1000 / max(1, d["occurrences"]["total"]), 1),
            "build_graph_ms_without_scip": graph_plain_ms,
            "build_graph_ms_with_scip": graph_scip_ms,
            "python_peak_alloc_mb_load_and_resolve": round(peak / 1e6, 2),
            "peak_rss_mb_before_memory_pass": round(rss_before, 1),
            "peak_rss_mb_after_memory_pass": round(peak_rss_mb(), 1),
            "definitions": d["definitions"]["total"],
            "references": d["references"]["total"],
            "reference_edges": d["edges"]["reference_edges"],
            "graph_edges_added": fg.diagnostics["scip"]["edges"]["added_to_graph"],
            "graph_edges_already_present": fg.diagnostics["scip"]["edges"]["already_present_from_extraction"],
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def measure_real(repeats):
    real = ROOT / "tests" / "fixtures" / "scip" / "real" / "typescript"
    docs = [FileDoc(path=p.relative_to(real).as_posix(), content=p.read_text(encoding="utf-8"))
            for p in sorted(real.rglob("*")) if p.suffix in (".ts", ".tsx")]
    index = ScipIndex.load(str(real / "index.scip"))
    index.validate_root(str(real), allow_mismatch=True)
    return {
        "index_bytes": index.file_bytes,
        "load_parse_ms": median_ms(lambda: ScipIndex.load(str(real / "index.scip")), repeats),
        "resolve_ms": median_ms(lambda: index.resolve(docs), repeats),
        "documents": len(index._msg.documents),
        "occurrences": index.resolve(docs).diagnostics["occurrences"]["total"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[10, 100, 1000, 5000])
    ap.add_argument("--functions", type=int, default=20)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", default=None)
    ap.add_argument("--single", type=int, default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.single is not None:  # child process: one size in a fresh interpreter
        print(json.dumps(measure_size(args.single, args.functions, args.repeats)))
        return

    results = {
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                        "processor": platform.processor() or platform.machine(),
                        "protobuf": google.protobuf.__version__, "protobuf_implementation": api_implementation.Type(),
                        "functions_per_file": args.functions, "repeats": args.repeats,
                        "isolation": "one fresh interpreter per size"},
        "synthetic": [],
    }
    for n in args.sizes:
        out = subprocess.run([sys.executable, __file__, "--single", str(n), "--functions", str(args.functions),
                              "--repeats", str(args.repeats)], capture_output=True, text=True, check=True).stdout
        results["synthetic"].append(json.loads(out.strip().splitlines()[-1]))
        print(json.dumps(results["synthetic"][-1]))
    results["real_scip_typescript"] = measure_real(args.repeats)
    print(json.dumps(results["real_scip_typescript"]))
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
