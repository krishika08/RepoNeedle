"""
V2 Stage 3: per-document semantic feature extraction lives in ``reponeedle/core/semantic_features.py``.

- the index binds the module's functions directly (no wrapper holds extraction logic outside the module);
- feature text, n-gram order, count insertion order and ``doc_signature`` are unchanged from Stage 2;
- the ``semantic`` artifact's extractor fingerprint covers ``semantic_features`` (and the tokenizer, signatures and
  codec) but NOT ``semantic.py``; the index fingerprint covers both;
- a change of the extraction code invalidates only ``semantic`` artifacts (the one-time invalidation of upgrading
  to Stage 3), a change of the global assembly invalidates none, and results stay identical to a fresh build.
"""

from pathlib import Path

import pytest

from cache_support import assert_same_as_fresh, cache_config, cached, last, make_repo
from reponeedle.core import semantic, semantic_features
from reponeedle.core.index_cache import fingerprints
from reponeedle.core.semantic import SubwordSemanticIndex
from reponeedle.engine import RepoNeedleEngine
from stage3_support import ReferenceSemanticIndex, doc, fixture_docs, random_corpus

ROOT = Path(__file__).resolve().parents[1]
DOCS = fixture_docs() + random_corpus(9, 20) + [doc("long.py", "x" * 9000 + " tail_token", ["Sym"])]


def test_the_index_binds_the_extraction_functions_directly():
    assert SubwordSemanticIndex._extract_features is semantic_features.extract_features
    assert SubwordSemanticIndex.__dict__["_feature_text"].__func__ is semantic_features.feature_text
    assert SubwordSemanticIndex.doc_signature is semantic_features.doc_signature
    assert SubwordSemanticIndex._count_features is semantic_features.count_features
    assert semantic.FEATURES_SIGNATURE_VERSION == semantic_features.FEATURES_SIGNATURE_VERSION \
        == "semantic-doc-features/1"


def test_no_extraction_logic_remains_in_the_global_module():
    source = (ROOT / "reponeedle" / "core" / "semantic.py").read_text(encoding="utf-8")
    for marker in ("content[:", "w_bound", "tokenize_text", "stable_signature", "CodeTokenizer("):
        assert marker not in source, marker
    features = (ROOT / "reponeedle" / "core" / "semantic_features.py").read_text(encoding="utf-8")
    assert "hash(" not in features.replace("_hash(", "")


@pytest.mark.parametrize("config", [{}, {"min_n": 2, "max_n": 4}, {"min_n": 6, "max_n": 3}])
def test_signatures_text_and_counts_are_unchanged_from_stage2(config):
    new, ref = SubwordSemanticIndex(**config), ReferenceSemanticIndex(**config)
    for d in DOCS:
        assert new._feature_text(d) == ref._feature_text(d)
        assert new.doc_signature(d) == ref.doc_signature(d)
        assert new._extract_features(new._feature_text(d)) == ref._extract_features(ref._feature_text(d))
        counts = new._count_features(d)
        expected = {}
        for f in ref._extract_features(ref._feature_text(d)):
            expected[f] = expected.get(f, 0) + 1
        assert list(counts.items()) == list(expected.items())
    new.fit(DOCS)
    ref.fit(DOCS)
    for d in DOCS:
        a, b = new._doc_feature_cache[d.path], ref._doc_feature_cache[d.path]
        assert a[0] == b[0] and list(a[1].items()) == list(b[1].items())


def test_the_8000_character_truncation_is_kept():
    d = doc("t.py", "a" * 8000 + " beyondlimit")
    assert "beyondlimit" not in SubwordSemanticIndex()._feature_text(d)
    assert semantic_features.CONTENT_CHARS == 8000


def _fps(monkeypatch, changed_module=None):
    real = fingerprints.module_source_digest

    def digest(name):
        return ("changed:" + name) if name == changed_module else real(name)

    monkeypatch.setattr(fingerprints, "module_source_digest", digest)
    engine = RepoNeedleEngine(docs=None)
    ext = fingerprints.extractor_fingerprints(engine)
    return ext, fingerprints.index_fingerprint(engine, ext)


def test_semantic_artifact_fingerprint_covers_extraction_not_global_assembly(monkeypatch):
    base, base_index = _fps(monkeypatch)
    monkeypatch.undo()
    ext, index = _fps(monkeypatch, "reponeedle.core.semantic_features")
    assert ext["semantic"] != base["semantic"]
    assert {k: v for k, v in ext.items() if k != "semantic"} == {k: v for k, v in base.items() if k != "semantic"}
    assert index != base_index
    monkeypatch.undo()
    ext, index = _fps(monkeypatch, "reponeedle.core.semantic")
    assert ext == base, "a change of the global assembly must not invalidate any per-file artifact"
    assert index != base_index, "the index fingerprint covers the global assembly"
    assert "reponeedle.core.semantic" not in fingerprints._EXTRACTOR_MODULES["semantic"]


def _simulate(monkeypatch, changed_module):
    real = fingerprints.module_source_digest
    monkeypatch.setattr(fingerprints, "module_source_digest",
                        lambda name: ("changed:" + name) if name == changed_module else real(name))


def test_changing_the_extraction_code_reextracts_only_semantic_artifacts(tmp_path, monkeypatch):
    """The one-time invalidation of the Stage 3 upgrade: semantic artifacts only; everything else is reused."""
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    first = cached(repo, cfg)
    n = len(first.docs)
    _simulate(monkeypatch, "reponeedle.core.semantic_features")
    engine = cached(repo, cfg)
    r = last(engine)
    assert r["state"] == "published" and not r["rebuilt_from_scratch"]
    sem = r["work_counters"]["semantic"]
    assert sem["feature_cache_misses"] == n and sem["feature_cache_hits"] == 0
    assert r["files_reused"] == 0                       # every file has one re-extracted kind (semantic)
    assert r["artifacts_written"] == n, "only the semantic artifacts are rewritten"
    assert r["work_counters"]["function_graph"]["files_resolved"] == 0, "graph resolutions are still reused"
    assert_same_as_fresh(engine, repo, "after an extraction-code change", packing_queries=None)
    again = cached(repo, cfg)                            # the new fingerprint persists: full reuse again
    assert last(again)["work_counters"]["semantic"]["feature_cache_hits"] == n
    assert last(again)["files_reused"] == n


def test_changing_the_global_assembly_reuses_every_artifact(tmp_path, monkeypatch):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    first = cached(repo, cfg)
    _simulate(monkeypatch, "reponeedle.core.semantic")
    engine = cached(repo, cfg)
    r = last(engine)
    assert r["files_reused"] == len(first.docs) and r["artifacts_written"] == 0
    assert r["work_counters"]["semantic"]["feature_cache_hits"] == len(first.docs)
    assert_same_as_fresh(engine, repo, "after a global-assembly change", packing_queries=None)
