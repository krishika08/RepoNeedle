"""
SCIP ingestion pieces that need no optional dependency: symbol grammar, project-root decoding, path
validation, position encodings, missing-Protobuf behaviour, defaults and packaging. Runs in every job.
"""

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from reponeedle.core import scip_ingestion as si
from reponeedle.core.function_graph import FunctionGraphEdge, FunctionGraphEngine
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import FileDoc, ScipConfig

ROOT = Path(__file__).resolve().parent.parent


# --- symbol grammar (scip.proto `message Symbol`) ----------------------------------

def test_global_symbol_with_method_disambiguator():
    ps = si.parse_symbol("scip-java maven com.acme 1.0 com/acme/Cart#add(+1).")
    assert (ps.scheme, ps.manager, ps.package, ps.version) == ("scip-java", "maven", "com.acme", "1.0")
    assert [(d.name, d.suffix, d.disambiguator) for d in ps.descriptors] == [
        ("com", "namespace", ""), ("acme", "namespace", ""), ("Cart", "type", ""), ("add", "method", "+1")]
    assert ps.name == "add" and ps.suffix == "method" and not ps.is_local


def test_escaped_identifiers_and_spaces():
    ps = si.parse_symbol("scip-typescript npm my  pkg . src/`a.ts`/`weird``name`#`<constructor>`().")
    assert ps.package == "my pkg" and ps.version == "."
    assert [(d.name, d.suffix) for d in ps.descriptors] == [
        ("src", "namespace"), ("a.ts", "namespace"), ("weird`name", "type"), ("<constructor>", "method")]


@pytest.mark.parametrize("symbol,suffix", [
    ("s m p v T#[A]", "type_parameter"), ("s m p v f().(x)", "parameter"), ("s m p v a:", "meta"),
    ("s m p v m!", "macro"), ("s m p v x.", "term"), ("s m p v ns/", "namespace"),
])
def test_descriptor_suffixes(symbol, suffix):
    assert si.parse_symbol(symbol).suffix == suffix


def test_local_symbols():
    ps = si.parse_symbol("local 42")
    assert ps.is_local and ps.local_id == "42" and ps.suffix == "local"


@pytest.mark.parametrize("bad", [
    "", "local ", "local a b", "scip only-two", "localscheme m p v x.", "s m p v", "s m p v `unterminated",
    "s m p v ``.", "s m p v x?", "s m p v f(a.", "s m p v f(a)x",
])
def test_malformed_symbols_are_rejected(bad):
    with pytest.raises(ValueError):
        si.parse_symbol(bad)


def test_overloads_and_same_display_names_stay_distinct():
    a, b = si.parse_symbol("s m p v C#run(+1)."), si.parse_symbol("s m p v C#run(+2).")
    assert a != b and a.name == b.name == "run"


# --- project roots -----------------------------------------------------------------

def test_decode_file_uris(tmp_path):
    real = tmp_path / "my repo"
    real.mkdir()
    decoded, how = si.decode_project_root(real.as_uri())
    assert how == "file-uri" and os.path.normcase(decoded) == os.path.normcase(os.path.normpath(str(real)))
    assert si.decode_project_root("file://localhost" + real.as_uri()[len("file://"):])[0] == decoded
    assert si.decode_project_root(str(real))[1] == "plain-path"


def test_decode_windows_forms():
    for uri in ("file:///C:/work/repo", "file:///c%3A/work/repo", "file:///C:/work%20dir/repo"):
        decoded, how = si.decode_project_root(uri)
        assert how == "file-uri" and decoded.replace("\\", "/").lower().startswith("c:/work")
        assert si.is_windows_style_root(uri)
    assert si.is_windows_style_root("file://server/share/repo")
    assert si.is_windows_style_root("C:\\work\\repo")
    assert not si.is_windows_style_root("file:///home/u/repo")


@pytest.mark.parametrize("bad,reason", [
    ("", "missing"), ("https://example.com/repo", "unsupported URI scheme"), ("relative/dir", "not an absolute"),
])
def test_undecodable_roots(bad, reason):
    decoded, how = si.decode_project_root(bad)
    assert decoded is None and reason in how


def test_unc_root_depends_on_host():
    decoded, how = si.decode_project_root("file://server/share/repo")
    if os.name == "nt":
        assert decoded.startswith("\\\\server\\share")
    else:
        assert decoded is None and "remote host" in how


# --- document paths --------------------------------------------------------------------

@pytest.mark.parametrize("path", ["src/a.ts", "a", "deep/er/x.go", "..cache/x.py", "a.b/c"])
def test_canonical_paths_accepted(path):
    assert si.validate_relative_path(path) is None


@pytest.mark.parametrize("path,reason", [
    ("", "empty path"), ("/etc/passwd", "absolute"), ("C:/x.ts", "absolute"), ("c:x", "absolute"),
    ("../outside.ts", "'.' or '..'"), ("src/../../x", "'.' or '..'"), ("./a.ts", "'.' or '..'"),
    ("src//a.ts", "empty path component"), ("src/", "empty path component"), ("src\\a.ts", "backslash"),
    ("a\x00b", "NUL"),
])
def test_non_canonical_paths_rejected(path, reason):
    assert reason in si.validate_relative_path(path)


# --- position encodings (examples from scip.proto) ---------------------------------------

def test_encoding_offsets_match_the_specification_example():
    line = "🚀 Woo"
    prefix = line[:line.index("W")]
    assert si.line_length(prefix, si.ENC_UTF8) == 5
    assert si.line_length(prefix, si.ENC_UTF16) == 3
    assert si.line_length(prefix, si.ENC_UTF32) == 2
    assert si.line_length(line, si.ENC_UNSPECIFIED) == si.line_length(line, si.ENC_UTF8)  # most permissive


def test_range_bounds_depend_on_encoding():
    lines = ["🚀 f();", ""]
    r = si.SourceRange(0, 5, 0, 6)  # 'f' in UTF-8 bytes
    assert si.range_in_bounds(r, lines, si.ENC_UTF8)
    assert not si.range_in_bounds(si.SourceRange(0, 5, 0, 9), lines, si.ENC_UTF32)
    assert not si.range_in_bounds(si.SourceRange(2, 0, 2, 0), lines, si.ENC_UTF8)


# --- half-open [start, end) ranges (scip.proto: "the end position is exclusive") --------------

def test_range_contains_its_start_position():
    assert si.SourceRange(2, 4, 2, 9).contains(2, 4)
    assert si.SourceRange(1, 3, 5, 0).contains(1, 3)


def test_range_contains_interior_positions():
    single = si.SourceRange(2, 4, 2, 9)
    assert single.contains(2, 5) and single.contains(2, 8)        # last included character is end - 1
    multi = si.SourceRange(1, 3, 5, 2)
    assert multi.contains(1, 99) and multi.contains(3, 0) and multi.contains(5, 1)


def test_range_excludes_its_end_position():
    assert not si.SourceRange(2, 4, 2, 9).contains(2, 9)
    assert not si.SourceRange(1, 3, 5, 2).contains(5, 2)
    assert not si.SourceRange(1, 0, 4, 0).contains(4, 0)          # range ending at the start of a line


def test_range_excludes_positions_outside():
    r = si.SourceRange(1, 3, 5, 2)
    assert not r.contains(1, 2) and not r.contains(0, 50)
    assert not r.contains(5, 3) and not r.contains(6, 0)


def test_empty_range_contains_nothing():
    empty = si.SourceRange(3, 7, 3, 7)
    assert not empty.contains(3, 7)
    assert not empty.contains(3, 6) and not empty.contains(3, 8)


def _callable_def(name: str, enclosing):
    return si.ScipDefinition(symbol=f"synthetic npm repo 1.0 m/{name}().", path="m.ts",
                             range=si.SourceRange(enclosing.start_line, enclosing.start_character,
                                                  enclosing.start_line, enclosing.start_character + 1),
                             enclosing=enclosing, callable=True, name=name)


def test_innermost_attribution_at_function_boundaries():
    # `function a() { return 1; }function b() { return helper(); }` on one line: a = [0:0, 0:26), b = [0:26, 0:60).
    a = _callable_def("a", si.SourceRange(0, 0, 0, 26))
    b = _callable_def("b", si.SourceRange(0, 26, 0, 60))
    defs = [a, b]

    def at(line, character):
        return si.SourceRange(line, character, line, character + 1)

    assert si._innermost(defs, at(0, 0)) is a        # start of a: included
    assert si._innermost(defs, at(0, 25)) is a       # last character of a
    assert si._innermost(defs, at(0, 26)) is b       # end of a is exclusive; start of b is inclusive
    assert si._innermost(defs, at(0, 59)) is b       # last character of b
    assert si._innermost(defs, at(0, 60)) is None    # end of b: outside every function


def test_innermost_prefers_the_nested_function_but_not_past_its_end():
    outer = _callable_def("outer", si.SourceRange(1, 0, 6, 1))
    inner = _callable_def("inner", si.SourceRange(4, 2, 4, 39))
    defs = [outer, inner]
    ref = lambda line, character: si.SourceRange(line, character, line, character + 1)  # noqa: E731
    assert si._innermost(defs, ref(4, 2)) is inner
    assert si._innermost(defs, ref(4, 38)) is inner
    assert si._innermost(defs, ref(4, 39)) is outer   # just past inner's end, still inside outer
    assert si._innermost(defs, ref(6, 1)) is None     # outer's exclusive end


def test_innermost_ignores_empty_and_missing_enclosing_ranges():
    empty = _callable_def("empty", si.SourceRange(2, 5, 2, 5))
    no_range = si.ScipDefinition(symbol="synthetic npm repo 1.0 m/n().", path="m.ts",
                                 range=si.SourceRange(2, 5, 2, 6), enclosing=None, callable=True, name="n")
    assert si._innermost([empty, no_range], si.SourceRange(2, 5, 2, 6)) is None


# --- missing Protobuf ----------------------------------------------------------------------

class _BlockProtobuf:
    def find_spec(self, name, path=None, target=None):
        if name == "google.protobuf" or name.startswith("google.protobuf."):
            raise ModuleNotFoundError(f"No module named '{name}'")
        return None


@pytest.fixture
def no_protobuf(monkeypatch):
    for mod in [m for m in sys.modules if m.startswith("google.protobuf") or m == "reponeedle.core._scip.scip_pb2"]:
        monkeypatch.delitem(sys.modules, mod)
    import reponeedle.core._scip as vendored
    monkeypatch.delattr(vendored, "scip_pb2", raising=False)  # `from package import module` would find it
    blocker = _BlockProtobuf()
    sys.meta_path.insert(0, blocker)
    yield
    sys.meta_path.remove(blocker)


def test_missing_protobuf_gives_install_instructions(no_protobuf, tmp_path):
    with pytest.raises(si.ScipIngestionError, match=r'pip install -e "\.\[scip\]"'):
        si.load_bindings()
    status = si.protobuf_status()
    assert status["available"] is False and "scip" in status["error"]
    index = tmp_path / "index.scip"
    index.write_bytes(b"")
    with pytest.raises(si.ScipIngestionError, match="optional 'scip' extra"):
        RepoNeedleEngine.from_directory(str(tmp_path), scip_config=ScipConfig(index_path=str(index)))


def test_missing_protobuf_with_on_error_skip_still_builds(no_protobuf, tmp_path, caplog):
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    index = tmp_path / "index.scip"
    index.write_bytes(b"")
    engine = RepoNeedleEngine.from_directory(
        str(tmp_path), scip_config=ScipConfig(index_path=str(index), on_error="skip"))
    assert engine.scip_diagnostics["status"] == "skipped"
    assert "optional 'scip' extra" in engine.scip_diagnostics["error"]
    assert engine.retrieve("f", budget_tokens=500).selected_files
    assert any("SCIP ingestion skipped" in r.getMessage() for r in caplog.records)


# --- defaults and API -------------------------------------------------------------------------

def test_default_engine_has_no_scip():
    engine = RepoNeedleEngine(docs=[FileDoc(path="a.py", content="def f():\n    return 1\n")])
    assert engine.scip_diagnostics is None
    assert engine.function_graph.scip_index is None
    assert "scip" not in engine.function_graph.diagnostics
    assert all(e.provenance is None for e in engine.function_graph.edges)


def test_edge_provenance_fields_default_to_none():
    e = FunctionGraphEdge("a", "b", None, "f", "verified_call", 1.0)
    assert (e.source_symbol, e.target_symbol, e.provenance) == (None, None, None)
    assert FunctionGraphEngine().scip_index is None


def test_scip_config_validation():
    assert ScipConfig(index_path="x").on_error == "raise"
    assert ScipConfig(index_path="x").allow_project_root_mismatch is False
    with pytest.raises(Exception):
        ScipConfig(index_path="x", max_index_bytes=0)
    with pytest.raises(Exception):
        ScipConfig(index_path="x", on_error="ignore")


def test_in_memory_documents_require_a_repository_root():
    with pytest.raises(si.ScipIngestionError, match="repo_root is required"):
        RepoNeedleEngine.from_documents([FileDoc(path="a.py", content="x = 1\n")],
                                        scip_config=ScipConfig(index_path="index.scip"))


def test_from_directory_rejects_a_conflicting_repo_root(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(ValueError, match="differs from repo_dir"):
        RepoNeedleEngine.from_directory(str(tmp_path), scip_config=ScipConfig(index_path="x", repo_root=str(other)))


# --- packaging -----------------------------------------------------------------------------------

def _project():
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_protobuf_is_only_in_the_scip_extra():
    project = _project()["project"]
    assert not any(d.lower().startswith("protobuf") for d in project["dependencies"])
    assert project["optional-dependencies"]["scip"] == ["protobuf>=5.29.0,<8"]
    for name, deps in project["optional-dependencies"].items():
        if name != "scip":
            assert not any(d.lower().startswith("protobuf") for d in deps), name


def test_vendored_schema_files_ship_with_the_package():
    package_data = _project()["tool"]["setuptools"]["package-data"]["reponeedle.core._scip"]
    for name in ("scip.proto", "LICENSE", "README.md", "*.pyi"):
        assert name in package_data
    base = ROOT / "reponeedle" / "core" / "_scip"
    for name in ("__init__.py", "scip_pb2.py", "scip_pb2.pyi", "scip.proto", "LICENSE", "README.md"):
        assert (base / name).is_file(), name


def test_importing_reponeedle_does_not_import_protobuf():
    code = ("import sys, reponeedle, reponeedle.core.scip_ingestion, reponeedle.core._scip;"
            "print(any(m.startswith('google.protobuf') for m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "False"


def test_scip_module_constants():
    assert si.SCIP_REFERENCE_EDGE_TYPE == "scip_reference"
    assert si.SCIP_REFERENCE_CONFIDENCE < 1.0
    importlib.import_module("reponeedle.core._scip")
    from reponeedle.core import _scip
    assert _scip.SCHEMA_TAG == "v0.10.0" and _scip.SCHEMA_COMMIT.startswith("1c2b6db7")
