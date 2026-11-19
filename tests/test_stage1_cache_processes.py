"""
V2 Stage 1: separate processes. Warm restarts in fresh interpreters, crash injection at every point of the writer
protocol, and concurrent readers and writers. Crashes are injected in the CHILD process by wrapping the writer
connection (no test hooks exist in the package): the child calls os._exit() at the chosen point, exactly like a
killed process, without running any cleanup.
"""

import hashlib
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cache_support import (FILES, ROOT, TESTS, assert_same_as_fresh, cache_config, cached, capture_in_child,
                           db_path, fresh, last, make_repo, published_generation, run_python, write)
from index_equivalence import capture_all, compare_captures, load_queries


def _published_digests(cfg):
    conn = sqlite3.connect(str(db_path(cfg)))
    try:
        return {p: bytes(d) for p, d in conn.execute("SELECT path, text_sha256 FROM manifest")}
    finally:
        conn.close()


def _repo_digests(engine):
    return {d.path: hashlib.sha256(d.content.encode("utf-8")).digest() for d in engine.docs}


# ------------------------------------------------------------------------------------------- warm restarts

@pytest.mark.parametrize("step", [1], ids=["full_225_query_corpus"])
def test_warm_restart_in_a_fresh_process_full_corpus(tmp_path, step):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    child = capture_in_child(repo, cfg, tmp_path / "warm.pickle", step=step)
    assert child["report"]["files_reused"] == child["report"]["files_indexed"] > 0
    reference = capture_in_child(repo, None, tmp_path / "fresh.pickle", step=step)["capture"]
    compare_captures(child["capture"], reference, label="warm restart in a separate process (225 queries)")


@pytest.mark.parametrize("mutation", ["modify", "add", "delete"])
def test_restart_in_a_fresh_process_after_a_change(tmp_path, mutation):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    if mutation == "modify":
        write(repo, "shop/inventory.py", FILES["shop/inventory.py"] + "\n\ndef restock(n):\n    return n\n")
    elif mutation == "add":
        write(repo, "shop/gift.py", "from shop.cart import Cart\n\n\ndef wrap(cart):\n    return Cart()\n")
    else:
        os.remove(repo / "shop" / "utils" / "config.py")
    child = capture_in_child(repo, cfg, tmp_path / f"{mutation}.pickle")
    assert child["report"]["files_extracted"] == (0 if mutation == "delete" else 1)
    reference = capture_in_child(repo, None, tmp_path / f"{mutation}-fresh.pickle")["capture"]
    compare_captures(child["capture"], reference, label=f"fresh-process restart after {mutation}")


def test_uncached_builds_already_differ_across_hash_seeds(tmp_path):
    """Documents the pre-existing behaviour that forces same-seed comparisons (not caused by the cache)."""
    repo = make_repo(tmp_path)
    a = capture_in_child(repo, None, tmp_path / "a.pickle", seed="1")["capture"]
    b = capture_in_child(repo, None, tmp_path / "b.pickle", seed="2")["capture"]
    with pytest.raises(AssertionError, match="doc_frequencies"):
        compare_captures(a, b, label="two uncached builds, different hash seeds")


# ------------------------------------------------------------------------------------------ crash injection

CRASH_CHILD = r'''
import os, sys
from reponeedle.core.index_cache import session, store
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import IndexCacheConfig

repo, cache_dir, point = sys.argv[1:4]
state = {"in_publish": False, "in_gc": False, "commits": 0}


class Proxy:
    def __init__(self, conn):
        self._c = conn

    def execute(self, sql, *args):
        if sql == "COMMIT":
            state["commits"] += 1
            if point == "publish_before_commit" and state["in_publish"]:
                os._exit(77)
            if point == "gc_before_commit" and state["in_gc"]:
                os._exit(77)
        result = self._c.execute(sql, *args)
        if sql == "COMMIT" and point == "after_first_artifact_batch" and state["commits"] == 2:
            os._exit(77)
        return result

    def __getattr__(self, name):
        return getattr(self._c, name)


real_open = session.open_writer
session.open_writer = lambda *a, **k: Proxy(real_open(*a, **k))
real_begin, real_publish, real_gc = (store.CacheWriter.begin_generation, store.CacheWriter.publish,
                                     store.CacheWriter.collect_garbage)


def begin(self, *a, **k):
    gen = real_begin(self, *a, **k)
    if point == "after_building_marker":
        os._exit(77)
    return gen


def publish(self, *a, **k):
    state["in_publish"] = True
    out = real_publish(self, *a, **k)
    state["in_publish"] = False
    if point == "after_publish_before_gc":
        os._exit(77)
    return out


def gc(self, *a, **k):
    state["in_gc"] = True
    return real_gc(self, *a, **k)


store.CacheWriter.begin_generation, store.CacheWriter.publish, store.CacheWriter.collect_garbage = begin, publish, gc
store.ARTIFACT_BATCH_ROWS = 7          # several batches, so a crash can land between them
RepoNeedleEngine.from_directory(repo, index_cache=IndexCacheConfig(cache_dir=cache_dir))
os._exit(0)
'''

CRASH_POINTS = {
    "after_building_marker": "old",
    "after_first_artifact_batch": "old",
    "publish_before_commit": "old",
    "after_publish_before_gc": "new",
    "gc_before_commit": "new",
}


@pytest.mark.parametrize("point", sorted(CRASH_POINTS))
def test_a_crash_never_exposes_a_partial_generation(tmp_path, point):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    old_engine = cached(repo, cfg)
    old = _published_digests(cfg)
    old_gen = published_generation(cfg)
    write(repo, "shop/cart.py", FILES["shop/cart.py"] + "\n\ndef clear(cart):\n    cart.items = {}\n")
    write(repo, "shop/new_module.py", "def created():\n    return 1\n")
    res = run_python(CRASH_CHILD, str(repo), cfg.cache_dir, point, check=False)
    assert res.returncode == 77, (res.returncode, res.stderr[-2000:])

    expected_new = {p: d for p, d in _repo_digests(fresh(repo)).items()}
    published = _published_digests(cfg)
    if CRASH_POINTS[point] == "old":
        assert published == old and published_generation(cfg) == old_gen
    else:
        assert published == expected_new and published_generation(cfg) == old_gen + 1
    # The surviving generation verifies (rebuild_policy="never" raises on anything unusable) and is equivalent.
    engine = cached(repo, cache_config(tmp_path, rebuild_policy="never"))
    assert last(engine)["state"] == "published" and not last(engine)["rebuilt_from_scratch"]
    assert_same_as_fresh(engine, repo, f"after a crash at {point}", packing_queries=None)
    del old_engine


def test_a_writer_killed_while_holding_the_lock_does_not_block_others(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    code = ("import os, sqlite3, sys\n"
            "c = sqlite3.connect(sys.argv[1], isolation_level=None)\n"
            "c.execute('BEGIN IMMEDIATE')\n"
            "c.execute(\"UPDATE meta SET value = value WHERE key = 'created_by'\")\n"
            "os._exit(77)\n")
    assert run_python(code, str(db_path(cfg)), check=False).returncode == 77
    engine = cached(repo, cache_config(tmp_path, busy_timeout_s=5))
    assert last(engine)["state"] == "published"
    assert_same_as_fresh(engine, repo, "after a writer died holding the lock", packing_queries=None)


# ---------------------------------------------------------------------------------------------- concurrency

READER_CHILD = r'''
import sys
from reponeedle.core.index_cache.connection import open_reader
from reponeedle.core.index_cache.fingerprints import extractor_fingerprints
from reponeedle.core.index_cache.paths import locate
from reponeedle.core.index_cache.store import load_generation
from reponeedle.engine import RepoNeedleEngine

repo, cache_dir, db, rounds = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
loc = locate(repo, cache_dir)
fps = {k: bytes.fromhex(v) for k, v in extractor_fingerprints(RepoNeedleEngine()).items()}
gens = []
from pathlib import Path
for _ in range(rounds):
    conn = open_reader(Path(db), 30.0, read_only=False)
    try:
        gens.append(load_generation(conn, loc.repo_root, loc.repo_id, fps).gen_id)   # raises on any torn read
    finally:
        conn.close()
print("OK", min(gens), max(gens), len(gens))
'''

WRITER_CHILD = r'''
import sys
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import IndexCacheConfig
repo, cache_dir, rounds = sys.argv[1], sys.argv[2], int(sys.argv[3])
for _ in range(rounds):
    e = RepoNeedleEngine.from_directory(repo, index_cache=IndexCacheConfig(cache_dir=cache_dir,
                                                                           rebuild_policy="always"))
    r = e.index_cache_diagnostics["last_update"]
    assert r["state"] == "published", r
print("OK", r["generation"])
'''


def _spawn(code, *args):
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT), str(TESTS)])}
    return subprocess.Popen([sys.executable, "-c", code, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=env, cwd=str(ROOT))


def _wait(proc, timeout=600):
    out, err = proc.communicate(timeout=timeout)
    assert proc.returncode == 0, err[-3000:]
    return out


def test_concurrent_readers_and_writers(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    db = str(db_path(cfg))
    writers = [_spawn(WRITER_CHILD, str(repo), cfg.cache_dir, "3") for _ in range(2)]
    readers = [_spawn(READER_CHILD, str(repo), cfg.cache_dir, db, "25") for _ in range(3)]
    reader_out = [_wait(p) for p in readers]
    writer_out = [_wait(p) for p in writers]
    assert all(o.startswith("OK") for o in reader_out + writer_out)
    assert published_generation(cfg) == 1 + 2 * 3, "every one of the six publishes must have happened"
    engine = cached(repo, cache_config(tmp_path, rebuild_policy="never"))
    assert last(engine)["files_reused"] == len(engine.docs)
    assert_same_as_fresh(engine, repo, "after concurrent writers and readers", packing_queries=None)


def test_writer_waits_for_a_lock_and_then_publishes(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    holder = sqlite3.connect(str(db_path(cfg)), isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    proc = _spawn(WRITER_CHILD, str(repo), cfg.cache_dir, "1")
    time.sleep(2.0)
    assert proc.poll() is None, "the writer must wait while another connection holds the write lock"
    holder.execute("ROLLBACK")
    holder.close()
    assert _wait(proc).startswith("OK")
    assert published_generation(cfg) == 2


def test_lock_timeout_leaves_a_correct_in_memory_engine(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    holder = sqlite3.connect(str(db_path(cfg)), isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    try:
        engine = cached(repo, cache_config(tmp_path, busy_timeout_s=0.2, rebuild_policy="always"))
    finally:
        holder.execute("ROLLBACK")
        holder.close()
    r = last(engine)
    assert r["state"] == "not_persisted" and "locked" in r["reason"].lower()
    assert published_generation(cfg) == 1
    assert_same_as_fresh(engine, repo, "write lock timeout", packing_queries=None)


def test_checkpoint_with_an_open_reader_is_postponed_not_unsafe(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    reader = sqlite3.connect(str(db_path(cfg)), isolation_level=None)
    reader.execute("BEGIN")
    reader.execute("SELECT count(*) FROM manifest").fetchone()      # holds a read snapshot
    try:
        engine = cached(repo, cache_config(tmp_path, rebuild_policy="always"))
        assert last(engine)["state"] == "published" and "checkpoint postponed" in last(engine)["reason"]
        old_view = reader.execute("SELECT value FROM meta WHERE key = 'current_generation'").fetchone()[0]
        assert old_view == "1", "an open reader keeps its snapshot of the previous generation"
    finally:
        reader.execute("COMMIT")
        reader.close()
    engine = cached(repo, cache_config(tmp_path, rebuild_policy="never"))
    assert last(engine)["files_reused"] == len(engine.docs)
    assert_same_as_fresh(engine, repo, "after a postponed checkpoint", packing_queries=None)
