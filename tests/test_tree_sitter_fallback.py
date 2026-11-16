"""
Default behaviour and fallback paths of the optional Tree-sitter extraction. These tests need no optional
packages: they run in every CI job, including the strict no-skip Linux job.

- The default ("regex") mode reproduces the 1.2.0 implementation exactly (golden produced from
  function_graph.py at d10ee70; see reports/v2_completion/tree_sitter/make_regex_golden.py).
- Python always uses the `ast` extractor, in both modes.
- A missing Tree-sitter runtime never raises: files fall back to the regex extractor, the reason is
  recorded in the diagnostics and a warning is logged.
- Nothing is downloaded: parsing works with sockets disabled.
"""

import json
import logging
import socket

import pytest

from tree_sitter_support import FIXTURES, load_docs

from reponeedle.core import tree_sitter_extraction as tse
from reponeedle.core.function_graph import STRUCTURAL_PARSERS, FunctionGraphEngine
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import AblationConfig, FileDoc

GOLDEN = json.loads((FIXTURES / "regex_mode_golden.json").read_text(encoding="utf-8"))
CORPORA = ["python", "typescript", "go", "rust", "java", "cpp"]


def _snapshot(fg: FunctionGraphEngine, docs):
    files = {}
    for d in docs:
        funcs, calls, syms, imps = fg.extract_polyglot(d.content, d.path)
        files[d.path] = {
            "functions": [[f.name, f.parent_class, f.is_method, f.is_test, f.start_line, f.arg_names] for f in funcs],
            "calls": [[c.callee_name, c.qualifier, c.is_attribute, c.caller_func, c.start_line] for c in calls],
            "symbols": syms,
            "imports": imps,
        }
    fg.build_graph(docs)
    edges = [[e.source_path, e.target_path, e.source_func, e.target_func, e.edge_type, e.confidence] for e in fg.edges]
    return {"files": files, "edges": edges}


@pytest.fixture
def no_tree_sitter(monkeypatch):
    """Simulates an installation without the optional packages."""
    real_import = tse._import_module

    def fake_import(name):
        if name == "tree_sitter" or name.startswith("tree_sitter_"):
            raise ModuleNotFoundError(f"No module named '{name}'")
        return real_import(name)

    tse.reset_parser_cache()
    monkeypatch.setattr(tse, "_import_module", fake_import)
    yield
    tse.reset_parser_cache()


# --- packaging ---------------------------------------------------------------------

def _pyproject():
    import re
    from pathlib import Path
    try:
        import tomllib
    except ImportError:  # Python 3.10
        import tomli as tomllib
    root = Path(__file__).resolve().parent.parent
    return tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"], re


def test_tree_sitter_is_never_a_core_dependency():
    project, _ = _pyproject()
    assert not any("tree-sitter" in d or "tree_sitter" in d for d in project["dependencies"])
    for name, deps in project["optional-dependencies"].items():
        if name != "treesitter":
            assert not any("tree-sitter" in d for d in deps), name


def test_treesitter_extra_pins_tested_compatible_versions():
    project, re = _pyproject()
    deps = project["optional-dependencies"]["treesitter"]
    names = {re.split(r"[<>=\[;]", d, maxsplit=1)[0].strip() for d in deps}
    assert names == {"tree-sitter", "tree-sitter-typescript", "tree-sitter-go", "tree-sitter-rust",
                     "tree-sitter-java", "tree-sitter-cpp"}
    assert not any("[core]" in d for d in deps)          # grammars' own extras allow ABI-incompatible runtimes
    runtime = next(d for d in deps if d.startswith("tree-sitter>") or d.startswith("tree-sitter="))
    assert ">=0.25" in runtime                           # ABI 15 grammars (Go, Rust) need runtime >= 0.25
    assert all("<" in d for d in deps)                   # upper bounds: grammar node types change between minors


def test_importing_reponeedle_does_not_import_tree_sitter():
    import subprocess
    import sys
    code = ("import sys, reponeedle, reponeedle.core.function_graph, reponeedle.core.tree_sitter_extraction;"
            "print(any(m == 'tree_sitter' or m.startswith('tree_sitter_') for m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "False"


# --- defaults --------------------------------------------------------------------

def test_defaults_are_the_1_2_0_behaviour():
    assert AblationConfig().structural_parser == "regex"
    assert FunctionGraphEngine().structural_parser == "regex"
    assert RepoNeedleEngine().function_graph.structural_parser == "regex"
    assert STRUCTURAL_PARSERS == ("regex", "tree_sitter")


def test_invalid_parser_names_are_rejected():
    with pytest.raises(ValueError):
        FunctionGraphEngine(structural_parser="treesitter")
    with pytest.raises(Exception):
        AblationConfig(structural_parser="ctags")


@pytest.mark.parametrize("corpus", CORPORA)
def test_default_mode_matches_the_1_2_0_golden(corpus):
    docs = load_docs(corpus)
    assert _snapshot(FunctionGraphEngine(), docs) == GOLDEN[corpus]


def test_default_mode_records_no_parser_diagnostics():
    fg = FunctionGraphEngine().build_graph(load_docs("go"))
    assert "structural_parser" not in fg.diagnostics


def test_python_extraction_is_identical_in_both_modes():
    docs = load_docs("python")
    regex = FunctionGraphEngine().build_graph(docs)
    ts = FunctionGraphEngine(structural_parser="tree_sitter").build_graph(docs)
    key = lambda fg: ([vars(f) for f in fg.functions], [vars(c) for c in fg.call_sites],
                      [vars(e) for e in fg.edges])
    assert key(regex) == key(ts)
    assert ts.diagnostics["structural_parser"]["files"]["python_ast"] == len(docs)


def test_python_ast_extractor_output_is_unchanged():
    content = (FIXTURES / "python" / "shop" / "pricing.py").read_text(encoding="utf-8")
    funcs, calls, syms, imps = FunctionGraphEngine().extract_python_ast(content, "shop/pricing.py")
    assert [(f.name, f.parent_class, f.is_method, f.start_line, f.arg_names) for f in funcs] == [
        ("apply_discount", None, False, 5, ["price", "pct"]),
        ("__init__", "Rule", True, 10, ["self", "pct"]),
        ("apply", "Rule", True, 13, ["self", "price"]),
    ]
    assert [(c.callee_name, c.qualifier, c.is_attribute, c.caller_func, c.start_line, c.qualifier_path) for c in calls] == [
        ("round2", None, False, "apply_discount", 6, None),
        ("apply_discount", None, False, "apply", 14, None),
    ]
    assert syms == ["round2", "apply_discount", "Rule", "__init__", "apply"]
    assert imps == ["shop.util", "shop.util.round2"]


# --- language routing ------------------------------------------------------------

@pytest.mark.parametrize("path,language", [
    ("a.ts", "typescript"), ("a.d.ts", "typescript"), ("a.mts", "typescript"), ("A.TSX", "tsx"),
    ("a.go", "go"), ("a.rs", "rust"), ("A.java", "java"), ("a.cpp", "cpp"), ("a.cc", "cpp"),
    ("a.hpp", "cpp"), ("a.h", "cpp"), ("dir\\a.go", "go"),
    ("a.py", None), ("a.js", None), ("a.jsx", None), ("a.c", None), ("a.md", None), ("Makefile", None),
])
def test_language_detection(path, language):
    assert tse.detect_language(path) == language


def test_unsupported_extensions_keep_the_regex_extractor():
    docs = [
        FileDoc(path="web/app.js", content="function run() { helper(); }\nfunction helper() {}\n"),
        FileDoc(path="native/util.c", content="int add(int a, int b) { return a + b; }\n"),
        FileDoc(path="README.md", content="# run()\n"),
    ]
    regex = FunctionGraphEngine()
    ts = FunctionGraphEngine(structural_parser="tree_sitter").build_graph(docs)
    for d in docs:
        a = regex.extract_polyglot(d.content, d.path)
        assert [vars(f) for f in a[0]] == [vars(f) for f in ts.functions if f.filepath == d.path]
    assert ts.diagnostics["structural_parser"]["files"]["regex_other_languages"] == 3
    assert ts.diagnostics["structural_parser"]["files"]["tree_sitter"] == []


# --- missing optional packages ------------------------------------------------------

def test_missing_runtime_is_reported(no_tree_sitter):
    status = tse.tree_sitter_status()
    assert status["runtime"]["available"] is False
    assert "tree_sitter" in status["runtime"]["error"]
    assert all(not v["available"] for v in status["languages"].values())
    assert tse.extract("package p", "p.go", "go", False) is None


@pytest.mark.parametrize("corpus", ["typescript", "go", "rust", "java", "cpp"])
def test_missing_runtime_falls_back_to_regex_exactly(no_tree_sitter, corpus, caplog):
    docs = load_docs(corpus)
    with caplog.at_level(logging.WARNING, logger="reponeedle.function_graph"):
        ts = FunctionGraphEngine(structural_parser="tree_sitter").build_graph(docs)
    regex_snapshot = _snapshot(FunctionGraphEngine(), docs)
    assert [[e.source_path, e.target_path, e.source_func, e.target_func, e.edge_type, e.confidence]
            for e in ts.edges] == regex_snapshot["edges"]

    diag = ts.diagnostics["structural_parser"]
    handled = [d.path for d in docs if tse.detect_language(d.path)]
    assert diag["runtime_available"] is False
    assert sorted(diag["files"]["regex_fallback"]) == sorted(handled)
    assert all("tree-sitter runtime unavailable" in r for r in diag["files"]["regex_fallback"].values())
    assert diag["files"]["tree_sitter"] == []
    assert any("regex fallback" in rec.getMessage() for rec in caplog.records)


def test_engine_with_tree_sitter_requested_but_unavailable_still_retrieves(no_tree_sitter):
    docs = load_docs("go")
    engine = RepoNeedleEngine(docs=docs, ablation_config=AblationConfig(structural_parser="tree_sitter"))
    baseline = RepoNeedleEngine(docs=docs)
    for ranker in ("legacy", "arm101"):
        got = engine.retrieve("apply discount to cart total", budget_tokens=2000, ranker=ranker)
        want = baseline.retrieve("apply discount to cart total", budget_tokens=2000, ranker=ranker)
        assert [f.path for f in got.selected_files] == [f.path for f in want.selected_files]


def test_extraction_errors_fall_back_per_file(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("simulated parser failure")

    monkeypatch.setattr(tse, "extract", boom)
    docs = load_docs("go")
    fg = FunctionGraphEngine(structural_parser="tree_sitter").build_graph(docs)
    reasons = fg.diagnostics["structural_parser"]["files"]["regex_fallback"]
    assert reasons and all("simulated parser failure" in r for r in reasons.values())
    assert [vars(e) for e in fg.edges] == [vars(e) for e in FunctionGraphEngine().build_graph(docs).edges]


def test_no_network_access_is_needed(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    tse.reset_parser_cache()
    monkeypatch.setattr(socket, "socket", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    for corpus in ["typescript", "go", "rust", "java", "cpp"]:
        FunctionGraphEngine(structural_parser="tree_sitter").build_graph(load_docs(corpus))
    tse.tree_sitter_status()
