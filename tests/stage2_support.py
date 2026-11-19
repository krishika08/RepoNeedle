"""
Helpers for the V2 Stage 2 tests (not a test module): a seeded synthetic repository whose files exercise every
resolution branch of both graph resolvers, and the mutation catalogue of the Stage 2 brief (section 18).

Every incrementally maintained engine is compared with a completely fresh UNCACHED build over the same repository
state with the Stage 0 differential harness (tests/index_equivalence.py).
"""

import os
import random
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from cache_support import fresh, last, write
from index_equivalence import assert_equivalent, compare_index_state, load_queries

QUERIES = load_queries()[::25]          # 9 queries across the categories (full corpus runs in dedicated tests)


def synthetic_files(seed: int = 7) -> Dict[str, str]:
    """
    A small polyglot repository with: duplicate and unique function names across files, classes with methods
    (unique and shared method names), module-qualified and class-qualified calls, imports matching callees, test
    files naming their targets, duplicate module stems, a Go module with packages, Rust crates with a path
    dependency under crates/, JS packages under packages/ with package.json and entrypoints, relative TS imports.
    """
    rng = random.Random(seed)
    f: Dict[str, str] = {}
    shared = ["normalize", "load_config", "render_view"]
    for i in range(8):
        pkg = ("core", "util", "app", "core/sub")[i % 4]
        mod = f"{pkg}/mod{i}.py"
        imports = [f"from {('core', 'util', 'app', 'core.sub')[(i + 1) % 4]}.mod{(i + 1) % 8} import helper_{(i + 1) % 8}",
                   f"import util.mod{(i + 2) % 8}"]
        body = [f'"""Module {i}."""'] + imports + ["", ""]
        body += [f"def helper_{i}(value):", f"    return normalize(value) + {i}", "", ""]
        if i % 3 == 0:          # normalize (mod0), load_config (mod3), render_view (mod6)
            body += [f"def {shared[(i // 3) % 3]}(value):", "    return value", "", ""]
        body += [f"class Widget{i}:", f"    def method_{i}_unique(self):", f"        return helper_{i}(1)", "",
                 "    def checkout(self):", f"        return mod{(i + 2) % 8}.helper_{(i + 2) % 8}(2)", "", ""]
        body += [f"def caller_{i}(w):",
                 f"    helper_{(i + 1) % 8}(w)",
                 f"    w.method_{(i + 3) % 8}_unique()",
                 f"    Widget{(i + 1) % 8}.checkout(w)",
                 f"    load_config({rng.randint(0, 9)})",
                 "    return render_view(w)", ""]
        f[mod] = "\n".join(body) + "\n"
    # Step E (unique method name across classes): two classes of ONE file define the method, so the definitions are
    # not globally unique (step D fails) but exactly one file defines it.
    f["core/sub/mod7.py"] += ("\n\nclass TwinA:\n    def rebalance_ledger(self):\n        return 1\n\n\n"
                              "class TwinB:\n    def rebalance_ledger(self):\n        return 2\n")
    f["app/mod2.py"] += "\n\ndef use_twins(x):\n    return x.rebalance_ledger()\n"
    f["core/__init__.py"] = ""
    f["util/__init__.py"] = "from util.mod1 import helper_1\n"
    f["util/mod5.py"] += "\n\ndef normalize(value):\n    return str(value)\n"      # normalize: two definitions
    f["legacy/mod3.py"] = ('"""Duplicate module stem mod3."""\n\ndef helper_3(value):\n    return value\n\n\n'
                           "def legacy_call():\n    return helper_5(1)\n")       # unqualified: global uniqueness
    f["tests/test_mod1.py"] = ("from util.mod1 import Widget1\n\n\ndef test_widget():\n"
                               "    w = Widget1()\n    assert w.method_1_unique() is not None\n")
    f["tests/test_mod2.py"] = "import app.mod2\n\n\ndef test_helper():\n    assert app.mod2.helper_2(1)\n"
    f["svc/go.mod"] = "module example.com/svc\n\ngo 1.21\n"
    f["svc/main.go"] = ('package main\n\nimport "example.com/svc/stock"\n\nfunc main() {\n'
                        '\tstock.Reserve("a", 1)\n\tRun()\n}\n')
    f["svc/run.go"] = "package main\n\nfunc Run() {\n\tReserve2()\n}\n"
    f["svc/stock/stock.go"] = ("package stock\n\ntype Store struct{}\n\nfunc (s *Store) Reserve2() int { return 1 }\n\n"
                               "func Reserve(sku string, n int) bool {\n\treturn n > 0\n}\n")
    f["svc/stock/stock_test.go"] = "package stock\n\nfunc TestReserve() {\n\ts := &Store{}\n\ts.Reserve2()\n}\n"
    f["crates/pricing/Cargo.toml"] = ('[package]\nname = "pricing"\nversion = "0.1.0"\n\n[dependencies]\n'
                                      'rules = { path = "../rules" }\n')
    f["crates/pricing/src/lib.rs"] = "mod engine;\nuse rules::apply;\n\npub fn price(x: u32) -> u32 {\n    rules::apply(x)\n}\n"
    f["crates/pricing/src/engine.rs"] = "pub fn run() -> u32 {\n    1\n}\n"
    f["crates/rules/Cargo.toml"] = '[package]\nname = "rules"\nversion = "0.1.0"\n'
    f["crates/rules/src/lib.rs"] = "pub fn apply(x: u32) -> u32 {\n    x + 1\n}\n"
    f["packages/ui/package.json"] = '{"name": "ui", "dependencies": {"core-lib": "1.0.0"}}\n'
    f["packages/ui/src/index.ts"] = "import { fmt } from './format';\nimport core from 'core-lib';\n\nexport function show(x: number) {\n  return fmt(x);\n}\n"
    f["packages/ui/src/format.ts"] = "export function fmt(x: number): string {\n  return String(x);\n}\n"
    f["packages/core-lib/package.json"] = '{"name": "core-lib"}\n'
    f["packages/core-lib/src/index.ts"] = "export function coreFn() {\n  return 1;\n}\n"
    f["web/app.test.ts"] = "import { show } from '../packages/ui/src/index';\n\ndescribe('x', () => { show(1); });\n"
    f["README.md"] = "# Synthetic\n\nA repository for dependency-invalidation tests.\n"
    return f


def write_tree(root: Path, files: Dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        write(root, rel, text)
    return root


def remove(repo: Path, rel: str) -> None:
    os.remove(repo.joinpath(*rel.split("/")))


def rename(repo: Path, old: str, new: str) -> None:
    target = repo.joinpath(*new.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(repo.joinpath(*old.split("/")), target)


def read(repo: Path, rel: str) -> str:
    with open(repo.joinpath(*rel.split("/")), encoding="utf-8", newline="") as fh:
        return fh.read()


def append(repo: Path, rel: str, text: str) -> None:
    write(repo, rel, read(repo, rel) + text)


def replace_in(repo: Path, rel: str, old: str, new: str) -> None:
    text = read(repo, rel)
    assert old in text, (rel, old)
    write(repo, rel, text.replace(old, new, 1))


@contextmanager
def reversed_discovery():
    """Reverses os.walk's directory and file order (same files, different discovery order)."""
    import reponeedle.engine as engine_module

    real_walk = os.walk

    def walk(top, *args, **kwargs):
        for root, dirs, files in real_walk(top, *args, **kwargs):
            dirs.reverse()
            files.reverse()
            yield root, dirs, files

    engine_module.os.walk = walk
    try:
        yield
    finally:
        engine_module.os.walk = real_walk


# ------------------------------------------------------------------------------------------- mutation catalogue
# Each mutation edits the repository on disk; ``kw`` changes engine arguments (max_files, persist_exclude).

def m_body_only(repo):
    replace_in(repo, "core/mod0.py", "return normalize(value) + 0", "return normalize(value) + 100")


def m_rename_function(repo):
    replace_in(repo, "util/mod1.py", "def helper_1(", "def helper_1_renamed(")


def m_add_function(repo):
    append(repo, "app/mod2.py", "\n\ndef brand_new_function(x):\n    return helper_2(x)\n")


def m_delete_function(repo):
    replace_in(repo, "app/mod6.py", "def caller_6(w):", "def _gone(w):")


def m_second_definition(repo):
    append(repo, "core/sub/mod3.py", "\n\ndef helper_5(value):\n    return value\n")


def m_delete_one_of_two(repo):
    replace_in(repo, "core/mod0.py", "def normalize(value):", "def normalize_unused(value):")


def m_add_method(repo):
    replace_in(repo, "util/mod5.py", "    def checkout(self):", "    def method_0_unique(self):\n        return 0\n\n    def checkout(self):")


def m_remove_method(repo):
    replace_in(repo, "core/sub/mod7.py", "    def method_7_unique(self):", "    def method_7_gone(self):")


def m_change_import(repo):
    replace_in(repo, "app/mod2.py", "import util.mod4", "import core.mod0")


def m_move_module(repo):
    rename(repo, "app/mod6.py", "core/mod6.py")


def m_duplicate_stem(repo):
    write(repo, "other/mod5.py", "def helper_5(value):\n    return -value\n")


def m_winning_provider(repo):
    write(repo, "src/core/mod4.py", "def helper_4(value):\n    return 4\n")


def m_manifests(repo):
    remove(repo, "packages/ui/package.json")
    write(repo, "packages/extra/package.json", '{"name": "core-lib"}\n')


def m_go_package(repo):
    replace_in(repo, "svc/stock/stock.go", "package stock", "package inventory")


def m_rust_crate(repo):
    replace_in(repo, "crates/rules/Cargo.toml", 'name = "rules"', 'name = "rulebook"')
    replace_in(repo, "crates/pricing/Cargo.toml", 'rules = { path = "../rules" }', 'rulebook = { path = "../rules" }')


def m_test_targets(repo):
    remove(repo, "tests/test_mod2.py")
    write(repo, "tests/test_mod4.py", "from util.mod4 import Widget4\n\n\ndef test_w():\n    Widget4().checkout()\n")


def m_rename_file(repo):
    rename(repo, "util/mod5.py", "util/mod5_renamed.py")


def m_add_files_positions(repo):
    write(repo, "aaa_first.py", "def helper_0(value):\n    return 0\n")
    write(repo, "core/sub/zzz.py", "def unique_late():\n    return helper_7(1)\n")


def m_delete_files(repo):
    remove(repo, "core/mod4.py")
    remove(repo, "README.md")


def m_gitignore(repo):
    write(repo, ".gitignore", "legacy/\n*.md\n")


def m_callers_change_only(repo):
    replace_in(repo, "util/mod1.py", "    load_config(", "    helper_3(")


MUTATIONS: List[Tuple[str, Callable]] = [
    ("body_only", m_body_only), ("rename_function", m_rename_function), ("add_function", m_add_function),
    ("delete_function", m_delete_function), ("second_definition", m_second_definition),
    ("delete_one_of_two", m_delete_one_of_two), ("add_method", m_add_method), ("remove_method", m_remove_method),
    ("change_import", m_change_import), ("move_module", m_move_module), ("duplicate_stem", m_duplicate_stem),
    ("winning_provider", m_winning_provider), ("manifests", m_manifests), ("go_package", m_go_package),
    ("rust_crate", m_rust_crate), ("test_targets", m_test_targets), ("rename_file", m_rename_file),
    ("add_files_positions", m_add_files_positions), ("delete_files", m_delete_files), ("gitignore", m_gitignore),
    ("callers_change_only", m_callers_change_only),
]


def check(engine, repo: Path, label: str, queries=QUERIES, **kw) -> None:
    assert_equivalent(engine, fresh(repo, **kw), label=label, queries=queries, packing_queries=None)


def state_matches(engine, repo: Path, **kw) -> bool:
    return not any(compare_index_state(engine, fresh(repo, **kw)).values())


def counters(engine) -> dict:
    return last(engine)["work_counters"]


def no_index_misses(engine) -> None:
    c = counters(engine)
    for g in ("function_graph", "repo_graph"):
        if g in c and "context_mismatches_outside_dependency_index" in c[g]:
            assert c[g]["context_mismatches_outside_dependency_index"] == 0, (g, c[g])
