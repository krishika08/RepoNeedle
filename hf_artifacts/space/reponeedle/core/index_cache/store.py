"""
Reading and writing cache generations (design sections 6.1, 10.2, 10.3, 10.4 and 12).

Reader: ``load_generation`` loads the current published generation inside ONE read transaction (one WAL snapshot)
and verifies, before anything is used: application id, schema version, repository identity, the published
generation, the canonical manifest digest, global-state checksums, path syntax, every referenced artifact's
identity (kind, path and the key recomputed from the expected inputs), its checksum and its decodability. Any
failure makes the WHOLE database unusable (CacheUnusable); nothing is partially reused.

Writer: ``CacheWriter`` implements the protocol: a 'building' generation marker, bounded immutable artifact batches,
one publish transaction (the only way a generation becomes valid), then garbage collection and WAL maintenance.
"""

import datetime
import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from reponeedle.core.index_cache import codecs
from reponeedle.core.index_cache.errors import CacheUnusable, PersistenceUnavailable
from reponeedle.core.semantic import FeatureCounts, FeaturePool
from reponeedle.core.index_cache.lease import CacheLease
from reponeedle.core.index_cache.schema import (APPLICATION_ID, KINDS, MIGRATABLE_VERSIONS, SCHEMA_VERSION, TABLES,
                                                artifact_checksum, artifact_key, doc_meta_digest, global_checksum,
                                                manifest_digest)

SUMMARY_STATE = "stage1.summary"
SUMMARY_CODEC = "summary-json/1"
ARTIFACT_BATCH_ROWS = 2500
STALE_BUILDING_HOURS = 6


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def valid_relative_path(path: str) -> bool:
    if not isinstance(path, str) or not path or "\x00" in path or "\\" in path or path.startswith("/"):
        return False
    if len(path) >= 2 and path[1] == ":":
        return False
    return all(part not in ("", ".", "..") for part in path.split("/"))


@dataclass
class ManifestEntry:
    path: str
    ordinal: int
    text_sha256: bytes
    language: str
    is_test: bool
    line_count: int
    token_estimate: int
    doc_meta_sha256: bytes
    file_id: int = 0
    artifacts: Dict[str, bytes] = field(default_factory=dict)     # kind -> artifact key


@dataclass
class LoadedArtifact:
    kind: str
    extractor_fp: bytes
    input_sig: bytes
    data: object        # decoded payload, or None when the extractor fingerprint is not the current one


@dataclass
class LoadedGeneration:
    gen_id: int
    meta: Dict[str, str]
    manifest: Dict[str, ManifestEntry]
    artifacts: Dict[bytes, LoadedArtifact]
    global_state: Dict[str, Tuple[str, bytes]] = field(default_factory=dict)   # name -> (codec, verified payload)

    @property
    def ordered_paths(self) -> List[str]:
        return [e.path for e in sorted(self.manifest.values(), key=lambda e: e.ordinal)]

    @property
    def purge_pending(self) -> bool:
        return self.meta.get("purge_pending") == "1"

    def data(self, path: str, kind: str):
        """The decoded artifact of ``kind`` for ``path`` (None if absent or from another extractor fingerprint)."""
        entry = self.manifest.get(path)
        key = entry.artifacts.get(kind) if entry is not None else None
        art = self.artifacts.get(key) if key is not None else None
        return art.data if art is not None else None


def _pragma(conn, name):
    return conn.execute(f"PRAGMA {name}").fetchone()[0]


def load_generation(conn: sqlite3.Connection, repo_root: str, repo_id: str, current_fps: Dict[str, bytes],
                    verify: bool = False) -> LoadedGeneration:
    """Verified load of the current published generation (see module docstring). Raises CacheUnusable."""
    try:
        conn.execute("BEGIN")
        try:
            return _load(conn, repo_root, repo_id, current_fps, verify)
        finally:
            conn.execute("COMMIT")
    except sqlite3.DatabaseError as exc:
        raise CacheUnusable(f"database error: {type(exc).__name__}: {exc}") from exc


def _load(conn, repo_root, repo_id, current_fps, verify) -> LoadedGeneration:
    if _pragma(conn, "application_id") != APPLICATION_ID:
        raise CacheUnusable("not a RepoNeedle index cache (application_id)")
    version = _pragma(conn, "user_version")
    if version != SCHEMA_VERSION:
        raise CacheUnusable(f"unsupported schema version {version} (this version reads {SCHEMA_VERSION})",
                            migratable=version in MIGRATABLE_VERSIONS)
    present = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if not set(TABLES) <= present:
        raise CacheUnusable("schema tables missing")
    meta = dict(conn.execute("SELECT key, value FROM meta"))
    if meta.get("repo_id") != repo_id or os.path.normcase(meta.get("repo_root", "")) != os.path.normcase(repo_root):
        raise CacheUnusable("cache belongs to a different repository root")
    try:
        gen_id = int(meta["current_generation"])
    except (KeyError, ValueError):
        raise CacheUnusable("no published generation")
    gen = conn.execute("SELECT state, manifest_sha256 FROM generations WHERE gen_id = ?", (gen_id,)).fetchone()
    if gen is None or gen[0] != "published" or not isinstance(gen[1], bytes):
        raise CacheUnusable("current generation is not published")

    manifest_rows = conn.execute("SELECT path, ordinal, text_sha256, language, is_test, line_count, token_estimate, "
                                 "doc_meta_sha256, file_id FROM manifest").fetchall()
    fa_rows = conn.execute("SELECT path, kind, artifact_key FROM file_artifacts").fetchall()
    excluded_rows = conn.execute("SELECT path, reason FROM excluded").fetchall()
    optional_rows = conn.execute("SELECT component, status FROM optional_components").fetchall()
    try:
        digest = manifest_digest(gen_id, manifest_rows, fa_rows, excluded_rows, optional_rows)
    except (ValueError, TypeError) as exc:
        raise CacheUnusable(f"manifest rows are malformed: {exc}") from exc
    if digest != gen[1]:
        raise CacheUnusable("manifest digest does not match the published rows")

    summary_ok = False
    global_state: Dict[str, Tuple[str, bytes]] = {}
    for name, row_gen, codec, payload, checksum in conn.execute(
            "SELECT name, gen_id, codec, payload, checksum FROM global_state"):
        if row_gen != gen_id or checksum != global_checksum(name, row_gen, codec, payload):
            raise CacheUnusable(f"global state {name!r} failed verification")
        global_state[name] = (codec, bytes(payload))
        if name == SUMMARY_STATE and codec == SUMMARY_CODEC:
            try:
                summary = json.loads(bytes(payload).decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as exc:
                raise CacheUnusable("global summary does not decode") from exc
            summary_ok = isinstance(summary, dict) and summary.get("persisted_files") == len(manifest_rows)
    if not summary_ok:
        raise CacheUnusable("global summary missing or inconsistent with the manifest")

    manifest: Dict[str, ManifestEntry] = {}
    ordinals = []
    for path, ordinal, text_sha, language, is_test, lines, tokens, meta_sha, file_id in manifest_rows:
        if not valid_relative_path(path):
            raise CacheUnusable("manifest contains an invalid path")
        if type(file_id) is not int or file_id < 1:
            raise CacheUnusable("manifest entry without a valid file id")
        manifest[path] = ManifestEntry(path, ordinal, text_sha, language, bool(is_test), lines, tokens, meta_sha,
                                       file_id)
        ordinals.append(ordinal)
    if sorted(ordinals) != list(range(len(ordinals))):
        raise CacheUnusable("manifest ordinals are not dense")
    try:
        next_file_id = int(meta.get("next_file_id", "1"))
    except ValueError:
        raise CacheUnusable("next_file_id is not an integer")
    if manifest and next_file_id <= max(e.file_id for e in manifest.values()):
        raise CacheUnusable("next_file_id would reuse an assigned file id")

    joined = conn.execute(
        "SELECT fa.path, fa.kind, a.artifact_key, a.kind, a.extractor_fp, a.path, a.input_sig, a.codec, a.payload, "
        "a.checksum FROM file_artifacts fa JOIN artifacts a ON a.artifact_key = fa.artifact_key").fetchall()
    if len(joined) != len(fa_rows):
        raise CacheUnusable("a referenced artifact is missing")
    artifacts: Dict[bytes, LoadedArtifact] = {}
    semantic_pool = FeaturePool()
    for fa_path, fa_kind, key, kind, fp, a_path, input_sig, codec, payload, checksum in joined:
        entry = manifest.get(fa_path)
        if entry is None or fa_kind not in KINDS or kind != fa_kind or a_path != fa_path:
            raise CacheUnusable("artifact metadata does not match its manifest entry")
        if key != artifact_key(kind, fp, a_path, entry.text_sha256, entry.doc_meta_sha256, input_sig):
            raise CacheUnusable("artifact key does not match the expected inputs")
        if checksum != artifact_checksum(key, kind, fp, a_path, input_sig, codec, payload):
            raise CacheUnusable("artifact checksum mismatch")
        data = None
        if current_fps.get(kind) == fp:
            try:
                data = codecs.decode(kind, codec, payload)
            except codecs.CodecError as exc:
                raise CacheUnusable(f"artifact payload does not decode: {exc}") from exc
            if kind == "semantic":
                # V2 Stage 4.1: one string per distinct feature across all decoded documents (a pool for this
                # load), from the moment each artifact is decoded: the generation is loaded at once, so this bounds
                # the load-time peak. The decoded strings are released here; the semantic index adopts the pool.
                data = FeatureCounts.from_counts(semantic_pool, data)
        if kind == "doc_meta" and data is not None:
            if (doc_meta_digest(data) != entry.doc_meta_sha256 or data["language"] != entry.language
                    or data["is_test"] != entry.is_test or data["line_count"] != entry.line_count
                    or data["token_count"] != entry.token_estimate):
                raise CacheUnusable("document metadata does not match its manifest entry")
        entry.artifacts[kind] = key
        artifacts[key] = LoadedArtifact(kind, fp, input_sig, data)
    if any("doc_meta" not in e.artifacts for e in manifest.values()):
        raise CacheUnusable("a manifest entry has no document metadata")

    if verify:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise CacheUnusable("PRAGMA integrity_check failed")
        for key, kind, fp, a_path, input_sig, codec, payload, checksum in conn.execute(
                "SELECT artifact_key, kind, extractor_fp, path, input_sig, codec, payload, checksum FROM artifacts"):
            if checksum != artifact_checksum(key, kind, fp, a_path, input_sig, codec, payload):
                raise CacheUnusable("an unreferenced artifact failed its checksum")
    return LoadedGeneration(gen_id, meta, manifest, artifacts, global_state)


ArtifactRow = Tuple[bytes, str, bytes, str, bytes, str, bytes, bytes, int]


def make_artifact_row(kind: str, extractor_fp: bytes, path: str, text_sha256: bytes, doc_meta_sha256: bytes,
                      input_sig: bytes, payload: bytes, gen_id: int) -> ArtifactRow:
    key = artifact_key(kind, extractor_fp, path, text_sha256, doc_meta_sha256, input_sig)
    codec = codecs.CODECS[kind]
    return (key, kind, extractor_fp, path, input_sig, codec, payload,
            artifact_checksum(key, kind, extractor_fp, path, input_sig, codec, payload), gen_id)


class CacheWriter:
    """The writer protocol on a connection from ``connection.open_writer`` (settings already verified)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _tx(self, fn):
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            result = fn()
            self.conn.execute("COMMIT")
            return result
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    def begin_generation(self, kind: str, fingerprints: Dict[str, str]) -> int:
        def run():
            cur = self.conn.execute(
                "INSERT INTO generations(state, kind, started_at, index_fp, discovery_fp, doc_meta_fp) "
                "VALUES ('building', ?, ?, ?, ?, ?)",
                (kind, utc_now(), fingerprints["index"], fingerprints["discovery"], fingerprints["doc_meta"]))
            return cur.lastrowid
        return self._tx(run)

    def write_artifacts(self, rows: Sequence[ArtifactRow]) -> int:
        """Immutable, content-addressed rows in bounded batches (INSERT OR IGNORE). Returns rows inserted."""
        inserted = 0
        for i in range(0, len(rows), ARTIFACT_BATCH_ROWS):
            chunk = rows[i:i + ARTIFACT_BATCH_ROWS]

            def run(chunk=chunk):
                before = self.conn.total_changes
                self.conn.executemany("INSERT OR IGNORE INTO artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", chunk)
                return self.conn.total_changes - before
            inserted += self._tx(run)
        return inserted

    def database_bytes(self) -> int:
        return _pragma(self.conn, "page_count") * _pragma(self.conn, "page_size")

    def publish(self, gen_id: int, meta: Dict[str, str], manifest_rows: List[tuple], fa_rows: List[tuple],
                excluded_rows: List[tuple], optional_rows: List[tuple], summary: Dict[str, object],
                artifact_for: Callable[[bytes], Optional[ArtifactRow]], work_counters: Dict[str, object],
                global_rows: Sequence[Tuple[str, str, bytes]] = (), purge_required: bool = False
                ) -> Dict[str, int]:
        """
        The single publish transaction. Replaces the published rows, re-inserts any referenced artifact that a
        concurrent writer's garbage collection removed meanwhile, writes the manifest digest and global state,
        supersedes the previous generation and moves ``current_generation``. Foreign keys are DEFERRED, so they are
        checked at COMMIT: a dangling reference aborts the publish.

        ``manifest_rows`` omit ``file_id``: ids are allocated HERE, under the write lock, from the rows that are
        published at this moment (which may come from a concurrent writer): a path keeps its id; a path not in the
        published manifest receives ``next_file_id`` (monotonic, so a retired id is never reused).
        ``purge_required`` records ``meta.purge_pending='1'`` in the same transaction (cleared by ``maintain`` once
        the WAL has been checkpointed and truncated). Returns counts: reinserted, file_ids_assigned, retired.
        """
        def run():
            c = self.conn
            current_ids = dict(c.execute("SELECT path, file_id FROM manifest WHERE file_id IS NOT NULL"))
            row = c.execute("SELECT value FROM meta WHERE key = 'next_file_id'").fetchone()
            next_id = max(int(row[0]) if row else 1, max(current_ids.values(), default=0) + 1)
            rows, assigned = [], 0
            for r in manifest_rows:
                fid = current_ids.get(r[0])
                if fid is None:
                    fid, next_id, assigned = next_id, next_id + 1, assigned + 1
                rows.append(tuple(r) + (fid,))
            published = {r[0] for r in manifest_rows}
            retired = sum(1 for p in current_ids if p not in published)
            for table in ("file_artifacts", "manifest", "excluded", "optional_components", "global_state"):
                c.execute(f"DELETE FROM {table}")
            c.executemany("INSERT INTO manifest VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
            c.executemany("INSERT INTO file_artifacts VALUES (?, ?, ?)", fa_rows)
            c.executemany("INSERT INTO excluded VALUES (?, ?)", excluded_rows)
            c.executemany("INSERT INTO optional_components VALUES (?, ?)", optional_rows)
            missing = [r[0] for r in c.execute(
                "SELECT fa.artifact_key FROM file_artifacts fa LEFT JOIN artifacts a "
                "ON a.artifact_key = fa.artifact_key WHERE a.artifact_key IS NULL")]
            for key in missing:
                row = artifact_for(key)
                if row is None:
                    raise PersistenceUnavailable("a referenced artifact is missing and cannot be re-created")
                c.execute("INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", row)
            digest = manifest_digest(gen_id, rows, fa_rows, excluded_rows, optional_rows)
            payload = json.dumps(summary, sort_keys=True, separators=(",", ":")).encode("utf-8")
            for name, codec, data in [(SUMMARY_STATE, SUMMARY_CODEC, payload), *global_rows]:
                c.execute("INSERT INTO global_state VALUES (?, ?, ?, ?, ?)",
                          (name, gen_id, codec, data, global_checksum(name, gen_id, codec, data)))
            c.execute("UPDATE generations SET state = 'superseded' WHERE state = 'published'")
            c.execute("UPDATE generations SET state = 'published', published_at = ?, file_count = ?, "
                      "manifest_sha256 = ?, work_counters = ? WHERE gen_id = ? AND state = 'building'",
                      (utc_now(), len(manifest_rows), digest, json.dumps(work_counters, sort_keys=True), gen_id))
            if c.execute("SELECT changes()").fetchone()[0] != 1:
                raise PersistenceUnavailable("the building generation disappeared before publish")
            extra = {"current_generation": str(gen_id), "next_file_id": str(next_id)}
            if purge_required:
                extra["purge_pending"] = "1"
            c.executemany("INSERT OR REPLACE INTO meta VALUES (?, ?)", sorted({**meta, **extra}.items()))
            return {"reinserted": len(missing), "file_ids_assigned": assigned, "file_ids_retired": retired}
        return self._tx(run)

    def abandon(self, gen_id: int) -> None:
        try:
            self._tx(lambda: self.conn.execute(
                "UPDATE generations SET state = 'abandoned' WHERE gen_id = ? AND state = 'building'", (gen_id,)))
        except sqlite3.Error:
            pass

    def collect_garbage(self) -> int:
        """Deletes unreferenced artifacts (except those of live building generations) and old generation rows."""
        cutoff = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(hours=STALE_BUILDING_HOURS)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        def run():
            c = self.conn
            c.execute("UPDATE generations SET state = 'abandoned' WHERE state = 'building' AND started_at < ?",
                      (cutoff,))
            before = c.total_changes
            c.execute("DELETE FROM artifacts WHERE artifact_key NOT IN (SELECT artifact_key FROM file_artifacts) "
                      "AND created_gen NOT IN (SELECT gen_id FROM generations WHERE state = 'building')")
            removed = c.total_changes - before
            c.execute("DELETE FROM generations WHERE state IN ('superseded', 'abandoned')")
            return removed
        return self._tx(run)

    def _checkpoint_truncate(self) -> Tuple[int, int, int]:
        """
        ``wal_checkpoint(TRUNCATE)`` without waiting: an open read snapshot makes it report busy instead of blocking
        for the busy timeout. The busy timeout is restored afterwards (it is not a durability setting).
        """
        busy_ms = _pragma(self.conn, "busy_timeout")
        self.conn.execute("PRAGMA busy_timeout = 0")
        try:
            return tuple(self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
        finally:
            self.conn.execute(f"PRAGMA busy_timeout = {int(busy_ms)}")

    def maintain(self) -> Dict[str, object]:
        """
        Reclaims free pages and truncates the WAL (both outside any transaction). If a privacy purge is pending
        (``meta.purge_pending``), it is complete only when this checkpoint backfilled every WAL frame and truncated
        the WAL: then no frame or database page holds the deleted rows (``secure_delete`` overwrote them), and the
        marker is cleared. Otherwise it stays pending, durably, for a later writer.
        """
        self.conn.execute("PRAGMA incremental_vacuum").fetchall()
        busy, log_frames, checkpointed = self._checkpoint_truncate()
        row = self.conn.execute("SELECT value FROM meta WHERE key = 'purge_pending'").fetchone()
        purge = None
        if row is not None and row[0] == "1":
            if busy:
                purge = "pending"
            else:
                self._tx(lambda: self.conn.execute("DELETE FROM meta WHERE key = 'purge_pending'"))
                self._checkpoint_truncate()          # best effort: the marker's own frame holds no file data
                purge = "complete"
        return {"checkpoint_busy": bool(busy), "wal_frames": log_frames, "checkpointed_frames": checkpointed,
                "purge": purge}


def quarantine(db_path: Path) -> str:
    """Moves an unusable database (and its sidecar files) aside. Raises PersistenceUnavailable if it cannot."""
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = f"{db_path}.corrupt-{stamp}"
    moved = []
    try:
        for suffix in ("", "-wal", "-shm"):
            src = Path(str(db_path) + suffix)
            if src.exists():
                os.replace(src, target + suffix)
                moved.append(src)
    except OSError as exc:
        raise PersistenceUnavailable(f"the unusable cache could not be moved aside: {type(exc).__name__}") from exc
    return os.path.basename(target)


def enforce_total_limit(cache_dir: Path, keep: Path, max_total_bytes: int) -> Dict[str, List[str]]:
    """
    Deletes least-recently-modified OTHER cache databases until the directory fits. A database is deleted only
    while this process holds its EXCLUSIVE lease (``lease.CacheLease``), which no process can obtain while another
    RepoNeedle process holds a shared lease (every reader and writer does while its connections are open). Databases
    in use are skipped, so the limit may stay exceeded. Returns {"removed": [...], "in_use": [...]}.
    """
    def size(base: Path) -> int:
        return sum(Path(str(base) + s).stat().st_size for s in ("", "-wal", "-shm") if Path(str(base) + s).exists())

    dbs = [p for p in cache_dir.glob("*-s*.sqlite3") if p.is_file()]
    total = sum(size(p) for p in dbs)
    removed, in_use = [], []
    for candidate in sorted((p for p in dbs if p.resolve() != keep.resolve()), key=lambda p: p.stat().st_mtime):
        if total <= max_total_bytes:
            break
        lease = CacheLease(candidate)
        if not lease.try_exclusive():
            in_use.append(candidate.name)
            continue
        try:
            freed = size(candidate)
            for s in ("", "-wal", "-shm"):
                Path(str(candidate) + s).unlink(missing_ok=True)
            total -= freed
            removed.append(candidate.name)
        except OSError:
            in_use.append(candidate.name)
        finally:
            lease.release()
    return {"removed": removed, "in_use": in_use}
