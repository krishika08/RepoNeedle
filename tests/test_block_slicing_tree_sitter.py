"""
AST block slicing for TypeScript/TSX, Go, Rust, Java and C++ (optional ``treesitter`` extra).

Expected boundaries below were read from tests/fixtures/block_slicing/<language>/ by hand: every start line is the
first decorator / attribute / annotation / attached doc comment, every end line is the closing brace.
"""

import pytest

from block_slicing_support import LANGUAGE_FIXTURES, assert_exact, read
from tree_sitter_support import FIXTURES as TS_FIXTURES, require_tree_sitter

require_tree_sitter()

from reponeedle.core import block_slicing as bs  # noqa: E402
from reponeedle.core import tree_sitter_extraction as tse  # noqa: E402
from reponeedle.core.packer import CodeSpanExtractor  # noqa: E402

# language -> {block name: (kind, start, end)} for the blocks each test relies on.
EXPECTED = {
    "typescript": {
        "Audited": ("callable", 14, 16),
        "constructor": ("callable", 24, 26),
        "totalUnits": ("callable", 28, 32),            # getter
        "reserve": ("callable", 34, 45),               # starts at @Audited
        "release": ("callable", 47, 50),               # arrow-function class field
        "planRestock": ("callable", 52, 63),
        "restockQuantity": ("callable", 53, 55),       # nested function declaration
        "discountedValue": ("callable", 66, 72),       # exported const arrow function
        "syncLevels": ("callable", 74, 77),            # export async function
        "averageUnits": ("callable", 80, 82),          # inside a namespace
        "Reservation": ("declaration", 8, 12),         # interface
    },
    "tsx": {
        "statusLabel": ("callable", 12, 17),
        "InventoryTable": ("callable", 19, 48),        # attached comment with multibyte text
        "handleReserve": ("callable", 27, 30),         # nested arrow function
        "EmptyInventory": ("callable", 50, 52),        # export default function
        "Props": ("declaration", 5, 8),
    },
    "go": {
        "New": ("callable", 29, 32),
        "Reserve": ("callable", 34, 44),               # method with receiver, doc comment attached
        "PlanRestock": ("callable", 46, 63),           # func literal stays inside
        "formatLevel": ("callable", 65, 67),           # var bound to a func literal
        "DiscountedValue": ("callable", 69, 76),
        "Inventory": ("declaration", 22, 27),          # struct with two attached comment lines
    },
    "rust": {
        "new": ("callable", 28, 31),
        "reserve": ("callable", 33, 44),               # doc comment + #[must_use]
        "plan_restock": ("callable", 46, 55),
        "below_threshold": ("callable", 47, 49),       # nested fn
        "fmt": ("callable", 65, 67),                   # trait impl method
        "discounted_value": ("callable", 70, 76),
        "reserve_reduces_stock": ("callable", 82, 87),  # #[test] inside #[cfg(test)] mod
        "Inventory": ("declaration", 15, 21),          # comments + #[derive]
    },
    "java": {
        "reserve": ("callable", 36, 49),               # javadoc + @Transactional
        "planRestock": ("callable", 51, 59),
        "restockQuantity": ("callable", 61, 63),
        "discountedValue": ("callable", 65, 71),
        "DEFAULT_THRESHOLD": ("declaration", 17, 17),
    },
    "cpp": {
        "clamp_units": ("callable", 13, 19),           # template <typename T> included
        "total_units": ("callable", 26, 32),           # inline member function
        "reserve": ("callable", 41, 49),               # out-of-line definition with /// comment
        "plan_restock": ("callable", 51, 59),
        "inventory_restock_quantity": ("callable", 64, 66),   # inside extern "C"
    },
}


def structure(language):
    rel = LANGUAGE_FIXTURES[language]
    content = read(rel)
    result = bs.analyze_structure(content, rel)
    assert result.fallback_reason is None, result.fallback_reason
    return content, result.structure


@pytest.mark.parametrize("language", sorted(EXPECTED))
def test_block_boundaries(language):
    _, fs = structure(language)
    assert fs.language == language and fs.parser == bs.TREE_SITTER_PARSER
    found = {}
    for b in fs.blocks:
        found.setdefault(b.name, []).append((b.kind, b.start_line, b.end_line))
    for name, expected in EXPECTED[language].items():
        assert expected in found.get(name, []), f"{language} {name}: {found.get(name)}"


@pytest.mark.parametrize("language", sorted(EXPECTED))
def test_callable_blocks_end_at_their_closing_brace(language):
    content, fs = structure(language)
    lines = bs.split_lines(content)
    for b in fs.blocks:
        if b.kind == "callable" and b.close_line is not None:
            assert b.close_line == b.end_line or lines[b.end_line - 1].strip().endswith((";", ")"))
            assert lines[b.close_line - 1].strip().startswith("}"), (language, b)


@pytest.mark.parametrize("language", sorted(EXPECTED))
def test_crlf_keeps_the_same_boundaries(language):
    content, fs = structure(language)
    rel = LANGUAGE_FIXTURES[language]
    crlf = bs.analyze_structure(content.replace("\n", "\r\n"), rel).structure
    assert [(b.name, b.start_line, b.end_line) for b in crlf.blocks] == \
           [(b.name, b.start_line, b.end_line) for b in fs.blocks]


def render(language, terms):
    content, _ = structure(language)
    s = bs.slice_blocks(content, LANGUAGE_FIXTURES[language], terms)
    assert s.text is not None, s.fallback_reason
    assert_exact(s.text, content)
    return s


def test_typescript_method_keeps_decorator_imports_and_class_context():
    s = render("typescript", {"emit"})
    assert s.selected == (("callable", "reserve", 34, 45),)
    assert "  @Audited" in s.text and "export class Inventory extends EventEmitter {" in s.text
    assert 'import { EventEmitter } from "events";' in s.text
    assert "applyDiscount" not in s.text and "planRestock" not in s.text
    assert "\n}\n// ... [lines 65-83 elided] ..." in s.text             # class closing brace, then the rest


def test_typescript_nested_function_and_namespace():
    s = render("typescript", {"ceil"})
    assert s.selected == (("callable", "restockQuantity", 53, 55),)
    assert "  planRestock(): Map<string, number> {" in s.text and "const plan" not in s.text
    ns = render("typescript", {"averageunits"})
    assert "export namespace InventoryStats {" in ns.text


def test_tsx_component_and_nested_handler():
    # Lines 27 (handler) and 39 (JSX) match. The handler wins on its name; the component contains it, so it is
    # not selected again but its header is rendered as context.
    s = render("tsx", {"handlereserve"})
    assert s.selected == (("callable", "handleReserve", 27, 30),)
    assert "export function InventoryTable({ inventory, skus }: Props) {" in s.text
    s = render("tsx", {"setfilter(filter)"})
    assert s.selected == (("callable", "handleReserve", 27, 30),)
    assert "export function InventoryTable({ inventory, skus }: Props) {" in s.text


def test_go_keeps_package_and_only_relevant_grouped_imports():
    s = render("go", {"errors.new"})
    assert s.selected == (("callable", "Reserve", 34, 44),)
    assert s.text.startswith("package inventory")
    assert '\t"errors"' in s.text and '\t"fmt"' in s.text and "import (" in s.text
    assert '\t"sort"' not in s.text and '\t"math"' not in s.text
    assert s.text.count("\n)\n") == 1                                  # grouped import closed


def test_rust_impl_and_test_module_context():
    s = render("rust", {"below_threshold"})
    assert ("callable", "below_threshold", 47, 49) in s.selected
    assert "impl Inventory {" in s.text
    t = render("rust", {"reserve_reduces_stock"})
    assert "#[cfg(test)]" in t.text and "mod tests {" in t.text and "    #[test]" in t.text


def test_java_keeps_package_annotations_and_class_header():
    s = render("java", {"illegalstateexception"})
    assert s.selected == (("callable", "reserve", 36, 49),)
    assert s.text.startswith("package com.shop.inventory;")
    assert "@Service" in s.text and "public class Inventory {" in s.text and "    @Transactional" in s.text
    assert "planRestock" not in s.text


def test_cpp_namespace_class_and_template():
    s = render("cpp", {"to_string"})
    assert s.selected == (("callable", "reserve", 41, 49),)
    assert "namespace shop {" in s.text and "}  // namespace shop" in s.text
    assert '#include "shop/inventory.h"' in s.text                    # includes are always kept
    t = render("cpp", {"value > high"})
    assert t.selected == (("callable", "clamp_units", 13, 19),) and "template <typename T>" in t.text
    u = render("cpp", {"entry.second;"})
    assert u.selected == (("callable", "total_units", 26, 32),) and "class Inventory {" in u.text


@pytest.mark.parametrize("language", sorted(EXPECTED))
def test_multibyte_comment_before_a_block(language):
    content, fs = structure(language)
    lines = bs.split_lines(content)
    marker_line = next(i for i, line in enumerate(lines, 1) if "Größe" in line)
    after = [b for b in fs.blocks if b.start_line <= marker_line + 2 and b.end_line > marker_line]
    for b in fs.blocks:
        assert 1 <= b.start_line <= b.end_line <= len(lines)
    assert after or any(s.start_line > marker_line for s in fs.scopes)


@pytest.mark.parametrize("rel", ["typescript/src/broken.ts", "go/broken.go", "rust/src/broken.rs",
                                 "java/src/main/java/com/shop/Broken.java", "cpp/src/broken.cpp"])
def test_syntax_errors_fall_back_to_legacy(rel):
    content = (TS_FIXTURES / rel).read_text(encoding="utf-8") * 6       # > 45 lines, still broken
    assert bs.analyze_structure(content, rel).fallback_reason == "syntax_error"
    ex = CodeSpanExtractor()
    assert ex.extract_block_span(content, rel, {"ok"}) == CodeSpanExtractor().extract_focus_span(content, rel, {"ok"})


@pytest.fixture
def no_tree_sitter(monkeypatch):
    real_import = tse._import_module

    def fake_import(name):
        if name == "tree_sitter" or name.startswith("tree_sitter_"):
            raise ModuleNotFoundError(f"No module named '{name}'")
        return real_import(name)

    tse.reset_parser_cache()
    monkeypatch.setattr(tse, "_import_module", fake_import)
    yield
    tse.reset_parser_cache()


@pytest.mark.parametrize("language", sorted(EXPECTED))
def test_missing_parser_falls_back_to_legacy(no_tree_sitter, language):
    rel = LANGUAGE_FIXTURES[language]
    content = read(rel)
    assert bs.analyze_structure(content, rel).fallback_reason == "parser_unavailable"
    ex = CodeSpanExtractor()
    assert ex.extract_block_span(content, rel, {"reserve"}) == \
           CodeSpanExtractor().extract_focus_span(content, rel, {"reserve"})


def test_python_does_not_need_tree_sitter(no_tree_sitter):
    rel = LANGUAGE_FIXTURES["python"]
    assert bs.slice_blocks(read(rel), rel, {"reserve"}).text is not None


def test_parse_source_reuses_the_extractor_parser_cache():
    tree, src = tse.parse_source("function f() {}\n", "typescript")
    assert not tree.root_node.has_error and src == b"function f() {}\n"
    assert "typescript" in tse._PARSERS
