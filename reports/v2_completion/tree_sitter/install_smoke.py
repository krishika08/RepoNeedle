"""
Installation smoke test for the optional Tree-sitter extra, run against an *installed* RepoNeedle
(for example a fresh virtual environment with the built wheel).

    python install_smoke.py absent    # pip install reponeedle-<ver>.whl
    python install_smoke.py present   # pip install "reponeedle-<ver>.whl[treesitter]"

absent:  the opt-in must not fail; every handled file falls back to the regex extractor with a reason,
         the edges equal the default mode, and retrieval works.
present: runtime and all grammars load; each language yields functions, calls and an import-bound
         verified edge; no file falls back.
"""

import importlib.util
import json
import sys

import reponeedle
from reponeedle.core import tree_sitter_extraction as tse
from reponeedle.core.function_graph import FunctionGraphEngine
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import AblationConfig, FileDoc

DOCS = [
    FileDoc(path="ts/util.ts", content="export function helper(x: number) { return x; }\n"),
    FileDoc(path="ts/main.ts", content='import { helper } from "./util";\nexport function run() { return helper(1); }\n'),
    FileDoc(path="go.mod", content="module example.com/m\n"),
    FileDoc(path="lib/lib.go", content="package lib\nfunc Help() int { return 1 }\n"),
    FileDoc(path="app/app.go", content='package app\nimport "example.com/m/lib"\nfunc Run() int { return lib.Help() }\n'),
    FileDoc(path="Cargo.toml", content='[package]\nname = "demo"\n'),
    FileDoc(path="src/lib.rs", content="pub mod util;\npub fn run() -> i32 { util::help() }\n"),
    FileDoc(path="src/util.rs", content="pub fn help() -> i32 { 1 }\n"),
    FileDoc(path="j/com/a/Util.java", content="package com.a;\npublic class Util { public static int help() { return 1; } }\n"),
    FileDoc(path="j/com/b/Main.java", content="package com.b;\nimport com.a.Util;\nclass Main { int run() { return Util.help(); } }\n"),
    FileDoc(path="c/util.cpp", content="int unique_helper_fn() { return 1; }\n"),
    FileDoc(path="c/main.cpp", content='#include "util.h"\nint main() { return unique_helper_fn(); }\n'),
]


def main(expect: str) -> int:
    installed = importlib.util.find_spec("tree_sitter") is not None
    print(f"reponeedle {reponeedle.__version__} from {reponeedle.__file__}; tree_sitter installed: {installed}")
    status = tse.tree_sitter_status()
    print(json.dumps(status, indent=1))
    ts = FunctionGraphEngine(structural_parser="tree_sitter").build_graph(DOCS)
    regex = FunctionGraphEngine().build_graph(DOCS)
    diag = ts.diagnostics["structural_parser"]
    edges = sorted((e.source_path, e.target_path, e.edge_type) for e in ts.edges)
    print("tree_sitter files:", diag["files"]["tree_sitter"])
    print("fallback:", diag["files"]["regex_fallback"])
    print("edges:", edges)

    engine = RepoNeedleEngine(docs=DOCS, ablation_config=AblationConfig(structural_parser="tree_sitter"))
    result = engine.retrieve("helper", budget_tokens=1000, ranker="arm101")
    assert result.selected_files, "retrieval returned nothing"

    handled = sorted(d.path for d in DOCS if tse.detect_language(d.path))
    if expect == "absent":
        assert not installed and not status["runtime"]["available"]
        assert sorted(diag["files"]["regex_fallback"]) == handled
        assert [vars(e) for e in ts.edges] == [vars(e) for e in regex.edges]
    else:
        assert installed and status["runtime"]["available"]
        assert all(v["available"] for v in status["languages"].values()), status["languages"]
        assert diag["files"]["tree_sitter"] == handled and not diag["files"]["regex_fallback"]
        for src, dst in [("ts/main.ts", "ts/util.ts"), ("app/app.go", "lib/lib.go"),
                         ("src/lib.rs", "src/util.rs"), ("j/com/b/Main.java", "j/com/a/Util.java")]:
            assert (src, dst, "verified_call") in edges, (src, dst)
        assert ("c/main.cpp", "c/util.cpp", "unique_global_call") in edges
    print(f"OK ({expect})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "present"))
