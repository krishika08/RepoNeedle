"""
V2 Stage 1: units of the persistent index cache (codecs, artifact identity, checksums, manifest digest,
fingerprints, configuration, paths, connection settings, and static security invariants).
"""

import ast
import math
import os
import sqlite3
import struct
from pathlib import Path

import pytest
from pydantic import ValidationError

from reponeedle.core.function_graph import CallSite, FunctionSymbol
from reponeedle.core.index_cache import codecs, connection, fingerprints, paths, schema
from reponeedle.core.index_cache.errors import PersistenceUnavailable
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import AblationConfig, IndexCacheConfig

PKG = Path(__file__).resolve().parents[1] / "reponeedle" / "core" / "index_cache"


# ------------------------------------------------------------------------------------------------------ codecs

def test_codecs_round_trip_exactly():
    meta = {"language": "python", "is_test": False, "line_count": 3, "token_count": 17, "symbols": ["a", "größe"],
            "imports": ["os", "翻訳"]}
    assert codecs.decode_doc_meta(codecs.encode_doc_meta(meta)) == meta
    counts = {"cart": 3.5, "total": 2.0, "größe": 0.1 + 0.2, "x" * 300: 1e-300}
    got, length = codecs.decode_lexical(codecs.encode_lexical(counts, 12.25))
    assert list(got.items()) == list(counts.items()) and length == 12.25
    assert all(struct.pack("<d", got[k]) == struct.pack("<d", v) for k, v in counts.items())
    feats = {"<ca": 2, "car": 1, "🛒": 7}
    assert list(codecs.decode_semantic(codecs.encode_semantic(feats)).items()) == list(feats.items())
    vocab = {"zeta", "alpha", "größe"}
    assert codecs.decode_vocab(codecs.encode_vocab(vocab)) == vocab
    funcs = [FunctionSymbol("f", None, "a.py", False, False, 3, ["x"]),
             FunctionSymbol("m", "C", "a.py", True, True, 9, [])]
    calls = [CallSite("a.py", "f", "g", True, "obj", 4, None), CallSite("a.py", None, "h", False, None, 1, "q.r")]
    decoded = codecs.decode_polyglot(codecs.encode_polyglot((funcs, calls, ["f"], ["os"])))
    assert decoded == (funcs, calls, ["f"], ["os"])
    assert type(decoded[0][0].is_method) is bool and type(decoded[0][0].start_line) is int


def test_codecs_are_canonical():
    assert codecs.encode_vocab({"b", "a"}) == codecs.encode_vocab({"a", "b"})
    meta = {"language": "go", "is_test": True, "line_count": 1, "token_count": 2, "symbols": [], "imports": []}
    assert codecs.encode_doc_meta(meta) == codecs.encode_doc_meta(dict(reversed(list(meta.items()))))


@pytest.mark.parametrize("kind,raw", [
    ("semantic", b'{"c":[0],"f":["ab"]}'),                       # count 0
    ("semantic", b'{"c":[1,1],"f":["a","a"]}'),                  # duplicate feature
    ("semantic", b'{"c":[1],"f":["a","b"]}'),                    # length mismatch
    ("semantic", b'{"c":[1.0],"f":["a"]}'),                      # float count
    ("semantic", b'{"c":[1],"f":["a"],"x":1}'),                  # unexpected key
    ("abstainer", b'["b","a"]'),                                 # not sorted
    ("abstainer", b'["a","a"]'),                                 # not unique
    ("lexical", b'{"l":1.0,"t":["a"],"w":[NaN]}'),               # NaN
    ("lexical", b'{"l":1.0,"t":["a"],"w":[1]}'),                 # int where a float is stored
    ("lexical", b'{"l":1.0,"t":["a","a"],"w":[1.0,2.0]}'),       # duplicate term
    ("doc_meta", b'{"language":"py"}'),
    ("doc_meta", b'{"imports":[],"is_test":1,"language":"py","line_count":1,"symbols":[],"token_count":1}'),
    ("function_graph", b'{"calls":[],"functions":[["f",null,"a",0,false,1,[]]],"imports":[],"symbols":[]}'),
    ("semantic", bytes([0xFF, 0xFE]) + b" not utf-8"),
])
def test_codecs_reject_malformed_payloads(kind, raw):
    import zlib

    with pytest.raises(codecs.CodecError):
        codecs.decode(kind, codecs.CODECS[kind], zlib.compress(raw))


def test_codec_mismatch_and_decompression_limits():
    import zlib

    with pytest.raises(codecs.CodecError, match="unexpected codec"):
        codecs.decode("semantic", "bm25-terms/1", zlib.compress(b"\x00"))
    with pytest.raises(codecs.CodecError):
        codecs.decode_vocab(zlib.compress(b"\x00")[:-2])               # truncated stream
    with pytest.raises(codecs.CodecError):
        codecs.decode_vocab(zlib.compress(b"\x00") + b"junk")          # trailing data


# ------------------------------------------------------------------------------------------- artifact identity

BASE = dict(kind="lexical", extractor_fp=b"\x01" * 32, path="a/b.py", text_sha256=b"\x02" * 32,
            doc_meta_sha256=b"\x03" * 32, input_sig=b"\x04" * 32)


@pytest.mark.parametrize("field,value", [
    ("kind", "semantic"), ("extractor_fp", b"\x09" * 32), ("path", "a/c.py"), ("text_sha256", b"\x09" * 32),
    ("doc_meta_sha256", b"\x09" * 32), ("input_sig", b"\x09" * 32)])
def test_artifact_key_covers_every_input(field, value):
    assert schema.artifact_key(**{**BASE, field: value}) != schema.artifact_key(**BASE)


def test_artifact_key_framing_is_unambiguous():
    a = schema.artifact_key(**{**BASE, "kind": "ab", "path": "c"})
    b = schema.artifact_key(**{**BASE, "kind": "a", "path": "bc"})
    assert a != b


def test_input_signature_carries_extractor_configuration():
    from reponeedle.core.lexical import BM25Index
    from reponeedle.models import FileDoc

    doc = FileDoc(path="a.py", content="def f():\n    return 1\n", symbols=["f"])
    assert BM25Index(path_weight=3.0).doc_signature(doc) != BM25Index().doc_signature(doc)


@pytest.mark.parametrize("index", range(7))
def test_artifact_checksum_binds_every_column(index):
    args = [b"k" * 32, "lexical", b"f" * 32, "a.py", b"s" * 32, "bm25-terms/1", b"payload"]
    changed = list(args)
    changed[index] = (changed[index] + b"x") if isinstance(changed[index], bytes) else changed[index] + "x"
    assert schema.artifact_checksum(*changed) != schema.artifact_checksum(*args)


def test_global_checksum_binds_name_generation_codec_and_payload():
    base = ("s", 1, "c", b"p")
    for variant in (("t", 1, "c", b"p"), ("s", 2, "c", b"p"), ("s", 1, "d", b"p"), ("s", 1, "c", b"q")):
        assert schema.global_checksum(*variant) != schema.global_checksum(*base)


def test_manifest_digest_is_order_independent_and_generation_bound():
    m = [("b.py", 1, b"\x01" * 32, "python", 0, 1, 1, b"\x02" * 32), ("a.py", 0, b"\x03" * 32, "python", 1, 2, 3,
                                                                       b"\x04" * 32)]
    fa = [("a.py", "lexical", b"\x05" * 32), ("b.py", "lexical", b"\x06" * 32)]
    d1 = schema.manifest_digest(1, m, fa, [], [("scip", "x")])
    assert d1 == schema.manifest_digest(1, list(reversed(m)), list(reversed(fa)), [], [("scip", "x")])
    assert d1 != schema.manifest_digest(2, m, fa, [], [("scip", "x")])
    assert d1 != schema.manifest_digest(1, m[:1], fa, [], [("scip", "x")])
    with pytest.raises(ValueError):
        schema.manifest_digest(1, m + m[:1], fa, [], [])


def test_doc_meta_digest_covers_every_field():
    meta = {"language": "python", "is_test": False, "line_count": 1, "token_count": 2, "symbols": ["a"],
            "imports": []}
    for k, v in (("language", "go"), ("is_test", True), ("line_count", 2), ("token_count", 3), ("symbols", ["b"]),
                 ("imports", ["os"])):
        assert schema.doc_meta_digest({**meta, k: v}) != schema.doc_meta_digest(meta)


# ------------------------------------------------------------------------------------------------ fingerprints

def test_fingerprints_follow_configuration_versions_and_sources(monkeypatch):
    base = fingerprints.extractor_fingerprints(RepoNeedleEngine())
    assert set(base) == set(schema.KINDS)
    poly = fingerprints.extractor_fingerprints(RepoNeedleEngine(ablation_config=AblationConfig(
        enable_polyglot_symbols=True)))
    assert poly["doc_meta"] != base["doc_meta"] and poly["lexical"] == base["lexical"]
    monkeypatch.setitem(fingerprints.ARTIFACT_VERSIONS, "abstainer", 2)
    bumped = fingerprints.extractor_fingerprints(RepoNeedleEngine())
    assert bumped["abstainer"] != base["abstainer"] and bumped["semantic"] == base["semantic"]
    monkeypatch.setitem(fingerprints.ARTIFACT_VERSIONS, "abstainer", 1)
    real = fingerprints.module_source_digest
    # V2 Stage 3: per-document semantic extraction lives in semantic_features; semantic.py is global assembly only.
    monkeypatch.setattr(fingerprints, "module_source_digest",
                        lambda n: "edited" if n == "reponeedle.core.semantic_features" else real(n))
    edited = fingerprints.extractor_fingerprints(RepoNeedleEngine())
    assert edited["semantic"] != base["semantic"] and edited["lexical"] == base["lexical"]
    monkeypatch.setattr(fingerprints, "module_source_digest",
                        lambda n: "edited" if n == "reponeedle.core.semantic" else real(n))
    assert fingerprints.extractor_fingerprints(RepoNeedleEngine()) == base


def test_source_digest_ignores_line_endings_only(tmp_path, monkeypatch):
    import importlib
    import sys

    (tmp_path / "rn_probe_mod.py").write_bytes(b"x = 1\r\ny = 2\r\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    sys.modules.pop("rn_probe_mod", None)
    crlf = fingerprints.module_source_digest.__wrapped__("rn_probe_mod")
    (tmp_path / "rn_probe_mod.py").write_bytes(b"x = 1\ny = 2\n")
    assert fingerprints.module_source_digest.__wrapped__("rn_probe_mod") == crlf
    (tmp_path / "rn_probe_mod.py").write_bytes(b"x = 1\ny = 3\n")
    assert fingerprints.module_source_digest.__wrapped__("rn_probe_mod") != crlf


def test_discovery_fingerprint_covers_ignore_rules_and_limits():
    base = fingerprints.discovery_fingerprint(["a"], 10, 100)
    assert base != fingerprints.discovery_fingerprint(["a", "b"], 10, 100)
    assert base != fingerprints.discovery_fingerprint(["a"], 11, 100)
    assert base != fingerprints.discovery_fingerprint(["a"], 10, 101)


# --------------------------------------------------------------------------------------- configuration, paths

@pytest.mark.parametrize("bad", [
    {"max_db_bytes": 0}, {"max_total_bytes": -1}, {"max_db_bytes": 10, "max_total_bytes": 5},
    {"validation": "mtime"}, {"rebuild_policy": "sometimes"}, {"busy_timeout_s": 0}, {"busy_timeout_s": 7200},
    {"persist_exclude": [""]}, {"persist_exclude": ["a\x00b"]}, {"cache_dir": ""}, {"cache_dir": "a\x00"},
    {"unknown_option": True}])
def test_invalid_configuration_is_rejected(bad):
    with pytest.raises(ValidationError):
        IndexCacheConfig(**bad)


def test_repository_identity_and_file_name(tmp_path):
    loc = paths.locate(str(tmp_path), str(tmp_path / "c"))
    assert loc.repo_root == os.path.realpath(str(tmp_path))
    assert loc.repo_id == paths.repo_identity(loc.repo_root) and len(loc.repo_id) == 64
    assert loc.db_path.name == f"{loc.repo_id[:32]}-s{schema.SCHEMA_MAJOR}.sqlite3"
    assert paths.locate(str(tmp_path / "x" / ".."), str(tmp_path / "c")).repo_id == loc.repo_id
    if os.name == "nt":
        assert paths.repo_identity(loc.repo_root.upper()) == paths.repo_identity(loc.repo_root.lower())


def test_database_path_that_is_a_link_is_refused(tmp_path):
    loc = paths.locate(str(tmp_path), str(tmp_path / "c"))
    loc.cache_dir.mkdir()
    target = tmp_path / "elsewhere.sqlite3"
    target.write_bytes(b"")
    try:
        os.symlink(target, loc.db_path)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted on this host")
    with pytest.raises(PersistenceUnavailable, match="symbolic link"):
        paths.prepare_cache_dir(loc, create=False)


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_posix_permissions(tmp_path):
    from cache_support import cache_config, cached, db_path, make_repo

    cfg = cache_config(tmp_path)
    cached(make_repo(tmp_path), cfg)
    assert (Path(cfg.cache_dir).stat().st_mode & 0o777) == 0o700
    assert (db_path(cfg).stat().st_mode & 0o777) == 0o600


def test_writer_settings_are_applied_and_verified(tmp_path):
    conn = connection.open_writer(tmp_path / "w.sqlite3", 3.0)
    try:
        values = {p: conn.execute(f"PRAGMA {p}").fetchone()[0] for p in
                  ("journal_mode", "synchronous", "foreign_keys", "busy_timeout", "secure_delete", "auto_vacuum",
                   "application_id", "user_version")}
    finally:
        conn.close()
    assert values == {"journal_mode": "wal", "synchronous": 2, "foreign_keys": 1, "busy_timeout": 3000,
                      "secure_delete": 1, "auto_vacuum": 2, "application_id": schema.APPLICATION_ID,
                      "user_version": schema.SCHEMA_VERSION}


def test_settings_mismatch_refuses_the_connection(tmp_path, monkeypatch):
    real = connection._pragma
    monkeypatch.setattr(connection, "_pragma", lambda c, n: 1 if n == "synchronous" else real(c, n))
    with pytest.raises(PersistenceUnavailable, match="settings could not be applied"):
        connection.open_writer(tmp_path / "w.sqlite3", 1.0)


def test_no_pragma_inside_a_transaction_in_the_writer_protocol():
    """Static check: every PRAGMA in store.py/connection.py runs outside BEGIN...COMMIT, except the header ones."""
    text = (PKG / "store.py").read_text(encoding="utf-8")
    run_body = text[text.index("def publish("):text.index("def abandon(")]
    assert "PRAGMA" not in run_body
    conn_text = (PKG / "connection.py").read_text(encoding="utf-8")
    creation = conn_text[conn_text.index('conn.execute("BEGIN IMMEDIATE")'):conn_text.index('conn.execute("COMMIT")')]
    assert [ln.strip() for ln in creation.splitlines() if "PRAGMA" in ln] == [
        'conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")',
        'conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")']


def test_no_unsafe_deserialisation_in_the_cache_package():
    for path in PKG.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
        modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert not ({"pickle", "marshal", "shelve", "dill"} & (names | modules)), path.name
        calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert not ({"eval", "exec", "__import__"} & calls), path.name


def test_minimum_sqlite_version_is_enforced(monkeypatch):
    monkeypatch.setattr(connection, "MIN_SQLITE_VERSION", (sqlite3.sqlite_version_info[0] + 1, 0, 0))
    with pytest.raises(PersistenceUnavailable, match="older than the minimum"):
        connection.check_sqlite_version()
