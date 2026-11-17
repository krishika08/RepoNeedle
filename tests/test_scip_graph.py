"""
SCIP symbol/reference resolution and function-graph integration (optional `scip` extra).

Ranges are computed from the source text, so every fixture occurrence is in bounds unless a test says
otherwise. Edge semantics: a `scip_reference` edge (confidence 0.9) means "code in the source file
references a callable defined in the target file", per the producer; it is never derived from names.
"""

import pytest

from scip_support import FIXTURES, build_index, doc, occ, rel, require_protobuf, sym, write_index, write_repo

pb = require_protobuf()

from reponeedle.core.function_graph import FunctionGraphEngine  # noqa: E402
from reponeedle.core.scip_ingestion import (  # noqa: E402
    ROLE_DEFINITION, ROLE_FORWARD_DEFINITION, ROLE_IMPORT, SCIP_REFERENCE_CONFIDENCE, ScipIndex,
)
from reponeedle.engine import RepoNeedleEngine  # noqa: E402
from reponeedle.models import FileDoc, ScipConfig  # noqa: E402

P = "synthetic npm repo 1.0 "
HELPER, HELPER2 = P + "util/helper(+1).", P + "util/helper(+2)."
SHAPE, AREA, LIMIT = P + "util/Shape#", P + "util/Shape#area().", P + "util/LIMIT."
RUN, INNER = P + "main/run().", P + "main/run().inner()."
EXT, MISSING = "other npm lib 2.0 lib/ext().", P + "util/missing()."

UTIL = (
    "export function helper(x) {\n"
    "  return x;\n"
    "}\n"
    "export function helper(x, y) { return y; }\n"
    "export class Shape {\n"
    "  area() { return 1; }\n"
    "}\n"
    "export const LIMIT = 3;\n"
)
MAIN = (
    "import { helper, Shape, LIMIT } from './util';\n"
    "export function run() {\n"
    "  const s = new Shape();\n"
    "  helper(LIMIT); helper(1, 2); helper(2);\n"
    "  function inner() { return s.area(); }\n"
    "  return inner() + ext() + missing();\n"
    "}\n"
    "helper(0);\n"
)


def at(text, line, token, nth=0):
    """[line, start, end] of the nth occurrence of token on a 0-based line."""
    src = text.split("\n")[line]
    start = -1
    for _ in range(nth + 1):
        start = src.index(token, start + 1)
    return [line, start, start + len(token)]


def util_doc(text=None):
    return doc("util.ts", [
        occ(HELPER, at(UTIL, 0, "helper"), roles=ROLE_DEFINITION, enclosing=[0, 0, 2, 1]),
        occ(HELPER2, at(UTIL, 3, "helper"), roles=ROLE_DEFINITION, enclosing=[3, 0, 3, 42]),
        occ(SHAPE, at(UTIL, 4, "Shape"), roles=ROLE_DEFINITION, enclosing=[4, 0, 6, 1]),
        occ(AREA, at(UTIL, 5, "area"), roles=ROLE_DEFINITION, enclosing=[5, 2, 5, 22]),
        occ(LIMIT, at(UTIL, 7, "LIMIT"), roles=ROLE_DEFINITION),
        occ("local 0", at(UTIL, 0, "x"), roles=ROLE_DEFINITION),
        occ("local 0", at(UTIL, 1, "x")),
    ], [
        sym(HELPER, "Function", display_name="helper"), sym(HELPER2, "Function", display_name="helper"),
        sym(SHAPE, "Class", relationships=[rel(P + "util/Drawable#", is_implementation=True)]),
        sym(AREA, "Method", relationships=[rel(P + "util/Drawable#area().", is_implementation=True, is_reference=True)]),
        sym(LIMIT, "Constant", relationships=[rel(P + "util/Num#", is_type_definition=True)]),
        sym("local 0", "Parameter"),
    ], text=text)


def main_doc():
    return doc("main.ts", [
        occ(HELPER, at(MAIN, 0, "helper"), roles=ROLE_IMPORT),
        occ(SHAPE, at(MAIN, 0, "Shape"), roles=ROLE_IMPORT),
        occ(LIMIT, at(MAIN, 0, "LIMIT"), roles=ROLE_IMPORT),
        occ(RUN, at(MAIN, 1, "run"), roles=ROLE_DEFINITION, enclosing=[1, 0, 6, 1]),
        occ(SHAPE, at(MAIN, 2, "Shape")),
        occ(HELPER, at(MAIN, 3, "helper")), occ(LIMIT, at(MAIN, 3, "LIMIT")),
        occ(HELPER2, at(MAIN, 3, "helper", 1)), occ(HELPER, at(MAIN, 3, "helper", 2)),
        occ(INNER, at(MAIN, 4, "inner"), roles=ROLE_DEFINITION, enclosing=[4, 2, 4, 39]),
        occ(AREA, at(MAIN, 4, "area")),
        occ(INNER, at(MAIN, 5, "inner")), occ(EXT, at(MAIN, 5, "ext")), occ(MISSING, at(MAIN, 5, "missing")),
        occ(HELPER, at(MAIN, 7, "helper")),
        occ("local 0", at(MAIN, 2, "s"), roles=ROLE_DEFINITION), occ("local 0", at(MAIN, 4, "s")),
    ], [sym(RUN, "Function", display_name="run"), sym(INNER, "Function", display_name="inner")])


def _repo(tmp_path, util_text=None, extra_docs=(), extra_files=None, index_docs=None):
    root = tmp_path / "repo"
    root.mkdir()
    write_repo(root, {"util.ts": UTIL, "main.ts": MAIN, **(extra_files or {})})
    documents = index_docs if index_docs is not None else [util_doc(util_text), main_doc(), *extra_docs]
    path = write_index(tmp_path, build_index(root.as_uri(), documents, external=[sym(EXT, "Function")]))
    return root, path


def _engine(tmp_path, **kw):
    root, path = _repo(tmp_path, **kw)
    return RepoNeedleEngine.from_directory(str(root), scip_config=ScipConfig(index_path=path))


def _resolved(engine):
    """Edges SCIP resolution produced (before graph-level de-duplication against extracted edges)."""
    res = engine.function_graph.scip_index.resolve(engine.docs)
    return sorted((e.source_path, e.source_name, e.target_path, e.target_name) for e in res.edges)


def _scip_edges(fg):
    return sorted((e.source_path, e.source_func, e.target_path, e.target_func, e.target_symbol, e.confidence)
                  for e in fg.edges if e.edge_type == "scip_reference")


def test_reference_edges_are_exact(tmp_path):
    _check_exact(_engine(tmp_path))


def _check_exact(engine):
    edges = _scip_edges(engine.function_graph)
    # `helper(0)` at top level is unattributed and dropped because run() references the same symbol.
    assert edges == sorted([
        ("main.ts", "inner", "util.ts", "area", AREA, SCIP_REFERENCE_CONFIDENCE),
        ("main.ts", "run", "util.ts", "helper", HELPER, SCIP_REFERENCE_CONFIDENCE),
        ("main.ts", "run", "util.ts", "helper", HELPER2, SCIP_REFERENCE_CONFIDENCE),
    ])


def test_reference_classification_counts(tmp_path):
    d = _engine(tmp_path).scip_diagnostics
    refs = d["references"]
    assert refs["import"] == 3                     # Import role: never a call
    assert refs["to_repository_non_callables"] == 2   # Shape# (class), LIMIT. (constant)
    assert refs["external"] == 1                   # listed in external_symbols
    assert refs["unresolved"] == 1                 # same package, no definition
    assert refs["local"] == 2                      # document-scoped locals
    assert refs["same_file"] == 1                  # inner() inside main.ts
    assert d["symbols"]["local"] == 2              # `local 0` in util.ts and in main.ts are different symbols
    assert d["edges"]["unattributed_duplicates_dropped"] == 1
    assert d["definitions"]["total"] == 9 and d["definitions"]["callable"] == 5   # 6 in util.ts, 3 in main.ts
    assert d["documents"]["matched"] == 2 and d["status"] == "ingested"
    assert d["producer"] == {"name": "synthetic-indexer", "version": "1.0"}


def test_relationships_are_stored_separately_from_edges(tmp_path):
    engine = _engine(tmp_path)
    rels = {(r.symbol, r.related_symbol, r.is_implementation, r.is_type_definition, r.is_reference)
            for r in engine.function_graph.scip_relationships}
    assert rels == {
        (SHAPE, P + "util/Drawable#", True, False, False),
        (AREA, P + "util/Drawable#area().", True, False, True),
        (LIMIT, P + "util/Num#", False, True, False),
    }
    assert engine.scip_diagnostics["relationships"] == {"implementation": 2, "type_definition": 1, "reference": 1,
                                                        "definition": 0}
    assert not any(e.target_symbol and "Drawable" in e.target_symbol for e in engine.function_graph.edges)


def test_duplicate_display_names_resolve_by_identifier(tmp_path):
    a, b = P + "a/f().", P + "b/f()."
    files = {"a.ts": "export function f() {}\n", "b.ts": "export function f() {}\n",
             "use.ts": "f(); f();\n"}
    docs = [
        doc("a.ts", [occ(a, at(files["a.ts"], 0, "f"), roles=1)], [sym(a, display_name="f")]),
        doc("b.ts", [occ(b, at(files["b.ts"], 0, "f"), roles=1)], [sym(b, display_name="f")]),
        doc("use.ts", [occ(b, at(files["use.ts"], 0, "f")), occ(a, at(files["use.ts"], 0, "f", 1))]),
    ]
    engine = _engine(tmp_path, extra_files=files, index_docs=docs)
    res = engine.function_graph.scip_index.resolve(engine.docs)
    assert {(e.target_path, e.target_symbol) for e in res.edges} == {("a.ts", a), ("b.ts", b)}


def test_ambiguous_definitions_are_not_resolved(tmp_path):
    dup = P + "dup/f()."
    files = {"a.ts": "export function f() {}\n", "b.ts": "export function f() {}\n", "use.ts": "f();\n"}
    docs = [
        doc("a.ts", [occ(dup, at(files["a.ts"], 0, "f"), roles=1)], [sym(dup)]),
        doc("b.ts", [occ(dup, at(files["b.ts"], 0, "f"), roles=1)], [sym(dup)]),
        doc("use.ts", [occ(dup, at(files["use.ts"], 0, "f"))]),
    ]
    engine = _engine(tmp_path, extra_files=files, index_docs=docs)
    assert _resolved(engine) == []
    assert engine.scip_diagnostics["references"]["ambiguous"] == 1
    assert engine.scip_diagnostics["definitions"]["multiply_defined_symbols"] == 1


def test_forward_declarations_are_neither_definitions_nor_references(tmp_path):
    f = P + "geo/area()."
    files = {"geo.h": "double area();\n", "geo.cpp": "double area() { return 1; }\n", "use.cpp": "int x = area();\n"}
    docs = [
        doc("geo.h", [occ(f, at(files["geo.h"], 0, "area"), roles=ROLE_FORWARD_DEFINITION)], language="cpp"),
        doc("geo.cpp", [occ(f, at(files["geo.cpp"], 0, "area"), roles=ROLE_DEFINITION)], [sym(f)], language="cpp"),
        doc("use.cpp", [occ(f, at(files["use.cpp"], 0, "area"))], language="cpp"),
    ]
    root = tmp_path / "repo"
    root.mkdir()
    write_repo(root, files)
    index = ScipIndex.from_bytes(build_index(root.as_uri(), docs))
    index.validate_root(str(root))
    res = index.resolve([FileDoc(path=p, content=c) for p, c in files.items()])
    assert res.diagnostics["definitions"]["forward_declarations"] == 1
    assert [(e.source_path, e.target_path) for e in res.edges] == [("use.cpp", "geo.cpp")]


def test_definition_in_a_rejected_document_is_not_used(tmp_path):
    hidden = P + "x/hidden()."
    files = {"use.ts": "hidden();\n"}
    docs = [doc("../x.ts", [occ(hidden, [0, 0, 6], roles=1)], [sym(hidden)]),
            doc("use.ts", [occ(hidden, at(files["use.ts"], 0, "hidden"))])]
    engine = _engine(tmp_path, extra_files=files, index_docs=docs)
    assert _resolved(engine) == []
    assert engine.scip_diagnostics["references"]["defined_in_unusable_documents"] == 1


def test_stale_definitions_produce_no_edges(tmp_path):
    engine = _engine(tmp_path, util_text=UTIL.replace("return x;", "return x + 1;"))
    assert _scip_edges(engine.function_graph) == []
    assert engine.scip_diagnostics["documents"]["stale"] == 1


def test_unknown_kind_falls_back_to_the_descriptor_suffix(tmp_path):
    g = P + "k/g()."
    files = {"k.ts": "export function g() {}\n", "use.ts": "g();\n"}
    index_docs = [doc("k.ts", [occ(g, at(files["k.ts"], 0, "g"), roles=1)], [sym(g, kind=None)]),
                  doc("use.ts", [occ(g, at(files["use.ts"], 0, "g"))])]
    engine = _engine(tmp_path, extra_files=files, index_docs=index_docs)
    assert [e[3] for e in _resolved(engine)] == ["g"]


@pytest.mark.parametrize("encoding,offset", [("UTF8CodeUnitOffsetFromLineStart", 18),
                                             ("UTF16CodeUnitOffsetFromLineStart", 16),
                                             ("UTF32CodeUnitOffsetFromLineStart", 15)])
def test_position_encodings(tmp_path, encoding, offset):
    g = P + "e/g()."
    files = {"e.ts": "export function g() {}\n", "use.ts": 'const r = "🚀"; g();\n'}
    assert files["use.ts"].index("g()") == 15  # code points; the emoji is 4 bytes / 2 UTF-16 units
    line = files["use.ts"].split("\n")[0]
    expected = {"UTF8CodeUnitOffsetFromLineStart": len(line[:15].encode("utf-8")),
                "UTF16CodeUnitOffsetFromLineStart": len(line[:15].encode("utf-16-le")) // 2,
                "UTF32CodeUnitOffsetFromLineStart": 15}[encoding]
    index_docs = [doc("e.ts", [occ(g, at(files["e.ts"], 0, "g"), roles=1)], [sym(g)], encoding=encoding),
                  doc("use.ts", [occ(g, [0, expected, expected + 1])], encoding=encoding)]
    engine = _engine(tmp_path, extra_files=files, index_docs=index_docs)
    assert [e[2] for e in _resolved(engine)] == ["e.ts"]
    assert engine.scip_diagnostics["occurrences"]["out_of_bounds"] == 0
    assert expected == offset  # 18 UTF-8 bytes, 16 UTF-16 units, 15 code points before `g`


def test_utf8_offsets_out_of_bounds_for_utf32(tmp_path):
    g = P + "e/g()."
    files = {"e.ts": "export function g() {}\n", "use.ts": "🚀🚀🚀🚀 g();\n"}
    index_docs = [doc("e.ts", [occ(g, at(files["e.ts"], 0, "g"), roles=1)], [sym(g)]),
                  doc("use.ts", [occ(g, [0, 17, 18])], encoding="UTF32CodeUnitOffsetFromLineStart")]
    engine = _engine(tmp_path, extra_files=files, index_docs=index_docs)
    assert _resolved(engine) == []
    assert engine.scip_diagnostics["occurrences"]["out_of_bounds"] == 1


def test_multi_line_and_legacy_ranges_resolve(tmp_path):
    g = P + "m/g()."
    files = {"m.ts": "export function\ng() {}\n", "use.ts": "export function u() {\n  g();\n}\n"}
    u = P + "use/u()."
    index_docs = [
        doc("m.ts", [occ(g, [1, 0, 1, 1], roles=1, enclosing=[0, 0, 1, 6])], [sym(g)]),
        doc("use.ts", [occ(u, [0, 16, 17], roles=1, enclosing=[0, 0, 2, 1], legacy=True), occ(g, [1, 2, 3], legacy=True)],
            [sym(u)]),
    ]
    engine = _engine(tmp_path, extra_files=files, index_docs=index_docs)
    assert [(e[1], e[2], e[3]) for e in _resolved(engine)] == [("u", "m.ts", "g")]


def test_reference_at_a_function_end_is_not_attributed_to_it(tmp_path):
    # Enclosing ranges are half-open: a call that starts exactly where `a`'s range ends lies outside `a`.
    a, b = P + "edge/a().", P + "edge/b()."
    text = "function a() { return 1; }helper(0);\nfunction b() { return 2; }\nhelper(1);\n"
    end_of_a = len("function a() { return 1; }")
    edge_doc = doc("edge.ts", [
        occ(a, at(text, 0, "a"), roles=ROLE_DEFINITION, enclosing=[0, 0, 0, end_of_a]),
        occ(HELPER, at(text, 0, "helper")),
        occ(b, at(text, 1, "b"), roles=ROLE_DEFINITION, enclosing=[1, 0, 2, 0]),   # ends at the start of line 2
        occ(HELPER, at(text, 2, "helper")),
    ], [sym(a), sym(b)])
    engine = _engine(tmp_path, extra_files={"edge.ts": text}, index_docs=[util_doc(), edge_doc])
    assert [e for e in _resolved(engine) if e[0] == "edge.ts"] == [("edge.ts", None, "util.ts", "helper")]
    assert engine.scip_diagnostics["references"]["with_enclosing_definition"] == 0


def test_no_duplicate_edges_and_determinism(tmp_path):
    root, path = _repo(tmp_path)
    runs = [_scip_edges(RepoNeedleEngine.from_directory(str(root), scip_config=ScipConfig(index_path=path)).function_graph)
            for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    assert len(runs[0]) == len(set(runs[0]))


def test_scip_does_not_duplicate_extracted_edges(tmp_path):
    files = {"lib.py": "def helper():\n    return 1\n", "app.py": "from lib import helper\n\ndef run():\n    return helper()\n"}
    h, r = "scip-python python repo 1.0 lib/helper().", "scip-python python repo 1.0 app/run()."
    index_docs = [
        doc("lib.py", [occ(h, [0, 4, 10], roles=1, enclosing=[0, 0, 1, 12])], [sym(h)], language="python"),
        doc("app.py", [occ(h, [0, 16, 22], roles=ROLE_IMPORT), occ(r, [2, 4, 7], roles=1, enclosing=[2, 0, 3, 19]),
                       occ(h, [3, 11, 17])], [sym(r)], language="python"),
    ]
    engine = _engine(tmp_path, extra_files=files, index_docs=index_docs)
    fg = engine.function_graph
    assert [(e.source_path, e.target_path, e.target_func, e.edge_type) for e in fg.edges
            if e.target_path == "lib.py"] == [("app.py", "lib.py", "helper", "verified_call")]
    assert engine.scip_diagnostics["edges"]["already_present_from_extraction"] == 1


def test_from_documents_requires_and_uses_repo_root(tmp_path):
    root, path = _repo(tmp_path)
    docs = [FileDoc(path="util.ts", content=UTIL), FileDoc(path="main.ts", content=MAIN)]
    engine = RepoNeedleEngine.from_documents(docs, scip_config=ScipConfig(index_path=path, repo_root=str(root)))
    _check_exact(engine)


def test_on_error_skip_records_the_reason(tmp_path):
    root, _ = _repo(tmp_path)
    bad = tmp_path / "bad.scip"
    bad.write_bytes(b"\xff\xff\xff")
    engine = RepoNeedleEngine.from_directory(str(root), scip_config=ScipConfig(index_path=str(bad), on_error="skip"))
    assert engine.scip_diagnostics["status"] == "skipped" and "not a valid SCIP index" in engine.scip_diagnostics["error"]
    assert _scip_edges(engine.function_graph) == []


def test_update_documents_re_resolves(tmp_path):
    root, path = _repo(tmp_path)
    engine = RepoNeedleEngine.from_directory(str(root), scip_config=ScipConfig(index_path=path))
    assert _scip_edges(engine.function_graph)
    engine.update_document(FileDoc(path="util.ts", content=UTIL + "\n// edited\n"))
    # Without embedded text the edit is not detectable as stale; ranges are still in bounds.
    assert engine.scip_diagnostics["freshness"]["status"] == "unverified"
    engine.update_document(FileDoc(path="main.ts", content="// emptied\n"))
    assert _scip_edges(engine.function_graph) == []  # every main.ts occurrence is now out of bounds
    assert engine.scip_diagnostics["occurrences"]["out_of_bounds"] > 0


def test_arm101_uses_scip_edges_and_legacy_is_unchanged(tmp_path):
    root, path = _repo(tmp_path)
    with_scip = RepoNeedleEngine.from_directory(str(root), scip_config=ScipConfig(index_path=path))
    without = RepoNeedleEngine.from_directory(str(root))
    assert "util.ts" in with_scip.function_graph.callees_map["main.ts"]
    q = "run the helper area computation"
    assert [f.path for f in with_scip.retrieve(q, budget_tokens=2000).selected_files] == \
           [f.path for f in without.retrieve(q, budget_tokens=2000).selected_files]
    assert with_scip.retrieve(q, budget_tokens=2000, ranker="arm101").selected_files


def test_function_graph_without_scip_is_unchanged(tmp_path):
    root, _ = _repo(tmp_path)
    docs = [FileDoc(path="util.ts", content=UTIL), FileDoc(path="main.ts", content=MAIN)]
    plain = FunctionGraphEngine().build_graph(docs)
    assert all(e.edge_type != "scip_reference" and e.provenance is None for e in plain.edges)
    assert "scip" not in plain.diagnostics


# --- real producer: scip-typescript 0.6.2 ---------------------------------------------------------

REAL = FIXTURES / "real" / "typescript"
TS = "scip-typescript npm . . "


def test_real_scip_typescript_index(tmp_path):
    engine = RepoNeedleEngine.from_directory(str(REAL), scip_config=ScipConfig(
        index_path=str(REAL / "index.scip"), allow_project_root_mismatch=True))
    d = engine.scip_diagnostics
    assert d["producer"] == {"name": "scip-typescript", "version": "0.6.2"}
    assert d["project_root"]["status"] == "mismatch"
    assert d["documents"]["matched"] == 7 and d["documents"]["backslash_paths_normalized"] == 7
    assert d["position_encoding"] == {"utf16": 7}
    assert d["occurrences"] == {"total": 153, "invalid_range": 0, "out_of_bounds": 0, "without_symbol": 0,
                                "malformed_symbol": 0}
    assert d["definitions"]["total"] == 55 and d["definitions"]["callable"] == 15
    assert d["references"]["total"] == 98 and d["references"]["external_package"] == 11
    assert d["references"]["unresolved"] == 0 and d["references"]["ambiguous"] == 0
    assert d["relationships"]["implementation"] == 4
    assert _scip_edges(engine.function_graph) == sorted([
        ("src/components/CartView.tsx", "CartView", "src/models/cart.ts", "describe", TS + "src/models/`cart.ts`/Cart#describe().", 0.9),
        ("src/models/cart.ts", "total", "src/util/format.ts", "round", TS + "src/util/`format.ts`/round().", 0.9),
        ("tests/cart.test.ts", None, "src/models/cart.ts", "add", TS + "src/models/`cart.ts`/Cart#add().", 0.9),
        ("tests/cart.test.ts", None, "src/models/cart.ts", "total", TS + "src/models/`cart.ts`/Cart#total().", 0.9),
        ("tests/shapes.test.ts", None, "src/models/shapes.ts", "<constructor>", TS + "src/models/`shapes.ts`/Circle#`<constructor>`().", 0.9),
        ("tests/shapes.test.ts", None, "src/models/shapes.ts", "<constructor>", TS + "src/models/`shapes.ts`/Square#`<constructor>`().", 0.9),
    ])
    impl = {(r.symbol.rsplit("/", 1)[-1], r.related_symbol.rsplit("/", 1)[-1])
            for r in engine.function_graph.scip_relationships if r.is_implementation}
    assert impl == {("Square#", "Shape#"), ("Square#area().", "Shape#area()."), ("Circle#", "Shape#"),
                    ("Circle#area().", "Shape#area().")}


def test_real_index_is_refused_without_explicit_mismatch_permission():
    from reponeedle.core.scip_ingestion import ScipIngestionError
    with pytest.raises(ScipIngestionError, match="file:///F:/scipfix/ts-shop"):
        RepoNeedleEngine.from_directory(str(REAL), scip_config=ScipConfig(index_path=str(REAL / "index.scip")))
