"""
V2 Stage 1: persist_exclude. A matching file is indexed in memory exactly as usual, but nothing derived from it is
in the cache files: not its path, decoded-text digest, symbols, imports, tokens, artifacts or ordinal position.

The scanner below searches the main database, the WAL, the SHM and every other file in the cache directory for:
raw marker strings, the path, the digests (raw and hex), every decodable zlib stream at any byte offset (stale
pages included), and every artifact payload decoded through the production codecs. It is first shown to FIND the
markers while the file is still persisted, so its silence afterwards is meaningful.
"""

import hashlib
import sqlite3
import zlib
from pathlib import Path

from cache_support import FILES, assert_same_as_fresh, cache_config, cached, db_path, last, make_repo
from reponeedle.core.index_cache import codecs, schema

SECRET_PATH = "private/zqxj_vault_settings.py"
MARKERS = ["ZQXJ_UNIQUE_MARKER_7f3a91", "zqxj_secret_function", "ZqxjCredentialHolder", "zqxj_vault_settings",
           "zqxj_internal_module"]
SECRET_TEXT = (
    "from zqxj_internal_module import loader\n\n\n"
    "API_TOKEN = 'ZQXJ_UNIQUE_MARKER_7f3a91'\n\n\n"
    "class ZqxjCredentialHolder:\n"
    "    def zqxj_secret_function(self):\n"
    "        return loader(API_TOKEN)\n"
)


def _repo(tmp_path):
    return make_repo(tmp_path, {**FILES, SECRET_PATH: SECRET_TEXT})


def _zlib_streams(raw: bytes):
    for i in range(len(raw) - 2):
        if raw[i] == 0x78 and raw[i + 1] in (0x01, 0x5E, 0x9C, 0xDA):
            d = zlib.decompressobj()
            try:
                out = d.decompress(raw[i:i + 1_000_000], 4_000_000)
            except zlib.error:
                continue
            if out:
                yield out


def _decoded_payloads(db: Path):
    conn = sqlite3.connect(str(db))
    try:
        for kind, codec, payload in conn.execute("SELECT kind, codec, payload FROM artifacts"):
            yield repr(codecs.decode(kind, codec, payload)).encode("utf-8")
    finally:
        conn.close()


def find_secret_traces(cache_dir: Path, db: Path):
    digest = hashlib.sha256(SECRET_TEXT.encode("utf-8")).digest()
    needles = [m.encode("utf-8") for m in MARKERS] + [SECRET_PATH.encode("utf-8"), digest, digest.hex().encode()]
    found = []
    for f in sorted(cache_dir.iterdir()):
        raw = f.read_bytes()
        found += [f"{f.name}: raw {n[:40]!r}" for n in needles if n in raw]
        for stream in _zlib_streams(raw):
            found += [f"{f.name}: zlib stream contains {n[:40]!r}" for n in needles if n in stream]
    for decoded in _decoded_payloads(db):
        found += [f"decoded payload contains {n[:40]!r}" for n in needles if n in decoded]
    return found


def _ordinals(db):
    conn = sqlite3.connect(str(db))
    try:
        return [r[0] for r in conn.execute("SELECT ordinal FROM manifest ORDER BY ordinal")]
    finally:
        conn.close()


def test_scanner_finds_the_markers_while_the_file_is_persisted(tmp_path):
    repo, cfg = _repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    traces = find_secret_traces(Path(cfg.cache_dir), db_path(cfg))
    assert any("decoded payload" in t for t in traces) and any("zlib stream" in t for t in traces)
    assert any("raw" in t for t in traces)


def test_excluded_from_the_start_is_never_persisted(tmp_path):
    repo, cfg = _repo(tmp_path), cache_config(tmp_path, persist_exclude=["private/**"])
    engine = cached(repo, cfg)
    assert SECRET_PATH in engine.path_to_doc
    assert last(engine)["files_persist_excluded"] == 1
    assert find_secret_traces(Path(cfg.cache_dir), db_path(cfg)) == []
    assert _ordinals(db_path(cfg)) == list(range(len(engine.docs) - 1)), "ordinals must be dense"
    assert_same_as_fresh(engine, repo, "persist_exclude from the start")
    warm = cached(repo, cfg)
    assert last(warm)["files_extracted"] == 1, "the excluded file is re-extracted on every start"
    assert find_secret_traces(Path(cfg.cache_dir), db_path(cfg)) == []
    assert_same_as_fresh(warm, repo, "persist_exclude, warm")


def test_newly_excluded_file_is_purged_from_every_cache_file(tmp_path):
    repo = _repo(tmp_path)
    first = cached(repo, cache_config(tmp_path))
    cfg = cache_config(tmp_path, persist_exclude=["**/zqxj_*"])
    engine = cached(repo, cfg)
    r = last(engine)
    assert r["state"] == "published" and r["files_persist_excluded"] == 1 and SECRET_PATH in r["deleted"]
    # The excluded file's nine artifacts, plus every other file's two resolution artifacts: while an excluded file
    # is indexed, graph contributions are not persisted (they could depend on it).
    assert r["artifacts_collected"] == len(schema.KINDS) + 2 * (len(first.docs) - 1)
    assert r["privacy_purge"] == "complete"
    assert find_secret_traces(Path(cfg.cache_dir), db_path(cfg)) == []
    assert _ordinals(db_path(cfg)) == list(range(len(engine.docs) - 1))
    assert_same_as_fresh(engine, repo, "file excluded after it was persisted")


def test_excluded_file_skipped_for_size_leaves_no_path(tmp_path):
    repo = _repo(tmp_path)
    (repo / "private" / "zqxj_big.json").write_text("{" + " " * 600_000 + "}", encoding="utf-8")
    cfg = cache_config(tmp_path, persist_exclude=["private/**"])
    engine = cached(repo, cfg)
    assert "private/zqxj_big.json" in engine.indexing_diagnostics.skipped_paths
    conn = sqlite3.connect(str(db_path(cfg)))
    assert conn.execute("SELECT count(*) FROM excluded WHERE path LIKE 'private/%'").fetchone()[0] == 0
    conn.close()
