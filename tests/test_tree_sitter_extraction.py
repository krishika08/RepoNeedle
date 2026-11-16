"""
Tree-sitter extraction (optional `treesitter` extra): exact RepoNeedle records per fixture file, plus
targeted checks for comments, strings, Unicode, nesting, qualified calls, imports and syntax errors.

Skipped (visibly) when the optional packages are absent; the dedicated CI job installs them and fails
on any skip.
"""

import pytest

from tree_sitter_support import EXPECTED, LANGUAGES, fixture_files, require_tree_sitter

require_tree_sitter()

from reponeedle.core import tree_sitter_extraction as tse  # noqa: E402


def _extract(corpus, path):
    content = fixture_files(corpus)[path]
    language = tse.detect_language(path)
    ex = tse.extract(content, path, language, is_test="test" in path.lower())
    assert ex is not None
    return ex


def _records(ex):
    return {
        "functions": [(f.name, f.parent_class, f.is_method, f.start_line) for f in ex.functions],
        "calls": [(c.callee_name, c.qualifier_path, c.is_attribute, c.caller_func, c.start_line) for c in ex.calls],
        "imports": [(r.kind, r.spec, r.local_name, r.imported_name, r.line) for r in ex.import_records],
        "has_error": ex.has_error,
    }


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_fixture_file_extraction_is_exact(key):
    corpus, path = key.split("/", 1)
    assert _records(_extract(corpus, path)) == EXPECTED[key]


def test_every_target_language_is_covered_by_fixtures():
    covered = {tse.detect_language(k.split("/", 1)[1]) for k in EXPECTED}
    assert covered == {"typescript", "tsx", "go", "rust", "java", "cpp"}


def test_runtime_and_all_grammars_load():
    status = tse.tree_sitter_status()
    assert status["runtime"]["available"] is True
    for lang in ("typescript", "tsx", "go", "rust", "java", "cpp"):
        assert status["languages"][lang]["available"] is True, status["languages"][lang]


# --- comments and strings ----------------------------------------------------

@pytest.mark.parametrize("corpus,path,fake", [
    ("typescript", "src/util/format.ts", ["fakeCommentFn", "notCalled"]),
    ("go", "pricing/pricing.go", ["FakeFromComment", "NotReal", "notCalled", "call"]),
    ("rust", "src/pricing.rs", ["fake_from_comment", "not_real", "not_called", "call"]),
    ("java", "src/main/java/com/shop/pricing/PriceCalculator.java", ["fakeFromJavadoc", "Fake", "notCalled", "call"]),
    ("cpp", "src/pricing.cpp", ["fake_from_comment", "not_real", "not_called", "call"]),
])
def test_comments_and_strings_produce_no_records(corpus, path, fake):
    ex = _extract(corpus, path)
    names = {f.name for f in ex.functions} | {c.callee_name for c in ex.calls} | set(ex.symbols)
    assert not names & set(fake)


def test_typescript_string_mentioning_a_call_is_not_a_call():
    ex = _extract("typescript", "src/models/cart.ts")
    # "call formatPrice(1) inside a string" is text; the only formatPrice call is fmt.formatPrice(...) on line 25.
    assert [(c.callee_name, c.start_line) for c in ex.calls if c.callee_name == "formatPrice"] == [("formatPrice", 25)]


# --- Unicode -------------------------------------------------------------------

@pytest.mark.parametrize("corpus,path,name,line", [
    ("typescript", "src/components/CartView.tsx", "Größe", 9),
    ("go", "pricing/pricing.go", "Größe", 25),
    ("rust", "src/pricing.rs", "größe", 28),
    ("java", "src/main/java/com/shop/pricing/PriceCalculator.java", "größe", 21),
    ("cpp", "src/pricing.cpp", "größe", 21),
])
def test_unicode_identifiers_and_line_numbers(corpus, path, name, line):
    ex = _extract(corpus, path)
    assert (name, line) in [(f.name, f.start_line) for f in ex.functions]


def test_non_ascii_text_before_code_keeps_line_numbers():
    ex = tse.extract('const s = "😀 € ü";\n// ✓\nexport function after(): number { return g(); }\n', "a.ts", "typescript", False)
    assert [(f.name, f.start_line) for f in ex.functions] == [("after", 3)]
    assert [(c.callee_name, c.start_line) for c in ex.calls] == [("g", 3)]


# --- nesting and membership ------------------------------------------------------

def test_nested_functions_are_free_functions_attributed_to_their_scope():
    ts = _extract("typescript", "src/models/cart.ts")
    assert ("constructor", "Cart", True, 9) in [(f.name, f.parent_class, f.is_method, f.start_line) for f in ts.functions]
    rust = _extract("rust", "src/cart/mod.rs")
    by_name = {f.name: f for f in rust.functions}
    assert by_name["local_helper"].is_method is False and by_name["local_helper"].parent_class is None
    assert by_name["total"].parent_class == "Cart" and by_name["total"].is_method is True
    # A call to the nested helper is attributed to the enclosing method.
    assert ("local_helper", None, False, "total", 21) in _records(rust)["calls"]


def test_typescript_nested_function_declaration():
    ex = tse.extract("export function outer() {\n  function inner() { return 1; }\n  return inner();\n}\n",
                     "n.ts", "typescript", False)
    assert [(f.name, f.parent_class, f.is_method, f.start_line) for f in ex.functions] == [
        ("outer", None, False, 1), ("inner", None, False, 2)]
    assert [(c.callee_name, c.caller_func) for c in ex.calls] == [("inner", "outer")]


def test_go_closures_are_attributed_to_the_enclosing_function():
    ex = tse.extract("package p\nfunc Outer() {\n\tf := func() { helper() }\n\tf()\n}\n", "p.go", "go", False)
    assert [f.name for f in ex.functions] == ["Outer"]
    assert [(c.callee_name, c.caller_func, c.start_line) for c in ex.calls] == [("helper", "Outer", 3), ("f", "Outer", 4)]


def test_go_methods_record_receiver_type():
    ex = _extract("go", "cart/cart.go")
    methods = {(f.name, f.parent_class) for f in ex.functions if f.is_method}
    assert methods == {("Total", "Cart"), ("sum", "Cart"), ("String", "Cart")}


def test_rust_trait_methods_belong_to_the_trait():
    ex = tse.extract("trait Shape {\n    fn area(&self) -> f64 { 0.0 }\n}\nstruct Sq;\nimpl Shape for Sq {\n    fn area(&self) -> f64 { 1.0 }\n}\n",
                     "s.rs", "rust", False)
    assert [(f.name, f.parent_class, f.start_line) for f in ex.functions] == [("area", "Shape", 2), ("area", "Sq", 6)]


def test_java_nested_and_anonymous_classes():
    ex = _extract("java", "src/main/java/com/shop/cart/Cart.java")
    rows = [(f.name, f.parent_class) for f in ex.functions]
    assert ("price", "Line") in rows          # nested static class
    assert ("visit", "Visitor") in rows       # nested interface
    assert ("run", "Cart") in rows            # anonymous class method -> enclosing named class
    assert rows.count(("Cart", "Cart")) == 2  # overloaded constructors


def test_cpp_members_inside_and_outside_the_class():
    header = _extract("cpp", "include/shop/pricing.h")
    assert [(f.name, f.parent_class) for f in header.functions] == [("clamp", "Rule"), ("round2", None)]
    impl = _extract("cpp", "src/pricing.cpp")
    assert [(f.name, f.parent_class, f.is_method) for f in impl.functions] == [
        ("apply_discount", None, False), ("Rule", "Rule", True), ("apply", "Rule", True), ("größe", None, False)]


def test_cpp_namespace_qualified_definition_is_not_a_method():
    ex = tse.extract("namespace geo { void setup(); }\nvoid geo::setup() { run(); }\n", "g.cpp", "cpp", False)
    assert [(f.name, f.parent_class, f.is_method) for f in ex.functions] == [("setup", None, False)]


# --- qualified calls, constructors, imports ---------------------------------------

def test_qualified_call_representation():
    rows = {(c.callee_name, c.qualifier_path) for c in _extract("rust", "src/cart/mod.rs").calls}
    assert ("apply_discount", "crate::pricing::") in rows   # path-qualified: ends with "::"
    assert ("sum", "self") in rows                          # method on self: member access
    assert ("new", "Rule::") in rows
    cpp_rows = {(c.callee_name, c.qualifier_path) for c in _extract("cpp", "src/cart.cpp").calls}
    assert ("apply_discount", "shop::") in cpp_rows and ("apply", "rule") in cpp_rows


def test_rust_self_paths_are_resolved_to_the_impl_type():
    calls = {(c.callee_name, c.qualifier_path) for c in _extract("rust", "src/pricing.rs").calls}
    assert ("validate", "Rule::") in calls and not any(q == "Self::" for _, q in calls)


def test_constructor_invocations_are_call_sites():
    java = {c.callee_name for c in _extract("java", "src/main/java/com/shop/cart/Cart.java").calls}
    assert {"PriceCalculator", "ArrayList"} <= java
    ts = {c.callee_name for c in _extract("typescript", "src/models/cart.ts").calls}
    assert "Cart" in ts
    cpp = [(c.callee_name, c.qualifier_path) for c in _extract("cpp", "src/cart.cpp").calls]
    assert ("Rule", "shop::") in cpp


def test_macro_bodies_are_not_parsed_as_calls():
    calls = {c.callee_name for c in _extract("rust", "src/cart/mod.rs").calls}
    assert "hidden_in_macro" not in calls  # inside println!(...): a token tree, not syntax


def test_package_declarations():
    assert _extract("go", "cart/cart.go").package == "cart"
    assert _extract("java", "src/main/java/com/shop/cart/Cart.java").package == "com.shop.cart"


# --- errors, empty input, determinism, paths -------------------------------------

@pytest.mark.parametrize("corpus,path,kept", [
    ("typescript", "src/broken.ts", ["ok"]),
    ("go", "broken.go", ["Good", "Bad", "After"]),
    ("rust", "src/broken.rs", ["good", "after"]),
    ("java", "src/main/java/com/shop/Broken.java", ["good", "bad", "after"]),
    ("cpp", "src/broken.cpp", ["good"]),
])
def test_syntax_errors_yield_flagged_partial_results(corpus, path, kept):
    ex = _extract(corpus, path)
    assert ex.has_error is True and ex.error_nodes >= 1
    assert [f.name for f in ex.functions] == kept


@pytest.mark.parametrize("language,path", [("typescript", "e.ts"), ("tsx", "e.tsx"), ("go", "e.go"),
                                           ("rust", "e.rs"), ("java", "E.java"), ("cpp", "e.cpp")])
def test_empty_files(language, path):
    ex = tse.extract("", path, language, False)
    assert (ex.functions, ex.calls, ex.symbols, ex.imports, ex.has_error) == ([], [], [], [], False)


@pytest.mark.parametrize("corpus", LANGUAGES)
def test_extraction_is_deterministic(corpus):
    for path, content in fixture_files(corpus).items():
        language = tse.detect_language(path)
        if language is None:
            continue
        runs = [_records(tse.extract(content, path, language, False)) for _ in range(3)]
        assert runs[0] == runs[1] == runs[2], path


def test_paths_are_passed_through_unchanged():
    ex = tse.extract("fn f() { g(); }", "crates/core/src/lib.rs", "rust", False)
    assert {f.filepath for f in ex.functions} == {"crates/core/src/lib.rs"}
    assert {c.caller_path for c in ex.calls} == {"crates/core/src/lib.rs"}


def test_test_flag_follows_the_existing_path_rule():
    assert {f.is_test for f in _extract("go", "cart/cart_test.go").functions} == {True}
    assert {f.is_test for f in _extract("go", "cart/cart.go").functions} == {False}


# --- documented capabilities (docs/TREE_SITTER.md §4) ------------------------------

def _ex(code, path):
    return tse.extract(code, path, tse.detect_language(path), False)


def test_typescript_import_forms():
    ex = _ex('import fs = require("fs");\nimport "./polyfill";\nimport Def from "./def";\n', "a.ts")
    assert [(r.kind, r.spec, r.local_name, r.imported_name) for r in ex.import_records] == [
        ("module", "fs", "fs", None), ("side_effect", "./polyfill", None, None), ("default", "./def", "Def", "default")]


def test_typescript_function_forms():
    ex = _ex("class A {\n  handler = (x: number) => go(x);\n  *gen() {}\n}\nfunction* items() {}\n"
             "const fe = function () { return 1; };\n", "f.ts")
    assert [(f.name, f.parent_class, f.is_method, f.start_line) for f in ex.functions] == [
        ("handler", "A", True, 2), ("gen", "A", True, 3), ("items", None, False, 5), ("fe", None, False, 6)]
    assert [(c.callee_name, c.caller_func) for c in ex.calls] == [("go", "handler")]


def test_go_blank_and_dot_imports():
    ex = _ex('package p\nimport (\n\t_ "embed"\n\t. "strings"\n)\n', "p.go")
    assert [(r.kind, r.spec, r.local_name) for r in ex.import_records] == [
        ("side_effect", "embed", None), ("wildcard", "strings", None)]


def test_java_enum_and_record_methods():
    ex = _ex("enum Color { RED; String label() { return name(); } }\nrecord P(int x) { int twice() { return x * 2; } }\n",
             "C.java")
    assert [(f.name, f.parent_class) for f in ex.functions] == [("label", "Color"), ("twice", "P")]


def test_cpp_arrow_member_calls_and_destructors():
    ex = _ex("struct S {\n  ~S() {}\n  int get() { return this->peek(); }\n};\nint S_use(S* s) { return s->get(); }\n", "s.hpp")
    assert [(f.name, f.parent_class) for f in ex.functions] == [("~S", "S"), ("get", "S"), ("S_use", None)]
    assert [(c.callee_name, c.qualifier_path) for c in ex.calls] == [("peek", "this"), ("get", "s")]
