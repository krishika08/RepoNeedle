"""
V2 Stage 4: large-repository scalability.

1. Shared semantic feature strings: every per-document feature count dict (extracted or decoded from the persistent
   cache) uses one interned string per distinct feature instead of one string object per (document, feature) pair.
   Keys, values, insertion order, persisted payloads and every index structure stay exactly as before.
2. The Stage 4 benchmark tooling: deterministic dataset manifests, statistics, visible exclusions, commit provenance,
   and an end-to-end run on a tiny corpus that checks the output schema.
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from cache_support import assert_same_as_fresh, cache_config, cached, db_path, last, make_repo
from reponeedle.core.index_cache import codecs
from reponeedle.core.semantic import SubwordSemanticIndex
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
    keys, ids, distinct = _key_objects(sem)
    assert len(keys) > len(distinct), "the corpus must repeat features across documents"
    assert len(ids) == len(distinct), "each distinct feature must be one string object"
    assert all(sys.intern(f) is f for f in distinct)


# ------------------------------------------------------------------------------------- shared feature strings

def test_shared_feature_counts_keep_keys_values_and_order():
    counts = {"".join(["ab", "c"]): 2, "<ab": 1, "".join(["x", "yz"]): 5}
    shared = SubwordSemanticIndex.shared_feature_counts(counts)
    assert list(shared.items()) == list(counts.items())
    assert all(sys.intern(k) is k for k in shared)
    assert shared is not counts and list(counts) == ["abc", "<ab", "xyz"]


def test_extracted_feature_strings_are_shared_and_the_index_is_unchanged():
    sem = SubwordSemanticIndex().fit(DOCS)
    assert_shared(sem)
    assert_semantic_equal(sem, ReferenceSemanticIndex().fit(DOCS), "shared strings", queries=QUERY_TEXTS[::10])


def test_shared_counts_are_the_extracted_counts():
    sem, ref = SubwordSemanticIndex().fit(DOCS), ReferenceSemanticIndex().fit(DOCS)
    for d in DOCS:
        assert sem._doc_feature_cache[d.path][0] == ref._doc_feature_cache[d.path][0]
        assert list(sem._doc_feature_cache[d.path][1].items()) == list(ref._doc_feature_cache[d.path][1].items())


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
    keys = [f for counts in decoded for f in counts]
    assert len(decoded) == len(engine.docs) and len(keys) > len(set(keys))
    assert len({id(f) for f in keys}) == len(set(keys))
    for p in loaded.manifest:
        assert list(loaded.data(p, "semantic").items()) == list(engine.semantic_index._doc_feature_cache[p][1].items())


def test_persisted_semantic_payloads_are_unchanged(tmp_path):
    """Interning changes object identity only: the persisted payloads equal the Stage 2 extraction's encoding."""
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    engine = cached(repo, cfg)
    ref = ReferenceSemanticIndex()
    by_path = {d.path: d for d in engine.docs}
    conn = sqlite3.connect(str(db_path(cfg)))
    try:
        rows = conn.execute("SELECT path, payload FROM artifacts WHERE kind = 'semantic'").fetchall()
    finally:
        conn.close()
    assert len(rows) == len(engine.docs)
    for path, payload in rows:
        expected = {}
        for f in ref._extract_features(ref._feature_text(by_path[path])):
            expected[f] = expected.get(f, 0) + 1
        assert bytes(payload) == codecs.encode_semantic(expected), path


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
    assert run["summary"]["candidate"]["warm_restart"]["ready_engine_s"]["n"] == 1
    assert "conditions" in run and out.with_suffix(".md").exists()
