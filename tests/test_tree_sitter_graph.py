"""
Graph correctness with Tree-sitter extraction (optional `treesitter` extra).

Import-bound calls are resolved through their import only: a verified edge (1.0) requires exactly one
resolved file that defines the called name. External or unresolvable imports produce no edge. All other
calls go through the unchanged resolver (intra-file, unique global, directory-local, structural method),
so Tree-sitter parsing never raises a confidence by itself.
"""

import pytest

from tree_sitter_support import load_docs, require_tree_sitter

require_tree_sitter()

from reponeedle.core import tree_sitter_extraction as tse  # noqa: E402
from reponeedle.core.function_graph import FunctionGraphEngine  # noqa: E402
from reponeedle.engine import RepoNeedleEngine  # noqa: E402
from reponeedle.models import AblationConfig, FileDoc  # noqa: E402

V, U = "verified_call", "unique_global_call"

EXPECTED_EDGES = {
    "typescript": {
        ("src/components/CartView.tsx", "CartView", "src/models/cart.ts", "createCart", V, 1.0),
        ("src/components/CartView.tsx", "CartView", "src/util/format.ts", "label", V, 1.0),
        ("src/components/CartView.tsx", "CartView", "src/models/cart.ts", "describe", U, 0.9),
        ("src/components/CartView.tsx", "Größe", "src/util/format.ts", "label", V, 1.0),
        ("src/models/cart.ts", "total", "src/util/format.ts", "round", V, 1.0),          # `round as roundValue`
        ("src/models/cart.ts", "describe", "src/util/format.ts", "formatPrice", V, 1.0),  # `* as fmt`
        ("tests/cart.test.ts", None, "src/models/cart.ts", "createCart", V, 1.0),
        ("tests/cart.test.ts", None, "src/models/item.ts", "makeItem", V, 1.0),
        ("tests/cart.test.ts", None, "src/models/cart.ts", "add", U, 0.9),
        ("tests/cart.test.ts", None, "src/models/cart.ts", "total", U, 0.9),
    },
    "go": {
        ("cart/cart.go", "Total", "pricing/pricing.go", "ApplyDiscount", V, 1.0),
        ("cart/cart.go", "Total", "pricing/tax.go", "AddTax", V, 1.0),                   # alias `pr`
        ("cart/cart_test.go", "TestTotal", "cart/cart.go", "New", U, 0.9),
        ("cart/cart_test.go", "TestTotal", "cart/cart.go", "Total", U, 0.9),
        ("pricing/tax.go", "AddTax", "pricing/pricing.go", "round2", U, 0.9),           # same package
    },
    "rust": {
        ("src/cart/mod.rs", "total", "src/pricing.rs", "new", V, 1.0),                  # Rule::new via `use`
        ("src/cart/mod.rs", "total", "src/pricing.rs", "apply_discount", V, 1.0),       # use + crate:: path
        ("src/cart/mod.rs", "total", "src/util.rs", "round2", V, 1.0),                   # `use crate::util`
        ("src/cart/mod.rs", "total", "src/pricing.rs", "apply", U, 0.9),
        ("tests/cart_tests.rs", "empty_cart_total_is_zero", "src/cart/mod.rs", "new", V, 1.0),  # `use shop::...`
    },
    "java": {
        ("src/main/java/com/shop/cart/Cart.java", "total", "src/main/java/com/shop/pricing/PriceCalculator.java", "PriceCalculator", V, 1.0),
        ("src/main/java/com/shop/cart/Cart.java", "total", "src/main/java/com/shop/pricing/PriceCalculator.java", "applyDiscount", V, 1.0),
        ("src/main/java/com/shop/cart/Cart.java", "total", "src/main/java/com/shop/pricing/PriceCalculator.java", "withTax", U, 0.9),
        ("src/test/java/com/shop/cart/CartTest.java", "totals", "src/main/java/com/shop/cart/Cart.java", "Cart", U, 0.9),
        ("src/test/java/com/shop/cart/CartTest.java", "totals", "src/main/java/com/shop/cart/Cart.java", "total", U, 0.9),
        ("src/test/java/com/shop/cart/CartTest.java", "totals", "src/main/java/com/shop/pricing/PriceCalculator.java", "applyDiscount", V, 1.0),
    },
    "cpp": {
        ("src/cart.cpp", "total", "src/pricing.cpp", "Rule", U, 0.9),
        ("src/cart.cpp", "total", "src/pricing.cpp", "apply", U, 0.9),
        ("src/cart.cpp", "total", "src/pricing.cpp", "apply_discount", U, 0.9),
        ("src/pricing.cpp", "apply_discount", "include/shop/pricing.h", "round2", U, 0.9),
        ("tests/cart_test.cpp", "main", "src/cart.cpp", "total", U, 0.9),
    },
}


def _ts_graph(docs):
    return FunctionGraphEngine(structural_parser="tree_sitter").build_graph(docs)


def _edges(fg):
    return [(e.source_path, e.source_func, e.target_path, e.target_func, e.edge_type, e.confidence) for e in fg.edges]


@pytest.mark.parametrize("corpus", sorted(EXPECTED_EDGES))
def test_fixture_edges_are_exact(corpus):
    fg = _ts_graph(load_docs(corpus))
    assert set(_edges(fg)) == EXPECTED_EDGES[corpus]


@pytest.mark.parametrize("corpus", sorted(EXPECTED_EDGES))
def test_no_duplicate_edges(corpus):
    edges = _edges(_ts_graph(load_docs(corpus)))
    assert len(edges) == len(set(edges))


@pytest.mark.parametrize("corpus", sorted(EXPECTED_EDGES))
def test_graph_is_deterministic(corpus):
    docs = load_docs(corpus)
    assert _edges(_ts_graph(docs)) == _edges(_ts_graph(docs)) == _edges(_ts_graph(list(docs)))


@pytest.mark.parametrize("corpus", sorted(EXPECTED_EDGES))
def test_all_handled_files_parsed_and_diagnosed(corpus):
    docs = load_docs(corpus)
    diag = _ts_graph(docs).diagnostics["structural_parser"]
    handled = sorted(d.path for d in docs if tse.detect_language(d.path))
    assert diag["runtime_available"] is True
    assert diag["files"]["tree_sitter"] == handled
    assert diag["files"]["regex_fallback"] == {}
    assert [p for p in diag["files"]["tree_sitter_with_syntax_errors"]] == [p for p in handled if "broken" in p.lower()]
    for entry in diag["languages"].values():
        assert entry["parser_available"] is True and entry["regex_fallback_files"] == 0


def test_external_imports_never_produce_edges():
    # fmt.Sprintf / testing / org.junit / EventEmitter are external even if a repo symbol shares the name.
    docs = load_docs("go") + [FileDoc(path="tools/fmtshim/shim.go", content="package fmtshim\nfunc Sprintf() {}\n")]
    fg = _ts_graph(docs)
    assert not any(e.target_func == "Sprintf" for e in fg.edges)
    assert fg.diagnostics["structural_parser"]["calls"]["import_bound_external"] >= 1


def test_import_bound_call_to_a_name_the_target_does_not_define_gets_no_edge():
    docs = [
        FileDoc(path="src/a.ts", content='import { missing } from "./b";\nexport function run() { missing(); }\n'),
        FileDoc(path="src/b.ts", content="export function present() {}\n"),
        FileDoc(path="src/c.ts", content="export function missing() {}\n"),  # same name elsewhere: not used
    ]
    fg = _ts_graph(docs)
    assert fg.edges == []
    assert fg.diagnostics["structural_parser"]["calls"]["import_bound_not_defined"] == 1


def test_unresolvable_relative_import_gets_no_edge():
    docs = [
        FileDoc(path="src/a.ts", content='import { helper } from "./does-not-exist";\nexport function run() { helper(); }\n'),
        FileDoc(path="src/helper.ts", content="export function helper() {}\n"),
    ]
    fg = _ts_graph(docs)
    assert fg.edges == []
    assert fg.diagnostics["structural_parser"]["calls"]["import_bound_unresolved"] == 1


def test_duplicate_function_names_across_files_are_not_resolved_by_name():
    docs = [
        FileDoc(path="a/x.go", content="package a\nfunc Shared() {}\n"),
        FileDoc(path="b/y.go", content="package b\nfunc Shared() {}\n"),
        FileDoc(path="c/z.go", content="package c\nfunc Use() { Shared() }\n"),
    ]
    assert _ts_graph(docs).edges == []


def test_ambiguous_simple_names_are_disambiguated_only_by_imports():
    a = "package com.a;\npublic class Util { public static void go() {} }\n"
    b = "package com.b;\npublic class Util { public static void go() {} }\n"
    imported = FileDoc(path="src/com/c/Main.java", content=(
        "package com.c;\nimport com.b.Util;\nclass Main { void m() { Util.go(); } }\n"))
    unimported = FileDoc(path="src/com/c/Other.java", content=(
        "package com.c;\nclass Other { void m() { Util.go(); } }\n"))
    docs = [FileDoc(path="src/com/a/Util.java", content=a), FileDoc(path="src/com/b/Util.java", content=b),
            imported, unimported]
    edges = {(e.source_path, e.target_path, e.edge_type) for e in _ts_graph(docs).edges}
    assert edges == {("src/com/c/Main.java", "src/com/b/Util.java", "verified_call")}


def test_deeper_member_chains_on_imports_are_not_verified():
    docs = [
        FileDoc(path="src/a.ts", content='import * as lib from "./lib";\nexport function run() { lib.sub.go(); }\n'),
        FileDoc(path="src/lib.ts", content="export function go() {}\nexport const sub = { go };\n"),
    ]
    fg = _ts_graph(docs)
    assert fg.edges == []
    assert fg.diagnostics["structural_parser"]["calls"]["import_bound_unverifiable"] == 1


def test_local_definition_shadows_an_import():
    docs = [
        FileDoc(path="src/a.ts", content=(
            'import { helper } from "./b";\nfunction helper() {}\nexport function run() { helper(); }\n')),
        FileDoc(path="src/b.ts", content="export function helper() {}\n"),
    ]
    assert _ts_graph(docs).edges == []  # intra-file call, as with the existing resolver


def test_unqualified_calls_do_not_match_other_files_methods():
    # `describe()` in a test is the test framework, not Cart.describe (a method in another file).
    docs = load_docs("typescript")
    assert not any(e.source_path == "tests/cart.test.ts" and e.target_func == "describe"
                   for e in _ts_graph(docs).edges)


def test_unbound_calls_keep_the_existing_confidence():
    # Same call, same resolver step, same confidence in both modes (regex mode only sees the free functions).
    docs = load_docs("go")
    regex = {(e.source_path, e.target_path, e.target_func): (e.edge_type, e.confidence)
             for e in FunctionGraphEngine().build_graph(docs).edges}
    ts = {(e.source_path, e.target_path, e.target_func): (e.edge_type, e.confidence) for e in _ts_graph(docs).edges}
    shared = set(regex) & set(ts)
    assert ("cart/cart_test.go", "cart/cart.go", "New") in shared
    for key in shared:
        if ts[key][0] != "verified_call":
            assert ts[key] == regex[key]


def test_verified_edges_require_an_import_binding():
    for corpus in EXPECTED_EDGES:
        fg = _ts_graph(load_docs(corpus))
        verified = [e for e in fg.edges if e.edge_type == "verified_call" and e.confidence == 1.0]
        resolved = fg.diagnostics["structural_parser"]["calls"]["import_bound_resolved"]
        # Every 1.0 edge comes from a resolved import binding (deduplicated edges <= resolved calls).
        assert len(verified) <= resolved, corpus


def test_test_files_link_to_the_code_they_exercise():
    expected = {
        "typescript": ("tests/cart.test.ts", "src/models/cart.ts"),
        "go": ("cart/cart_test.go", "cart/cart.go"),
        "rust": ("tests/cart_tests.rs", "src/cart/mod.rs"),
        "java": ("src/test/java/com/shop/cart/CartTest.java", "src/main/java/com/shop/cart/Cart.java"),
        "cpp": ("tests/cart_test.cpp", "src/cart.cpp"),
    }
    for corpus, (test_file, code_file) in expected.items():
        fg = _ts_graph(load_docs(corpus))
        assert code_file in fg.callees_map[test_file], corpus
        assert test_file in fg.callers_map[code_file], corpus


def test_function_records_carry_repository_relative_paths():
    docs = load_docs("rust")
    fg = _ts_graph(docs)
    paths = {d.path for d in docs}
    assert {f.filepath for f in fg.functions} <= paths
    assert {c.caller_path for c in fg.call_sites} <= paths


def test_one_missing_grammar_falls_back_for_that_language_only(monkeypatch):
    real_import = tse._import_module

    def fake_import(name):
        if name == "tree_sitter_go":
            raise ModuleNotFoundError("No module named 'tree_sitter_go'")
        return real_import(name)

    tse.reset_parser_cache()
    monkeypatch.setattr(tse, "_import_module", fake_import)
    try:
        docs = load_docs("go") + load_docs("rust")
        fg = _ts_graph(docs)
        diag = fg.diagnostics["structural_parser"]
        go_files = sorted(d.path for d in docs if d.path.endswith(".go"))
        assert sorted(diag["files"]["regex_fallback"]) == go_files
        assert all("tree-sitter-go" in r for r in diag["files"]["regex_fallback"].values())
        assert diag["languages"]["go"]["parser_available"] is False
        assert diag["languages"]["rust"]["parser_available"] is True
        assert sorted(d.path for d in docs if d.path.endswith(".rs")) == diag["files"]["tree_sitter"]
    finally:
        tse.reset_parser_cache()


def test_engine_opt_in_builds_the_tree_sitter_graph_and_retrieves():
    docs = load_docs("java")
    engine = RepoNeedleEngine(docs=docs, ablation_config=AblationConfig(structural_parser="tree_sitter"))
    assert engine.function_graph.structural_parser == "tree_sitter"
    assert engine.function_graph.diagnostics["structural_parser"]["files"]["tree_sitter"]
    result = engine.retrieve("cart total with discount", budget_tokens=3000, ranker="arm101")
    assert result.selected_files
    # Legacy ranking does not use the function graph: identical with or without the opt-in.
    legacy_ts = engine.retrieve("cart total with discount", budget_tokens=3000)
    legacy_default = RepoNeedleEngine(docs=docs).retrieve("cart total with discount", budget_tokens=3000)
    assert [f.path for f in legacy_ts.selected_files] == [f.path for f in legacy_default.selected_files]


# --- documented import resolution (docs/TREE_SITTER.md §4) ------------------------

def _edge_set(docs):
    return {(e.source_path, e.target_path, e.target_func, e.edge_type) for e in _ts_graph(docs).edges}


def test_typescript_resolution_variants():
    docs = [
        FileDoc(path="src/main.ts", content=(
            'import { a } from "./lib";\nimport { b } from "./types";\nimport { c } from "./mod.js";\n'
            'import Def from "./def";\nexport function run() { a(); b(); c(); Def(); }\n')),
        FileDoc(path="src/lib/index.ts", content="export function a() {}\n"),
        FileDoc(path="src/types.d.ts", content="export function b(): void;\nexport function b() {}\n"),
        FileDoc(path="src/mod.ts", content="export function c() {}\n"),
        FileDoc(path="src/def.ts", content="export default function () {}\n"),
    ]
    assert _edge_set(docs) == {
        ("src/main.ts", "src/lib/index.ts", "a", V),   # directory index
        ("src/main.ts", "src/types.d.ts", "b", V),     # .d.ts
        ("src/main.ts", "src/mod.ts", "c", V),         # ".js" specifier -> .ts source
        ("src/main.ts", "src/def.ts", "Def", V),       # default import -> file
    }


def test_go_resolution_without_go_mod_uses_a_unique_directory_suffix():
    docs = [
        FileDoc(path="internal/store/store.go", content="package store\nfunc Open() {}\n"),
        FileDoc(path="cmd/app/main.go", content='package main\nimport "example.com/x/internal/store"\nfunc main() { store.Open() }\n'),
    ]
    assert _edge_set(docs) == {("cmd/app/main.go", "internal/store/store.go", "Open", V)}


def test_rust_self_and_super_paths():
    docs = [
        FileDoc(path="src/lib.rs", content="pub mod net;\n"),
        FileDoc(path="src/net/mod.rs", content="pub mod http;\npub mod tcp;\npub fn shared() {}\n"),
        FileDoc(path="src/net/tcp.rs", content="pub fn connect() {}\n"),
        FileDoc(path="src/net/http.rs", content=(
            "use super::tcp;\npub fn get() { tcp::connect(); super::shared(); self::local(); }\nfn local() {}\n")),
    ]
    assert _edge_set(docs) == {
        ("src/net/http.rs", "src/net/tcp.rs", "connect", V),
        ("src/net/http.rs", "src/net/mod.rs", "shared", V),
    }
