"""
Deterministic signatures for per-document extraction caches.

The per-document caches (BM25 term counts, semantic features, abstainer vocabularies, function-graph and Tree-sitter
extractions) skip re-extraction when a document's extraction inputs are unchanged. Their signatures must be:

* deterministic across interpreter processes (Python's built-in ``hash()`` of ``str`` is randomised per process, so it
  cannot identify an input outside the process that computed it);
* unambiguous: every field is framed with its type and byte length, so ``("a,b",)`` and ``("a", "b")`` differ;
* complete: each cache signs exactly the inputs its extractor reads, plus a versioned namespace that must change when
  the extractor's output for the same inputs changes.
"""

import hashlib
from typing import Iterable, Union

Field = Union[str, int, float, bool, None, Iterable[str]]


def _frame(tag: bytes, payload: bytes) -> bytes:
    return tag + len(payload).to_bytes(8, "big") + payload


def _encode(value: Field) -> bytes:
    # bool is checked before int because bool is a subclass of int.
    if value is None:
        return _frame(b"N", b"")
    if isinstance(value, bool):
        return _frame(b"B", b"1" if value else b"0")
    if isinstance(value, int):
        return _frame(b"I", str(value).encode("ascii"))
    if isinstance(value, float):
        return _frame(b"F", value.hex().encode("ascii"))
    if isinstance(value, str):
        # surrogatepass keeps the encoding total and injective for any Python str (including lone surrogates).
        return _frame(b"S", value.encode("utf-8", "surrogatepass"))
    if isinstance(value, (bytes, bytearray)):
        raise TypeError("bytes are not a supported signature field")
    items = list(value)
    if not all(isinstance(item, str) for item in items):
        raise TypeError("sequence signature fields must contain only str")
    return _frame(b"L", b"".join(_encode(item) for item in items))


def stable_signature(namespace: str, *fields: Field) -> str:
    """SHA-256 (hex) over the namespace and the type- and length-framed fields, in order."""
    h = hashlib.sha256()
    h.update(_encode(namespace))
    for f in fields:
        h.update(_encode(f))
    return h.hexdigest()
