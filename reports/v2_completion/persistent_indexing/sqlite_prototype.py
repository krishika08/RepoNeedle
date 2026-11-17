"""
Isolated SQLite prototype for the persistent-indexing design. RESEARCH ONLY: nothing here is imported by the
package, and the engine does not persist anything. The script builds a throwaway database in a temporary directory
and deletes it afterwards.

    python reports/v2_completion/persistent_indexing/sqlite_prototype.py [--snapshot COMMIT] [--out sqlite_prototype.json]

Part 1 checks the SQLite behaviour the writer protocol relies on (design §10.1): which PRAGMAs are rejected or
silently ignored inside a transaction, and how Python's sqlite3 implicit transactions interact with them.

Part 2 builds prototype databases with the schema of design §6 (checksummed artifacts, strings and global state) from
the indexes of a pinned snapshot of this repository (snapshot.py) and of a synthetic repository, in two payload
encodings: A, strings replaced by ids into one shared ``strings`` table (the encoding proposed in PR #21), and B,
self-contained payloads with strings inline (no shared table). For each it reports the seven size components
separately:

1. encoded per-file artifact payloads;
2. the shared string table;
3. the actual database file;
4. B-tree indexes and page overhead;
5. WAL growth during the build (temporary-file use is not measured);
6. optional Tree-sitter and SCIP artifacts (measured only if those extras are installed; otherwise reported as not
   measured);
7. global state.

Part 3 checks that structurally valid but altered data (a re-encoded payload with a changed count, two swapped
payloads, an altered or moved string, altered global state) is rejected by the checksums, and times verification
and a string-table sweep (the mark phase of string garbage collection).

Not covered: provides/consumes rows are approximated from FileDoc symbols/imports (the real key sets do not exist yet);
`repo_graph_facts` artifacts are not measured (RepoGraph has no per-document extraction to encode). The 100,000-file
figure is a linear projection, not a measurement.
"""

import argparse
import hashlib
import json
import platform
import shutil
import sqlite3
import sys
import tempfile
import time
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from profile_current import write_synthetic_repo  # noqa: E402
from reponeedle.engine import RepoNeedleEngine  # noqa: E402
from snapshot import Snapshot, check_out_path, package_matches_commit  # noqa: E402

BATCH_FILES = 500

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE generations (
  gen_id INTEGER PRIMARY KEY, state TEXT NOT NULL, kind TEXT NOT NULL, started_at TEXT NOT NULL,
  published_at TEXT, index_fingerprint BLOB NOT NULL, discovery_fingerprint BLOB NOT NULL,
  file_count INTEGER, manifest_sha256 BLOB, work_counters TEXT);
CREATE TABLE strings (sid INTEGER PRIMARY KEY, text TEXT NOT NULL UNIQUE, checksum BLOB NOT NULL);
CREATE TABLE manifest (
  path TEXT PRIMARY KEY, ordinal INTEGER NOT NULL UNIQUE, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL,
  ctime_ns INTEGER, inode INTEGER, content_sha256 BLOB NOT NULL, text_sha256 BLOB NOT NULL, language TEXT NOT NULL,
  is_test INTEGER NOT NULL, line_count INTEGER NOT NULL, token_estimate INTEGER NOT NULL, artifact_set BLOB NOT NULL,
  doc_meta_fp BLOB NOT NULL);
CREATE TABLE artifacts (
  artifact_key BLOB PRIMARY KEY, kind TEXT NOT NULL, extractor_fp BLOB NOT NULL, path TEXT NOT NULL,
  codec TEXT NOT NULL, payload BLOB NOT NULL, checksum BLOB NOT NULL, created_gen INTEGER NOT NULL,
  last_used_gen INTEGER NOT NULL);
CREATE INDEX artifacts_by_path ON artifacts(path, kind);
CREATE TABLE file_artifacts (
  path TEXT NOT NULL REFERENCES manifest(path) ON DELETE CASCADE, kind TEXT NOT NULL,
  artifact_key BLOB NOT NULL REFERENCES artifacts(artifact_key), PRIMARY KEY (path, kind));
CREATE TABLE provides (
  path TEXT NOT NULL REFERENCES manifest(path) ON DELETE CASCADE, space TEXT NOT NULL, key TEXT NOT NULL,
  seq INTEGER NOT NULL, PRIMARY KEY (space, key, path, seq));
CREATE INDEX provides_by_path ON provides(path);
CREATE TABLE consumes (
  path TEXT NOT NULL REFERENCES manifest(path) ON DELETE CASCADE, space TEXT NOT NULL, key TEXT NOT NULL,
  PRIMARY KEY (space, key, path));
CREATE INDEX consumes_by_path ON consumes(path);
CREATE TABLE global_state (
  name TEXT PRIMARY KEY, gen_id INTEGER NOT NULL, codec TEXT NOT NULL, payload BLOB NOT NULL,
  checksum BLOB NOT NULL);
CREATE TABLE optional_components (component TEXT PRIMARY KEY, version TEXT, digest BLOB, status TEXT NOT NULL);
"""
SECONDARY_INDEXES = ("artifacts_by_path", "provides_by_path", "consumes_by_path")


# ---------------------------------------------------------------- encoding

def varint(n: int) -> bytes:
    if n < 0:
        raise ValueError("varint of a negative number")
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def read_varints(buf: bytes):
    out, cur, shift = [], 0, 0
    for byte in buf:
        cur |= (byte & 0x7F) << shift
        if byte & 0x80:
            shift += 7
            if shift > 63:
                raise ValueError("varint too long")
        else:
            out.append(cur)
            cur, shift = 0, 0
    if shift:
        raise ValueError("truncated varint")
    return out


def enc_ints(values) -> bytes:
    return zlib.compress(b"".join(varint(v) for v in values), 6)


def dec_ints(blob: bytes):
    return read_varints(zlib.decompress(blob))


def enc_json(obj) -> bytes:
    return zlib.compress(json.dumps(obj, separators=(",", ":"), default=str).encode("utf-8"), 6)


def artifact_checksum(key: bytes, codec: str, payload: bytes) -> bytes:
    return hashlib.sha256(b"artifact\0" + key + b"\0" + codec.encode() + b"\0" + payload).digest()


def string_checksum(sid: int, text: str) -> bytes:
    return hashlib.sha256(b"string\0" + sid.to_bytes(8, "little") + text.encode("utf-8")).digest()


def global_checksum(name: str, gen_id: int, codec: str, payload: bytes) -> bytes:
    return hashlib.sha256(b"global\0" + name.encode() + b"\0" + gen_id.to_bytes(8, "little") + b"\0"
                          + codec.encode() + b"\0" + payload).digest()


# ---------------------------------------------------------------- part 1: SQLite behaviour

def pragma_behaviour(tmp: Path) -> dict:
    res = {}
    db = tmp / "pragma.sqlite3"
    c = sqlite3.connect(db, isolation_level=None)
    c.execute("CREATE TABLE t (x)")
    c.execute("PRAGMA auto_vacuum = INCREMENTAL")                 # after the first table: silently not applied
    res["auto_vacuum_after_first_table (2 = incremental)"] = c.execute("PRAGMA auto_vacuum").fetchone()[0]
    res["journal_mode_returned"] = c.execute("PRAGMA journal_mode = WAL").fetchone()[0]
    c.execute("BEGIN IMMEDIATE")
    try:
        c.execute("PRAGMA synchronous = FULL")
        res["synchronous_inside_transaction"] = "accepted"
    except sqlite3.Error as e:
        res["synchronous_inside_transaction"] = f"error: {e}"
    c.execute("PRAGMA foreign_keys = ON")                         # documented no-op inside a transaction
    res["foreign_keys_set_inside_transaction (read back)"] = c.execute("PRAGMA foreign_keys").fetchone()[0]
    try:
        c.execute("PRAGMA journal_mode = DELETE")
        res["journal_mode_change_inside_transaction"] = c.execute("PRAGMA journal_mode").fetchone()[0]
    except sqlite3.Error as e:
        res["journal_mode_change_inside_transaction"] = f"error: {e}"
    c.execute("COMMIT")
    c.close()
    c = sqlite3.connect(db, isolation_level=None)
    res["journal_mode_after_reopen (persistent)"] = c.execute("PRAGMA journal_mode").fetchone()[0]
    res["synchronous_after_reopen (per connection; 2 = FULL)"] = c.execute("PRAGMA synchronous").fetchone()[0]
    c.close()
    # Python's default (legacy) transaction control opens a transaction implicitly before INSERT/UPDATE/DELETE,
    # so a PRAGMA issued after a DML statement runs inside a transaction the code never began explicitly.
    c = sqlite3.connect(db)
    c.execute("INSERT INTO t VALUES (1)")
    try:
        c.execute("PRAGMA synchronous = FULL")
        res["python_default_isolation_pragma_after_insert"] = "accepted"
    except sqlite3.Error as e:
        res["python_default_isolation_pragma_after_insert"] = f"error: {e}"
    c.rollback()
    c.close()
    return res


def open_writer(path: Path) -> sqlite3.Connection:
    """Writer connection as design §10.1 specifies: settings applied outside any transaction, then verified."""
    c = sqlite3.connect(path, isolation_level=None)             # autocommit: transactions only where we BEGIN
    new = c.execute("PRAGMA page_count").fetchone()[0] == 0
    if new:
        c.execute("PRAGMA auto_vacuum = INCREMENTAL")
    mode = c.execute("PRAGMA journal_mode = WAL").fetchone()[0]
    c.execute("PRAGMA synchronous = FULL")
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA busy_timeout = 30000")
    eff = {"journal_mode": mode, "synchronous": c.execute("PRAGMA synchronous").fetchone()[0],
           "foreign_keys": c.execute("PRAGMA foreign_keys").fetchone()[0],
           "busy_timeout": c.execute("PRAGMA busy_timeout").fetchone()[0]}
    expected = {"journal_mode": "wal", "synchronous": 2, "foreign_keys": 1, "busy_timeout": 30000}
    if eff != expected:
        raise RuntimeError(f"effective settings {eff} != {expected}")
    if new:
        c.executescript("BEGIN IMMEDIATE; PRAGMA application_id = 0x524E4458; PRAGMA user_version = 1;"
                        + SCHEMA + "COMMIT;")
        if c.execute("PRAGMA auto_vacuum").fetchone()[0] != 2:
            raise RuntimeError("auto_vacuum not incremental")
    return c


# ---------------------------------------------------------------- part 2: build and measure

def db_bytes(c) -> int:
    return c.execute("PRAGMA page_count").fetchone()[0] * c.execute("PRAGMA page_size").fetchone()[0]


def optional_component_status() -> dict:
    out = {}
    for mod in ("tree_sitter", "google.protobuf"):
        try:
            __import__(mod)
            out[mod] = "installed"
        except ImportError:
            out[mod] = "not installed"
    return out


class SharedStrings:
    """Variant A (design as merged in PR #21): strings replaced by ids into one shared ``strings`` table."""
    name = "A_shared_string_table"

    def __init__(self):
        self.ids = {}

    def sid(self, s: str) -> int:
        return self.ids.setdefault(s, len(self.ids) + 1)

    def pairs(self, items):
        return "sid-pairs+zlib/1", enc_ints([x for k, v in items for x in (self.sid(k), v)])

    def strlist(self, items):
        return "sid-list+zlib/1", enc_ints(sorted(self.sid(k) for k in items))


class InlineStrings:
    """Variant B: self-contained payloads. Strings are written inline (varint length + UTF-8), then zlib."""
    name = "B_self_contained"
    ids = {}

    @staticmethod
    def _s(k: str) -> bytes:
        b = k.encode("utf-8")
        return varint(len(b)) + b

    def pairs(self, items):
        return "inline-pairs+zlib/1", zlib.compress(b"".join(self._s(k) + varint(v) for k, v in items), 6)

    def strlist(self, items):
        return "inline-list+zlib/1", zlib.compress(b"".join(self._s(k) for k in sorted(items)), 6)


def decode_inline(blob: bytes, with_values: bool):
    buf, i, out = zlib.decompress(blob), 0, []
    while i < len(buf):
        n, shift = 0, 0
        while True:
            b = buf[i]
            i += 1
            n |= (b & 0x7F) << shift
            shift += 7
            if not b & 0x80:
                break
        text = buf[i:i + n].decode("utf-8")
        i += n
        if with_values:
            v, shift = 0, 0
            while True:
                b = buf[i]
                i += 1
                v |= (b & 0x7F) << shift
                shift += 7
                if not b & 0x80:
                    break
            out.append((text, v))
        else:
            out.append(text)
    return out


def decode(codec: str, payload: bytes):
    if codec.startswith("sid-pairs"):
        return dec_ints(payload)
    if codec.startswith("sid-list"):
        return dec_ints(payload)
    if codec.startswith("inline-pairs"):
        return decode_inline(payload, True)
    if codec.startswith("inline-list"):
        return decode_inline(payload, False)
    if codec.startswith("json"):
        return json.loads(zlib.decompress(payload))
    if codec.startswith(("f32", "f64")):
        return zlib.decompress(payload)
    raise ValueError(codec)


def encode_all(engine, enc) -> dict:
    docs = engine.docs
    lex, sem, abst, fg = engine.lexical_index, engine.semantic_index, engine.abstainer, engine.function_graph
    arts, manifest, file_arts, provides, consumes, by_kind = [], [], [], [], [], {}
    for ordinal, d in enumerate(docs):
        text_sha = hashlib.sha256(d.content.encode("utf-8")).digest()
        counts = lex._doc_term_cache[d.path][1]
        if any(v * 2 != int(v * 2) for v in counts.values()):
            raise ValueError("lexical weight not a multiple of 0.5")
        funcs, calls, syms, imps = fg._polyglot_cache[d.path][1]
        per = {
            "lexical": enc.pairs((t, int(v * 2)) for t, v in counts.items()),
            "semantic": enc.pairs(sem._doc_feature_cache[d.path][1].items()),
            "abstainer": enc.strlist(abst._doc_vocab_cache[d.path][1]),
            "function_graph": ("json+zlib/1", enc_json({
                "functions": [[f.name, f.parent_class, f.is_method, f.is_test, f.start_line, f.arg_names]
                              for f in funcs],
                "calls": [[c.caller_func, c.callee_name, c.is_attribute, c.qualifier, c.start_line] for c in calls],
                "symbols": syms, "imports": imps})),
            "symbols": ("json+zlib/1", enc_json({"symbols": d.symbols, "imports": d.imports})),
        }
        keys = []
        for kind, (codec, payload) in per.items():
            key = hashlib.sha256(f"{kind}\0fp\0{d.path}\0".encode() + text_sha).digest()
            arts.append((key, kind, b"fp-" + kind.encode(), d.path, codec, payload,
                         artifact_checksum(key, codec, payload), 1, 1))
            file_arts.append((d.path, kind, key))
            by_kind[kind] = by_kind.get(kind, 0) + len(payload)
            keys.append(key)
        manifest.append((d.path, ordinal, len(d.content.encode("utf-8")), 0, None, None, text_sha, text_sha,
                         d.language, int(d.is_test), d.line_count, d.token_count,
                         hashlib.sha256(b"".join(sorted(keys))).digest(), hashlib.sha256(b"doc-meta-fp").digest()))
        # Approximation of the dependency index: symbols as provided keys, imports as consumed keys.
        provides += [(d.path, "symbol", k, i) for i, k in enumerate(dict.fromkeys(d.symbols))]
        consumes += [(d.path, "module", k) for k in dict.fromkeys(d.imports)]

    sem_df, abst_ref = {}, {}
    for d in docs:
        for f in sem._doc_feature_cache[d.path][1]:
            sem_df[f] = sem_df.get(f, 0) + 1
        for t in abst._doc_vocab_cache[d.path][1]:
            abst_ref[t] = abst_ref.get(t, 0) + 1
    rg = engine.repo_graph
    vocab_list = list(sem.vocabulary)
    glob = {
        "bm25.df": enc.pairs(lex.doc_frequencies.items()),
        "bm25.lengths": ("f32le+zlib/1", zlib.compress(np.asarray(lex.doc_lengths, "<f4").tobytes(), 6)),
        "semantic.df": enc.pairs(sem_df.items()),
        "semantic.vocabulary": enc.pairs((f, i) for i, f in enumerate(vocab_list)),
        "semantic.idf": ("f32le+zlib/1", zlib.compress(np.asarray(sem.idf, "<f4").tobytes(), 6)),
        "repo_graph.edges": ("json+zlib/1", enc_json([[u, v, a] for u, v, a in rg.graph.edges(data=True)])),
        "repo_graph.pagerank": ("f64le+zlib/1", zlib.compress(np.asarray(rg.pagerank_scores, "<f8").tobytes(), 6)),
        "function_graph.edges": ("json+zlib/1", enc_json([vars(e) if hasattr(e, "__dict__") else str(e)
                                                          for e in fg.edges])),
        "abstainer.refcounts": enc.pairs(abst_ref.items()),
    }
    return {"arts": arts, "manifest": manifest, "file_arts": file_arts, "provides": provides,
            "consumes": consumes, "by_kind": by_kind, "glob": glob, "strings": dict(enc.ids)}


def write_db(data: dict, workdir: Path, n_docs: int) -> dict:
    path = workdir / "prototype.sqlite3"
    wal = workdir / "prototype.sqlite3-wal"
    c = open_writer(path)
    steps = {"empty_schema": db_bytes(c)}
    wal_peak = 0
    t_write = time.perf_counter()

    def commit():
        nonlocal wal_peak
        c.execute("COMMIT")
        wal_peak = max(wal_peak, wal.stat().st_size if wal.exists() else 0)

    c.execute("BEGIN IMMEDIATE")
    c.execute("INSERT INTO generations(gen_id, state, kind, started_at, index_fingerprint, discovery_fingerprint)"
              " VALUES (1, 'building', 'cold', 'now', x'00', x'00')")
    commit()
    before = db_bytes(c)
    rows = sorted(data["strings"].items(), key=lambda kv: kv[1])
    for i in range(0, len(rows), 50_000):
        c.execute("BEGIN IMMEDIATE")
        c.executemany("INSERT INTO strings(sid, text, checksum) VALUES (?, ?, ?)",
                      [(s, t, string_checksum(s, t)) for t, s in rows[i:i + 50_000]])
        commit()
    steps["strings_table"] = db_bytes(c) - before
    before = db_bytes(c)
    arts = data["arts"]
    per_batch = BATCH_FILES * max(1, len(arts) // max(1, n_docs))
    for i in range(0, len(arts), per_batch):
        c.execute("BEGIN IMMEDIATE")
        c.executemany("INSERT OR IGNORE INTO artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", arts[i:i + per_batch])
        commit()
    steps["artifacts_table"] = db_bytes(c) - before
    # The publish transaction: manifest, file_artifacts, dependency index, global state, generation marker.
    c.execute("BEGIN IMMEDIATE")
    before = db_bytes(c)
    c.executemany("INSERT INTO manifest VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", data["manifest"])
    c.executemany("INSERT INTO file_artifacts VALUES (?, ?, ?)", data["file_arts"])
    mid = db_bytes(c)
    c.executemany("INSERT OR IGNORE INTO provides VALUES (?, ?, ?, ?)", data["provides"])
    c.executemany("INSERT OR IGNORE INTO consumes VALUES (?, ?, ?)", data["consumes"])
    mid2 = db_bytes(c)
    c.executemany("INSERT INTO global_state VALUES (?, 1, ?, ?, ?)",
                  [(n, codec, p, global_checksum(n, 1, codec, p)) for n, (codec, p) in data["glob"].items()])
    c.execute("UPDATE generations SET state='published', published_at='now', file_count=? WHERE gen_id=1", (n_docs,))
    c.execute("INSERT INTO meta VALUES ('current_generation', '1')")
    end = db_bytes(c)
    commit()
    write_s = time.perf_counter() - t_write
    steps["manifest_and_file_artifacts"] = mid - before
    steps["provides_consumes (approximation)"] = mid2 - mid
    steps["global_state_table"] = end - mid2
    wal_before_checkpoint = wal.stat().st_size if wal.exists() else 0
    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    db_file = path.stat().st_size

    copy = workdir / "copy.sqlite3"
    c.execute(f"VACUUM INTO '{copy.as_posix()}'")
    cc = sqlite3.connect(copy, isolation_level=None)
    vacuumed = db_bytes(cc)
    for ix in SECONDARY_INDEXES:
        cc.execute(f"DROP INDEX {ix}")
    cc.execute("VACUUM")
    secondary = vacuumed - db_bytes(cc)
    cc.close()
    copy.unlink()

    # Verification cost: every string and artifact checksum, then decode.
    t = time.perf_counter()
    for s, text, ck in c.execute("SELECT sid, text, checksum FROM strings"):
        if string_checksum(s, text) != ck:
            raise RuntimeError("string checksum")
    load_strings_s = time.perf_counter() - t
    t = time.perf_counter()
    n_ok = 0
    for key, codec, payload, ck in c.execute("SELECT artifact_key, codec, payload, checksum FROM artifacts"):
        if artifact_checksum(key, codec, payload) != ck:
            raise RuntimeError("artifact checksum")
        decode(codec, payload)
        n_ok += 1
    verify_decode_s = time.perf_counter() - t
    sweep_s = None
    if data["strings"]:
        t = time.perf_counter()
        live = set()
        for codec, payload in c.execute("SELECT codec, payload FROM artifacts WHERE codec LIKE 'sid-%' UNION ALL "
                                        "SELECT codec, payload FROM global_state WHERE codec LIKE 'sid-%'"):
            vals = dec_ints(payload)
            live.update(vals[0::2] if codec.startswith("sid-pairs") else vals)
        sweep_s = time.perf_counter() - t
    c.close()

    payload_total = sum(data["by_kind"].values())
    string_text = sum(len(t.encode("utf-8")) for t in data["strings"])
    glob_payload = sum(len(p) for _, p in data["glob"].values())
    return {
        "1_encoded_per_file_payload_bytes": {"total": payload_total, "by_kind": data["by_kind"]},
        "2_string_table": {"unique_strings": len(data["strings"]), "utf8_text_bytes": string_text,
                           "checksum_bytes": 32 * len(data["strings"]),
                           "sqlite_bytes_incl_unique_index": steps["strings_table"]},
        "3_database_file_bytes_after_checkpoint": db_file,
        "3_database_bytes_after_vacuum_into": vacuumed,
        "4_overhead": {
            "secondary_indexes_bytes": secondary,
            "everything_else_bytes": db_file - secondary - payload_total - string_text - glob_payload,
            "note": "file size minus secondary indexes, artifact payloads, string text and global payloads: "
                    "checksums, keys, manifest and dependency rows, implicit PRIMARY KEY/UNIQUE indexes, page "
                    "headers and free space",
        },
        "5_wal": {"peak_wal_bytes_observed_after_commits": wal_peak,
                  "wal_bytes_before_truncate_checkpoint": wal_before_checkpoint,
                  "wal_bytes_after_truncate_checkpoint": 0, "temporary_files": "not measured"},
        "7_global_state": {"payload_bytes": {n: len(p) for n, (_, p) in data["glob"].items()},
                           "payload_total": glob_payload, "sqlite_bytes": steps["global_state_table"]},
        "sqlite_growth_by_step_bytes": steps,
        "timings_s (indicative, single run)": {
            "write_all_with_synchronous_full": round(write_s, 3),
            "verify_string_checksums": round(load_strings_s, 3),
            "verify_checksums_and_decode_all_artifacts": round(verify_decode_s, 3),
            "string_sweep_collect_live_sids": None if sweep_s is None else round(sweep_s, 3)},
        "artifacts_verified": n_ok,
    }


def corruption_checks(data: dict) -> dict:
    """Structurally valid alterations must fail the checksums (variant A data)."""
    out = {}
    key, kind, _, _, codec, payload, ck, _, _ = next(a for a in data["arts"] if a[1] == "lexical")
    vals = dec_ints(payload)
    vals[1] += 2                                              # one term weight +1.0: still a valid payload
    altered = enc_ints(vals)
    out["altered_payload_still_decodes"] = len(dec_ints(altered)) == len(vals)
    out["altered_payload_rejected"] = artifact_checksum(key, codec, altered) != ck
    a1, a2 = [a for a in data["arts"] if a[1] == "lexical"][:2]
    out["swapped_payloads_rejected"] = (artifact_checksum(a1[0], a1[4], a2[5]) != a1[6]
                                        and artifact_checksum(a2[0], a2[4], a1[5]) != a2[6])
    text, s = next(iter(data["strings"].items()))
    out["altered_string_rejected"] = string_checksum(s, text + "x") != string_checksum(s, text)
    out["string_moved_to_another_sid_rejected"] = string_checksum(s + 1, text) != string_checksum(s, text)
    codec, payload = data["glob"]["bm25.lengths"]
    arr = np.frombuffer(zlib.decompress(payload), "<f4").copy()
    arr[0] += 1.0
    out["altered_global_state_rejected"] = (global_checksum("bm25.lengths", 1, codec, zlib.compress(arr.tobytes(), 6))
                                            != global_checksum("bm25.lengths", 1, codec, payload))
    return out


def measure(repo: str, workdir: Path, snap=None) -> dict:
    t0 = time.perf_counter()
    engine = RepoNeedleEngine.from_directory(repo, max_files=10 ** 7)
    build_s = time.perf_counter() - t0
    docs = engine.docs
    source = sum(len(d.content.encode("utf-8")) for d in docs)
    out = {}
    if snap:
        out["snapshot"] = {**snap.describe(docs), "package_code_matches_commit": package_matches_commit(snap.commit)}
    out.update({"files": len(docs), "source_bytes": source, "from_directory_s": round(build_s, 3)})
    m = engine.semantic_index.doc_matrix.tocsr()
    out["semantic_csr_matrix_if_persisted_bytes (not proposed for Stage 1)"] = len(zlib.compress(
        m.indptr.astype("<i4").tobytes() + m.indices.astype("<i4").tobytes() + m.data.astype("<f4").tobytes(), 6))
    out["6_optional_tree_sitter_scip"] = {
        "status": optional_component_status(),
        "bytes": "not measured: the extras are not installed in the measurement environment, and the default "
                 "build produces no Tree-sitter or SCIP artifacts"}
    for enc in (SharedStrings(), InlineStrings()):
        data = encode_all(engine, enc)
        work = workdir / enc.name
        work.mkdir()
        res = write_db(data, work, len(docs))
        db = res["3_database_file_bytes_after_checkpoint"]
        res["ratios_to_source"] = {
            "per_file_payload": round(res["1_encoded_per_file_payload_bytes"]["total"] / source, 3),
            "per_file_payload_plus_string_text": round((res["1_encoded_per_file_payload_bytes"]["total"]
                                                        + res["2_string_table"]["utf8_text_bytes"]) / source, 3),
            "database_file": round(db / source, 3)}
        res["projection_100k_files_database_bytes (linear, estimate)"] = int(db / len(docs) * 100_000)
        if isinstance(enc, SharedStrings):
            res["corruption_checks"] = corruption_checks(data)
        out[enc.name] = res
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default="HEAD", help="commit of this repository to measure")
    ap.add_argument("--synthetic", type=int, default=3000)
    ap.add_argument("--file-set-out", default=None, help="also write the measured file list (path, bytes) here")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    result = {"environment": {"python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
                              "platform": platform.platform()}}
    tmp = Path(tempfile.mkdtemp(prefix="rn_sqlite_proto_"))
    try:
        result["sqlite_behaviour"] = pragma_behaviour(tmp)
        with Snapshot(args.snapshot) as snap:
            check_out_path(args.out, snap.path)
            check_out_path(args.file_set_out, snap.path)
            work = tmp / "repo"
            work.mkdir()
            result["this repository (pinned snapshot)"] = measure(str(snap.path), work, snap)
            if args.file_set_out:
                engine_docs = RepoNeedleEngine.from_directory(str(snap.path), max_files=10 ** 7).docs
                Path(args.file_set_out).write_text(json.dumps(snap.describe(engine_docs, with_list=True), indent=1)
                                                   + "\n", encoding="utf-8")
        if args.synthetic:
            syn = tmp / "synthetic"
            write_synthetic_repo(syn, args.synthetic)
            work = tmp / "syn_db"
            work.mkdir()
            result[f"synthetic {args.synthetic} files"] = measure(str(syn), work)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps(result, indent=1, default=str))
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
