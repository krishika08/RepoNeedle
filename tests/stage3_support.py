"""
Helpers for the V2 Stage 3 tests (not a test module): the Stage 2 semantic reference, exact comparisons of every
semantic structure, and corpora that exercise the vocabulary order (equal document frequencies, equal feature
lengths, ties across the ``max_features`` cutoff, truncation at 8,000 characters, documents without features).

Comparisons are exact: vocabulary items in order (keys, values and value types), IDF dtype and bytes, ``num_docs``,
``doc_paths``, CSR format, shape, and the dtype and bytes of ``indptr``/``indices``/``data``, and score arrays by
bytes. Nothing is sorted or rounded to make two results agree.
"""

import random
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np

from equivalence_fixture import FILES, write_files
from index_equivalence import capture_semantic, diff, load_queries
from reference_stage2_semantic import SubwordSemanticIndex as ReferenceSemanticIndex
from reponeedle.core.semantic import SubwordSemanticIndex
from reponeedle.models import FileDoc

QUERY_TEXTS: List[str] = [q["text"] for q in load_queries()]
CONFIGS: Dict[str, dict] = {
    "default": {},
    "max_features=0": {"max_features": 0},
    "max_features=1": {"max_features": 1},
    "max_features=37": {"max_features": 37},
    "max_features=50": {"max_features": 50},
    "min_n=2,max_n=4": {"min_n": 2, "max_n": 4},
    "min_n=4,max_n=6": {"min_n": 4, "max_n": 6},
    "empty n-gram range (min_n=6,max_n=3)": {"min_n": 6, "max_n": 3},
}


def doc(path: str, content: str = "", symbols: Sequence[str] = ()) -> FileDoc:
    return FileDoc(path=path, content=content, symbols=list(symbols))


def docs_from_files(files: Dict[str, str]) -> List[FileDoc]:
    """FileDocs exactly as from_directory() builds them (symbols, imports, language, counts), in file order."""
    import tempfile

    from reponeedle.engine import RepoNeedleEngine

    with tempfile.TemporaryDirectory() as tmp:
        root = write_files(Path(tmp), files)
        engine = RepoNeedleEngine.from_directory(str(root))
        by_path = {d.path: d for d in engine.docs}
    return [by_path[p] for p in files if p in by_path]


def fixture_docs() -> List[FileDoc]:
    return docs_from_files(FILES)


def tie_corpus(n_docs: int = 9, n_words: int = 14, seed: int = 3) -> List[FileDoc]:
    """
    Every document contains the same three-letter words (so every word and n-gram has df = n_docs, and lengths tie
    in large groups) in a different order per document; first-seen order alone decides the order of each tie group
    and which members fall inside small ``max_features`` cutoffs.
    """
    rng = random.Random(seed)
    words = [a + b + c for a, b, c in zip("bcdfghjklmnpqrst", "aeiouaeiouaeiouae", "xyzwvxyzwvxyzwvxy")][:n_words]
    out = []
    for i in range(n_docs):
        order = list(words)
        rng.shuffle(order)
        out.append(doc(f"t{i}.txt", " ".join(order)))
    return out


def random_corpus(seed: int, n_docs: int = 40) -> List[FileDoc]:
    """Seeded documents: Zipf-like vocabulary, repeated words, symbols, unicode, very short, empty and long texts."""
    rng = random.Random(seed)
    syll = ["ka", "lo", "mi", "ra", "te", "su", "vo", "ne", "pi", "da", "ü", "λx", "zen"]
    vocab = ["".join(rng.choice(syll) for _ in range(rng.randint(1, 4))) for _ in range(300)]
    weights = [1 / (k + 1) for k in range(len(vocab))]
    docs = []
    for i in range(n_docs):
        kind = rng.random()
        if kind < 0.05:
            content = ""
        elif kind < 0.10:
            content = rng.choice(vocab)
        elif kind < 0.15:     # beyond the 8,000-character truncation
            content = " ".join(rng.choices(vocab, weights, k=3000))
        else:
            content = "\n".join("def " + "_".join(rng.choices(vocab, weights, k=rng.randint(1, 3))) + "(): "
                                + " ".join(rng.choices(vocab, weights, k=rng.randint(0, 12)))
                                for _ in range(rng.randint(1, 30)))
        symbols = rng.sample(vocab, rng.randint(0, 4))
        docs.append(doc(f"pkg{i % 4}/m{i}.py", content, symbols))
    return docs


def semantic_state(sem) -> dict:
    return capture_semantic(sem)


def score_arrays(sem, queries: Iterable[str]) -> dict:
    out = {}
    n = sem.num_docs
    subset = list(range(0, n, 3))
    for q in queries:
        out[q] = sem.score(q)
        out[q + " [candidates]"] = sem.score(q, candidate_indices=subset)
    return out


def semantic_mismatches(actual, reference, queries: Optional[Iterable[str]] = None) -> List[str]:
    """Every located difference in semantic state (and, with ``queries``, in score arrays). Empty when equal."""
    found: List[str] = []
    diff(semantic_state(reference), semantic_state(actual), "semantic", found)
    if queries is not None:
        queries = list(queries)
        diff(score_arrays(reference, queries), score_arrays(actual, queries), "scores", found)
    return found


def assert_semantic_equal(actual, reference, label: str, queries: Optional[Iterable[str]] = None) -> None:
    found = semantic_mismatches(actual, reference, queries)
    assert not found, f"semantic index differs from the Stage 2 reference ({label}):\n  " + "\n  ".join(found)


def fit_both(docs: Sequence[FileDoc], **config):
    """(optimised, reference) indexes, each freshly constructed and fitted on the same documents."""
    return SubwordSemanticIndex(**config).fit(list(docs)), ReferenceSemanticIndex(**config).fit(list(docs))


@contextmanager
def reference_semantic():
    """Engines constructed inside use the Stage 2 reference semantic index (for whole-engine comparisons)."""
    import reponeedle.engine as engine_module

    real = engine_module.SubwordSemanticIndex
    engine_module.SubwordSemanticIndex = ReferenceSemanticIndex
    try:
        yield
    finally:
        engine_module.SubwordSemanticIndex = real


@contextmanager
def engine_semantic(config: Optional[dict] = None, reference: bool = False):
    """
    Engines constructed inside use a semantic index with ``config`` (the engine has no parameter for it), either
    the production class or, with ``reference=True``, the Stage 2 reference.
    """
    import reponeedle.engine as engine_module

    base = ReferenceSemanticIndex if reference else SubwordSemanticIndex
    config = dict(config or {})

    def __init__(self):
        base.__init__(self, **config)

    configured = type("ConfiguredSemanticIndex", (base,), {"__init__": __init__})
    real = engine_module.SubwordSemanticIndex
    engine_module.SubwordSemanticIndex = configured
    try:
        yield
    finally:
        engine_module.SubwordSemanticIndex = real


def is_float32_product() -> bool:
    """What the expression the Stage 2 fit evaluates (Python float times a numpy float32 scalar) returns here."""
    return isinstance(1.0 * np.float32(1.0), np.float32)
