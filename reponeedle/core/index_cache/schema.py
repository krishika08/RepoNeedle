"""
SQLite schema, artifact identity, checksums and the canonical manifest digest (design sections 6 and 6.1).

Stage 1 stores only what is needed to reconstruct the per-document caches; every global structure is recomputed.
The dependency tables (``provides``/``consumes``) of the design belong to Stage 2 and are not created.
"""

import hashlib
import json
from typing import Dict, Iterable, List, Sequence, Tuple

APPLICATION_ID = 0x524E4458          # 'RNDX'
SCHEMA_MAJOR = 1                     # part of the file name: a new major means a new file (design section 10.6)
SCHEMA_VERSION = 1                   # PRAGMA user_version; this file only reads exactly this version
MANIFEST_DIGEST_VERSION = b"reponeedle-manifest-v1"

KINDS = ("doc_meta", "lexical", "semantic", "abstainer", "function_graph")

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
  doc_meta_sha256 BLOB NOT NULL CHECK (length(doc_meta_sha256) = 32)
) WITHOUT ROWID;

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
    signature (``doc_signature``), i.e. a SHA-256 of the exact extraction inputs including its configuration.
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
                    excluded: Iterable[Sequence], optional_components: Iterable[Sequence]) -> bytes:
    """
    Versioned, canonical digest of the published rows: each table is sorted by its primary key, so the digest does
    not depend on row iteration order. Row tuples use the column order of the DDL.
    """
    h = hashlib.sha256()
    h.update(framed(MANIFEST_DIGEST_VERSION, str(gen_id).encode("ascii")))
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
