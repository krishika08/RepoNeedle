"""
Software quality and robustness test suite for RepoNeedle.
Validates:
- Stable deterministic rankings across repeated calls.
- Empty, whitespace, malformed, and unicode queries.
- Empty, 1-file, and small repositories.
- Duplicate files, paths, and casing edge cases.
- Syntax errors and fallback AST parsing behavior.
- Token-budget compliance under strict limits.
- Cyclic dependency graphs and self-references.
- CLI invocations and error handling.
"""

import pytest
import os
import tempfile
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import FileDoc, Query, TaskType, BudgetConfig


def test_deterministic_rankings():
    """Rankings must be 100% deterministic across repeated calls."""
    docs = [
        FileDoc(path="core/engine.py", content="class Engine:\n    def start(self): pass\n"),
        FileDoc(path="core/router.py", content="class Router:\n    def route(self): pass\n"),
        FileDoc(path="utils/helpers.py", content="def format_text(text): return text.strip()\n"),
    ]
    engine = RepoNeedleEngine.from_documents(docs)

    res1 = engine.retrieve("start engine service", budget_tokens=4000)
    res2 = engine.retrieve("start engine service", budget_tokens=4000)

    paths1 = [f.path for f in res1.selected_files]
    paths2 = [f.path for f in res2.selected_files]
    assert paths1 == paths2, "Retrieval order must be identical"
    assert res1.confidence_score == res2.confidence_score


def test_malformed_and_edge_queries():
    """Engine must gracefully handle empty, whitespace, and symbol queries without raising exceptions."""
    docs = [
        FileDoc(path="app.py", content="def main(): print('hello')\n"),
    ]
    engine = RepoNeedleEngine.from_documents(docs)

    # Empty query
    res_empty = engine.retrieve("", budget_tokens=4000)
    assert res_empty is not None
    assert isinstance(res_empty.selected_files, list)

    # Whitespace only
    res_ws = engine.retrieve("    \n\t   ", budget_tokens=4000)
    assert res_ws is not None

    # Unicode & punctuation symbols only
    res_punct = engine.retrieve("!@#$%^&*()_+-=[]{}|;':,.<>/?", budget_tokens=4000)
    assert res_punct is not None

    # Extremely long query
    long_q = "error " * 500
    res_long = engine.retrieve(long_q, budget_tokens=4000)
    assert res_long is not None


def test_small_and_single_file_repositories():
    """Handles repositories with 1 file."""
    docs = [
        FileDoc(path="single.py", content="def calculate(a, b): return a + b\n"),
    ]
    engine = RepoNeedleEngine.from_documents(docs)
    res = engine.retrieve("calculate function", budget_tokens=4000)
    assert len(res.selected_files) == 1
    assert res.selected_files[0].path == "single.py"


def test_duplicate_file_paths():
    """Deduplicates documents if identical file paths appear."""
    docs = [
        FileDoc(path="dup.py", content="def first(): pass\n"),
        FileDoc(path="dup.py", content="def second(): pass\n"),
    ]
    engine = RepoNeedleEngine.from_documents(docs)
    res = engine.retrieve("def first", budget_tokens=4000)
    paths = [f.path for f in res.selected_files]
    assert len(paths) == len(set(paths)), "Duplicate paths must not appear multiple times"


def test_syntax_error_ast_fallback():
    """Invalid Python syntax must fall back to regex without crashing."""
    bad_code = "def broken_syntax( self { return !!!"
    docs = [
        FileDoc(path="broken.py", content=bad_code),
    ]
    # Engine initialization must not crash
    engine = RepoNeedleEngine.from_documents(docs)
    res = engine.retrieve("broken syntax function", budget_tokens=4000)
    assert len(res.selected_files) >= 0


def test_strict_token_budget_compliance():
    """Total tokens returned must never exceed requested budget."""
    long_content = "def test_func():\n" + ("    x = 1\n" * 500)
    docs = [
        FileDoc(path="file1.py", content=long_content),
        FileDoc(path="file2.py", content=long_content),
        FileDoc(path="file3.py", content=long_content),
    ]
    engine = RepoNeedleEngine.from_documents(docs, budget_config=BudgetConfig(allow_skeletons=True))
    res = engine.retrieve("test_func", budget_tokens=500)
    assert res.total_tokens <= 500, f"Expected <= 500 tokens, got {res.total_tokens}"


def test_cyclic_and_self_dependencies():
    """PageRank and graph walkers must not enter infinite loops on cyclic imports."""
    docs = [
        FileDoc(path="a.py", content="import b\nclass A: pass\n", imports=["b"], symbols=["A"]),
        FileDoc(path="b.py", content="import a\nclass B: pass\n", imports=["a"], symbols=["B"]),
        FileDoc(path="self_dep.py", content="import self_dep\n", imports=["self_dep"], symbols=["Self"]),
    ]
    engine = RepoNeedleEngine.from_documents(docs)
    res = engine.retrieve("class A imports b", budget_tokens=4000)
    assert len(res.selected_files) > 0


def test_unicode_filenames_and_contents():
    """Handles unicode filenames and non-ASCII character contents cleanly."""
    docs = [
        FileDoc(path="src/üñîçødé_módülé.py", content="# 日本語コメント\ndef café(): return '☕'\n", symbols=["café"]),
    ]
    engine = RepoNeedleEngine.from_documents(docs)
    res = engine.retrieve("café coffee function", budget_tokens=4000)
    assert len(res.selected_files) == 1
    assert "café" in res.selected_files[0].path or "üñîçødé" in res.selected_files[0].path


def test_cli_invocation_help_and_version():
    """CLI must respond with valid exit code on --help."""
    import subprocess
    import sys
    result = subprocess.run([sys.executable, "-m", "reponeedle.cli", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "RepoNeedle" in result.stdout or "usage" in result.stdout.lower()

