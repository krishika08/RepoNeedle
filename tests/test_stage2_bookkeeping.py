"""
V2 Stage 2: incremental global bookkeeping, compared EXACTLY with the existing fits.

BM25 (``incremental.bm25_update``): partially incremental when the documents and their order are unchanged since
the index's previous fit; everything else takes ``fit()``. The result must equal ``BM25Index().fit(docs)``
bit for bit, INCLUDING the insertion order of ``doc_frequencies``, ``idf`` and ``inverted_index`` (first-seen by
document, in term-set order resp. term-dict order) and the ordered postings, over seeded random edit sequences
designed to move terms between first-seen documents.

Abstainer (``incremental.abstainer_assemble``): the vocabulary from reference counts equals ``fit()`` as a set.
"""

import random

import numpy as np
import pytest

from index_equivalence import capture_abstainer, capture_bm25, diff
from reponeedle.core.abstention import SelectiveAbstainer
from reponeedle.core.index_cache.incremental import (MODE_FULL, MODE_INCREMENTAL, MODE_PARTIAL,
                                                     abstainer_assemble, bm25_update)
from reponeedle.core.lexical import BM25Index
from reponeedle.models import FileDoc

WORDS = [f"w{i}" for i in range(60)] + ["shared", "common", "rare_term", "alpha", "beta"]


def _doc(path, rng, n_words=None):
    words = [rng.choice(WORDS) for _ in range(n_words if n_words is not None else rng.randint(0, 40))]
    return FileDoc(path=path, content=" ".join(words), symbols=[rng.choice(WORDS)] if rng.random() < 0.5 else [])


def _same_bm25(actual, docs, label):
    ref = BM25Index().fit(docs)
    out = []
    diff(capture_bm25(ref), capture_bm25(actual), "bm25", out)
    assert out == [], (label, out)
    for q in ("shared w1 w2", "rare_term", "alpha beta common", "nothing_matches"):
        assert np.array_equal(ref.score(q), actual.score(q)), (label, q)


@pytest.mark.parametrize("seed", range(25))
def test_bm25_updates_match_a_fresh_fit_including_dictionary_order(seed):
    rng = random.Random(seed)
    docs = [_doc(f"d{i}.py", rng) for i in range(rng.randint(1, 12))]
    lex = BM25Index()
    lex.fit(docs)
    for step in range(15):
        docs = list(docs)
        for _ in range(rng.randint(1, 3)):
            i = rng.randrange(len(docs))
            choice = rng.random()
            if choice < 0.3:      # remove the words of another document: moves first-seen documents later
                donor = docs[rng.randrange(len(docs))]
                docs[i] = FileDoc(path=docs[i].path, content=" ".join(
                    w for w in docs[i].content.split() if w not in set(donor.content.split())))
            elif choice < 0.6:    # introduce words first seen elsewhere, or brand-new ones
                docs[i] = FileDoc(path=docs[i].path, content=docs[i].content + f" fresh{seed}_{step} shared w0")
            else:
                docs[i] = _doc(docs[i].path, rng)
        mode, counters = bm25_update(lex, docs)
        assert mode == MODE_PARTIAL, counters
        assert counters["postings_rebuilt_full"] is False and counters["idf_recomputed_full"] is False
        _same_bm25(lex, docs, f"seed {seed} step {step}")


def test_bm25_unchanged_documents_do_no_work():
    rng = random.Random(1)
    docs = [_doc(f"d{i}.py", rng) for i in range(6)]
    lex = BM25Index()
    lex.fit(docs)
    mode, c = bm25_update(lex, [FileDoc(**d.model_dump()) for d in docs])
    assert mode == MODE_PARTIAL and c["documents_changed"] == 0 and c["postings_entries_rewritten"] == 0
    _same_bm25(lex, docs, "unchanged")


def test_bm25_counters_separate_proportional_from_global_work():
    rng = random.Random(2)
    docs = [_doc(f"d{i}.py", rng, 30) for i in range(10)]
    lex = BM25Index()
    lex.fit(docs)
    docs[4] = FileDoc(path="d4.py", content=docs[4].content + " brand_new_term")
    mode, c = bm25_update(lex, docs)
    assert mode == MODE_PARTIAL and c["documents_changed"] == 1
    assert c["terms_df_updated"] >= 1 and c["idf_recomputed"] == c["terms_df_updated"]
    # One more token changes the effective length: avg_doc_len and EVERY norm are recomputed (global O(N)).
    assert c["doc_lengths_updated"] == 1 and c["avg_doc_len_recomputed"] and c["norms_recomputed"] == 10
    _same_bm25(lex, docs, "one term added")


@pytest.mark.parametrize("change", ["add", "delete", "reorder", "empty"])
def test_bm25_structural_changes_take_the_full_fit(change):
    rng = random.Random(3)
    docs = [_doc(f"d{i}.py", rng) for i in range(6)]
    lex = BM25Index()
    lex.fit(docs)
    new = {"add": docs[:3] + [_doc("new.py", rng)] + docs[3:], "delete": docs[1:],
           "reorder": list(reversed(docs)), "empty": []}[change]
    mode, c = bm25_update(lex, new)
    assert mode == MODE_FULL and c["postings_rebuilt_full"] and c["idf_recomputed_full"] == bool(new)
    _same_bm25(lex, new, change)


def test_bm25_first_fit_is_full():
    rng = random.Random(4)
    docs = [_doc(f"d{i}.py", rng) for i in range(4)]
    lex = BM25Index()
    mode, c = bm25_update(lex, docs, allow=False)
    assert mode == MODE_FULL and "reason" in c
    _same_bm25(lex, docs, "first fit")


# -------------------------------------------------------------------------------------------- abstainer counts

def _vocab_docs(rng, n):
    return [FileDoc(path=f"p{i}/f{i}.py", content=" ".join(rng.choice(WORDS) for _ in range(rng.randint(0, 25))),
                    symbols=[rng.choice(WORDS)]) for i in range(n)]


def _assemble(prev_docs, prev_counts, docs, persisted=None, unchanged=None):
    ab = SelectiveAbstainer()
    persisted = {d.path for d in docs} if persisted is None else persisted
    old_vocab = {d.path: SelectiveAbstainer().doc_vocabulary(d) for d in prev_docs}
    if unchanged is None:
        prev_content = {d.path: d.content for d in prev_docs}
        unchanged = {d.path for d in docs if prev_content.get(d.path) == d.content}
    mode, counts, counters = abstainer_assemble(ab, docs, persisted, prev_counts, old_vocab, unchanged)
    ref = SelectiveAbstainer().fit(docs)
    out = []
    diff(capture_abstainer(ref), capture_abstainer(ab), "abstainer", out)
    assert out == []
    return mode, counts, counters


def _counts(docs):
    _, counts, _ = abstainer_assemble(SelectiveAbstainer(), docs, {d.path for d in docs}, None, {}, set())
    return counts


@pytest.mark.parametrize("seed", range(12))
def test_abstainer_reference_counts_match_a_fresh_fit(seed):
    rng = random.Random(seed)
    docs = _vocab_docs(rng, rng.randint(0, 8))
    counts = _counts(docs)
    for step in range(10):
        new = list(docs)
        op = rng.choice(["modify", "add", "delete", "reorder", "none"])
        if op == "modify" and new:
            i = rng.randrange(len(new))
            new[i] = FileDoc(path=new[i].path, content=new[i].content + f" tok{step}", symbols=new[i].symbols)
        elif op == "add":
            new.insert(rng.randint(0, len(new)), FileDoc(path=f"n{step}.py", content="shared alpha zeta_new"))
        elif op == "delete" and new:
            del new[rng.randrange(len(new))]
        elif op == "reorder":
            rng.shuffle(new)
        mode, counts, _ = _assemble(docs, counts, new)
        assert mode == MODE_INCREMENTAL
        assert counts == _counts(new), "counts equal a recount over the same documents"
        docs = new


def test_abstainer_shared_and_last_provider_deletion():
    a = FileDoc(path="a.py", content="sharedtoken onlya")
    b = FileDoc(path="b.py", content="sharedtoken onlyb")
    counts = _counts([a, b])
    assert counts["sharedtoken"] == 2
    mode, counts, c = _assemble([a, b], counts, [b])               # one provider of 'sharedtoken' deleted
    assert mode == MODE_INCREMENTAL and counts["sharedtoken"] == 1 and "onlya" not in counts
    mode, counts, c = _assemble([b], counts, [])                   # last provider deleted
    assert counts == {} and c["tokens_left_vocabulary"] > 0


def test_abstainer_modified_file_removes_and_adds_tokens():
    a = FileDoc(path="a.py", content="oldtoken keepme")
    counts = _counts([a])
    a2 = FileDoc(path="a.py", content="newtoken keepme")
    mode, counts, c = _assemble([a], counts, [a2])
    assert "oldtoken" not in counts and counts["newtoken"] == 1 and counts["keepme"] == 1
    assert c["documents_removed"] == c["documents_added"] == 1


def test_abstainer_excluded_documents_are_in_the_vocabulary_but_not_the_counts():
    a = FileDoc(path="a.py", content="public words")
    secret = FileDoc(path="secret.py", content="privatetoken")
    mode, counts, _ = _assemble([], None, [a, secret], persisted={"a.py"})
    assert "privatetoken" not in counts and mode == MODE_FULL


def test_abstainer_inconsistent_counts_fall_back_to_a_recount():
    a = FileDoc(path="a.py", content="alpha beta")
    mode, counts, c = _assemble([a], {"unrelated": 1}, [], unchanged=set())
    assert mode == MODE_FULL and "inconsistent" in c.get("fallback", "")


def test_abstainer_repeated_identical_assembly_is_stable():
    rng = random.Random(9)
    docs = _vocab_docs(rng, 5)
    counts = _counts(docs)
    for _ in range(3):
        mode, again, c = _assemble(docs, counts, docs)
        assert again == counts and c["tokens_incremented"] == c["tokens_decremented"] == 0
