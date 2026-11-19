"""
V2 Stage 2: cache-safety hardening and schema evolution.

1. Cross-process cache-use leases: size-limit eviction never deletes a database (or its WAL/SHM) that another live
   RepoNeedle process is reading or writing; a killed lease holder releases its lease; eviction proceeds once the
   database is genuinely unused; a reader that starts during an eviction waits and then builds a new cache.
2. Privacy purge: when a persisted file becomes persist_exclude'd while another connection holds an older read
   snapshot, the purge is reported (durably) as PENDING, never as complete; a later refresh completes it, after
   which no cache file contains the file's path, digest or tokens.
3. Schema version 1 -> 2: in-place migration in one transaction, idempotent, crash-safe (a crash mid-migration
   leaves version 1 intact), refused by read-only clients, with Stage 1 artifacts reused afterwards.
4. Stable file ids: assigned on first sight, kept through edits and reordering, never reused, never given to
   persist_exclude'd files, allocated transaction-safely by concurrent writers.
5. Crash injection and concurrent writers with provider changes (Stage 2 artifacts included).
"""

import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cache_support import (FILES, ROOT, TESTS, cache_config, cached, db_path, fresh, last, make_repo,
                           published_generation, run_python, write)
from reponeedle.core.index_cache import schema
from reponeedle.core.index_cache.lease import CacheLease, lease_path
from reponeedle.core.index_cache.store import enforce_total_limit
from stage2_support import (MUTATIONS, check, no_index_misses, remove, rename, reversed_discovery, synthetic_files,
                            write_tree)
from test_stage1_cache_processes import CRASH_CHILD, CRASH_POINTS, _published_digests, _repo_digests
from test_stage1_persist_exclude import SECRET_PATH, SECRET_TEXT, find_secret_traces


def _spawn(code, *args):
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT), str(TESTS)])}
    return subprocess.Popen([sys.executable, "-c", code, *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=env, cwd=str(ROOT))


def _wait_for(proc, marker, timeout=120):
    deadline = time.monotonic() + timeout
    line = proc.stdout.readline()
    while marker not in line:
        assert time.monotonic() < deadline and line, f"child did not report {marker!r}: {proc.stderr.read()[-2000:]}"
        line = proc.stdout.readline()
    return line


def _kill(proc):
    proc.kill()
    proc.wait(timeout=60)


# A child that holds a cache-use lease exactly as a reader or writer does, plus (optionally) an open SQLite read
# snapshot or write lock, until it is killed.
HOLDER = r'''
import sqlite3, sys
from pathlib import Path
from reponeedle.core.index_cache.lease import CacheLease
db, mode = Path(sys.argv[1]), sys.argv[2]
lease = CacheLease(db)
assert lease.acquire_shared(10.0)
conn = sqlite3.connect(str(db), isolation_level=None)
if mode == "reader":
    conn.execute("BEGIN"); conn.execute("SELECT count(*) FROM manifest").fetchone()
elif mode == "writer":
    conn.execute("BEGIN IMMEDIATE")
print("HELD", flush=True)
sys.stdin.read()
'''


def _two_caches(tmp_path):
    """Two repositories sharing one cache directory; returns (repo_a, repo_b, cfg, db_a, db_b)."""
    repo_a = make_repo(tmp_path, name="repo_a")
    repo_b = make_repo(tmp_path, name="repo_b")
    cfg = cache_config(tmp_path)
    cached(repo_b, cfg)
    time.sleep(0.05)
    cached(repo_a, cfg)
    dbs = sorted(Path(cfg.cache_dir).glob("*-s1.sqlite3"), key=lambda p: p.stat().st_mtime)
    return repo_a, repo_b, cfg, dbs[1], dbs[0]


def _size(db):
    return sum(Path(str(db) + s).stat().st_size for s in ("", "-wal", "-shm") if Path(str(db) + s).exists())


def _limit_cfg(tmp_path, db_a, db_b):
    limit = _size(db_a) + _size(db_b) // 2           # forces eviction of one database
    return cache_config(tmp_path, max_db_bytes=limit, max_total_bytes=limit)


# ------------------------------------------------------------------------------------------------- 1. leases

def test_a_shared_lease_blocks_the_exclusive_lease_until_its_process_dies(tmp_path):
    db = tmp_path / "x-s1.sqlite3"
    sqlite3.connect(str(db)).close()
    holder = _spawn(HOLDER, str(db), "lease")
    try:
        _wait_for(holder, "HELD")
        probe = CacheLease(db)
        assert not probe.try_exclusive(), "an exclusive lease must fail while another process holds a shared one"
    finally:
        _kill(holder)                                      # killed, no cleanup: the OS releases the lock
    probe = CacheLease(db)
    assert probe.try_exclusive()
    probe.release()


def test_shared_leases_coexist(tmp_path):
    db = tmp_path / "x-s1.sqlite3"
    a, b = CacheLease(db), CacheLease(db)
    assert a.acquire_shared(1.0) and b.acquire_shared(1.0)
    c = CacheLease(db)
    assert not c.try_exclusive()
    a.release()
    b.release()
    assert c.try_exclusive()
    c.release()


@pytest.mark.parametrize("mode", ["reader", "writer"])
def test_eviction_skips_a_database_in_use_and_evicts_it_once_unused(tmp_path, mode):
    repo_a, repo_b, cfg, db_a, db_b = _two_caches(tmp_path)
    holder = _spawn(HOLDER, str(db_b), mode)
    try:
        _wait_for(holder, "HELD")
        engine = cached(repo_a, _limit_cfg(tmp_path, db_a, db_b))
        assert last(engine)["state"] == "published"
        assert db_b.exists(), f"a database held by a live {mode} must never be deleted"
        assert "in use and were kept" in last(engine)["reason"]
        result = enforce_total_limit(Path(cfg.cache_dir), db_a, 1)
        assert result["removed"] == [] and db_b.name in result["in_use"]
    finally:
        _kill(holder)
    engine = cached(repo_a, _limit_cfg(tmp_path, db_a, db_b))
    assert not db_b.exists() and not Path(str(db_b) + "-wal").exists() and not Path(str(db_b) + "-shm").exists()
    assert "removed 1 other cache database" in last(engine)["reason"]


def test_a_reader_starting_during_an_eviction_waits_and_builds_a_new_cache(tmp_path):
    repo_a, repo_b, cfg, db_a, db_b = _two_caches(tmp_path)
    evictor = CacheLease(db_b)
    assert evictor.try_exclusive()                        # an evictor between its check and its deletion
    code = ("import sys\nfrom reponeedle.engine import RepoNeedleEngine\nfrom reponeedle.models import IndexCacheConfig\n"
            "e = RepoNeedleEngine.from_directory(sys.argv[1], index_cache=IndexCacheConfig(cache_dir=sys.argv[2]))\n"
            "r = e.index_cache_diagnostics['last_update']\nprint('DONE', r['state'], r['generation'], flush=True)\n")
    reader = _spawn(code, str(repo_b), cfg.cache_dir)
    try:
        time.sleep(1.5)
        assert reader.poll() is None, "the reader must wait for the evictor's exclusive lease"
        for s in ("", "-wal", "-shm"):
            Path(str(db_b) + s).unlink(missing_ok=True)
    finally:
        evictor.release()
    out, err = reader.communicate(timeout=300)
    assert reader.returncode == 0, err[-2000:]
    assert "DONE published 1" in out, "the reader found no cache and built a new one"
    engine = cached(repo_b, cache_config(tmp_path, rebuild_policy="never"))
    check(engine, repo_b, "after waiting for an eviction")


def test_lease_files_are_never_evicted_or_deleted(tmp_path):
    repo_a, repo_b, cfg, db_a, db_b = _two_caches(tmp_path)
    cached(repo_a, _limit_cfg(tmp_path, db_a, db_b))
    assert not db_b.exists() and lease_path(db_b).exists() and lease_path(db_a).exists()


# ------------------------------------------------------------------------------------------- 2. privacy purge

def _meta(db, key):
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def test_privacy_purge_is_pending_while_a_reader_holds_an_old_snapshot(tmp_path):
    repo = make_repo(tmp_path, {**FILES, SECRET_PATH: SECRET_TEXT})
    cached(repo, cache_config(tmp_path))
    db = db_path(cache_config(tmp_path))
    assert find_secret_traces(Path(db).parent, db), "the scanner sees the marker while the file is persisted"

    reader = sqlite3.connect(str(db), isolation_level=None)
    reader.execute("BEGIN")
    reader.execute("SELECT count(*) FROM artifacts").fetchone()      # an old read snapshot
    try:
        cfg = cache_config(tmp_path, persist_exclude=["**/zqxj_*"])
        engine = cached(repo, cfg)
        r = last(engine)
        assert r["state"] == "published" and SECRET_PATH in r["deleted"]
        assert r["privacy_purge"] == "pending", "a purge must not be reported complete while stale pages remain"
        assert "privacy purge pending" in r["reason"]
        assert _meta(db, "purge_pending") == "1", "the pending purge is recorded durably"
        check(engine, repo, "excluded while a reader held a snapshot")
        ro = cached(repo, cache_config(tmp_path, persist_exclude=["**/zqxj_*"], read_only=True))
        assert last(ro)["privacy_purge"] == "pending"
    finally:
        reader.execute("COMMIT")
        reader.close()
    r = engine.refresh()
    assert r.privacy_purge == "complete" and _meta(db, "purge_pending") is None
    assert find_secret_traces(Path(db).parent, db) == []
    check(engine, repo, "after the purge completed")


def test_pending_purge_is_completed_by_any_later_writer(tmp_path):
    repo = make_repo(tmp_path, {**FILES, SECRET_PATH: SECRET_TEXT})
    cached(repo, cache_config(tmp_path))
    db = db_path(cache_config(tmp_path))
    reader = sqlite3.connect(str(db), isolation_level=None)
    reader.execute("BEGIN")
    reader.execute("SELECT count(*) FROM manifest").fetchone()
    try:
        assert last(cached(repo, cache_config(tmp_path, persist_exclude=["private/**"])))["privacy_purge"] == "pending"
    finally:
        reader.execute("COMMIT")
        reader.close()
    later = cached(repo, cache_config(tmp_path, persist_exclude=["private/**"]))   # a later, unrelated start
    assert last(later)["privacy_purge"] == "complete"
    assert find_secret_traces(Path(db).parent, db) == []


PURGE_CRASH = r'''
import os, sys
from reponeedle.core.index_cache import store
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import IndexCacheConfig
real_publish = store.CacheWriter.publish
def publish(self, *a, **k):
    out = real_publish(self, *a, **k)
    os._exit(77)                      # killed after the publish, before garbage collection and the checkpoint
store.CacheWriter.publish = publish
RepoNeedleEngine.from_directory(sys.argv[1], index_cache=IndexCacheConfig(cache_dir=sys.argv[2],
                                                                         persist_exclude=["**/zqxj_*"]))
'''


def test_a_crash_before_the_purge_leaves_it_pending_for_the_next_writer(tmp_path):
    repo = make_repo(tmp_path, {**FILES, SECRET_PATH: SECRET_TEXT})
    cached(repo, cache_config(tmp_path))
    db = db_path(cache_config(tmp_path))
    assert run_python(PURGE_CRASH, str(repo), str(tmp_path / "cache"), check=False).returncode == 77
    assert _meta(db, "purge_pending") == "1", "the publish recorded the pending purge durably"
    engine = cached(repo, cache_config(tmp_path, persist_exclude=["**/zqxj_*"]))
    assert last(engine)["privacy_purge"] == "complete" and _meta(db, "purge_pending") is None
    assert find_secret_traces(Path(db).parent, db) == []
    check(engine, repo, "after a crash between publish and purge")


def test_no_purge_needed_without_newly_excluded_files(tmp_path):
    repo = make_repo(tmp_path)
    cfg = cache_config(tmp_path)
    cached(repo, cfg)
    assert last(cached(repo, cfg))["privacy_purge"] == "not_required"


# --------------------------------------------------------------------------------------------- 3. migration

# The version-1 (Stage 1) schema, verbatim from reponeedle/core/index_cache/schema.py at commit c5b1e02.
V1_DDL = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID;
CREATE TABLE generations (
  gen_id INTEGER PRIMARY KEY AUTOINCREMENT,
  state TEXT NOT NULL CHECK (state IN ('building', 'published', 'superseded', 'abandoned')),
  kind TEXT NOT NULL CHECK (kind IN ('cold', 'refresh')), started_at TEXT NOT NULL, published_at TEXT,
  index_fp TEXT NOT NULL, discovery_fp TEXT NOT NULL, doc_meta_fp TEXT NOT NULL, file_count INTEGER,
  manifest_sha256 BLOB, work_counters TEXT);
CREATE TABLE manifest (
  path TEXT PRIMARY KEY, ordinal INTEGER NOT NULL UNIQUE CHECK (ordinal >= 0),
  text_sha256 BLOB NOT NULL CHECK (length(text_sha256) = 32), language TEXT NOT NULL,
  is_test INTEGER NOT NULL CHECK (is_test IN (0, 1)), line_count INTEGER NOT NULL CHECK (line_count >= 0),
  token_estimate INTEGER NOT NULL CHECK (token_estimate >= 0),
  doc_meta_sha256 BLOB NOT NULL CHECK (length(doc_meta_sha256) = 32)) WITHOUT ROWID;
CREATE TABLE excluded (path TEXT PRIMARY KEY, reason TEXT NOT NULL CHECK (reason IN ('skipped_large', 'unreadable',
  'symlink_outside_repository', 'directory_skipped'))) WITHOUT ROWID;
CREATE TABLE artifacts (
  artifact_key BLOB PRIMARY KEY CHECK (length(artifact_key) = 32), kind TEXT NOT NULL,
  extractor_fp BLOB NOT NULL CHECK (length(extractor_fp) = 32), path TEXT NOT NULL,
  input_sig BLOB NOT NULL CHECK (length(input_sig) = 32), codec TEXT NOT NULL, payload BLOB NOT NULL,
  checksum BLOB NOT NULL CHECK (length(checksum) = 32), created_gen INTEGER NOT NULL);
CREATE INDEX artifacts_by_path ON artifacts(path);
CREATE TABLE file_artifacts (
  path TEXT NOT NULL REFERENCES manifest(path) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
  kind TEXT NOT NULL,
  artifact_key BLOB NOT NULL REFERENCES artifacts(artifact_key) DEFERRABLE INITIALLY DEFERRED,
  PRIMARY KEY (path, kind)) WITHOUT ROWID;
CREATE INDEX file_artifacts_by_key ON file_artifacts(artifact_key);
CREATE TABLE global_state (name TEXT PRIMARY KEY, gen_id INTEGER NOT NULL, codec TEXT NOT NULL,
  payload BLOB NOT NULL, checksum BLOB NOT NULL CHECK (length(checksum) = 32));
CREATE TABLE optional_components (component TEXT PRIMARY KEY, status TEXT NOT NULL) WITHOUT ROWID;
"""


def make_stage1_database(db: Path) -> None:
    """
    Rewrites a current cache as the exact database Stage 1 would have published for the same files: the version-1
    schema, Stage 1 artifact kinds and rows only, no file ids, and the version-1 manifest digest.
    """
    src = sqlite3.connect(str(db))
    meta = {k: v for k, v in src.execute("SELECT key, value FROM meta") if k not in ("next_file_id", "purge_pending")}
    gen_id = int(meta["current_generation"])
    gen = src.execute("SELECT * FROM generations WHERE gen_id = ?", (gen_id,)).fetchone()
    manifest = src.execute("SELECT path, ordinal, text_sha256, language, is_test, line_count, token_estimate, "
                           "doc_meta_sha256 FROM manifest").fetchall()
    kinds = schema.STAGE1_KINDS
    marks = ",".join("?" * len(kinds))
    fa = src.execute(f"SELECT path, kind, artifact_key FROM file_artifacts WHERE kind IN ({marks})", kinds).fetchall()
    arts = src.execute(f"SELECT * FROM artifacts WHERE kind IN ({marks}) AND artifact_key IN "
                       "(SELECT artifact_key FROM file_artifacts)", kinds).fetchall()
    excluded = src.execute("SELECT path, reason FROM excluded").fetchall()
    optional = src.execute("SELECT component, status FROM optional_components").fetchall()
    summary = src.execute("SELECT * FROM global_state WHERE name = 'stage1.summary'").fetchone()
    src.close()
    for s in ("", "-wal", "-shm"):
        Path(str(db) + s).unlink(missing_ok=True)
    conn = sqlite3.connect(str(db), isolation_level=None)
    conn.execute("PRAGMA auto_vacuum = INCREMENTAL")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(f"PRAGMA application_id = {schema.APPLICATION_ID}")
    conn.execute("PRAGMA user_version = 1")
    for statement in V1_DDL.split(";"):
        if statement.strip():
            conn.execute(statement)
    conn.executemany("INSERT INTO meta VALUES (?, ?)", sorted(meta.items()))
    digest = schema.manifest_digest(gen_id, manifest, fa, excluded, optional, version=schema.MANIFEST_DIGEST_VERSION_1)
    conn.execute("INSERT INTO generations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 tuple(gen[:9]) + (digest, gen[10]))
    conn.executemany("INSERT INTO manifest VALUES (?, ?, ?, ?, ?, ?, ?, ?)", manifest)
    conn.executemany("INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", arts)
    conn.executemany("INSERT INTO file_artifacts VALUES (?, ?, ?)", fa)
    conn.executemany("INSERT INTO excluded VALUES (?, ?)", excluded)
    conn.executemany("INSERT INTO optional_components VALUES (?, ?)", optional)
    conn.execute("INSERT INTO global_state VALUES (?, ?, ?, ?, ?)", summary)
    conn.execute("COMMIT")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()


def _stage1_cache(tmp_path):
    repo = make_repo(tmp_path)
    cfg = cache_config(tmp_path)
    n = len(cached(repo, cfg).docs)
    db = db_path(cfg)
    make_stage1_database(db)
    conn = sqlite3.connect(str(db))
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    assert "file_id" not in [r[1] for r in conn.execute("PRAGMA table_info(manifest)")]
    conn.close()
    return repo, cfg, db, n


def test_a_stage1_cache_is_migrated_in_place_and_its_artifacts_reused(tmp_path):
    repo, cfg, db, n = _stage1_cache(tmp_path)
    engine = cached(repo, cfg)
    r = last(engine)
    assert r["state"] == "published" and r["migrated_from_schema"] == 1 and not r["rebuilt_from_scratch"]
    assert r["artifacts_reused"] == len(schema.STAGE1_KINDS) * n, "every Stage 1 artifact stays reusable"
    assert r["global_structures"]["function_graph.call_resolution"] == "fallback_full"
    assert "provider index" in r["fallbacks"]["function_graph.call_resolution"]
    conn = sqlite3.connect(str(db))
    assert conn.execute("PRAGMA user_version").fetchone()[0] == schema.SCHEMA_VERSION
    ids = dict(conn.execute("SELECT path, file_id FROM manifest"))
    ords = dict(conn.execute("SELECT path, ordinal FROM manifest"))
    conn.close()
    assert ids == {p: o + 1 for p, o in ords.items()}, "migrated ids follow the manifest ordinals"
    check(engine, repo, "after migrating a Stage 1 cache")
    again = cached(repo, cfg)
    assert last(again)["migrated_from_schema"] is None and last(again)["work_counters"]["function_graph"][
        "files_resolved"] == 0
    check(again, repo, "warm restart after migration")


def test_migration_is_idempotent(tmp_path):
    repo, cfg, db, n = _stage1_cache(tmp_path)
    conn = sqlite3.connect(str(db), isolation_level=None)
    try:
        assert schema.migrate(conn) == [1]
        assert schema.migrate(conn) == []
        assert conn.execute("PRAGMA user_version").fetchone()[0] == schema.SCHEMA_VERSION
    finally:
        conn.close()
    assert last(cached(repo, cfg))["state"] == "published"


MIGRATION_CRASH = r'''
import os, sqlite3, sys
from reponeedle.core.index_cache import schema
real = schema.manifest_digest
def digest(*a, **k):
    if k.get("version", schema.MANIFEST_DIGEST_VERSION) == schema.MANIFEST_DIGEST_VERSION:
        os._exit(77)          # inside the migration transaction, after ALTER TABLE and the id assignment
    return real(*a, **k)
schema.manifest_digest = digest
conn = sqlite3.connect(sys.argv[1], isolation_level=None)
schema.migrate(conn)
'''


def test_a_crash_during_migration_leaves_the_version_1_database_usable(tmp_path):
    repo, cfg, db, n = _stage1_cache(tmp_path)
    before = db.read_bytes()
    assert run_python(MIGRATION_CRASH, str(db), check=False).returncode == 77
    conn = sqlite3.connect(str(db))
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    assert "file_id" not in [r[1] for r in conn.execute("PRAGMA table_info(manifest)")]
    conn.close()
    engine = cached(repo, cache_config(tmp_path, rebuild_policy="never"))
    assert last(engine)["migrated_from_schema"] == 1 and last(engine)["artifacts_reused"] >= 5 * n
    check(engine, repo, "migration after a crashed migration")
    assert before  # the version-1 file existed before the crash


def test_a_read_only_client_never_migrates(tmp_path):
    repo, cfg, db, n = _stage1_cache(tmp_path)
    before = {s: Path(str(db) + s).read_bytes() for s in ("",) if Path(str(db) + s).exists()}
    engine = cached(repo, cache_config(tmp_path, read_only=True))
    r = last(engine)
    assert r["state"] == "not_persisted" and "migration" in r["reason"]
    conn = sqlite3.connect(str(db))
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    conn.close()
    assert {s: Path(str(db) + s).read_bytes() for s in before} == before
    check(engine, repo, "read-only client with a version-1 cache")


def test_an_unverifiable_version_1_database_is_not_migrated(tmp_path):
    repo, cfg, db, n = _stage1_cache(tmp_path)
    conn = sqlite3.connect(str(db), isolation_level=None)
    conn.execute("UPDATE manifest SET is_test = 1 - is_test WHERE ordinal = 0")
    conn.close()
    engine = cached(repo, cfg)
    r = last(engine)
    assert r["rebuilt_from_scratch"] and "does not verify" in r["reason"]
    check(engine, repo, "unverifiable version-1 cache rebuilt")


# --------------------------------------------------------------------------------------------- 4. file ids

def _ids(cfg):
    conn = sqlite3.connect(str(db_path(cfg)))
    try:
        ids = dict(conn.execute("SELECT path, file_id FROM manifest"))
        nxt = int(conn.execute("SELECT value FROM meta WHERE key = 'next_file_id'").fetchone()[0])
        return ids, nxt
    finally:
        conn.close()


def test_file_ids_are_stable_and_never_reused(tmp_path):
    repo = write_tree(tmp_path / "repo", synthetic_files())
    cfg = cache_config(tmp_path)
    engine = cached(repo, cfg)
    ids0, next0 = _ids(cfg)
    assert sorted(ids0.values()) == list(range(1, len(ids0) + 1)) and next0 == len(ids0) + 1
    # edits and a different discovery order keep every id
    dict(MUTATIONS)["body_only"](repo)
    with reversed_discovery():
        engine.refresh()
    ids1, next1 = _ids(cfg)
    assert ids1 == ids0 and next1 == next0
    # a deleted path retires its id; re-adding the path gets a NEW id
    text = (repo / "README.md").read_text(encoding="utf-8")
    remove(repo, "README.md")
    r = engine.refresh()
    assert r.file_ids_retired == 1 and "README.md" not in _ids(cfg)[0]
    write(repo, "README.md", text)
    r = engine.refresh()
    ids2, next2 = _ids(cfg)
    assert r.file_ids_assigned == 1 and ids2["README.md"] == next1 and next2 == next1 + 1
    assert ids2["README.md"] not in ids0.values()
    # a rename is a delete plus an add: the new path gets a new id
    rename(repo, "util/mod5.py", "util/mod5b.py")
    engine.refresh()
    ids3, next3 = _ids(cfg)
    assert ids3["util/mod5b.py"] == next2 and "util/mod5.py" not in ids3
    assert len(set(ids3.values())) == len(ids3)
    check(engine, repo, "after file-id lifecycle")


def test_persist_excluded_files_never_receive_an_id(tmp_path):
    repo = write_tree(tmp_path / "repo", synthetic_files())
    cached(repo, cache_config(tmp_path))
    ids0, next0 = _ids(cache_config(tmp_path))
    cfg = cache_config(tmp_path, persist_exclude=["util/**"])
    engine = cached(repo, cfg)
    ids, nxt = _ids(cfg)
    assert not any(p.startswith("util/") for p in ids) and nxt == next0
    assert all(ids[p] == ids0[p] for p in ids)
    assert len(ids) == last(engine)["files_persisted"]
    cached(repo, cache_config(tmp_path))                  # no longer excluded: new ids, never the retired ones
    ids2, next2 = _ids(cache_config(tmp_path))
    util_ids = [ids2[p] for p in ids2 if p.startswith("util/")]
    assert util_ids and min(util_ids) >= next0 and not set(util_ids) & set(ids0.values())


def test_a_lowered_next_file_id_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    cfg = cache_config(tmp_path)
    cached(repo, cfg)
    conn = sqlite3.connect(str(db_path(cfg)), isolation_level=None)
    conn.execute("UPDATE meta SET value = '2' WHERE key = 'next_file_id'")
    conn.close()
    engine = cached(repo, cfg)
    assert last(engine)["rebuilt_from_scratch"] and "reuse an assigned file id" in last(engine)["reason"]


def test_a_changed_file_id_fails_the_manifest_digest(tmp_path):
    repo = make_repo(tmp_path)
    cfg = cache_config(tmp_path)
    cached(repo, cfg)
    conn = sqlite3.connect(str(db_path(cfg)), isolation_level=None)
    conn.execute("UPDATE manifest SET file_id = file_id + 1000 WHERE ordinal = 0")
    conn.close()
    engine = cached(repo, cfg)
    assert last(engine)["rebuilt_from_scratch"] and "manifest digest" in last(engine)["reason"]


# ------------------------------------------------------------------------------ 5. crashes and concurrency

@pytest.mark.parametrize("point", sorted(CRASH_POINTS))
def test_a_crash_with_provider_changes_never_exposes_a_partial_generation(tmp_path, point):
    repo = write_tree(tmp_path / "repo", synthetic_files())
    cfg = cache_config(tmp_path)
    cached(repo, cfg)
    old, old_gen, old_ids = _published_digests(cfg), published_generation(cfg), _ids(cfg)
    for name in ("second_definition", "move_module", "add_files_positions"):
        dict(MUTATIONS)[name](repo)
    res = run_python(CRASH_CHILD, str(repo), cfg.cache_dir, point, check=False)
    assert res.returncode == 77, (res.returncode, res.stderr[-2000:])
    published = _published_digests(cfg)
    if CRASH_POINTS[point] == "old":
        assert published == old and published_generation(cfg) == old_gen and _ids(cfg) == old_ids
    else:
        assert published == _repo_digests(fresh(repo)) and published_generation(cfg) == old_gen + 1
    engine = cached(repo, cache_config(tmp_path, rebuild_policy="never"))
    assert last(engine)["state"] == "published" and not last(engine)["rebuilt_from_scratch"]
    no_index_misses(engine)
    check(engine, repo, f"after a crash at {point}")


INCREMENTAL_WRITER = r'''
import sys
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import IndexCacheConfig
repo, cache_dir, rounds = sys.argv[1], sys.argv[2], int(sys.argv[3])
for _ in range(rounds):
    e = RepoNeedleEngine.from_directory(repo, index_cache=IndexCacheConfig(cache_dir=cache_dir))
    r = e.index_cache_diagnostics["last_update"]
    assert r["state"] == "published", r
    for g in ("function_graph", "repo_graph"):
        assert r["work_counters"][g].get("context_mismatches_outside_dependency_index", 0) == 0, r["work_counters"][g]
print("OK", r["generation"], flush=True)
'''


def test_concurrent_incremental_writers_with_provider_changes(tmp_path):
    from test_stage1_cache_processes import READER_CHILD, _spawn as spawn_child, _wait

    repo = write_tree(tmp_path / "repo", synthetic_files())
    cfg = cache_config(tmp_path)
    cached(repo, cfg)
    db = str(db_path(cfg))
    writers = [spawn_child(INCREMENTAL_WRITER, str(repo), cfg.cache_dir, "4") for _ in range(2)]
    readers = [spawn_child(READER_CHILD, str(repo), cfg.cache_dir, db, "20") for _ in range(2)]
    for name in ("second_definition", "delete_one_of_two", "add_method", "winning_provider", "rename_file"):
        time.sleep(0.4)
        dict(MUTATIONS)[name](repo)
    outs = [_wait(p) for p in writers + readers]
    assert all(o.startswith("OK") for o in outs)
    ids, nxt = _ids(cfg)
    assert len(set(ids.values())) == len(ids) and max(ids.values()) < nxt
    engine = cached(repo, cache_config(tmp_path, rebuild_policy="never"))
    no_index_misses(engine)
    check(engine, repo, "after concurrent incremental writers with provider changes")
