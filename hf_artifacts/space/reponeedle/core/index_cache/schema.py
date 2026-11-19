"""
SQLite schema, artifact identity, checksums and the canonical manifest digest (design sections 6, 6.1 and 10.6).

Schema version 2 (V2 Stage 2) adds, as a minor additive change to version 1 (Stage 1):
- ``manifest.file_id``: a stable identity assigned when a persisted path is first seen, never reused, and
  ``meta.next_file_id`` (monotonic);
- artifact kinds ``repo_graph_facts``, ``provides``, ``fg_edges`` and ``rg_edges`` (no table change: ``kind`` is
  free text);
- ``meta.purge_pending``: a durable marker that a privacy purge has not reached the WAL yet.
A version-1 database is migrated in place, in one transaction (``migrate``); the file name keeps the schema major.
"""

import hashlib
import json
import sqlite3
from typing import Dict, Iterable, List, Sequence, Tuple

APPLICATION_ID = 0x524E4458          # 'RNDX'
SCHEMA_MAJOR = 1                     # part of the file name: a new major means a new file (design section 10.6)
SCHEMA_VERSION = 2                   # PRAGMA user_version; this code reads exactly this version
MIGRATABLE_VERSIONS = (1,)           # older minor versions migrated in place by ``migrate``
MANIFEST_DIGEST_VERSION = b"reponeedle-manifest-v2"
MANIFEST_DIGEST_VERSION_1 = b"reponeedle-manifest-v1"

# Stage 1 kinds: per-document caches of the indexes (``doc_meta`` is required for every manifest entry).
STAGE1_KINDS = ("doc_meta", "lexical", "semantic", "abstainer", "function_graph")
# Stage 2 kinds: per-document class-to-test facts, the typed provider events (design section 9.1) and the per-file
# resolved graph contributions with their consumed keys (sections 9.1-9.4).
STAGE2_KINDS = ("repo_graph_facts", "provides", "fg_edges", "rg_edges")
KINDS = STAGE1_KINDS + STAGE2_KINDS
# Kinds whose key depends on other files (through the dependency context): never decoded into a per-document cache.
RESOLUTION_KINDS = ("fg_edges", "rg_edges")

DDL = """
CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE generations (
  gen_id          INTEGER PRIMARY KEY AUTOINCREMENT,
  state           TEXT NOT NULL CHECK (state IN ('building', 'published', 'superseded', 'abandoned')),
  kind            TEXT NOT NULL CHECK (kind IN ('cold', 'refresh')),
  started_at      TEXT NOT NULL,
  published_at    TEXT,
  index_fp        TEXT NOT NULL,
  discovery_fp    TEXT NOT NULL,
  doc_meta_fp     TEXT NOT NULL,
  file_count      INTEGER,
  manifest_sha256 BLOB,
  work_counters   TEXT
);

CREATE TABLE manifest (
  path            TEXT PRIMARY KEY,
  ordinal         INTEGER NOT NULL UNIQUE CHECK (ordinal >= 0),
  text_sha256     BLOB NOT NULL CHECK (length(text_sha256) = 32),
  language        TEXT NOT NULL,
  is_test         INTEGER NOT NULL CHECK (is_test IN (0, 1)),
  line_count      INTEGER NOT NULL CHECK (line_count >= 0),
  token_estimate  INTEGER NOT NULL CHECK (token_estimate >= 0),
  doc_meta_sha256 BLOB NOT NULL CHECK (length(doc_meta_sha256) = 32),
  file_id         INTEGER CHECK (file_id >= 1)
) WITHOUT ROWID;
CREATE UNIQUE INDEX manifest_by_file_id ON manifest(file_id);

CREATE TABLE excluded (
  path   TEXT PRIMARY KEY,
  reason TEXT NOT NULL CHECK (reason IN ('skipped_large', 'unreadable', 'symlink_outside_repository',
                                         'directory_skipped'))
) WITHOUT ROWID;

CREATE TABLE artifacts (
  artifact_key  BLOB PRIMARY KEY CHECK (length(artifact_key) = 32),
  kind          TEXT NOT NULL,
  extractor_fp  BLOB NOT NULL CHECK (length(extractor_fp) = 32),
  path          TEXT NOT NULL,
  input_sig     BLOB NOT NULL CHECK (length(input_sig) = 32),
  codec         TEXT NOT NULL,
  payload       BLOB NOT NULL,
  checksum      BLOB NOT NULL CHECK (length(checksum) = 32),
  created_gen   INTEGER NOT NULL
);
CREATE INDEX artifacts_by_path ON artifacts(path);

CREATE TABLE file_artifacts (
  path         TEXT NOT NULL REFERENCES manifest(path) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
  kind         TEXT NOT NULL,
  artifact_key BLOB NOT NULL REFERENCES artifacts(artifact_key) DEFERRABLE INITIALLY DEFERRED,
  PRIMARY KEY (path, kind)
) WITHOUT ROWID;
CREATE INDEX file_artifacts_by_key ON file_artifacts(artifact_key);

CREATE TABLE global_state (
  name     TEXT PRIMARY KEY,
  gen_id   INTEGER NOT NULL,
  codec    TEXT NOT NULL,
  payload  BLOB NOT NULL,
  checksum BLOB NOT NULL CHECK (length(checksum) = 32)
);

CREATE TABLE optional_components (
  component TEXT PRIMARY KEY,
  status    TEXT NOT NULL
) WITHOUT ROWID;
"""

TABLES = ("meta", "generations", "manifest", "excluded", "artifacts", "file_artifacts", "global_state",
          "optional_components")

# Version 1 -> 2: additive. Statements run inside the migration transaction (``migrate``).
MIGRATION_1_TO_2 = (
    "ALTER TABLE manifest ADD COLUMN file_id INTEGER CHECK (file_id >= 1)",
    "CREATE UNIQUE INDEX manifest_by_file_id ON manifest(file_id)",
)


def framed(*parts: bytes) -> bytes:
    """Unambiguous concatenation: every part is prefixed with its 8-byte big-endian length."""
    out = bytearray()
    for part in parts:
        out += len(part).to_bytes(8, "big") + part
    return bytes(out)


def _b(text: str) -> bytes:
    return text.encode("utf-8", "surrogatepass")


def artifact_key(kind: str, extractor_fp: bytes, path: str, text_sha256: bytes, doc_meta_sha256: bytes,
                 input_sig: bytes) -> bytes:
    """
    Canonical artifact identity: every input that defines the artifact. ``input_sig`` is the extractor's Stage 0
    signature (``doc_signature``), i.e. a SHA-256 of the exact extraction inputs including its configuration; for
    the resolution kinds it also binds the file's dependency context (``dependencies.resolution_input_sig``).
    """
    return hashlib.sha256(framed(b"reponeedle-artifact-key-v1", _b(kind), extractor_fp, _b(path), text_sha256,
                                 doc_meta_sha256, input_sig)).digest()


def artifact_checksum(key: bytes, kind: str, extractor_fp: bytes, path: str, input_sig: bytes, codec: str,
                      payload: bytes) -> bytes:
    """Binds the payload to every column of its row."""
    return hashlib.sha256(framed(b"reponeedle-artifact-v1", key, _b(kind), extractor_fp, _b(path), input_sig,
                                 _b(codec), payload)).digest()


def global_checksum(name: str, gen_id: int, codec: str, payload: bytes) -> bytes:
    return hashlib.sha256(framed(b"reponeedle-global-v1", _b(name), str(gen_id).encode("ascii"), _b(codec),
                                 payload)).digest()


def _canon(value):
    if isinstance(value, (bytes, bytearray)):
        return {"hex": bytes(value).hex()}
    return value


def manifest_digest(gen_id: int, manifest: Iterable[Sequence], file_artifacts: Iterable[Sequence],
                    excluded: Iterable[Sequence], optional_components: Iterable[Sequence],
                    version: bytes = MANIFEST_DIGEST_VERSION) -> bytes:
    """
    Versioned, canonical digest of the published rows: each table is sorted by its primary key, so the digest does
    not depend on row iteration order. Row tuples use the column order of the DDL (version 2: the manifest rows end
    with ``file_id``).
    """
    h = hashlib.sha256()
    h.update(framed(version, str(gen_id).encode("ascii")))
    tables: List[Tuple[str, Iterable[Sequence], Tuple[int, ...]]] = [
        ("manifest", manifest, (0,)),
        ("file_artifacts", file_artifacts, (0, 1)),
        ("excluded", excluded, (0,)),
        ("optional_components", optional_components, (0,)),
    ]
    for name, rows, pk in tables:
        keyed: Dict[tuple, tuple] = {}
        for row in rows:
            k = tuple(row[i] for i in pk)
            if k in keyed:
                raise ValueError(f"duplicate primary key in {name}")
            keyed[k] = tuple(row)
        payload = json.dumps([[_canon(v) for v in keyed[k]] for k in sorted(keyed)], separators=(",", ":"),
                             ensure_ascii=True)
        h.update(framed(name.encode("ascii"), payload.encode("ascii")))
    return h.digest()


def doc_meta_digest(meta: Dict[str, object]) -> bytes:
    """doc_meta_sha256: canonical digest of a document's derived metadata (language, is_test, counts, symbols)."""
    canonical = json.dumps({k: meta[k] for k in ("language", "is_test", "line_count", "token_count", "symbols",
                                                 "imports")}, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8", "surrogatepass")
    return hashlib.sha256(framed(b"reponeedle-doc-meta-v1", canonical)).digest()


class MigrationError(Exception):
    """The database cannot be migrated (it is then treated as unusable)."""


def migrate(conn: sqlite3.Connection) -> List[int]:
    """
    Migrates an older minor schema version in place, in ONE transaction (``BEGIN IMMEDIATE`` ... ``COMMIT``), so a
    crash leaves the previous version intact. Idempotent: a database already at ``SCHEMA_VERSION`` is untouched.
    Returns the versions migrated from (empty when nothing was done).

    Version 1 -> 2: the published version-1 generation's manifest digest is verified first (an unverifiable
    database is not migrated: MigrationError); then ``manifest.file_id`` is added, the published files receive
    ids 1..n in manifest-ordinal order, ``meta.next_file_id`` is set, and the generation's manifest digest is
    recomputed with the version-2 rows. Superseded or abandoned generations are not migrated (garbage collection
    removes them).
    """
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version == SCHEMA_VERSION:
        return []
    if version not in MIGRATABLE_VERSIONS:
        raise MigrationError(f"schema version {version} cannot be migrated to {SCHEMA_VERSION}")
    conn.execute("BEGIN IMMEDIATE")
    try:
        # Re-read inside the write transaction: another process may have migrated meanwhile.
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version == SCHEMA_VERSION:
            conn.execute("COMMIT")
            return []
        meta = dict(conn.execute("SELECT key, value FROM meta"))
        current = meta.get("current_generation")
        rows = conn.execute("SELECT path, ordinal, text_sha256, language, is_test, line_count, token_estimate, "
                            "doc_meta_sha256 FROM manifest").fetchall()
        fa = conn.execute("SELECT path, kind, artifact_key FROM file_artifacts").fetchall()
        excluded = conn.execute("SELECT path, reason FROM excluded").fetchall()
        optional = conn.execute("SELECT component, status FROM optional_components").fetchall()
        if current is not None:
            gen_id = int(current)
            gen = conn.execute("SELECT state, manifest_sha256 FROM generations WHERE gen_id = ?",
                               (gen_id,)).fetchone()
            if gen is None or gen[0] != "published" or gen[1] != manifest_digest(
                    gen_id, rows, fa, excluded, optional, version=MANIFEST_DIGEST_VERSION_1):
                raise MigrationError("the version-1 generation does not verify; it is not migrated")
        for statement in MIGRATION_1_TO_2:
            conn.execute(statement)
        ordered = sorted(rows, key=lambda r: r[1])
        conn.executemany("UPDATE manifest SET file_id = ? WHERE path = ?",
                         [(i + 1, r[0]) for i, r in enumerate(ordered)])
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('next_file_id', ?)", (str(len(ordered) + 1),))
        if current is not None:
            new_rows = [tuple(r) + (i + 1,) for i, r in enumerate(ordered)]
            conn.execute("UPDATE generations SET manifest_sha256 = ? WHERE gen_id = ?",
                         (manifest_digest(gen_id, new_rows, fa, excluded, optional), gen_id))
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return [1]
