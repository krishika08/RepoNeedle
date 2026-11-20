"""
V2 Stage 3: the semantic index through every engine lifecycle, compared exactly with the Stage 2 reference and with
fresh uncached builds:
new cache, warm restart, in-process refresh(), update_documents(), remove_documents(), builds in fresh processes
under PYTHONHASHSEED 0 and 1 (the semantic index does not depend on the hash seed), a corrupt semantic artifact,
a crash at every publish step, and concurrent writers. The database stays schema version 2 with no semantic
global state.
"""

import json
import sqlite3

import pytest

from cache_support import (SAMPLE, assert_same_as_fresh, cache_config, cached, db_path, fresh, last, make_repo,
                           published_generation, run_python, write)
from index_equivalence import assert_equivalent
from reponeedle.engine import RepoNeedleEngine
from stage2_support import MUTATIONS, check, synthetic_files, write_tree
from stage3_support import (QUERY_TEXTS, assert_semantic_equal, docs_from_files, fixture_docs,
                            reference_semantic)
from test_stage1_cache_processes import CRASH_CHILD, CRASH_POINTS, _published_digests, _repo_digests

SEM_QUERIES = QUERY_TEXTS[::10]


def _same_as_stage2(engine, repo, label, **kw):
    with reference_semantic():
        ref = fresh(repo, **kw)
    assert_semantic_equal(engine.semantic_index, ref.semantic_index, label, queries=SEM_QUERIES)


def test_new_cache_warm_restart_and_refresh(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cold = cached(repo, cfg)
    assert last(cold)["state"] == "published"
    _same_as_stage2(cold, repo, "new cache")
    warm = cached(repo, cfg)
    assert last(warm)["work_counters"]["semantic"]["feature_cache_misses"] == 0
    _same_as_stage2(warm, repo, "warm restart")
    assert_same_as_fresh(warm, repo, "warm restart", packing_queries=None)
    write(repo, "shop/refresh_added.py", "def refreshed_semantic_feature(x):\n    return x\n")
    warm.refresh()
    _same_as_stage2(warm, repo, "refresh")
    assert_same_as_fresh(warm, repo, "refresh", packing_queries=None)


def test_update_and_remove_documents_equal_the_reference():
    docs = fixture_docs()
    engine = RepoNeedleEngine.from_documents([d.model_copy(deep=True) for d in docs])
    with reference_semantic():
        reference = RepoNeedleEngine.from_documents([d.model_copy(deep=True) for d in docs])
    extra = docs_from_files({"shop/extra_module.py": "def extra_semantic_feature(order):\n    return order\n"})
    edited = docs[2].model_copy(update={"content": docs[2].content + "\n# ledger reconciliation\n"})
    for e in (engine, reference):
        e.update_documents([d.model_copy(deep=True) for d in extra + [edited]])
    assert_semantic_equal(engine.semantic_index, reference.semantic_index, "update_documents", queries=SEM_QUERIES)
    assert_equivalent(engine, reference, label="update_documents: whole engine vs the Stage 2 semantic index",
                      queries=SAMPLE, packing_queries=None)
    removed = [docs[0].path, docs[5].path]
    for e in (engine, reference):
        e.remove_documents(removed)
    assert_semantic_equal(engine.semantic_index, reference.semantic_index, "remove_documents", queries=SEM_QUERIES)
    assert_equivalent(engine, reference, label="remove_documents: whole engine vs the Stage 2 semantic index",
                      queries=SAMPLE, packing_queries=None)
    rebuilt = RepoNeedleEngine.from_documents([d.model_copy(deep=True) for d in engine.docs])
    assert_equivalent(engine, rebuilt, label="remove_documents vs a fresh build", queries=SAMPLE,
                      packing_queries=None)


DIGEST_CHILD = r'''
import hashlib, json, sys
from index_equivalence import capture_semantic, load_queries
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import IndexCacheConfig
repo, cache_dir = sys.argv[1], sys.argv[2]
cfg = None if cache_dir == "-" else IndexCacheConfig(cache_dir=cache_dir)
engine = RepoNeedleEngine.from_directory(repo, index_cache=cfg)
sem = engine.semantic_index
h = hashlib.sha256()
state = capture_semantic(sem)
h.update(json.dumps([list(state["vocabulary"].items()), state["doc_paths"], state["num_docs"],
                     list(state["matrix_shape"]), state["matrix_format"]]).encode())
for k in ("idf", "indptr", "indices", "data"):
    h.update(str(state[k].dtype).encode() + state[k].tobytes())
for q in load_queries()[::5]:
    h.update(sem.score(q["text"]).tobytes())
report = engine.index_cache_diagnostics["last_update"] if cfg else None
print(json.dumps({"digest": h.hexdigest(),
                  "misses": report["work_counters"]["semantic"]["feature_cache_misses"] if report else None}))
'''


def test_semantic_output_is_identical_across_processes_and_hash_seeds(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)                                    # the cache other processes start from
    results = {}
    for seed in ("0", "1"):
        for mode, cache_dir in (("uncached", "-"), ("warm", cfg.cache_dir)):
            out = run_python(DIGEST_CHILD, str(repo), cache_dir, env={"PYTHONHASHSEED": seed}).stdout
            results[(seed, mode)] = json.loads(out.strip().splitlines()[-1])
    digests = {k: v["digest"] for k, v in results.items()}
    assert len(set(digests.values())) == 1, digests
    assert results[("0", "warm")]["misses"] == 0 and results[("1", "warm")]["misses"] == 0
    with reference_semantic():
        ref = fresh(repo)
    assert_semantic_equal(fresh(repo).semantic_index, ref.semantic_index, "in-process vs Stage 2")


def test_a_corrupt_semantic_artifact_is_rejected_and_rebuilt(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    path = db_path(cfg)
    conn = sqlite3.connect(str(path), isolation_level=None)
    (k1, p1), (k2, p2) = conn.execute("SELECT artifact_key, payload FROM artifacts WHERE kind = 'semantic' "
                                      "ORDER BY artifact_key LIMIT 2").fetchall()
    conn.execute("UPDATE artifacts SET payload = ? WHERE artifact_key = ?", (p2, k1))
    conn.execute("UPDATE artifacts SET payload = ? WHERE artifact_key = ?", (p1, k2))
    conn.close()
    engine = cached(repo, cfg)
    r = last(engine)
    assert r["rebuilt_from_scratch"] and "checksum" in r["reason"]
    assert r["work_counters"]["semantic"]["feature_cache_hits"] == 0
    _same_as_stage2(engine, repo, "rebuilt after a corrupt semantic artifact")
    assert_same_as_fresh(engine, repo, "rebuilt after a corrupt semantic artifact", packing_queries=None)


@pytest.mark.parametrize("point", sorted(CRASH_POINTS))
def test_an_interrupted_publish_never_exposes_a_partial_generation(tmp_path, point):
    repo = write_tree(tmp_path / "repo", synthetic_files())
    cfg = cache_config(tmp_path)
    cached(repo, cfg)
    old, old_gen = _published_digests(cfg), published_generation(cfg)
    write(repo, "app/semantic_crash.py", "def crash_time_semantic_feature(x):\n    return x\n")
    dict(MUTATIONS)["rename_file"](repo)
    res = run_python(CRASH_CHILD, str(repo), cfg.cache_dir, point, check=False)
    assert res.returncode == 77, (res.returncode, res.stderr[-2000:])
    if CRASH_POINTS[point] == "old":
        assert _published_digests(cfg) == old and published_generation(cfg) == old_gen
    else:
        assert _published_digests(cfg) == _repo_digests(fresh(repo)) and published_generation(cfg) == old_gen + 1
    engine = cached(repo, cache_config(tmp_path, rebuild_policy="never"))
    assert last(engine)["state"] == "published" and not last(engine)["rebuilt_from_scratch"]
    _same_as_stage2(engine, repo, f"after a crash at {point}")
    check(engine, repo, f"after a crash at {point}")


SEMANTIC_WRITER = r'''
import sys
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import IndexCacheConfig
repo, cache_dir, rounds = sys.argv[1], sys.argv[2], int(sys.argv[3])
for _ in range(rounds):
    e = RepoNeedleEngine.from_directory(repo, index_cache=IndexCacheConfig(cache_dir=cache_dir))
    r = e.index_cache_diagnostics["last_update"]
    assert r["state"] == "published", r
    assert r["global_structures"]["semantic"] == "recomputed_in_full", r["global_structures"]
print("OK", r["generation"], flush=True)
'''


def test_concurrent_writers(tmp_path):
    import time

    from test_stage1_cache_processes import READER_CHILD, _spawn, _wait

    repo = write_tree(tmp_path / "repo", synthetic_files())
    cfg = cache_config(tmp_path)
    cached(repo, cfg)
    db = str(db_path(cfg))
    writers = [_spawn(SEMANTIC_WRITER, str(repo), cfg.cache_dir, "4") for _ in range(2)]
    readers = [_spawn(READER_CHILD, str(repo), cfg.cache_dir, db, "15")]
    for i, name in enumerate(("add_function", "rename_file", "delete_files")):
        time.sleep(0.4)
        dict(MUTATIONS)[name](repo)
        write(repo, f"conc/w{i}.py", f"def concurrent_feature_{i}(x):\n    return x\n")
    outs = [_wait(p) for p in writers + readers]
    assert all(o.startswith("OK") for o in outs), outs
    engine = cached(repo, cache_config(tmp_path, rebuild_policy="never"))
    _same_as_stage2(engine, repo, "after concurrent writers")
    check(engine, repo, "after concurrent writers")


def test_the_database_stays_schema_version_2(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    conn = sqlite3.connect(str(db_path(cfg)))
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
        assert not conn.execute("SELECT count(*) FROM global_state WHERE name LIKE '%semantic%'").fetchone()[0]
    finally:
        conn.close()
    engine = cached(repo, cache_config(tmp_path, rebuild_policy="never", read_only=True))
    assert last(engine)["state"] == "loaded_read_only"
    _same_as_stage2(engine, repo, "read-only load of a version-2 database")
