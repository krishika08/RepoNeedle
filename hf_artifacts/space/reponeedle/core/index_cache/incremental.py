"""
Incremental bookkeeping for the global lexical and abstainer state (design sections 9.5 and 3; V2 Stage 2).

BM25 (``bm25_update``) is **partially incremental** and applies only when the document paths and their order are
unchanged since the index's previous fit in this process (a ``refresh()``):
- per changed document: its term counts are replaced, document frequencies change by +-1 for the terms in the
  symmetric difference of its old and new term sets, and only its entries in the affected positional postings are
  rewritten (found by binary search on the document index);
- IDF is recomputed only for terms whose document frequency changed (the document count is unchanged);
- ``doc_lengths`` entries of changed documents are replaced; ``avg_doc_len`` (``np.mean`` over the float32 array)
  and every ``doc_len_norms`` entry are recomputed in full by the same vectorised expressions as ``fit()`` whenever
  a length changed, because a float32 reduction cannot be updated by a running sum and stay bit-identical;
- the insertion order of ``doc_frequencies``, ``idf`` and ``inverted_index`` is the first-seen order of ``fit()``:
  terms grouped by the first document containing them, in that document's term-set (``doc_frequencies``) or
  term-dict (postings) iteration order. Only the groups whose membership or document changed are rebuilt.
Additions, deletions or a different discovery order change the positional indices of postings and the document
count of every IDF, so they take the existing ``fit()`` (reported as recomputed in full). A warm restart in a new
process also uses ``fit()``: the insertion order of ``doc_frequencies`` follows Python's per-process string-hash
order (term sets), so a persisted copy could not reproduce a fresh build's dictionary order in another process.

Abstainer (``abstainer_assemble``): ``repo_vocabulary`` is the set of tokens with a positive reference count over
the persisted documents (``token -> number of documents containing it``), maintained by per-document deltas, plus
the vocabularies of documents excluded from persistence. Set equality with ``fit()`` is exact; the abstainer only
tests membership.
"""

import math
from bisect import bisect_left
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

MODE_INCREMENTAL = "incremental"
MODE_PARTIAL = "partially_incremental"
MODE_FULL = "recomputed_in_full"
MODE_REUSED = "reused"
MODE_FALLBACK = "fallback_full"


def _bm25_counters(**kw) -> Dict[str, Any]:
    base = {"terms_df_updated": 0, "idf_recomputed": 0, "idf_recomputed_full": False, "doc_lengths_updated": 0,
            "avg_doc_len_recomputed": False, "norms_recomputed": 0, "postings_entries_rewritten": 0,
            "postings_rebuilt_full": False, "documents_changed": 0, "order_groups_rebuilt": 0}
    base.update(kw)
    return base


def bm25_full(lex, docs, reason: str) -> Tuple[str, Dict[str, Any]]:
    lex.fit(docs)
    n_terms = len(lex.idf)
    return MODE_FULL, _bm25_counters(reason=reason, terms_df_updated=n_terms, idf_recomputed=n_terms,
                                     idf_recomputed_full=lex.num_docs > 0, doc_lengths_updated=lex.num_docs,
                                     avg_doc_len_recomputed=lex.num_docs > 0, norms_recomputed=lex.num_docs,
                                     postings_rebuilt_full=True, documents_changed=lex.num_docs)


def bm25_update(lex, docs, allow: bool = True) -> Tuple[str, Dict[str, Any]]:
    """Updates ``lex`` (a fitted ``BM25Index``) to equal ``lex.fit(docs)`` exactly. Returns (mode, counters)."""
    paths = [d.path for d in docs]
    n = len(docs)
    if not allow:
        return bm25_full(lex, docs, "no in-process index to update (first build or warm restart)")
    if n == 0 or lex.num_docs != n or lex.doc_paths != paths or len(lex.doc_term_freqs) != n:
        return bm25_full(lex, docs, "documents were added, deleted or reordered")

    new_terms = [lex.doc_terms(d) for d in docs]
    changed = [i for i in range(n) if new_terms[i][0] is not lex.doc_term_freqs[i]]
    if not changed:
        lex.docs = docs
        lex.doc_paths = paths
        return MODE_PARTIAL, _bm25_counters()

    postings = lex.inverted_index
    df = dict(lex.doc_frequencies)
    idf = lex.idf

    # Old first-document groups, before any posting changes.
    def first(term):
        return postings[term][0][0]

    old_df_groups: Dict[int, List[str]] = {}
    for t in lex.doc_frequencies:
        old_df_groups.setdefault(first(t), []).append(t)
    old_inv_groups: Dict[int, List[str]] = {}
    for t in postings:
        old_inv_groups.setdefault(first(t), []).append(t)

    delta_terms: Set[str] = set()
    affected_groups: Set[int] = set(changed)
    rewritten = 0
    for i in changed:
        old_c = lex.doc_term_freqs[i]
        new_c = new_terms[i][0]
        removed = [t for t in old_c if t not in new_c]
        added = [t for t in new_c if t not in old_c]
        for t in removed + added:
            affected_groups.add(first(t)) if t in postings else None
        for t in removed:
            plist = postings[t]
            pos = bisect_left(plist, (i,))
            del plist[pos]
            rewritten += 1
            df[t] -= 1
            delta_terms.add(t)
            if not plist:
                del postings[t]
                del df[t]
            else:
                affected_groups.add(plist[0][0])
        for t, tf in new_c.items():
            if t in old_c:
                if old_c[t] != tf or type(old_c[t]) is not type(tf):
                    plist = postings[t]
                    plist[bisect_left(plist, (i,))] = (i, tf)
                    rewritten += 1
                continue
            plist = postings.get(t)
            if plist is None:
                postings[t] = [(i, tf)]
                df[t] = 1
            else:
                plist.insert(bisect_left(plist, (i,)), (i, tf))
                df[t] += 1
            rewritten += 1
            delta_terms.add(t)
            affected_groups.add(postings[t][0][0])
        lex.doc_term_freqs[i] = new_c

    # Rebuild the first-seen orders: unaffected groups are kept, affected ones recomputed exactly as fit() orders
    # them (term SET iteration for document frequencies, term DICT iteration for postings).
    df_order: List[str] = []
    inv_order: List[str] = []
    for j in range(n):
        if j in affected_groups:
            counts_j = lex.doc_term_freqs[j]
            df_order.extend(t for t in set(counts_j.keys()) if postings[t][0][0] == j)
            inv_order.extend(t for t in counts_j if postings[t][0][0] == j)
        else:
            df_order.extend(old_df_groups.get(j, ()))
            inv_order.extend(old_inv_groups.get(j, ()))

    idf_recomputed = 0
    new_idf: Dict[str, float] = {}
    for t in df_order:
        if t in delta_terms or t not in idf:
            idf_val = math.log((n - df[t] + 0.5) / (df[t] + 0.5) + 1.0)
            new_idf[t] = max(0.0, idf_val)
            idf_recomputed += 1
        else:
            new_idf[t] = idf[t]
    lex.doc_frequencies = {t: df[t] for t in df_order}
    lex.idf = new_idf
    lex.inverted_index = {t: postings[t] for t in inv_order}

    lengths = lex.doc_lengths.copy()
    lengths_changed = 0
    for i in changed:
        new_len = new_terms[i][1]
        before = lengths[i]
        lengths[i] = new_len
        lengths_changed += int(lengths[i].tobytes() != before.tobytes())
    lex.doc_lengths = lengths
    if lengths_changed:
        lex.avg_doc_len = float(np.mean(lex.doc_lengths)) if len(lex.doc_lengths) > 0 else 1.0
        if lex.avg_doc_len > 0:
            lex.doc_len_norms = lex.k1 * (1.0 - lex.b + lex.b * (lex.doc_lengths / lex.avg_doc_len))
        else:
            lex.doc_len_norms = np.ones(lex.num_docs, dtype=np.float32) * lex.k1
    lex.docs = docs
    lex.doc_paths = paths
    return MODE_PARTIAL, _bm25_counters(terms_df_updated=len(delta_terms), idf_recomputed=idf_recomputed,
                                        doc_lengths_updated=lengths_changed,
                                        avg_doc_len_recomputed=bool(lengths_changed),
                                        norms_recomputed=n if lengths_changed else 0,
                                        postings_entries_rewritten=rewritten, documents_changed=len(changed),
                                        order_groups_rebuilt=len(affected_groups))


def abstainer_assemble(ab, docs, persisted: Set[str], previous: Optional[Dict[str, int]],
                       old_vocab: Dict[str, Optional[Set[str]]], unchanged: Set[str]
                       ) -> Tuple[str, Dict[str, int], Dict[str, Any]]:
    """
    Sets ``ab.repo_vocabulary`` exactly as ``ab.fit(docs)`` would (as a set) and returns (mode, the reference counts
    over the persisted documents, counters).

    ``previous``: the previous generation's verified counts (None: recompute). ``old_vocab``: path -> vocabulary of
    each file of the previous generation (None when unavailable). ``unchanged``: persisted paths whose vocabulary
    artifact is the previous generation's.
    """
    vocab_of = {d.path: ab.doc_vocabulary(d) for d in docs}
    counters = {"documents_added": 0, "documents_removed": 0, "tokens_incremented": 0, "tokens_decremented": 0,
                "tokens_entered_vocabulary": 0, "tokens_left_vocabulary": 0}
    counts: Optional[Dict[str, int]] = None
    mode = MODE_FULL
    if previous is not None:
        leaving = [p for p in old_vocab if p not in persisted or p not in unchanged]
        if all(old_vocab[p] is not None for p in leaving):
            counts = dict(previous)
            try:
                for p in leaving:
                    counters["documents_removed"] += 1
                    for t in old_vocab[p]:
                        c = counts[t] - 1          # KeyError: counts inconsistent with the vocabularies
                        counters["tokens_decremented"] += 1
                        if c:
                            counts[t] = c
                        else:
                            del counts[t]
                            counters["tokens_left_vocabulary"] += 1
                for d in docs:
                    if d.path in persisted and (d.path not in old_vocab or d.path not in unchanged):
                        counters["documents_added"] += 1
                        for t in vocab_of[d.path]:
                            c = counts.get(t, 0)
                            counters["tokens_incremented"] += 1
                            if not c:
                                counters["tokens_entered_vocabulary"] += 1
                            counts[t] = c + 1
                mode = MODE_INCREMENTAL
            except KeyError:
                counts = None
                counters = {k: 0 for k in counters}
                counters["fallback"] = "stored reference counts are inconsistent with the stored vocabularies"
    if counts is None:
        counts = {}
        for d in docs:
            if d.path in persisted:
                for t in vocab_of[d.path]:
                    counts[t] = counts.get(t, 0) + 1
        counters["documents_added"] = len(persisted)
    vocabulary = set(counts)
    for d in docs:
        if d.path not in persisted:
            vocabulary.update(vocab_of[d.path])
    ab.repo_vocabulary = vocabulary
    return mode, counts, counters
