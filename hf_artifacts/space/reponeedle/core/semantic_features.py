"""
Per-document semantic feature extraction (V2 Stage 3: separated from the global index assembly in ``semantic.py``).

Everything that determines a persisted per-document ``semantic`` artifact lives here, so the artifact's extractor
fingerprint (``index_cache.fingerprints``) covers exactly this module (plus the tokenizer, the signature encoding and
the codec), and a change to the global assembly in ``semantic.py`` no longer invalidates per-document artifacts.

``SubwordSemanticIndex`` binds these functions directly as its methods (no wrappers), so no extraction logic remains
outside this module. The behaviour is unchanged from Stage 2:
- the feature text is ``path + " " + " ".join(symbols) + " " + content[:8000]``;
- features are the tokenizer's words, then, for each word of at least ``min_n`` characters, the character n-grams of
  ``"<" + word + ">"`` for n from ``min_n`` to ``max_n`` (left to right);
- a document's counts are a dict in first-occurrence order of the feature list.
"""

from typing import Dict, List

from reponeedle.core.signatures import stable_signature
from reponeedle.core.tokenizer import CodeTokenizer

# Bump when the per-document feature extraction changes its output for the same inputs.
FEATURES_SIGNATURE_VERSION = "semantic-doc-features/1"
CONTENT_CHARS = 8000


def new_tokenizer() -> CodeTokenizer:
    return CodeTokenizer()


def extract_features(index, text: str) -> List[str]:
    """Word tokens and character n-grams of ``text`` (``index`` supplies ``tokenizer``, ``min_n`` and ``max_n``)."""
    words = index.tokenizer.tokenize_text(text)
    features: List[str] = list(words)

    for w in words:
        if len(w) < index.min_n:
            continue
        # Add character n-grams
        w_bound = f"<{w}>"
        for n in range(index.min_n, min(len(w_bound) + 1, index.max_n + 1)):
            for i in range(len(w_bound) - n + 1):
                features.append(w_bound[i: i + n])

    return features


def feature_text(doc) -> str:
    """The exact text features are extracted from: path, symbols and the first 8,000 characters."""
    return f"{doc.path} {' '.join(doc.symbols)} {doc.content[:CONTENT_CHARS]}"


def doc_signature(index, doc) -> str:
    """Deterministic signature of everything the per-document feature extraction reads."""
    return stable_signature(FEATURES_SIGNATURE_VERSION, index.min_n, index.max_n, index._feature_text(doc))


def count_features(index, doc) -> Dict[str, int]:
    """The document's feature counts, in first-occurrence order (the persisted ``semantic-counts-json/1`` data)."""
    counts: Dict[str, int] = {}
    for f in index._extract_features(index._feature_text(doc)):
        counts[f] = counts.get(f, 0) + 1
    return counts
