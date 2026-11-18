"""
V2 Stage 0: per-document cache signatures are SHA-256 based and identical across interpreter processes.

Before Stage 0 the BM25, semantic, abstainer and function-graph caches keyed on ``hash(doc.content)``, which Python
randomises per process (PYTHONHASHSEED), and joined symbols with "," (so ["a,b"] and ["a", "b"] collided).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from reponeedle.core.abstention import SelectiveAbstainer
from reponeedle.core.function_graph import FunctionGraphEngine
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex
from reponeedle.core.signatures import stable_signature
from reponeedle.models import FileDoc

ROOT = Path(__file__).resolve().parents[1]

DOCS = [
    FileDoc(path="pkg/mod.py", content="def f(x):\n    return x\n", symbols=["f"]),
    FileDoc(path="i18n/übersetzung.py", content="def größe():\n    return '翻訳 🛒'\n", symbols=["größe"]),
    FileDoc(path="empty.py", content="", symbols=[]),
]


def all_signatures(doc):
    return {
        "bm25": BM25Index().doc_signature(doc),
        "semantic": SubwordSemanticIndex().doc_signature(doc),
        "abstainer": SelectiveAbstainer.doc_signature(doc),
        "polyglot": FunctionGraphEngine.polyglot_signature(doc),
        "tree_sitter": FunctionGraphEngine.tree_sitter_signature(doc),
    }


_CHILD = """
import json, sys
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
from test_stage0_signatures import DOCS, all_signatures
print(json.dumps([all_signatures(d) for d in DOCS] + [hash("probe")]))
"""


def _signatures_in_process(seed: str):
    env = {**os.environ, "PYTHONHASHSEED": seed}
    out = subprocess.run([sys.executable, "-c", _CHILD, str(ROOT), str(ROOT / "tests")], env=env,
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    *sigs, probe = json.loads(out.strip().splitlines()[-1])
    return sigs, probe


def test_signatures_are_identical_across_processes_and_hash_seeds():
    results = [_signatures_in_process(seed) for seed in ("0", "1", "12345", "random")]
    probes = {probe for _, probe in results}
    assert len(probes) > 1, "the hash seeds must actually change hash(): otherwise this test proves nothing"
    first = results[0][0]
    assert all(sigs == first for sigs, _ in results)
    assert first == [all_signatures(d) for d in DOCS], "signatures differ between this process and children"


def test_signature_is_sha256_hex():
    sig = stable_signature("ns", "x")
    assert len(sig) == 64 and int(sig, 16) >= 0


@pytest.mark.parametrize("a,b", [
    (("a,b",), ("a", "b")),
    ((["a,b"],), (["a", "b"],)),
    (("ab", "c"), ("a", "bc")),
    (("",), ()),
    ((None,), ("",)),
    ((1,), ("1",)),
    ((True,), (1,)),
    ((1.0,), (1,)),
    (([],), ("",)),
])
def test_framing_is_unambiguous(a, b):
    assert stable_signature("ns", *a) != stable_signature("ns", *b)


def test_namespace_separates_caches():
    assert stable_signature("one", "x") != stable_signature("two", "x")


def test_unicode_and_empty_content_are_deterministic():
    assert stable_signature("ns", "") == stable_signature("ns", "")
    assert stable_signature("ns", "größe 翻訳 🛒") == stable_signature("ns", "größe 翻訳 🛒")
    assert stable_signature("ns", "é") != stable_signature("ns", "é"), "no Unicode normalisation"
    assert stable_signature("ns", "\ud800") == stable_signature("ns", "\ud800"), "lone surrogates are encodable"


def test_unsupported_field_types_are_rejected():
    with pytest.raises(TypeError):
        stable_signature("ns", b"bytes")
    with pytest.raises(TypeError):
        stable_signature("ns", [1, 2])


BASE = FileDoc(path="pkg/mod.py", content="def f(x):\n    return x\n" * 400, symbols=["f", "g"],
               imports=["os"], is_test=False, language="python")


def _variant(**changes):
    return BASE.model_copy(update=changes)


# Which inputs each extractor reads. A change to an input must change the signature; a change to anything else
# must not (otherwise the cache would miss for no reason).
SENSITIVITY = {
    "bm25": {"content": True, "path": True, "symbols": True, "imports": False, "is_test": False},
    "semantic": {"content": True, "path": True, "symbols": True, "imports": False, "is_test": False},
    "abstainer": {"content": True, "path": True, "symbols": True, "imports": False, "is_test": False},
    "polyglot": {"content": True, "path": True, "symbols": False, "imports": False, "is_test": False},
    "tree_sitter": {"content": True, "path": True, "symbols": False, "imports": False, "is_test": False},
}
CHANGES = {
    "content": {"content": "def f(x):\n    return x + 1\n"},
    "path": {"path": "pkg/other.py"},
    "symbols": {"symbols": ["f"]},
    "imports": {"imports": ["sys"]},
    "is_test": {"is_test": True},
}


@pytest.mark.parametrize("cache", sorted(SENSITIVITY))
@pytest.mark.parametrize("field", sorted(CHANGES))
def test_signature_tracks_exactly_the_extraction_inputs(cache, field):
    before = all_signatures(BASE)[cache]
    after = all_signatures(_variant(**CHANGES[field]))[cache]
    assert (before != after) == SENSITIVITY[cache][field]


def test_symbol_order_is_part_of_the_signature():
    assert BM25Index().doc_signature(_variant(symbols=["g", "f"])) != BM25Index().doc_signature(BASE)


def test_truncated_extractors_ignore_text_they_never_read():
    tail_edit = _variant(content=BASE.content + "# appended far beyond the extracted prefix\n")
    assert len(BASE.content) > 8000
    assert SubwordSemanticIndex().doc_signature(tail_edit) == SubwordSemanticIndex().doc_signature(BASE)
    assert SelectiveAbstainer.doc_signature(tail_edit) == SelectiveAbstainer.doc_signature(BASE)
    assert BM25Index().doc_signature(tail_edit) != BM25Index().doc_signature(BASE)


def test_extractor_configuration_is_part_of_the_signature():
    assert BM25Index(path_weight=3.0).doc_signature(BASE) != BM25Index().doc_signature(BASE)
    assert BM25Index(decouple_symbols=False).doc_signature(BASE) != BM25Index().doc_signature(BASE)
    assert SubwordSemanticIndex(min_n=2).doc_signature(BASE) != SubwordSemanticIndex().doc_signature(BASE)
    assert SubwordSemanticIndex(max_features=10).doc_signature(BASE) == SubwordSemanticIndex().doc_signature(BASE), \
        "max_features is applied globally, after per-document extraction"


def test_no_builtin_hash_in_per_document_caches():
    for module in ("lexical", "semantic", "abstention", "function_graph"):
        source = (ROOT / "reponeedle" / "core" / f"{module}.py").read_text(encoding="utf-8")
        assert "hash(" not in source.replace("_hash(", ""), module


def _count_extractions(monkeypatch, target, attr):
    calls = []
    real = getattr(target, attr)

    def wrapper(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(target, attr, wrapper)
    return calls


def test_cache_hits_for_unchanged_documents_and_misses_after_changes(monkeypatch):
    docs = [FileDoc(path=f"m{i}.py", content=f"def f{i}():\n    return {i}\n", symbols=[f"f{i}"]) for i in range(5)]
    lex, sem, ab, fg = BM25Index(), SubwordSemanticIndex(), SelectiveAbstainer(), FunctionGraphEngine()
    for idx in (lex, sem, ab):
        idx.fit(docs)
    fg.build_graph(docs)

    lex_calls = _count_extractions(monkeypatch, lex.tokenizer, "tokenize_path")
    sem_calls = _count_extractions(monkeypatch, sem, "_extract_features")
    ab_calls = _count_extractions(monkeypatch, ab.tokenizer, "tokenize_path")
    fg_calls = _count_extractions(monkeypatch, fg, "extract_polyglot")

    for idx in (lex, sem, ab):
        idx.fit(docs)
    fg.build_graph(docs)
    assert (len(lex_calls), len(sem_calls), len(ab_calls), len(fg_calls)) == (0, 0, 0, 0), "expected cache hits"

    edited = docs[:2] + [docs[2].model_copy(update={"content": docs[2].content + "x = 1\n"})] + docs[3:]
    for idx in (lex, sem, ab):
        idx.fit(edited)
    fg.build_graph(edited)
    assert (len(lex_calls), len(sem_calls), len(ab_calls), len(fg_calls)) == (1, 1, 1, 1), "expected one miss each"


def test_cached_results_equal_uncached_results():
    from index_equivalence import capture_bm25, capture_semantic, diff

    docs = [FileDoc(path=d.path, content=d.content, symbols=list(d.symbols)) for d in DOCS]
    warm_lex, warm_sem = BM25Index(), SubwordSemanticIndex()
    for _ in range(2):
        warm_lex.fit(docs)
        warm_sem.fit(docs)
    found = []
    diff(capture_bm25(BM25Index().fit(docs)), capture_bm25(warm_lex), "bm25", found)
    diff(capture_semantic(SubwordSemanticIndex().fit(docs)), capture_semantic(warm_sem), "semantic", found)
    assert not found, found
