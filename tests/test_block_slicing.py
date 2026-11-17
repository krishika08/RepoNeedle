"""
AST block slicing: Python (standard-library ``ast``) and language-independent behaviour. No optional extras.

Fixtures: tests/fixtures/block_slicing/python/inventory.py (hand-written, realistic) and two real RepoNeedle
modules snapshotted from main at 0c0effe (packer_snapshot.py, function_graph_snapshot.py).
"""

import ast
import re
import textwrap

import pytest

from block_slicing_support import REAL_PYTHON, assert_exact, read
from reponeedle.core import block_slicing as bs
from reponeedle.core.packer import CodeSpanExtractor

INVENTORY = "python/inventory.py"
def blocks_by_name(structure):
    out = {}
    for b in structure.blocks:
        out.setdefault(b.name, []).append((b.kind, b.start_line, b.end_line))
    return out


@pytest.fixture(scope="module")
def inventory():
    content = read(INVENTORY)
    result = bs.analyze_structure(content, INVENTORY)
    assert result.fallback_reason is None
    return content, result.structure


# --- structure -------------------------------------------------------------------------------

def test_python_blocks_have_exact_source_boundaries(inventory):
    _, fs = inventory
    assert fs.language == "python" and fs.parser == bs.PYTHON_PARSER
    blocks = blocks_by_name(fs)
    assert blocks["audited"] == [("callable", 18, 23)]
    assert blocks["wrapper"] == [("callable", 20, 22)]                 # nested function
    assert blocks["total_units"] == [("callable", 42, 44)]             # starts at @property
    assert blocks["reserve"] == [("callable", 46, 54)]                 # starts at @audited
    assert blocks["restock_quantity"] == [("callable", 60, 64)]        # starts at @staticmethod
    assert blocks["plan_restock"] == [("callable", 66, 75)]
    assert blocks["below_threshold"] == [("callable", 68, 69)]         # nested inside a method
    assert blocks["sync_levels"] == [("callable", 78, 83)]             # async def
    assert blocks["DEFAULT_RESTOCK_THRESHOLD"] == [("declaration", 15, 15)]
    assert ("class", "Inventory", 34, 35) in [(s.kind, s.name, s.start_line, s.header_end_line) for s in fs.scopes]


def test_async_functions_methods_and_nesting_are_callables(inventory):
    _, fs = inventory
    by_name = {b.name: b for b in fs.blocks if b.kind == "callable"}
    nested = by_name["below_threshold"]
    assert [fs.scopes[i].name for i in nested.scope_chain] == ["Inventory", "plan_restock"]
    assert [fs.scopes[i].name for i in by_name["reserve"].scope_chain] == ["Inventory"]
    assert by_name["sync_levels"].scope_chain == ()


def test_every_python_block_is_complete_syntax():
    for rel in (INVENTORY,) + REAL_PYTHON:
        content = read(rel)
        lines = bs.split_lines(content)
        fs = bs.analyze_structure(content, rel).structure
        assert fs is not None and len(fs.blocks) > 5
        for b in fs.blocks:
            source = textwrap.dedent("\n".join(lines[b.start_line - 1:b.end_line]))
            ast.parse(source)                    # raises if a block were cut through its syntax


# --- selection and rendering -------------------------------------------------------------------

def test_match_inside_a_body_selects_the_enclosing_function(inventory):
    content, fs = inventory
    s = bs.slice_blocks(content, INVENTORY, {"ceil"})            # only in restock_quantity's body
    assert s.selected == (("callable", "restock_quantity", 60, 64),)
    assert_exact(s.text, content)
    assert "import math" in s.text and "@staticmethod" in s.text
    assert "def plan_restock" not in s.text


def test_nested_function_does_not_return_the_enclosing_class_or_function(inventory):
    content, _ = inventory
    s = bs.slice_blocks(content, INVENTORY, {"below_threshold"})
    assert s.selected == (("callable", "below_threshold", 68, 69),)
    assert_exact(s.text, content)
    assert "class Inventory:" in s.text and "@dataclass" in s.text           # class context
    assert "    def plan_restock(self) -> Dict[str, int]:" in s.text          # enclosing function header
    assert "plan = {}" not in s.text and "def reserve" not in s.text         # rest elided


def test_method_keeps_decorators_and_class_context(inventory):
    content, _ = inventory
    s = bs.slice_blocks(content, INVENTORY, {"reservation"})
    names = [sel[1] for sel in s.selected]
    assert "reserve" in names and "release" in names
    assert "    @audited" in s.text and "class Inventory:" in s.text
    assert_exact(s.text, content)


def test_imports_are_kept_only_when_used_by_selected_blocks(inventory):
    content, _ = inventory
    s = bs.slice_blocks(content, INVENTORY, {"apply_discount"})
    assert [sel[1] for sel in s.selected] == ["discounted_value"]
    assert "from shop.pricing import apply_discount" in s.text
    assert "from __future__ import annotations" in s.text                    # always kept
    assert "import asyncio" not in s.text and "from shop.storage import StockStore" not in s.text


def test_multiple_blocks_are_rendered_in_source_order_with_markers(inventory):
    content, _ = inventory
    s = bs.slice_blocks(content, INVENTORY, {"restock", "threshold"})
    starts = [sel[2] for sel in s.selected]
    assert starts == sorted(starts) and len(starts) >= 2
    assert re.search(r"# \.\.\. \[lines \d+-\d+ elided\] \.\.\.", s.text)
    assert_exact(s.text, content)


def test_ranking_is_deterministic_and_documented():
    filler = "\n".join(f"x{i} = {i}" for i in range(50))
    content = textwrap.dedent('''\
        def one_term():
            return alpha

        def two_terms():
            return alpha + beta

        def alpha_named():
            return 1

        def many_hits():
            alpha
            alpha
            return alpha
        ''') + filler + "\n"
    pick = lambda terms, n=1: [x[1] for x in bs.slice_blocks(content, "m.py", terms, max_blocks=n).selected]
    assert pick({"alpha", "beta"}) == ["two_terms"]                   # 1. distinct terms
    assert pick({"alpha"}) == ["alpha_named"]                         # 2. name match
    assert pick({"alpha"}, 2) == ["alpha_named", "many_hits"]         # 3. matching lines (rendered in source order)
    tie = "def a():\n    return term\n\ndef b():\n    return term\n" + filler + "\n"
    assert [x[1] for x in bs.slice_blocks(tie, "m.py", {"term"}, max_blocks=1).selected] == ["a"]   # 4. source order
    runs = {bs.slice_blocks(content, "m.py", terms).text for terms in ({"alpha", "beta"}, ["beta", "alpha"],
                                                                       ("alpha", "beta"))}
    assert len(runs) == 1                                             # independent of term order/container


def test_oversized_blocks_are_never_cut():
    big = "def huge():\n" + "".join(f"    step_{i} = target + {i}\n" for i in range(200)) + "    return 0\n"
    small = "def small():\n    return target\n"
    content = big + "\n" + small + "".join(f"\nZ{i} = {i}" for i in range(10)) + "\n"
    s = bs.slice_blocks(content, "m.py", {"target"})
    assert s.selected == (("callable", "small", 204, 205),)           # huge = 1-202, blank line 203
    assert s.header_only == (("callable", "huge", 1, 202),)          # signature only, body elided
    assert "def huge():" in s.text and "step_150" not in s.text
    assert_exact(s.text, content)
    only_big = bs.slice_blocks(big + "".join(f"\nZ{i} = {i}" for i in range(10)) + "\n", "m.py", {"target"})
    assert only_big.text is None and only_big.fallback_reason == "oversized_block"


def test_line_budget_limits_selection():
    content = "".join(f"def f{i}():\n" + "    term\n" * 30 + "\n" for i in range(8))
    s = bs.slice_blocks(content, "m.py", {"term"}, max_total_lines=100)
    assert len(s.selected) == 3                                       # 3 x 31 lines <= 100 < 4 x 31
    assert len(bs.slice_blocks(content, "m.py", {"term"}).selected) == 5   # default max_blocks


# --- line model ----------------------------------------------------------------------------------

@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_multibyte_text_and_line_endings_keep_exact_boundaries(inventory, newline):
    content = read(INVENTORY).replace("\n", newline)
    s = bs.slice_blocks(content, INVENTORY, {"release"})
    assert s.selected == (("callable", "release", 56, 58),)          # line 33 holds multibyte characters
    assert_exact(s.text, content)
    assert "Größe" not in s.text


def test_split_lines_matches_python_line_numbers():
    content = "a = 1\r\nb = 2\rc = 3\nd = ' \x0c'\n"
    tree = ast.parse(content)
    assert [n.lineno for n in tree.body] == [1, 2, 3, 4]
    assert bs.split_lines(content)[3] == "d = ' \x0c'"


# --- fallbacks -----------------------------------------------------------------------------------

@pytest.mark.parametrize("path,reason", [
    ("broken.py", "syntax_error"),
    ("app.js", "unsupported_language"),
    ("native.c", "unsupported_language"),
    ("notes.txt", "unsupported_language"),
])
def test_fallback_reasons(path, reason):
    content = "def broken(:\n    pass\n" if path.endswith(".py") else "function x() { return 1; }\n"
    assert bs.slice_blocks(content, path, {"x"}).fallback_reason == reason


def test_no_match_and_no_terms_fall_back(inventory):
    content, _ = inventory
    assert bs.slice_blocks(content, INVENTORY, {"zzzz_absent"}).fallback_reason == "no_block_match"
    assert bs.slice_blocks(content, INVENTORY, set()).fallback_reason == "no_query_terms"


@pytest.mark.parametrize("content", ["", "   \n\t\n"])
def test_empty_files(content):
    assert CodeSpanExtractor().extract_block_span(content, "e.py", {"x"}) == ("", 0)


def test_short_files_are_returned_whole_like_legacy():
    content = read(INVENTORY).split("\n")[:40]
    content = "\n".join(content) + "\n"
    ex = CodeSpanExtractor()
    assert ex.extract_block_span(content, "short.py", {"reserve"}) == ex.extract_focus_span(content, "short.py",
                                                                                              {"reserve"})
    assert ex.slice_blocks(content, "short.py", {"reserve"}).fallback_reason == "short_file"


@pytest.mark.parametrize("path,content", [
    ("broken.py", "import os\n" + "def broken(:\n    pass\n" * 30),
    ("app.js", "import x from 'y';\n" + "function reserve() {\n  return 1;\n}\n" * 20),
    ("native.c", "#include <stdio.h>\n" + "int reserve(void) {\n  return 1;\n}\n" * 20),
])
def test_fallback_output_is_exactly_the_legacy_focus_span(path, content):
    ex = CodeSpanExtractor()
    assert ex.extract_block_span(content, path, {"reserve"}) == CodeSpanExtractor().extract_focus_span(
        content, path, {"reserve"})


def test_real_source_slices_are_exact():
    for rel in REAL_PYTHON:
        content = read(rel)
        for terms in ({"skeleton"}, {"resolve", "import"}, {"cache"}, {"tokens", "budget"}, {"edge"}):
            s = bs.slice_blocks(content, rel, terms)
            if s.text is not None:
                assert_exact(s.text, content)
                assert len(s.selected) <= bs.DEFAULT_MAX_BLOCKS
                assert sum(e - st + 1 for _, _, st, e in s.selected) <= bs.DEFAULT_MAX_TOTAL_LINES
