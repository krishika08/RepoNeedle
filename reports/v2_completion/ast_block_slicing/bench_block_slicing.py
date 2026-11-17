"""
Extraction benchmark: AST block slicing vs the legacy focus span on large single files.

    python reports/v2_completion/ast_block_slicing/bench_block_slicing.py [--out results.json] [--repeats 5]

Inputs are reproducible: synthetic files with many functions are generated deterministically per language (classes,
decorators/attributes, nested functions), plus two real RepoNeedle modules snapshotted in tests/fixtures. For each
file and query, it reports:

* cold time: a new CodeSpanExtractor (parse + select + render; Tree-sitter grammars already loaded),
* warm time: the same extractor and query again (result cache hit),
* warm-structure time: same file, a different query (parse cached, selection + rendering only),
* peak Python allocation of one cold extraction (tracemalloc, measured in a separate pass),
* blocks considered / selected and output size (lines, exact benchmark tokens) for both extractors.

Medians over ``--repeats`` runs. Timings depend on the machine; see REPORT.md for the recorded environment.
"""

import argparse
import json
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from reponeedle.core import block_slicing as bs  # noqa: E402
from reponeedle.core import tree_sitter_extraction as tse  # noqa: E402
from reponeedle.core.packer import CodeSpanExtractor  # noqa: E402


def gen_python(n: int) -> str:
    out = ["import math", "import os", "from typing import Dict, List", ""]
    for c in range(n // 10):
        out += ["", f"class Service{c}:", f'    """Service {c}."""', ""]
        for m in range(10):
            i = c * 10 + m
            out += [f"    @staticmethod" if m % 3 == 0 else f"    # method {i}",
                    f"    def handle_{i}(value: int) -> int:",
                    f"        def nested_{i}(x):",
                    f"            return x * {i} + math.floor(x)",
                    f"        total = nested_{i}(value)",
                    f"        for k in range({i % 7 + 2}):",
                    f"            total += k",
                    f"        return total", ""]
    return "\n".join(out) + "\n"


def gen_typescript(n: int) -> str:
    out = ['import { round } from "./math";', 'import { log } from "./log";', ""]
    for c in range(n // 10):
        out += [f"export class Service{c} {{"]
        for m in range(10):
            i = c * 10 + m
            out += [f"  @Trace()" if m % 3 == 0 else f"  // method {i}",
                    f"  handle{i}(value: number): number {{",
                    f"    const nested{i} = (x: number) => x * {i} + round(x);",
                    f"    let total = nested{i}(value);",
                    f"    for (let k = 0; k < {i % 7 + 2}; k++) {{",
                    f"      total += k;",
                    f"    }}",
                    f"    return total;",
                    f"  }}", ""]
        out += ["}", ""]
    return "\n".join(out) + "\n"


def gen_go(n: int) -> str:
    out = ["package service", "", "import (", '\t"fmt"', '\t"math"', ")", ""]
    for i in range(n):
        out += [f"// Handle{i} handles one value.",
                f"func (s *Service) Handle{i}(value int) int {{",
                f"\tnested := func(x int) int {{ return x*{i} + int(math.Floor(float64(x))) }}",
                f"\ttotal := nested(value)",
                f"\tfor k := 0; k < {i % 7 + 2}; k++ {{",
                f"\t\ttotal += k",
                f"\t}}",
                f'\tfmt.Sprint(total)',
                f"\treturn total",
                "}", ""]
    return "\n".join(out) + "\n"


def gen_rust(n: int) -> str:
    out = ["use std::collections::HashMap;", "", "pub struct Service;", "", "impl Service {"]
    for i in range(n):
        out += [f"    /// Handles value {i}.",
                f"    #[inline]" if i % 3 == 0 else f"    // method {i}",
                f"    pub fn handle_{i}(&self, value: i64) -> i64 {{",
                f"        fn nested_{i}(x: i64) -> i64 {{ x * {i} }}",
                f"        let mut total = nested_{i}(value);",
                f"        for k in 0..{i % 7 + 2} {{",
                f"            total += k;",
                f"        }}",
                f"        total",
                f"    }}", ""]
    out += ["}", ""]
    return "\n".join(out) + "\n"


def gen_java(n: int) -> str:
    out = ["package com.example.service;", "", "import java.util.List;", "import java.util.Map;", "",
           "public class Service {"]
    for i in range(n):
        out += [f"    /** Handles value {i}. */",
                f"    @Override" if i % 3 == 0 else f"    // method {i}",
                f"    public int handle{i}(int value) {{",
                f"        int total = value * {i};",
                f"        for (int k = 0; k < {i % 7 + 2}; k++) {{",
                f"            total += k;",
                f"        }}",
                f"        return total;",
                f"    }}", ""]
    out += ["}", ""]
    return "\n".join(out) + "\n"


def gen_cpp(n: int) -> str:
    out = ['#include "service.h"', "#include <cmath>", "", "namespace service {", ""]
    for i in range(n):
        out += [f"/// Handles value {i}.",
                f"int Service::handle_{i}(int value) {{",
                f"    int total = value * {i} + static_cast<int>(std::floor(value));",
                f"    for (int k = 0; k < {i % 7 + 2}; ++k) {{",
                f"        total += k;",
                f"    }}",
                f"    return total;",
                "}", ""]
    out += ["}  // namespace service", ""]
    return "\n".join(out) + "\n"


GENERATORS = {"python": ("py", gen_python), "typescript": ("ts", gen_typescript), "go": ("go", gen_go),
              "rust": ("rs", gen_rust), "java": ("java", gen_java), "cpp": ("cpp", gen_cpp)}


def inputs():
    for lang, (ext, gen) in GENERATORS.items():
        for n in (200, 2000):
            name = f"synthetic {lang} {n} functions"
            fid = n * 3 // 4                                            # a function near the end of the file
            yield name, f"bench/service_{n}.{ext}", gen(n), {f"handle{fid}", f"handle_{fid}"}, {"floor"}
    fixtures = ROOT / "tests" / "fixtures" / "block_slicing" / "python"
    for rel, q1, q2 in (("packer_snapshot.py", {"skeleton", "truncated"}, {"overhead"}),
                        ("function_graph_snapshot.py", {"resolve", "import"}, {"edge", "confidence"})):
        yield f"real python {rel}", f"reponeedle/core/{rel}", (fixtures / rel).read_text(encoding="utf-8"), q1, q2


def median_ms(fn, repeats: int) -> float:
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    return round(statistics.median(times), 3)


def peak_kib(fn) -> float:
    tracemalloc.start()
    fn()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return round(peak / 1024, 1)


def measure(name, path, content, terms, other_terms, repeats):
    lines = len(content.splitlines())
    warm_ex = CodeSpanExtractor()
    block_text, block_tokens = warm_ex.extract_block_span(content, path, terms)
    sliced = warm_ex.slice_blocks(content, path, terms)
    legacy_text, legacy_tokens = CodeSpanExtractor().extract_focus_span(content, path, terms)
    structure = bs.analyze_structure(content, path).structure
    row = {
        "input": name, "language": bs.detect_language(path), "lines": lines, "bytes": len(content.encode()),
        "blocks_in_file": len(structure.blocks) if structure else None,
        "blocks_considered": sliced.blocks_considered, "blocks_matched": sliced.matched_blocks,
        "blocks_selected": len(sliced.selected), "fallback_reason": sliced.fallback_reason,
        "ast_blocks": {
            "cold_ms": median_ms(lambda: CodeSpanExtractor().extract_block_span(content, path, terms), repeats),
            "warm_cached_ms": median_ms(lambda: warm_ex.extract_block_span(content, path, terms), repeats),
            "warm_structure_new_query_ms": median_ms(
                lambda: warm_ex.slice_blocks(content, path, other_terms | {str(time.perf_counter_ns())}), repeats),
            "peak_alloc_kib": peak_kib(lambda: CodeSpanExtractor().extract_block_span(content, path, terms)),
            "output_lines": len(block_text.splitlines()), "output_tokens": block_tokens,
        },
        "legacy_focus_span": {
            "cold_ms": median_ms(lambda: CodeSpanExtractor().extract_focus_span(content, path, terms), repeats),
            "peak_alloc_kib": peak_kib(lambda: CodeSpanExtractor().extract_focus_span(content, path, terms)),
            "output_lines": len(legacy_text.splitlines()), "output_tokens": legacy_tokens,
        },
    }
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    status = tse.tree_sitter_status()
    for lang in tse.GRAMMARS:                                          # load grammars outside the timings
        tse.load_language(lang)
    rows = [measure(*inp, args.repeats) for inp in inputs()]
    result = {
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                        "processor": platform.processor() or platform.machine(),
                        "tree_sitter": status["runtime"]["version"], "repeats": args.repeats},
        "results": rows,
    }
    for r in rows:
        a, l = r["ast_blocks"], r["legacy_focus_span"]
        print(f"{r['input']:<44} {r['lines']:>6} lines  blocks {r['blocks_in_file']}  "
              f"ast cold {a['cold_ms']:>8.2f} ms warm {a['warm_cached_ms']:.3f} new-query {a['warm_structure_new_query_ms']:.2f}"
              f" | legacy {l['cold_ms']:>7.2f} ms | tokens ast {a['output_tokens']} legacy {l['output_tokens']}")
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
