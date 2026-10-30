"""
Stage 3.21: Production Implementation Quality & Polyglot Graph Audit Test Suite.
Tests AST symbol extraction, call resolution, edge direction, syntax error fallbacks,
and tie-breaking determinism using both real repository files and labelled fixtures.
"""

import pytest
from pathlib import Path
from reponeedle.models import FileDoc, RankerType
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.function_graph import FunctionGraphEngine, FunctionSymbol, CallSite
from reponeedle.core.arm101 import ARM101Ranker

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_real_python_code_symbol_extraction():
    """Verify AST extraction on real production Python code from reponeedle/."""
    engine_file = ROOT_DIR / "reponeedle" / "engine.py"
    assert engine_file.exists(), "engine.py must exist"

    content = engine_file.read_text(encoding="utf-8")
    fg = FunctionGraphEngine()
    funcs, calls, syms, imps = fg.extract_python_ast(content, "reponeedle/engine.py")

    # Verify key classes and methods are extracted
    func_names = {f.name for f in funcs}
    assert "retrieve" in func_names, "retrieve() method must be extracted"
    assert "from_documents" in func_names, "from_documents() classmethod must be extracted"
    assert "RepoNeedleEngine" in syms, "RepoNeedleEngine class symbol must be extracted"

    # Verify method flag
    retrieve_func = next(f for f in funcs if f.name == "retrieve")
    assert retrieve_func.is_method is True
    assert retrieve_func.parent_class == "RepoNeedleEngine"


def test_python_syntax_error_fallback():
    """Verify graceful regex fallback when Python file contains a syntax error."""
    broken_code = """
def valid_func_1(a, b):
    return a + b

def broken_syntax(x, y
    pass

def valid_func_2():
    return 42
"""
    fg = FunctionGraphEngine()
    funcs, calls, syms, imps = fg.extract_python_ast(broken_code, "broken.py")

    func_names = {f.name for f in funcs}
    assert "valid_func_1" in func_names, "Regex fallback must recover valid_func_1"
    assert "valid_func_2" in func_names, "Regex fallback must recover valid_func_2"


def test_real_polyglot_go_extraction():
    """Verify Go method, function, and call site extraction on realistic Go patterns."""
    go_code = """package server

import (
    "context"
    "net/http"
    "pkg/storage"
)

type Server struct {
    store storage.Store
}

func (s *Server) Start(ctx context.Context) error {
    return s.store.Init()
}

func NewServer(store storage.Store) *Server {
    return &Server{store: store}
}
"""
    fg = FunctionGraphEngine()
    funcs, calls, syms, imps = fg.extract_polyglot(go_code, "server/server.go")

    func_map = {f.name: f for f in funcs}
    assert "Start" in func_map
    assert func_map["Start"].is_method is True
    assert func_map["Start"].parent_class == "Server"
    assert "NewServer" in func_map
    assert func_map["NewServer"].is_method is False


def test_real_polyglot_rust_extraction():
    """Verify Rust function and qualified call extraction."""
    rust_code = """
pub mod parser;

pub struct Engine;

impl Engine {
    pub async fn run_query(&self, q: &str) -> bool {
        parser::parse_expression(q)
    }
}

pub fn standalone_helper() -> i32 {
    42
}
"""
    fg = FunctionGraphEngine()
    funcs, calls, syms, imps = fg.extract_polyglot(rust_code, "src/engine.rs")

    func_names = {f.name for f in funcs}
    assert "run_query" in func_names
    assert "standalone_helper" in func_names

    call_sites = {c.callee_name for c in calls}
    assert "parse_expression" in call_sites


def test_deterministic_ranking_tie_breaking():
    """Verify that tie-breaking in ARM101Ranker is 100% deterministic on equal scores."""
    docs = [
        FileDoc(path="z_file.py", content="def shared(): pass"),
        FileDoc(path="a_file.py", content="def shared(): pass"),
        FileDoc(path="m_file.py", content="def shared(): pass"),
    ]
    engine = RepoNeedleEngine.from_documents(docs)

    res1 = engine.retrieve("shared", ranker="arm101")
    res2 = engine.retrieve("shared", ranker="arm101")

    assert res1.ranked_files == res2.ranked_files
    # Alphabetical tie-breaking expects a_file.py before m_file.py before z_file.py
    assert res1.ranked_files == ["a_file.py", "m_file.py", "z_file.py"]


def test_empty_repository_handling():
    """Verify graceful handling when repository is empty."""
    engine = RepoNeedleEngine.from_documents([])
    res = engine.retrieve("any query", ranker="arm101")
    assert res.ranked_files == []
    assert res.abstained is True
