"""
Repository validation for SCIP indexes (optional `scip` extra): project-root matching, path canonicality
and containment, symlink escapes, missing and unindexed documents, freshness, and no file reads.
"""

import builtins
import io
import os
import sys
from pathlib import Path

import pytest

from scip_support import build_index, doc, occ, pkg, require_protobuf, sym, write_index, write_repo

require_protobuf()

from reponeedle.core.scip_ingestion import ScipIndex, ScipIngestionError  # noqa: E402
from reponeedle.engine import RepoNeedleEngine  # noqa: E402
from reponeedle.models import FileDoc, ScipConfig  # noqa: E402

A_TS = "export function f() {\n  return 1;\n}\n"
F = pkg("a", "f")


def _repo(tmp_path, files=None, name="repo"):
    root = tmp_path / name
    root.mkdir()
    write_repo(root, files or {"a.ts": A_TS})
    return root


def _docs(root):
    return [FileDoc(path=p.relative_to(root).as_posix(), content=p.read_text(encoding="utf-8"))
            for p in sorted(root.rglob("*.ts"))]


def _index(root, documents, project_root=None):
    return ScipIndex.from_bytes(build_index(project_root if project_root is not None else root.as_uri(), documents))


def _def_doc(path="a.ts", **kw):
    return doc(path, [occ(F, [0, 16, 17], roles=1)], [sym(F)], **kw)


# --- project root ---------------------------------------------------------------------------

def test_matching_root(tmp_path):
    root = _repo(tmp_path)
    index = _index(root, [_def_doc()])
    assert index.validate_root(str(root)) == "match"
    d = index.resolve(_docs(root)).diagnostics
    assert d["project_root"]["status"] == "match" and d["documents"]["matched"] == 1


def test_mismatched_root_is_refused_unless_allowed(tmp_path):
    root = _repo(tmp_path)
    other = tmp_path / "elsewhere"
    other.mkdir()
    index = _index(root, [_def_doc()], project_root=other.as_uri())
    with pytest.raises(ScipIngestionError, match="was generated for project_root"):
        index.validate_root(str(root))
    assert index.validate_root(str(root), allow_mismatch=True) == "mismatch"
    assert index.resolve(_docs(root)).diagnostics["documents"]["matched"] == 1  # paths still validated


def test_uri_encoded_root_with_spaces_and_unicode(tmp_path):
    root = _repo(tmp_path, name="my repo ü %20")
    uri = root.as_uri()
    assert "%20" in uri and "%C3%BC" in uri
    assert _index(root, [_def_doc()], project_root=uri).validate_root(str(root)) == "match"


def test_trailing_slash_and_localhost_forms_match(tmp_path):
    root = _repo(tmp_path)
    uri = root.as_uri()
    for variant in (uri + "/", "file://localhost" + uri[len("file://"):]):
        assert _index(root, [], project_root=variant).validate_root(str(root)) == "match", variant


def test_windows_drive_letter_forms(tmp_path):
    root = _repo(tmp_path)
    uri = root.as_uri()
    if os.name == "nt":
        drive = str(root)[0]
        for variant in (uri.replace(f"/{drive}:", f"/{drive.lower()}:"), uri.replace(f"/{drive}:", f"/{drive}%3A")):
            assert _index(root, [], project_root=variant).validate_root(str(root)) == "match", variant
    else:
        index = _index(root, [], project_root="file:///C:/work/repo")
        assert index.validate_root(str(root), allow_mismatch=True) == "mismatch"


@pytest.mark.parametrize("project_root,status", [("", "unverifiable"), ("relative/path", "unverifiable"),
                                                 ("https://example.com/repo", "unverifiable")])
def test_unverifiable_roots(tmp_path, project_root, status):
    root = _repo(tmp_path)
    index = _index(root, [], project_root=project_root)
    with pytest.raises(ScipIngestionError, match=status):
        index.validate_root(str(root))


def test_engine_reports_root_mismatch_actionably(tmp_path):
    root = _repo(tmp_path)
    path = write_index(tmp_path, build_index("file:///somewhere/else", [_def_doc()]))
    with pytest.raises(ScipIngestionError, match="Regenerate the index in this checkout"):
        RepoNeedleEngine.from_directory(str(root), scip_config=ScipConfig(index_path=path))


# --- document paths ----------------------------------------------------------------------------

@pytest.mark.parametrize("bad,reason", [
    ("../outside.ts", "'.' or '..'"), ("sub/../../outside.ts", "'.' or '..'"), ("./a.ts", "'.' or '..'"),
    ("/etc/passwd", "absolute"), ("C:/Windows/win.ini", "absolute"), ("a//b.ts", "empty path component"),
    ("", "empty path"),
])
def test_non_canonical_document_paths_are_rejected(tmp_path, bad, reason):
    root = _repo(tmp_path)
    (tmp_path / "outside.ts").write_text("export function secret() {}\n", encoding="utf-8")
    index = _index(root, [_def_doc(), doc(bad, [occ(F, [0, 0, 1])])])
    index.validate_root(str(root))
    d = index.resolve(_docs(root)).diagnostics
    assert reason in d["documents"]["rejected"][bad]
    assert d["documents"]["matched"] == 1


def test_backslash_paths_only_normalized_for_windows_indexes(tmp_path):
    root = _repo(tmp_path, {"src/a.ts": A_TS})
    posix_index = _index(root, [doc("src\\a.ts", [occ(F, [0, 16, 17], roles=1)], [sym(F)])])
    posix_index.validate_root(str(root))
    d = posix_index.resolve(_docs(root)).diagnostics["documents"]
    if os.name == "nt":  # the root URI of a Windows temp dir is a Windows path
        assert d["backslash_paths_normalized"] == 1 and d["matched"] == 1
    else:
        assert d["backslash_paths_normalized"] == 0 and "backslash" in d["rejected"]["src\\a.ts"]
    win_index = _index(root, [doc("src\\a.ts", [occ(F, [0, 16, 17], roles=1)], [sym(F)])],
                       project_root="file:///C:/build/repo")
    win_index.validate_root(str(root), allow_mismatch=True)
    d = win_index.resolve(_docs(root)).diagnostics["documents"]
    assert d["backslash_paths_normalized"] == 1 and d["matched"] == 1


def _make_dir_link(link: Path, target: Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        if sys.platform != "win32":
            raise
        import _winapi
        _winapi.CreateJunction(str(target), str(link))


def test_directory_link_escape_is_rejected(tmp_path):
    root = _repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.ts").write_text("export function secret() {}\n", encoding="utf-8")
    _make_dir_link(root / "linked", outside)
    index = _index(root, [_def_doc(), doc("linked/secret.ts", [occ(pkg("s", "secret"), [0, 16, 22], roles=1)],
                                          [sym(pkg("s", "secret"))])])
    index.validate_root(str(root))
    res = index.resolve(_docs(root) + [FileDoc(path="linked/secret.ts", content="export function secret() {}\n")])
    assert res.diagnostics["documents"]["rejected"]["linked/secret.ts"] == "resolves outside the repository"
    assert pkg("s", "secret") not in res.definitions


def test_file_symlink_document_is_rejected(tmp_path):
    root = _repo(tmp_path)
    try:
        os.symlink(root / "a.ts", root / "alias.ts")
    except (OSError, NotImplementedError):
        pytest.skip("file symlink creation not permitted on this host")
    index = _index(root, [doc("alias.ts", [occ(F, [0, 16, 17], roles=1)], [sym(F)])])
    index.validate_root(str(root))
    d = index.resolve(_docs(root)).diagnostics
    assert "symbolic link" in d["documents"]["rejected"]["alias.ts"]


def test_missing_and_unindexed_documents_are_diagnosed(tmp_path):
    root = _repo(tmp_path, {"a.ts": A_TS, "notes/readme.txt": "text\n"})
    index = _index(root, [_def_doc(), doc("gone.ts"), doc("notes/readme.txt")])
    index.validate_root(str(root))
    d = index.resolve(_docs(root)).diagnostics["documents"]
    assert d["missing"] == ["gone.ts"]
    assert d["not_indexed_by_reponeedle"] == ["notes/readme.txt"]
    assert d["matched"] == 1


def test_duplicate_documents_use_the_first(tmp_path):
    root = _repo(tmp_path)
    index = _index(root, [_def_doc(), _def_doc()])
    index.validate_root(str(root))
    d = index.resolve(_docs(root)).diagnostics["documents"]
    assert d["matched"] == 1 and d["duplicate"] == ["a.ts"]


def test_case_differences(tmp_path):
    root = _repo(tmp_path, {"src/Cart.ts": A_TS})
    index = _index(root, [doc("SRC/cart.ts", [occ(F, [0, 16, 17], roles=1)], [sym(F)])])
    index.validate_root(str(root))
    d = index.resolve(_docs(root)).diagnostics["documents"]
    if os.name == "nt":  # case-insensitive file system: unique case-folded match is accepted and counted
        assert d["matched"] == 1 and d["matched_case_insensitive"] == 1
    else:
        assert d["matched"] == 0 and d["missing"] == ["SRC/cart.ts"]


# --- freshness -----------------------------------------------------------------------------------

def test_freshness_identical_text_is_verified(tmp_path):
    root = _repo(tmp_path)
    index = _index(root, [_def_doc(text=A_TS.replace("\n", "\r\n"))])  # line endings are normalised
    index.validate_root(str(root))
    fr = index.resolve(_docs(root)).diagnostics["freshness"]
    assert fr == {"verified_identical": 1, "stale": 0, "unverified_no_text": 0, "status": "verified"}


def test_stale_documents_are_skipped(tmp_path):
    root = _repo(tmp_path)
    index = _index(root, [_def_doc(text="export function f() {\n  return 2;\n}\n")])
    index.validate_root(str(root))
    res = index.resolve(_docs(root))
    assert res.diagnostics["freshness"]["status"] == "stale_documents_skipped"
    assert res.diagnostics["documents"]["stale"] == 1 and res.definitions == {}


def test_documents_without_text_are_unverified(tmp_path):
    root = _repo(tmp_path)
    index = _index(root, [_def_doc()])
    index.validate_root(str(root))
    assert index.resolve(_docs(root)).diagnostics["freshness"]["status"] == "unverified"


def test_out_of_bounds_ranges_are_dropped(tmp_path):
    root = _repo(tmp_path)
    index = _index(root, [doc("a.ts", [occ(F, [0, 16, 17], roles=1), occ(F, [99, 0, 1]), occ(F, [0, 500, 501])],
                              [sym(F)])])
    index.validate_root(str(root))
    d = index.resolve(_docs(root)).diagnostics["occurrences"]
    assert d["total"] == 3 and d["out_of_bounds"] == 2


# --- no file reads ----------------------------------------------------------------------------------

def test_resolution_never_opens_files(tmp_path, monkeypatch):
    root = _repo(tmp_path)
    (tmp_path / "outside.ts").write_text("export function secret() {}\n", encoding="utf-8")
    index = _index(root, [_def_doc(), doc("../outside.ts"), doc("a.ts")])
    index.validate_root(str(root))
    docs = _docs(root)

    def refuse(*args, **kwargs):
        raise AssertionError(f"file opened during resolution: {args[0]!r}")

    monkeypatch.setattr(builtins, "open", refuse)
    monkeypatch.setattr(io, "open", refuse)
    index.resolve(docs)
