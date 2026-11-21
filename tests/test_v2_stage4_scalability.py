"""
V2 Stage 4: large-repository scalability.

1. Shared semantic features (Stage 4.1): every document's feature counts (extracted or decoded from the persistent
   cache) are integer ids into one per-index ``FeaturePool`` plus counts (``FeatureCounts``), with one string object
   per distinct feature. Keys, values, insertion order, persisted payloads, fingerprints and every index structure
   stay exactly as before; caches written by earlier releases are reused as they are.
2. The Stage 4 benchmark tooling: deterministic dataset manifests, statistics, visible exclusions, commit provenance,
   and an end-to-end run on a tiny corpus that checks the output schema.
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from cache_support import assert_same_as_fresh, cache_config, cached, db_path, last, make_repo
from reponeedle.core.index_cache import codecs
from reponeedle.core.semantic import FeatureCounts, FeaturePool, SubwordSemanticIndex
from stage3_support import (QUERY_TEXTS, ReferenceSemanticIndex, assert_semantic_equal, fixture_docs, random_corpus,
                            reference_semantic)

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "reports" / "v2_completion" / "persistent_indexing"
sys.path.insert(0, str(BENCH))
import stage4_benchmark as s4  # noqa: E402

DOCS = fixture_docs() + random_corpus(11, 25)


def _key_objects(sem):
    keys = [f for _, counts in sem._doc_feature_cache.values() for f in counts]
    return keys, {id(f) for f in keys}, set(keys)


def assert_shared(sem):
    """One string object per distinct feature, every cached document in the index's own pool."""
    keys, ids, distinct = _key_objects(sem)
    assert len(keys) > len(distinct), "the corpus must repeat features across documents"
    assert len(ids) == len(distinct), "each distinct feature must be one string object"
    for _, counts in sem._doc_feature_cache.values():
        assert isinstance(counts, FeatureCounts) and counts.pool is sem._pool
    assert all(sem._pool.strings[sem._pool[f]] is f for f in distinct)


def _items(counts):
    return list(counts.items())


# ------------------------------------------------------------------------------------- feature pool and counts

def test_pool_ids_are_deterministic_append_only_and_shared():
    a, b = FeaturePool(), FeaturePool()
    words = ["".join(["ab", "c"]), "<ab", "".join(["ab", "c"]), "xyz", "<ab"]
    assert a.ids(words, 5).tolist() == b.ids(words, 5).tolist() == [0, 1, 0, 2, 1]
    assert a.strings == ["abc", "<ab", "xyz"] and len(a) == 3
    first = a.strings[0]
    assert a.ids(["new", "abc"], 2).tolist() == [3, 0] and a.strings[0] is first, "ids never change"
    assert a.ids([], 0).dtype == np.int32 and len(a.ids([], 0)) == 0


def test_feature_counts_behave_exactly_like_the_dict():
    counts = {"".join(["ab", "c"]): 2, "<ab": 1, "".join(["x", "yz"]): 5}
    fc = FeatureCounts.from_counts(FeaturePool(), counts)
    assert list(fc) == list(counts) and fc.keys() == list(counts)
    assert fc.values() == [2, 1, 5] and fc.items() == list(counts.items())
    assert len(fc) == 3 and fc == counts and counts == dict(fc.items())
    assert fc["xyz"] == 5 and "abc" in fc and "zzz" not in fc and 3 not in fc
    for missing in ("zzz", 3):
        with pytest.raises(KeyError):
            fc[missing]
    assert fc.get("zzz", 7) == 7 and dict(fc) == counts
    assert fc != {"abc": 2, "<ab": 1} and fc != {"abc": 2, "<ab": 1, "xyz": 6}
    assert fc == {"<ab": 1, "abc": 2, "xyz": 5}, "equality is the dict's (order-insensitive); order is checked by items()"
    assert fc.items() != [("<ab", 1), ("abc", 2), ("xyz", 5)]
    assert list(counts) == ["abc", "<ab", "xyz"], "the source dict is not modified"
    empty = FeatureCounts.from_counts(FeaturePool(), {})
    assert empty == {} and len(empty) == 0 and list(empty) == [] and empty.values() == []


def test_feature_counts_keep_counts_beyond_int32():
    big = {"a": 2 ** 40, "b": 1}
    fc = FeatureCounts.from_counts(FeaturePool(), big)
    assert fc.items() == list(big.items()) and fc.counts.dtype == np.int64
    assert FeatureCounts.from_counts(FeaturePool(), {"a": 3}).counts.dtype == np.int32


def test_a_large_pool_round_trips_through_the_codec():
    pool = FeaturePool()
    counts = {f"f{i:06d}": (i % 97) + 1 for i in range(200_000)}
    fc = FeatureCounts.from_counts(pool, counts)
    assert len(pool) == 200_000 and fc.items() == list(counts.items())
    assert codecs.encode_semantic(fc) == codecs.encode_semantic(counts), "the persisted bytes are unchanged"
    assert codecs.decode_semantic(codecs.encode_semantic(fc)) == counts


# ------------------------------------------------------------------------------------- fit on shared features

def test_extracted_feature_strings_are_shared_and_the_index_is_unchanged():
    sem = SubwordSemanticIndex().fit(DOCS)
    assert_shared(sem)
    assert_semantic_equal(sem, ReferenceSemanticIndex().fit(DOCS), "shared strings", queries=QUERY_TEXTS[::10])


def test_shared_counts_are_the_extracted_counts():
    sem, ref = SubwordSemanticIndex().fit(DOCS), ReferenceSemanticIndex().fit(DOCS)
    for d in DOCS:
        assert sem._doc_feature_cache[d.path][0] == ref._doc_feature_cache[d.path][0]
        assert _items(sem._doc_feature_cache[d.path][1]) == list(ref._doc_feature_cache[d.path][1].items())


def test_counts_from_other_pools_and_plain_dicts_are_brought_into_the_index_pool():
    """Seeded entries (the cache loader's pool, a plain mapping) give the same index as extraction."""
    ref = ReferenceSemanticIndex().fit(DOCS)
    for adopt in (True, False):
        sem = SubwordSemanticIndex()
        if not adopt:      # the index pool already holds features: other pools are translated, not adopted
            sem.fit(DOCS[:3])
        loader_pool = FeaturePool()
        for i, d in enumerate(DOCS):
            counts = sem._count_features(d)
            seeded = dict(counts) if (i % 3 == 0 and i) else FeatureCounts.from_counts(loader_pool, counts)
            sem._doc_feature_cache[d.path] = (sem.doc_signature(d), seeded)
        sem.fit(DOCS)
        assert sem.fit_stats["feature_cache_hits"] == len(DOCS)
        assert_shared(sem)
        assert (sem._pool is loader_pool) is adopt
        assert_semantic_equal(sem, ref, f"seeded counts (adopt={adopt})", queries=QUERY_TEXTS[::10])


def test_the_pool_is_compacted_and_the_index_stays_exact(monkeypatch):
    """Replaced documents leave unused features in the append-only pool; compaction removes them exactly."""
    from reponeedle.core import semantic

    monkeypatch.setattr(semantic, "POOL_COMPACT_SLACK", 0)
    sem = SubwordSemanticIndex()
    compacted = 0
    for seed in range(5):
        docs = random_corpus(100 + seed, 12)
        sem._doc_feature_cache.clear()           # only these documents are live
        before = sem._pool
        sem.fit(docs)
        live = {f for _, c in sem._doc_feature_cache.values() for f in c}
        if sem._pool is not before and seed:
            compacted += 1
            assert len(sem._pool) == len(live), "a compacted pool holds exactly the live features"
        assert_shared(sem)
        assert_semantic_equal(sem, ReferenceSemanticIndex().fit(docs), f"after fit {seed}",
                              queries=QUERY_TEXTS[::20])
    assert compacted >= 1, "the pool must have been compacted at least once"


def test_empty_documents_and_corpora_without_features():
    from stage3_support import doc

    for docs in ([doc(""), doc("a.py", "alpha")], [doc("")], [doc(""), doc("b.py", "")]):
        sem = SubwordSemanticIndex().fit(docs)
        assert_semantic_equal(sem, ReferenceSemanticIndex().fit(docs), f"{[d.path for d in docs]}")
        assert sem._doc_feature_cache[""][1] == {}


# ------------------------------------------------------------------------------------- persistent cache

def test_cached_restart_shares_decoded_feature_strings(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    warm = cached(repo, cfg)
    assert last(warm)["work_counters"]["semantic"]["feature_cache_hits"] == len(warm.docs)
    assert_shared(warm.semantic_index)
    assert_same_as_fresh(warm, repo, "warm restart with shared feature strings", packing_queries=None)
    with reference_semantic():
        from cache_support import fresh
        ref = fresh(repo)
    assert_semantic_equal(warm.semantic_index, ref.semantic_index, "warm restart vs Stage 2 reference",
                          queries=QUERY_TEXTS[::10])


def test_the_loader_shares_feature_strings_as_it_decodes(tmp_path):
    """load_generation decodes every artifact at once; semantic keys are shared from decoding on (load-time peak)."""
    from reponeedle.core.index_cache.connection import open_reader
    from reponeedle.core.index_cache.fingerprints import extractor_fingerprints
    from reponeedle.core.index_cache.paths import locate
    from reponeedle.core.index_cache.store import load_generation

    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    engine = cached(repo, cfg)
    loc = locate(str(repo), cfg.cache_dir)
    fps = {k: bytes.fromhex(v) for k, v in extractor_fingerprints(engine).items()}
    conn = open_reader(loc.db_path, 5.0, True)
    try:
        loaded = load_generation(conn, loc.repo_root, loc.repo_id, fps)
    finally:
        conn.close()
    decoded = [loaded.data(p, "semantic") for p in loaded.manifest]
    assert len({id(c.pool) for c in decoded}) == 1, "one pool per load"
    keys = [f for counts in decoded for f in counts]
    assert len(decoded) == len(engine.docs) and len(keys) > len(set(keys))
    assert len({id(f) for f in keys}) == len(set(keys))
    for p in loaded.manifest:
        assert _items(loaded.data(p, "semantic")) == _items(engine.semantic_index._doc_feature_cache[p][1])


def test_persisted_semantic_payloads_are_unchanged(tmp_path):
    """The representation changes object layout only: the persisted payloads equal the Stage 2 extraction's."""
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    engine = cached(repo, cfg)
    ref = ReferenceSemanticIndex()
    by_path = {d.path: d for d in engine.docs}
    conn = sqlite3.connect(str(db_path(cfg)))
    try:
        rows = conn.execute("SELECT path, payload, codec FROM artifacts WHERE kind = 'semantic'").fetchall()
    finally:
        conn.close()
    assert len(rows) == len(engine.docs)
    for path, payload, codec in rows:
        expected = {}
        for f in ref._extract_features(ref._feature_text(by_path[path])):
            expected[f] = expected.get(f, 0) + 1
        assert codec == "semantic-counts-json/1"
        assert bytes(payload) == codecs.encode_semantic(expected), path


def test_a_cache_written_with_plain_dict_counts_is_reused_without_reextraction(tmp_path, monkeypatch):
    """
    Compatibility with existing caches: a cache written with the Stage 2 representation (plain per-document dicts)
    is read by the new code with every semantic artifact reused, and the result equals a fresh build. The format,
    codec and extractor fingerprints are unchanged, so nothing is invalidated.
    """
    import reponeedle.engine as engine_module

    class PlainDictSemanticIndex(SubwordSemanticIndex):
        """The Stage 2/3 in-memory representation: one plain dict per document (encoded by the same codec)."""

        def fit(self, docs):
            super().fit(docs)
            self._doc_feature_cache = {k: (sig, dict(c.items())) for k, (sig, c) in self._doc_feature_cache.items()}
            return self

    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    monkeypatch.setattr(engine_module, "SubwordSemanticIndex", PlainDictSemanticIndex)
    old = cached(repo, cfg)
    monkeypatch.undo()
    assert not isinstance(next(iter(old.semantic_index._doc_feature_cache.values()))[1], FeatureCounts)
    warm = cached(repo, cfg)
    r = last(warm)
    assert r["files_reused"] == len(warm.docs) and not r["rebuilt_from_scratch"]
    assert r["work_counters"]["semantic"]["feature_cache_hits"] == len(warm.docs)
    assert r["work_counters"]["semantic"]["documents_reextracted"] == 0
    assert_shared(warm.semantic_index)
    assert_same_as_fresh(warm, repo, "plain-dict cache read by the shared-feature code", packing_queries=None)


def test_a_semantic_payload_with_a_duplicated_feature_is_rejected_and_rebuilt(tmp_path):
    """A structurally invalid semantic payload with a VALID checksum: the loader rejects the whole cache."""
    import zlib

    from reponeedle.core.index_cache import IndexCacheError
    from reponeedle.core.index_cache.schema import artifact_checksum

    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    conn = sqlite3.connect(str(db_path(cfg)), isolation_level=None)
    key, kind, fp, path, sig, codec = conn.execute(
        "SELECT artifact_key, kind, extractor_fp, path, input_sig, codec FROM artifacts WHERE kind = 'semantic' "
        "ORDER BY artifact_key LIMIT 1").fetchone()
    bad = zlib.compress(json.dumps({"c": [1, 2], "f": ["abc", "abc"]}, separators=(",", ":")).encode(), 1)
    conn.execute("UPDATE artifacts SET payload = ?, checksum = ? WHERE artifact_key = ?",
                 (bad, artifact_checksum(key, kind, fp, path, sig, codec, bad), key))
    conn.close()
    with pytest.raises(IndexCacheError) as err:
        cached(repo, cache_config(tmp_path, rebuild_policy="never"))
    assert "does not decode" in str(err.value), str(err.value)
    engine = cached(repo, cfg)
    assert last(engine)["rebuilt_from_scratch"]
    assert_shared(engine.semantic_index)
    assert_same_as_fresh(engine, repo, "rebuilt after a duplicated semantic feature", packing_queries=None)


def test_refresh_keeps_feature_strings_shared(tmp_path):
    from cache_support import write

    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    engine = cached(repo, cfg)
    write(repo, "shop/stage4_added.py", "def shared_feature_strings(order):\n    return order\n")
    engine.refresh()
    assert_shared(engine.semantic_index)
    assert_same_as_fresh(engine, repo, "refresh with shared feature strings", packing_queries=None)


# ------------------------------------------------------------------------------------- benchmark tooling

def _manifest(root, n):
    s4.s1.generate(root, n, "reduced")
    m = s4.dataset_manifest(root, n, "reduced", {"generation_seconds": 0.0})
    m.pop("generated_utc")
    return m


def test_dataset_manifests_are_deterministic(tmp_path):
    a, b = _manifest(tmp_path / "a", 40), _manifest(tmp_path / "b", 40)
    assert a == b
    assert a["file_count"] == 40 and len(a["manifest_sha256"]) == 64
    assert sum(a["language_distribution"].values()) == 40
    assert a["size_bytes"]["min"] <= a["size_bytes"]["p50"] <= a["size_bytes"]["max"]
    assert a["seed"] == 7 and a["dataset_id"] == "stage1-generator/reduced/40/seed-7"
    (tmp_path / "b" / "pkg0").mkdir(exist_ok=True)
    (tmp_path / "b" / "pkg0" / "extra.py").write_text("x = 1\n", encoding="utf-8")
    changed = s4.dataset_manifest(tmp_path / "b", 40, "reduced", {})
    assert changed["manifest_sha256"] != a["manifest_sha256"]


def test_statistics_and_visible_exclusions():
    assert s4.stats([]) == {"n": 0}
    s = s4.stats([3.0, 1.0, 2.0])
    assert (s["n"], s["median"], s["min"], s["max"]) == (3, 2.0, 1.0, 3.0) and s["stdev"] == 1.0

    def phase(t, **kw):
        return {"seconds_to_ready_engine": t, "semantic_fit_calls": [{"s": t / 2}], "peak_rss_bytes": 2 ** 30,
                "peak_committed_bytes": 2 ** 30, "peak_wal_bytes": 0, **kw}
    rounds = [{"baseline": {p: phase(4.0) for p in s4.PHASES}, "candidate": {p: phase(2.0) for p in s4.PHASES}},
              {"baseline": {p: phase(9.0, paging_suspected=True) for p in s4.PHASES},
               "candidate": {p: phase(2.0) for p in s4.PHASES}}]
    out = s4.summarise(rounds)
    assert out["baseline"]["warm_restart"]["ready_engine_s"] == {"n": 1, "median": 4.0, "min": 4.0, "max": 4.0,
                                                                 "stdev": 0.0}
    assert len(out["excluded_phases"]) == 3 and all(e["round"] == 2 for e in out["excluded_phases"])
    assert out["per_round_ratio_baseline_over_candidate"]["warm_restart"]["ready_engine_s"] == [2.0, None]


def test_three_revisions_rotate_and_are_summarised_per_revision():
    roots = {"baseline": "a", "intern": "b", "candidate": "c"}
    assert [s4.variant_order(roots, r) for r in range(3)] == [
        ["baseline", "intern", "candidate"], ["intern", "candidate", "baseline"], ["candidate", "baseline", "intern"]]
    assert s4.variant_order({"baseline": "a", "candidate": "c"}, 1) == ["candidate", "baseline"]

    def phase(t):
        return {"seconds_to_ready_engine": t, "semantic_fit_calls": [], "peak_rss_bytes": 2 ** 30,
                "peak_committed_bytes": 2 ** 30, "peak_wal_bytes": 0}
    rnd = {v: {p: phase(t) for p in s4.PHASES} for v, t in (("candidate", 2.0), ("baseline", 6.0), ("intern", 3.0))}
    out = s4.summarise([rnd])
    assert out["intern"]["uncached"]["ready_engine_s"]["median"] == 3.0
    assert out["per_round_ratio_intern_over_candidate"]["uncached"]["ready_engine_s"] == [1.5]
    assert out["per_round_ratio_baseline_over_candidate"]["uncached"]["ready_engine_s"] == [3.0]


def test_phases_on_battery_are_recorded_and_excluded(monkeypatch):
    states = iter([True, False])
    monkeypatch.setattr(s4, "ac_power", lambda: next(states))
    monkeypatch.setattr(s4.s3, "run_child", lambda *a, **k: {"seconds_to_ready_engine": 1.0})
    r = s4.run_phase(Path("."), Path("."), Path("."), "cached", 1, None)
    assert r["ac_power"] == [True, False] and r["on_battery_suspected"] is True
    assert not s4._clean(r) and s4._clean({"seconds_to_ready_engine": 1.0, "ac_power": [None, None]})
    rnd = {v: {p: dict(r, semantic_fit_calls=[], peak_rss_bytes=1, peak_committed_bytes=1, peak_wal_bytes=0)
               for p in s4.PHASES} for v in ("baseline", "candidate")}
    out = s4.summarise([rnd])
    assert len(out["excluded_phases"]) == 6 and all(e["on_battery_suspected"] for e in out["excluded_phases"])


def test_component_memory_follows_slotted_objects():
    assert "__slots__" in s4.MEMORY_CHILD and "klass.__dict__.get" in s4.MEMORY_CHILD


def test_environment_probe_tolerates_missing_sysconf_names(monkeypatch):
    """macOS has no SC_AVPHYS_PAGES: the probe and the child record unknown memory instead of failing."""
    import os

    def sysconf(name):
        if name == "SC_AVPHYS_PAGES":
            raise ValueError("unrecognized configuration name")
        return {"SC_PHYS_PAGES": 1000, "SC_PAGE_SIZE": 4096}[name]

    monkeypatch.setattr(s4.sys, "platform", "darwin")
    monkeypatch.setattr(os, "sysconf", sysconf, raising=False)
    env = s4.environment()
    assert env["ram_total_bytes"] == 4096000 and env["ram_available_bytes_at_start"] is None
    assert "except (AttributeError, ValueError, OSError):\n        avail = 0" in s4.CHILD
    compile(s4.CHILD, "<child>", "exec")


def test_revisions_are_identified_by_commit():
    rev = s4.git_revision(ROOT)
    assert rev["commit"] and len(rev["commit"]) == 40 and rev["package_version"]


def test_end_to_end_tiny_run_writes_the_documented_schema(tmp_path):
    out = tmp_path / "bench.json"
    res = subprocess.run([sys.executable, str(BENCH / "stage4_benchmark.py"), "--baseline-root", str(ROOT),
                          "--files", "12", "--profile", "reduced", "--rounds", "1", "--verify",
                          "--component-memory", "--out", str(out)], capture_output=True, text=True, timeout=900,
                         cwd=str(ROOT))
    assert res.returncode == 0, res.stderr[-3000:]
    data = json.loads(out.read_text(encoding="utf-8"))
    assert {"platform", "python", "numpy", "scipy", "logical_cpus"} <= set(data["environment"])
    assert not any("/" in a or "\\" in a for a in data["environment"]["argv"]), "no local paths in published results"
    assert all(len(data["revisions"][v]["commit"]) == 40 for v in ("baseline", "candidate"))
    run = data["runs"]["reduced 12 files"]
    assert run["dataset"]["file_count"] == 12 and len(run["dataset"]["manifest_sha256"]) == 64
    rnd = run["rounds"][0]
    assert rnd["verification"]["identical"] is True and len(rnd["verification"]["digests"]) == 4
    for v in ("baseline", "candidate"):
        for p in s4.PHASES:
            ph = rnd[v][p]
            assert ph["seconds_to_ready_engine"] > 0 and "max_heartbeat_gap_s" in ph and ph["started_utc"]
        assert len(rnd[v]["warm_restart"]["query_latency_ms"]) == s4.QUERY_SAMPLE
        mem = run["component_memory"][v]
        assert mem["semantic_distinct_key_objects"] == mem["semantic_distinct_features"] < mem["semantic_pairs"]
    on_battery = rnd["candidate"]["warm_restart"]["on_battery_suspected"]
    assert isinstance(on_battery, bool) and len(rnd["candidate"]["warm_restart"]["ac_power"]) == 2
    assert run["summary"]["candidate"]["warm_restart"]["ready_engine_s"]["n"] == (0 if on_battery else 1)
    assert "conditions" in run and out.with_suffix(".md").exists()
