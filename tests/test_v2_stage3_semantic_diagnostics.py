"""
V2 Stage 3: semantic diagnostics are reported honestly and never become index state.

- ``fit_stats`` counts what the fit did (cache hits and misses, pairs, distinct features, vocabulary, non-zeros, IDF
  entries, the numeric product rule, vocabulary churn relative to the previous in-process fit, sub-stage timings);
- ``IndexUpdateReport.work_counters['semantic']`` carries them for cached, refreshed and uncached builds;
- the stage label stays ``recomputed_in_full`` (never incremental);
- diagnostics are not part of the compared index state, and no semantic global state is persisted.
"""

import sqlite3

from cache_support import cache_config, cached, db_path, last, make_repo, write
from index_equivalence import capture_semantic
from reponeedle.core import semantic
from reponeedle.core.semantic import SubwordSemanticIndex
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import IndexCacheConfig
from stage3_support import doc, fixture_docs

COUNT_KEYS = {"documents", "feature_cache_hits", "feature_cache_misses", "documents_reextracted",
              "document_feature_pairs", "distinct_features", "vocabulary_size", "matrix_nnz", "idf_entries_computed",
              "product_rule", "product_self_check_values", "vocabulary_added", "vocabulary_removed"}
TIMING_KEYS = {"feature_collection_ms", "feature_counting_ms", "vocabulary_selection_ms", "idf_ms",
               "matrix_assembly_ms", "normalisation_ms", "fit_ms"}


def test_fit_stats_describe_the_fit():
    docs = fixture_docs()
    sem = SubwordSemanticIndex(max_features=200).fit(docs)
    s = sem.fit_stats
    assert set(s) == COUNT_KEYS | TIMING_KEYS
    assert s["documents"] == len(docs) == s["feature_cache_misses"] == s["documents_reextracted"]
    assert s["feature_cache_hits"] == 0
    assert s["document_feature_pairs"] == sum(len(sem._doc_feature_cache[d.path][1]) for d in docs)
    assert s["vocabulary_size"] == len(sem.vocabulary) == 200 == s["idf_entries_computed"]
    assert s["distinct_features"] > 200 and s["matrix_nnz"] == sem.doc_matrix.nnz
    assert s["product_rule"] == semantic.product_rule()
    assert s["vocabulary_added"] is None and s["vocabulary_removed"] is None, "no previous fit in this process"
    assert all(isinstance(s[k], float) and s[k] >= 0 for k in TIMING_KEYS)

    sem.fit(docs)                                       # unchanged refit: all hits, no vocabulary churn
    assert sem.fit_stats["feature_cache_hits"] == len(docs) and sem.fit_stats["feature_cache_misses"] == 0
    assert sem.fit_stats["vocabulary_added"] == 0 == sem.fit_stats["vocabulary_removed"]

    extra = doc("zz.py", " ".join(["qqvocabularyword"] * 50) + " " + " ".join(f"w{i}" for i in range(300)))
    sem.fit(docs + [extra] * 1)
    assert sem.fit_stats["feature_cache_misses"] == 1
    assert sem.fit_stats["vocabulary_added"] == sem.fit_stats["vocabulary_removed"]   # the size stays 200


def test_empty_fit_stats():
    sem = SubwordSemanticIndex().fit([])
    assert sem.fit_stats["documents"] == 0 and sem.fit_stats["vocabulary_size"] == 0
    assert sem.fit_stats["product_rule"] is None
    sem.fit(fixture_docs())
    sem.fit([])
    assert sem.fit_stats["vocabulary_removed"] > 0 and sem.fit_stats["vocabulary_added"] == 0


def test_diagnostics_are_not_index_state():
    a = SubwordSemanticIndex().fit(fixture_docs())
    b = SubwordSemanticIndex()
    b.fit(fixture_docs()[:3])
    b.fit(fixture_docs())
    assert a.fit_stats != b.fit_stats
    assert "fit_stats" not in capture_semantic(a)
    assert not any("stat" in k or k.endswith("_ms") for k in capture_semantic(a))


def test_cached_build_reports_semantic_counters_and_the_full_label(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    engine = cached(repo, cfg)
    n = len(engine.docs)
    r = last(engine)
    assert r["global_structures"]["semantic"] == "recomputed_in_full"
    sem = r["work_counters"]["semantic"]
    assert sem["feature_cache_misses"] == n and sem["feature_cache_hits"] == 0
    assert "recomputed in full by design" in sem["reason"] and "not maintained incrementally" in sem["reason"]
    assert "semantic" not in r["fallbacks"]

    warm = cached(repo, cfg)
    sem = last(warm)["work_counters"]["semantic"]
    assert last(warm)["global_structures"]["semantic"] == "recomputed_in_full"
    assert sem["feature_cache_hits"] == n and sem["feature_cache_misses"] == 0
    assert sem["vocabulary_added"] is None, "a fresh process has no previous fit to compare with"

    write(repo, "shop/new_module.py", "def brand_new_semantic_feature(x):\n    return x\n")
    rep = warm.refresh()
    sem = rep.work_counters["semantic"]
    assert rep.global_structures["semantic"] == "recomputed_in_full"
    assert sem["feature_cache_misses"] == 1 and sem["feature_cache_hits"] == n
    assert sem["vocabulary_added"] > 0 and sem["documents"] == n + 1


def test_the_uncached_route_reports_semantic_counters(tmp_path):
    """A read-only configuration without a cache directory takes the uncached route (state 'disabled')."""
    repo = make_repo(tmp_path)
    engine = RepoNeedleEngine.from_directory(str(repo), index_cache=IndexCacheConfig(
        cache_dir=str(tmp_path / "c"), read_only=True))
    r = last(engine)
    assert r["state"] in ("disabled", "not_persisted") and r["files_reused"] == 0
    assert r["global_structures"]["semantic"] == "recomputed_in_full"
    assert r["work_counters"]["semantic"]["documents"] == len(engine.docs)
    assert r["work_counters"]["semantic"]["feature_cache_misses"] == len(engine.docs)


def test_no_semantic_global_state_is_persisted(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    engine = cached(repo, cfg)
    write(repo, "shop/new_module.py", "def another(x):\n    return x\n")
    engine.refresh()
    conn = sqlite3.connect(str(db_path(cfg)))
    try:
        names = [r[0] for r in conn.execute("SELECT name FROM global_state")]
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' "
                                             "AND name NOT LIKE 'sqlite_%'")}
        kinds = {r[0] for r in conn.execute("SELECT DISTINCT kind FROM artifacts")}
    finally:
        conn.close()
    assert sorted(n.split("/")[0] for n in names) == ["abstainer.refcounts", "stage1.summary"]
    assert not any("semantic" in n for n in names)
    assert version == 2
    assert tables == {"meta", "generations", "manifest", "excluded", "artifacts", "file_artifacts", "global_state",
                      "optional_components"}
    assert kinds == {"doc_meta", "lexical", "semantic", "abstainer", "function_graph", "repo_graph_facts",
                     "provides", "fg_edges", "rg_edges"}
