"""
Versioned payload codecs for persisted artifacts. No pickle, no eval, no dynamic imports: payloads are explicit
binary formats or canonical JSON, zlib-compressed, and every decoded value is checked for type, range, length and
uniqueness before it is used. Encoding is canonical (deterministic), so equal data always yields equal bytes.

Payloads are canonical JSON (sorted object keys, no whitespace, NaN/Infinity rejected), zlib-compressed. JSON is
parsed by the C-accelerated standard-library decoder, and Python's float repr round-trips exactly, so weights are
bit-identical after a round trip (tested).

| Kind            | Codec                  | Payload (before zlib)                                                        |
| doc_meta        | doc-meta-json/1        | {"language","is_test","line_count","token_count","symbols","imports"}        |
| lexical         | bm25-terms-json/1      | {"t": [terms, insertion order], "w": [float weights], "l": float length}     |
| semantic        | semantic-counts-json/1 | {"f": [features, insertion order], "c": [int counts >= 1]}                   |
| abstainer       | vocab-set-json/1       | [tokens, sorted and unique]                                                  |
| function_graph  | polyglot-json/1        | {"functions": [...], "calls": [...], "symbols": [...], "imports": [...]}     |
"""

import json
import math
import zlib
from typing import Any, Dict, List, Optional, Set, Tuple

from reponeedle.core.function_graph import CallSite, FunctionSymbol

MAX_DECODED_BYTES = 64 * 1024 * 1024   # zlib output bound per payload (decompression-bomb guard)
ZLIB_LEVEL = 1          # measured: 6.3x faster than level 6 for ~15% larger payloads (Stage 1 report)

CODECS = {
    "doc_meta": "doc-meta-json/1",
    "lexical": "bm25-terms-json/1",
    "semantic": "semantic-counts-json/1",
    "abstainer": "vocab-set-json/1",
    "function_graph": "polyglot-json/1",
}


class CodecError(ValueError):
    """A payload is malformed, out of range or not canonical."""


# ---------------------------------------------------------------------------------------------------- primitives

def _compress(raw: bytes) -> bytes:
    return zlib.compress(raw, ZLIB_LEVEL)


def _decompress(payload: bytes) -> bytes:
    d = zlib.decompressobj()
    try:
        raw = d.decompress(payload, MAX_DECODED_BYTES)
    except zlib.error as exc:
        raise CodecError(f"zlib: {exc}") from exc
    if d.unconsumed_tail or not d.eof or d.unused_data:
        raise CodecError("payload exceeds the size limit, is truncated or has trailing data")
    return raw


def _json_dumps(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False).encode("utf-8")


def _json_loads(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise CodecError(f"invalid JSON: {exc}") from exc


def _str_list(value: Any, what: str) -> List[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise CodecError(f"{what} must be a list of strings")
    return value


def _int(value: Any, what: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise CodecError(f"{what} must be an integer >= {minimum}")
    return value


def _opt_str(value: Any, what: str) -> Optional[str]:
    if value is not None and not isinstance(value, str):
        raise CodecError(f"{what} must be a string or null")
    return value


def _bool(value: Any, what: str) -> bool:
    if type(value) is not bool:
        raise CodecError(f"{what} must be a boolean")
    return value


# ------------------------------------------------------------------------------------------------------ doc_meta

def encode_doc_meta(meta: Dict[str, Any]) -> bytes:
    return _compress(_json_dumps(meta))


def decode_doc_meta(payload: bytes) -> Dict[str, Any]:
    obj = _json_loads(_decompress(payload))
    if not isinstance(obj, dict) or set(obj) != {"language", "is_test", "line_count", "token_count", "symbols",
                                                 "imports"}:
        raise CodecError("doc_meta keys")
    if not isinstance(obj["language"], str):
        raise CodecError("doc_meta language")
    return {"language": obj["language"], "is_test": _bool(obj["is_test"], "is_test"),
            "line_count": _int(obj["line_count"], "line_count"), "token_count": _int(obj["token_count"], "tokens"),
            "symbols": _str_list(obj["symbols"], "symbols"), "imports": _str_list(obj["imports"], "imports")}


# ------------------------------------------------------------------------------------------------------- lexical

def encode_lexical(counts: Dict[str, float], effective_len: float) -> bytes:
    return _compress(_json_dumps({"t": list(counts), "w": [float(w) for w in counts.values()],
                                  "l": float(effective_len)}))


def decode_lexical(payload: bytes) -> Tuple[Dict[str, float], float]:
    obj = _json_loads(_decompress(payload))
    if not isinstance(obj, dict) or set(obj) != {"t", "w", "l"}:
        raise CodecError("lexical keys")
    terms, weights, length = obj["t"], obj["w"], obj["l"]
    _str_list(terms, "lexical terms")
    if (not isinstance(weights, list) or len(weights) != len(terms)
            or not all(type(w) is float and math.isfinite(w) for w in weights)):
        raise CodecError("lexical weights must be finite floats, one per term")
    if type(length) is not float or not math.isfinite(length):
        raise CodecError("lexical length must be a finite float")
    counts = dict(zip(terms, weights))
    if len(counts) != len(terms):
        raise CodecError("lexical term duplicated")
    return counts, length


# ------------------------------------------------------------------------------------------------------ semantic

def encode_semantic(counts: Dict[str, int]) -> bytes:
    return _compress(_json_dumps({"f": list(counts), "c": list(counts.values())}))


def decode_semantic(payload: bytes) -> Dict[str, int]:
    obj = _json_loads(_decompress(payload))
    if not isinstance(obj, dict) or set(obj) != {"f", "c"}:
        raise CodecError("semantic keys")
    features, values = obj["f"], obj["c"]
    _str_list(features, "semantic features")
    if not isinstance(values, list) or len(values) != len(features) or             not all(type(v) is int and v >= 1 for v in values):
        raise CodecError("semantic counts must be integers >= 1, one per feature")
    counts = dict(zip(features, values))
    if len(counts) != len(features):
        raise CodecError("semantic feature duplicated")
    return counts


# ----------------------------------------------------------------------------------------------------- abstainer

def encode_vocab(vocab: Set[str]) -> bytes:
    return _compress(_json_dumps(sorted(vocab)))


def decode_vocab(payload: bytes) -> Set[str]:
    items = _str_list(_json_loads(_decompress(payload)), "vocabulary")
    if any(a >= b for a, b in zip(items, items[1:])):
        raise CodecError("vocabulary not sorted and unique")
    return set(items)


# ------------------------------------------------------------------------------------------------ function graph

def encode_polyglot(extraction: Tuple[List[FunctionSymbol], List[CallSite], List[str], List[str]]) -> bytes:
    funcs, calls, syms, imps = extraction
    obj = {
        "functions": [[f.name, f.parent_class, f.filepath, f.is_method, f.is_test, f.start_line, list(f.arg_names)]
                      for f in funcs],
        "calls": [[c.caller_path, c.caller_func, c.callee_name, c.is_attribute, c.qualifier, c.start_line,
                   c.qualifier_path] for c in calls],
        "symbols": list(syms),
        "imports": list(imps),
    }
    return _compress(_json_dumps(obj))


def decode_polyglot(payload: bytes) -> Tuple[List[FunctionSymbol], List[CallSite], List[str], List[str]]:
    obj = _json_loads(_decompress(payload))
    if not isinstance(obj, dict) or set(obj) != {"functions", "calls", "symbols", "imports"}:
        raise CodecError("function_graph keys")
    funcs, calls = [], []
    for row in obj["functions"] if isinstance(obj["functions"], list) else [None]:
        if not isinstance(row, list) or len(row) != 7:
            raise CodecError("function record")
        name, parent, filepath, is_method, is_test, line, args = row
        if not isinstance(name, str) or not isinstance(filepath, str):
            raise CodecError("function record fields")
        funcs.append(FunctionSymbol(name=name, parent_class=_opt_str(parent, "parent_class"), filepath=filepath,
                                    is_method=_bool(is_method, "is_method"), is_test=_bool(is_test, "is_test"),
                                    start_line=_int(line, "start_line"), arg_names=_str_list(args, "arg_names")))
    for row in obj["calls"] if isinstance(obj["calls"], list) else [None]:
        if not isinstance(row, list) or len(row) != 7:
            raise CodecError("call record")
        caller_path, caller_func, callee, is_attr, qualifier, line, qpath = row
        if not isinstance(caller_path, str) or not isinstance(callee, str):
            raise CodecError("call record fields")
        calls.append(CallSite(caller_path=caller_path, caller_func=_opt_str(caller_func, "caller_func"),
                              callee_name=callee, is_attribute=_bool(is_attr, "is_attribute"),
                              qualifier=_opt_str(qualifier, "qualifier"), start_line=_int(line, "start_line"),
                              qualifier_path=_opt_str(qpath, "qualifier_path")))
    return funcs, calls, _str_list(obj["symbols"], "symbols"), _str_list(obj["imports"], "imports")


ENCODERS = {"doc_meta": encode_doc_meta, "semantic": encode_semantic, "abstainer": encode_vocab,
            "function_graph": encode_polyglot}
DECODERS = {"doc_meta": decode_doc_meta, "lexical": decode_lexical, "semantic": decode_semantic,
            "abstainer": decode_vocab, "function_graph": decode_polyglot}


def decode(kind: str, codec: str, payload: bytes) -> Any:
    if CODECS.get(kind) != codec:
        raise CodecError(f"unexpected codec {codec!r} for {kind!r}")
    return DECODERS[kind](payload)
