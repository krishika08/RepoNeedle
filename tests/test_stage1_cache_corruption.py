"""
V2 Stage 1: corrupt, foreign or inconsistent caches are rejected as a WHOLE by the production reader
(reponeedle.core.index_cache.store.load_generation) and handled by the rebuild policy:
- "auto": set aside, rebuilt, results identical to a fresh uncached build;
- "never": IndexCacheError naming the reason;
- "always": the cache is not read.
Nothing from a corrupt database is ever partially reused.
"""

import hashlib
import shutil
import sqlite3
import zlib

import pytest

from cache_support import assert_same_as_fresh, cache_config, cached, db_path, last, make_repo
from reponeedle.core.index_cache import IndexCacheError
from reponeedle.core.index_cache.connection import open_reader
from reponeedle.core.index_cache.errors import CacheUnusable
from reponeedle.core.index_cache.fingerprints import extractor_fingerprints
from reponeedle.core.index_cache.paths import locate
from reponeedle.core.index_cache.store import load_generation


def _sql(path, *statements):
    conn = sqlite3.connect(str(path), isolation_level=None)   # foreign keys OFF: external corruption
    for statement, *args in statements:
        conn.execute(statement, *args)
    conn.close()


def _first_key(path, kind="lexical"):
    conn = sqlite3.connect(str(path))
    key = conn.execute("SELECT artifact_key FROM artifacts WHERE kind = ? ORDER BY artifact_key LIMIT 1",
                       (kind,)).fetchone()[0]
    conn.close()
    return key


def _reencode_lexical(path):
    """Structurally valid payload with one changed weight: decodes cleanly, must fail the checksum."""
    from reponeedle.core.index_cache import codecs

    conn = sqlite3.connect(str(path), isolation_level=None)
    key, payload = conn.execute("SELECT artifact_key, payload FROM artifacts WHERE kind = 'lexical' "
                                "ORDER BY artifact_key LIMIT 1").fetchone()
    counts, length = codecs.decode_lexical(payload)
    first = next(iter(counts))
    counts[first] += 1.0
    altered = codecs.encode_lexical(counts, length)
    codecs.decode_lexical(altered)
    conn.execute("UPDATE artifacts SET payload = ? WHERE artifact_key = ?", (altered, key))
    conn.close()


def _swap_payloads(path):
    conn = sqlite3.connect(str(path), isolation_level=None)
    (k1, p1), (k2, p2) = conn.execute("SELECT artifact_key, payload FROM artifacts WHERE kind = 'semantic' "
                                      "ORDER BY artifact_key LIMIT 2").fetchall()
    conn.execute("UPDATE artifacts SET payload = ? WHERE artifact_key = ?", (p2, k1))
    conn.execute("UPDATE artifacts SET payload = ? WHERE artifact_key = ?", (p1, k2))
    conn.close()


def _forge_key(path):
    old = _first_key(path)
    new = hashlib.sha256(b"forged" + old).digest()
    _sql(path, ("UPDATE artifacts SET artifact_key = ? WHERE artifact_key = ?", (new, old)),
         ("UPDATE file_artifacts SET artifact_key = ? WHERE artifact_key = ?", (new, old)))


def _flip_payload_bytes(path):
    """Flips one byte INSIDE a stored payload in the raw file (SQLite itself does not notice)."""
    conn = sqlite3.connect(str(path))
    payload = conn.execute("SELECT payload FROM artifacts WHERE kind = 'semantic' ORDER BY length(payload) DESC "
                           "LIMIT 1").fetchone()[0]
    conn.close()
    raw = bytearray(path.read_bytes())
    at = raw.find(payload[: min(64, len(payload))])
    assert at > 0, "payload not found contiguously in the file"
    raw[at + 20] ^= 0x5A
    path.write_bytes(bytes(raw))


def _damage_page_bytes(path):
    raw = bytearray(path.read_bytes())
    for i in range(100, 220):          # page 1 b-tree header and cell pointers (sqlite_master)
        raw[i] ^= 0xFF
    path.write_bytes(bytes(raw))


def _truncate(path):
    raw = path.read_bytes()
    path.write_bytes(raw[: len(raw) // 2])


CORRUPTIONS = {
    "main_database_truncated": (_truncate, None),
    "page_bytes_changed": (_damage_page_bytes, None),
    "payload_bytes_changed_in_the_file": (_flip_payload_bytes, None),
    "payload_reencoded_but_valid": (_reencode_lexical, "checksum"),
    "payloads_swapped": (_swap_payloads, "checksum"),
    "artifact_kind_changed": (lambda p: _sql(p, ("UPDATE artifacts SET kind = 'abstainer' WHERE artifact_key = ?",
                                                 (_first_key(p),))), "metadata"),
    "artifact_path_changed": (lambda p: _sql(p, ("UPDATE artifacts SET path = 'elsewhere.py' WHERE artifact_key = ?",
                                                 (_first_key(p),))), "metadata"),
    "artifact_extractor_fp_changed": (lambda p: _sql(p, (
        "UPDATE artifacts SET extractor_fp = ? WHERE artifact_key = ?", (b"\x01" * 32, _first_key(p)))), "key"),
    "document_metadata_digest_changed": (lambda p: _sql(p, (
        "UPDATE manifest SET doc_meta_sha256 = ? WHERE ordinal = 0", (b"\x02" * 32,))), "manifest digest"),
    "artifact_key_forged_consistently": (_forge_key, "manifest digest"),
    "manifest_digest_changed": (lambda p: _sql(p, (
        "UPDATE generations SET manifest_sha256 = ? WHERE state = 'published'", (b"\x03" * 32,))),
        "manifest digest"),
    "artifact_mapping_missing": (lambda p: _sql(p, (
        "DELETE FROM file_artifacts WHERE kind = 'lexical' AND path = (SELECT min(path) FROM file_artifacts)",)),
        "manifest digest"),
    "referenced_artifact_deleted": (lambda p: _sql(p, ("DELETE FROM artifacts WHERE artifact_key = ?",
                                                       (_first_key(p),))), "missing"),
    "generation_id_changed": (lambda p: _sql(p, ("UPDATE meta SET value = '999' WHERE key = 'current_generation'",)),
                              "not published"),
    "generation_unpublished": (lambda p: _sql(p, ("UPDATE generations SET state = 'building'",)), "not published"),
    "global_state_changed": (lambda p: _sql(p, ("UPDATE global_state SET payload = ?",
                                                (b'{"persisted_files":1}',))), "global state"),
    "application_id_changed": (lambda p: _sql(p, ("PRAGMA application_id = 1",)), "application_id"),
    "schema_version_unsupported": (lambda p: _sql(p, ("PRAGMA user_version = 7",)), "unsupported schema"),
    "repository_root_changed": (lambda p: _sql(p, ("UPDATE meta SET value = 'C:/elsewhere' WHERE key = 'repo_root'",)),
                                "different repository"),
    "manifest_path_traversal": (lambda p: _sql(p, ("PRAGMA foreign_keys = OFF",),
                                               ("UPDATE manifest SET path = '../../etc/passwd' WHERE ordinal = 0",)),
                                "digest"),
}


@pytest.mark.parametrize("name", sorted(CORRUPTIONS))
def test_corruption_is_rejected_and_rebuilt(tmp_path, name):
    corrupt, reason = CORRUPTIONS[name]
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    path = db_path(cfg)
    corrupt(path)

    with pytest.raises(IndexCacheError) as err:
        cached(repo, cache_config(tmp_path, rebuild_policy="never"))
    if reason:
        assert reason in str(err.value), str(err.value)

    engine = cached(repo, cfg)
    r = last(engine)
    assert r["rebuilt_from_scratch"] and "set aside" in r["reason"], r
    assert r["files_reused"] == 0 and r["state"] == "published"
    assert any(p.name.startswith(path.name + ".corrupt-") for p in path.parent.iterdir())
    assert_same_as_fresh(engine, repo, f"rebuilt after {name}", packing_queries=None)
    assert last(cached(repo, cfg))["files_reused"] == len(engine.docs), "the rebuilt cache must be usable"


def test_rebuild_policy_always_never_reads_a_corrupt_cache(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    _reencode_lexical(db_path(cfg))
    engine = cached(repo, cache_config(tmp_path, rebuild_policy="always"))
    assert last(engine)["state"] == "published"
    assert_same_as_fresh(engine, repo, "always after corruption", packing_queries=None)


def test_rebuild_policy_always_replaces_a_file_that_is_not_a_database(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    path = db_path(cfg)
    path.write_bytes(b"\x00not a database" * 200)
    engine = cached(repo, cache_config(tmp_path, rebuild_policy="always"))
    r = last(engine)
    assert r["state"] == "published" and "set aside" in r["reason"], r
    assert any(p.name.startswith(path.name + ".corrupt-") for p in path.parent.iterdir())
    assert last(cached(repo, cfg))["files_reused"] == len(engine.docs)


def test_a_locked_database_is_never_set_aside(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    holder = sqlite3.connect(str(db_path(cfg)), isolation_level=None)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        engine = cached(repo, cache_config(tmp_path, rebuild_policy="always", busy_timeout_s=0.2))
    finally:
        holder.execute("ROLLBACK")
        holder.close()
    assert last(engine)["state"] == "not_persisted"
    assert not any(".corrupt-" in p.name for p in db_path(cfg).parent.iterdir())
    assert_same_as_fresh(engine, repo, "locked database", packing_queries=None)


def test_reader_rejects_without_partial_reuse(tmp_path, monkeypatch):
    """A single bad artifact makes load_generation fail as a whole: no LoadedGeneration is ever returned."""
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    engine = cached(repo, cfg)
    _reencode_lexical(db_path(cfg))
    loc = locate(str(repo), cfg.cache_dir)
    fps = {k: bytes.fromhex(v) for k, v in extractor_fingerprints(engine).items()}
    conn = open_reader(db_path(cfg), 5.0, read_only=False)
    with pytest.raises(CacheUnusable, match="checksum"):
        load_generation(conn, loc.repo_root, loc.repo_id, fps)
    conn.close()


def test_damaged_wal_and_shm_sidecars_never_change_results(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    path = db_path(cfg)
    for suffix in ("-wal", "-shm"):
        (path.parent / (path.name + suffix)).write_bytes(b"\x00garbage" * 512)
    engine = cached(repo, cfg)
    assert last(engine)["state"] == "published"
    assert_same_as_fresh(engine, repo, "garbage WAL/SHM sidecars", packing_queries=None)


def test_database_copied_without_its_wal_is_a_consistent_earlier_state(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    path = db_path(cfg)
    holder = sqlite3.connect(str(path), isolation_level=None)
    holder.execute("PRAGMA wal_autocheckpoint = 0")
    holder.execute("BEGIN IMMEDIATE")
    holder.execute("UPDATE meta SET value = 'changed-after-copy' WHERE key = 'created_by'")
    holder.execute("COMMIT")                        # committed into the WAL, not checkpointed
    copy_dir = tmp_path / "copied"
    copy_dir.mkdir()
    shutil.copyfile(path, copy_dir / path.name)     # the main file only, as a careless copy would
    holder.close()
    copied_cfg = cache_config(tmp_path).model_copy(update={"cache_dir": str(copy_dir)})
    engine = cached(repo, copied_cfg)
    assert last(engine)["files_reused"] == len(engine.docs), last(engine)
    assert_same_as_fresh(engine, repo, "main file without its WAL", packing_queries=None)


def test_malformed_compressed_payload_is_rejected(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    bomb = zlib.compress(b"\x00" * (80 * 1024 * 1024))
    from reponeedle.core.index_cache import codecs

    with pytest.raises(codecs.CodecError, match="size limit"):
        codecs.decode_semantic(bomb)
    with pytest.raises(codecs.CodecError):
        codecs.decode_semantic(b"not zlib at all")
