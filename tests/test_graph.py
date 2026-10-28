"""
Tests for RepoGraph and structural analysis.
"""

import pytest
import numpy as np
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph


def test_repo_graph_ast_extraction():
    content = (
        "import os\n"
        "from flask import Request\n"
        "class App:\n"
        "    def run(self): pass\n"
        "def main(): pass\n"
    )
    symbols, imports = RepoGraph.extract_python_ast(content, "app.py")
    assert "App" in symbols
    assert "main" in symbols
    assert "os" in imports
    assert "flask" in imports


def test_repo_graph_linkages():
    docs = [
        FileDoc(path="src/app.py", content="from .utils import helper\n", imports=["utils"]),
        FileDoc(path="src/utils.py", content="def helper(): pass\n", symbols=["helper"]),
        FileDoc(path="tests/test_utils.py", content="from src.utils import helper\n", imports=["src.utils"], is_test=True),
    ]
    graph = RepoGraph().fit(docs)
    assert len(graph.graph.nodes) == 3
    # PageRank scores should be computed
    assert len(graph.pagerank_scores) == 3
    # test_utils.py should map to utils.py
    assert "src/utils.py" in graph.test_to_target_map.get("tests/test_utils.py", set())


def test_cargo_manifest_parsing_valid_and_malformed():
    valid_toml = """
[package]
name = "ripgrep_core"
version = "0.1.0"

[workspace]
members = ["crates/*"]

[dependencies]
printer = { path = "../printer" }
serde = "1.0"
"""
    res = RepoGraph.parse_cargo_manifest(valid_toml, "crates/core/Cargo.toml")
    assert res["name"] == "ripgrep_core"
    assert res["workspace_members"] == ["crates/*"]
    assert res["path_dependencies"].get("printer") == "../printer"

    # Malformed syntax
    malformed_toml = "THIS IS NOT VALID TOML [[[[ == ???"
    res_malformed = RepoGraph.parse_cargo_manifest(malformed_toml, "Cargo.toml")
    assert res_malformed["name"] == ""
    assert res_malformed["workspace_members"] == []

    # Empty content
    res_empty = RepoGraph.parse_cargo_manifest("", "Cargo.toml")
    assert res_empty["name"] == ""


def test_go_mod_parsing_valid_and_malformed():
    valid_go_mod = """
module github.com/caddyserver/caddy/v2

go 1.22
"""
    assert RepoGraph.parse_go_mod(valid_go_mod) == "github.com/caddyserver/caddy/v2"

    malformed_go_mod = "package main // no module directive"
    assert RepoGraph.parse_go_mod(malformed_go_mod) == ""


def test_package_json_parsing_valid_and_malformed():
    valid_pkg = """
{
  "name": "@vitejs/plugin-vue",
  "workspaces": ["packages/*"],
  "dependencies": {
    "vue": "^3.4.0",
    "vite": "workspace:*"
  }
}
"""
    res = RepoGraph.parse_package_json(valid_pkg)
    assert res["name"] == "@vitejs/plugin-vue"
    assert res["workspaces"] == ["packages/*"]
    assert "vite" in res["dependencies"]

    # Malformed JSON
    res_bad = RepoGraph.parse_package_json("{ broken json ...")
    assert res_bad["name"] == ""
    assert res_bad["dependencies"] == []


def test_rust_mod_declaration_and_resolution():
    content_main = "mod parser;\nmod ast;\nfn main() {}"
    syms, imps = RepoGraph.extract_polyglot_symbols(content_main, "src/main.rs")
    assert "main" in syms
    assert "mod:parser" in imps
    assert "mod:ast" in imps

    docs = [
        FileDoc(path="src/main.rs", content=content_main, symbols=syms, imports=imps),
        FileDoc(path="src/parser.rs", content="pub fn parse() {}", symbols=["parse"], imports=[]),
        FileDoc(path="src/ast/mod.rs", content="pub struct AstNode {}", symbols=["AstNode"], imports=[]),
    ]
    graph = RepoGraph().fit(docs)
    assert graph.graph.has_edge("src/main.rs", "src/parser.rs")
    assert graph.graph.has_edge("src/main.rs", "src/ast/mod.rs")


def test_cross_language_symbol_resolution():
    # Go package and functions
    go_content = "package router\nfunc RouteRequest() {}\ntype Engine struct {}"
    g_syms, g_imps = RepoGraph.extract_polyglot_symbols(go_content, "pkg/router/router.go")
    assert "RouteRequest" in g_syms
    assert "Engine" in g_syms
    assert "pkg:router" in g_syms

    # TS named imports
    ts_content = "import { RouteRequest } from './router';\nexport function handle() {}"
    ts_syms, ts_imps = RepoGraph.extract_polyglot_symbols(ts_content, "pkg/router/handler.ts")
    assert "handle" in ts_syms
    assert "./router" in ts_imps
    assert "RouteRequest" in ts_imps

    docs = [
        FileDoc(path="pkg/router/router.go", content=go_content, symbols=g_syms, imports=g_imps),
        FileDoc(path="pkg/router/handler.ts", content=ts_content, symbols=ts_syms, imports=ts_imps),
    ]
    graph = RepoGraph().fit(docs)
    # RouteRequest should resolve symbol-to-paths
    assert graph.graph.has_edge("pkg/router/handler.ts", "pkg/router/router.go")


def test_graph_edge_deduplication_and_disconnected_components():
    docs = [
        FileDoc(path="a.py", content="import b\nimport b\n", imports=["b", "b"]),
        FileDoc(path="b.py", content="x = 1\n", symbols=["x"]),
        FileDoc(path="isolated.py", content="y = 2\n", symbols=["y"]),
    ]
    graph = RepoGraph().fit(docs)
    # Only 1 directed edge from a.py -> b.py
    assert graph.graph.number_of_edges() == 1
    assert graph.graph.has_edge("a.py", "b.py")
    # isolated.py has degree 0
    assert graph.graph.degree("isolated.py") == 0
    # PageRank scores still compute for all nodes
    assert len(graph.pagerank_scores) == 3
    assert all(np.isfinite(graph.pagerank_scores))


