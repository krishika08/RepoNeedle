"""
V2 Stage 0 guardrails for Stage 1 (design: docs/PERSISTENT_INDEXING_DESIGN.md, sections 6.1, 10.1 and 14.3).

These tests exercise the isolated research prototype in reports/v2_completion/persistent_indexing/ (not package
code; the package has no persistence). They pin down properties the Stage 1 implementation must keep:
- integrity: for BOTH payload encodings, including the selected self-contained encoding B, every structurally valid
  corruption of a written database is rejected by the reader-side verification;
- artifact identity: kind, path, extractor fingerprint, codec and key are checked against the expected inputs;
- SQLite behaviour the writer protocol relies on;
- the research snapshot helper refuses unsafe archive members even without tarfile extraction filters.
"""

import importlib.util
import io
import sys
import tarfile
from pathlib import Path

import pytest

from equivalence_fixture import FILES, write_files
from reponeedle.engine import RepoNeedleEngine

RESEARCH = Path(__file__).resolve().parents[1] / "reports" / "v2_completion" / "persistent_indexing"


def _load(name):
    sys.path.insert(0, str(RESEARCH))
    try:
        spec = importlib.util.spec_from_file_location(f"research_{name}", RESEARCH / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(RESEARCH))


proto = _load("sqlite_prototype")
snapshot = _load("snapshot")


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    root = write_files(tmp_path_factory.mktemp("repo"), FILES)
    return RepoNeedleEngine.from_directory(str(root))


@pytest.fixture(scope="module", params=["A_shared_string_table", "B_self_contained"])
def database(request, engine, tmp_path_factory):
    enc = proto.SharedStrings() if request.param.startswith("A") else proto.InlineStrings()
    work = tmp_path_factory.mktemp(request.param)
    proto.write_db(proto.encode_all(engine, enc), work, len(engine.docs))
    return request.param, work / "prototype.sqlite3", work


def test_written_database_verifies_clean(database):
    _, path, _ = database
    assert proto.verify_database(path) == []


def test_every_corruption_is_rejected_for_both_encodings(database):
    name, path, work = database
    results = proto.corruption_suite(path, work / "corrupted")
    assert results["baseline_problems"] == []
    cases = {k: v for k, v in results.items() if isinstance(v, dict)}
    expected = set(proto.CORRUPTIONS) | (set(proto.STRING_CORRUPTIONS) if name.startswith("A") else set())
    assert set(cases) == expected
    accepted = [k for k, v in cases.items() if not v["rejected"]]
    assert accepted == [], f"{name}: corruptions accepted by the reader: {accepted}"


def test_decodable_corruption_is_caught_by_the_checksum_not_by_decoding(database):
    name, path, work = database
    copy = work / "decodable.sqlite3"
    copy.write_bytes(path.read_bytes())
    import sqlite3
    c = sqlite3.connect(copy, isolation_level=None)
    proto._corrupt_reencoded_payload(c)
    c.close()
    problems = proto.verify_database(copy)
    assert any("checksum mismatch" in p for p in problems), problems
    assert not any("does not decode" in p for p in problems)


def test_artifact_identity_is_verified_against_expected_inputs(database):
    _, path, work = database
    results = proto.corruption_suite(path, work / "identity")
    for case in ("artifact_kind_changed", "artifact_path_changed", "artifact_extractor_fp_changed",
                 "artifact_codec_changed", "artifact_key_changed_consistently_in_both_tables"):
        assert results[case]["rejected"], case
    # A key rewritten consistently in both tables still fails: the reader recomputes it from the expected inputs.
    import sqlite3
    copy = work / "forged_key.sqlite3"
    copy.write_bytes(path.read_bytes())
    c = sqlite3.connect(copy, isolation_level=None)
    proto._change_key_consistently(c)
    c.close()
    assert any("key does not match the expected inputs" in p for p in proto.verify_database(copy))


def test_manifest_ordinals_are_dense(engine):
    data = proto.encode_all(engine, proto.InlineStrings())
    ordinals = [row[1] for row in data["manifest"]]
    assert ordinals == list(range(len(ordinals)))


def test_sqlite_settings_behaviour_the_writer_protocol_relies_on(tmp_path):
    behaviour = proto.pragma_behaviour(tmp_path)
    assert behaviour["synchronous_inside_transaction"].startswith("error")
    assert behaviour["foreign_keys_set_inside_transaction (read back)"] == 0
    assert behaviour["auto_vacuum_after_first_table (2 = incremental)"] == 0
    assert behaviour["journal_mode_after_reopen (persistent)"] == "wal"
    assert behaviour["python_default_isolation_pragma_after_insert"].startswith("error")


def test_writer_connection_verifies_its_settings(tmp_path):
    c = proto.open_writer(tmp_path / "w.sqlite3")
    assert c.execute("PRAGMA synchronous").fetchone()[0] == 2
    assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert c.execute("PRAGMA auto_vacuum").fetchone()[0] == 2
    c.close()


# ---------------------------------------------------------------------------------------------------------------
# Snapshot helper: unsafe archive members are refused before anything is written
# ---------------------------------------------------------------------------------------------------------------

def _tar(*members):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for info, data in members:
            tar.addfile(info, io.BytesIO(data) if data is not None else None)
    return buf.getvalue()


def _file(name, data=b"x"):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    return info, data


def _link(name, target, kind=tarfile.SYMTYPE):
    info = tarfile.TarInfo(name)
    info.type = kind
    info.linkname = target
    return info, None


UNSAFE = {
    "parent traversal": _tar(_file("../escape.txt")),
    "nested traversal": _tar(_file("a/../../escape.txt")),
    "absolute path": _tar(_file("/etc/escape.txt")),
    "backslash path": _tar(_file("a\\..\\..\\escape.txt")),
    "drive letter": _tar(_file("C:/escape.txt")),
    "empty component": _tar(_file("a//b.txt")),
    "symlink": _tar(_link("link", "/etc/passwd")),
    "hard link": _tar(_file("ok.txt"), _link("hard", "ok.txt", tarfile.LNKTYPE)),
    "symlink then file through it": _tar(_link("dir", ".."), _file("dir/escape.txt")),
}


@pytest.mark.parametrize("use_filter", [True, False], ids=["with_filter", "legacy_fallback"])
@pytest.mark.parametrize("case", sorted(UNSAFE))
def test_snapshot_extraction_refuses_unsafe_members(tmp_path, case, use_filter):
    dest = tmp_path / "dest"
    dest.mkdir()
    with pytest.raises(ValueError):
        snapshot.extract_archive(UNSAFE[case], dest, use_filter=use_filter)
    assert list(dest.iterdir()) == [], "nothing may be written when any member is unsafe"
    assert not (tmp_path / "escape.txt").exists()


@pytest.mark.parametrize("use_filter", [True, False], ids=["with_filter", "legacy_fallback"])
def test_snapshot_extraction_accepts_regular_files_and_directories(tmp_path, use_filter):
    dir_info = tarfile.TarInfo("pkg")
    dir_info.type = tarfile.DIRTYPE
    dir_info.mode = 0o755
    data = _tar((dir_info, None), _file("pkg/mod.py", b"print(1)\n"), _file("README.md", b"# r\n"))
    snapshot.extract_archive(data, tmp_path, use_filter=use_filter)
    assert (tmp_path / "pkg" / "mod.py").read_bytes() == b"print(1)\n"
