"""
Cache fingerprints (design section 7). Each is a SHA-256 ``stable_signature`` over a versioned namespace plus:

- **extractor fingerprint** (one per artifact kind): the kind's signature-version constant, its codec, the
  extractor's configuration, the Python minor version, the Unicode database version and a digest of the SOURCE CODE
  of every module the extractor runs. A code change therefore invalidates the kind's artifacts even if nobody
  remembers to bump a constant (the constants remain for explicit invalidation);
- **document-metadata fingerprint**: decoding semantics, language detection, ``is_test``, token estimation, line
  counting and symbol/import extraction (the discovery code in ``engine.py`` and the extractors in ``graph.py``);
- **discovery fingerprint**: the effective ignore patterns (defaults, ``extra_ignore``, root ``.gitignore``), the
  limits, the ``pathspec`` version and path case-sensitivity. It identifies the file set; a change produces an
  ordinary file-set diff, because artifacts never depend on it;
- **index fingerprint**: everything global assembly depends on (all of the above plus the global parameters and
  the source of the global-assembly code). Stage 1 recomputes global structures on every start, so a mismatch is
  reported but never needs invalidation.
"""

import functools
import json
import os
import sys
import unicodedata
from importlib import import_module
from typing import Dict, List, Optional

from reponeedle.core.index_cache.codecs import CODECS
from reponeedle.core.index_cache.schema import SCHEMA_VERSION
from reponeedle.core.signatures import stable_signature

FINGERPRINT_VERSION = "reponeedle-index-fingerprints/1"
# Explicit per-kind versions: bump to invalidate a kind's artifacts without a code change elsewhere.
ARTIFACT_VERSIONS: Dict[str, int] = {"doc_meta": 1, "lexical": 1, "semantic": 1, "abstainer": 1, "function_graph": 1}
DECODING = "utf-8/errors=ignore/universal-newlines"

_CODECS_MODULE = "reponeedle.core.index_cache.codecs"
_EXTRACTOR_MODULES = {
    "doc_meta": ("reponeedle.engine", "reponeedle.models", "reponeedle.core.graph", "reponeedle.core.tokenizer",
                 _CODECS_MODULE),
    "lexical": ("reponeedle.core.lexical", "reponeedle.core.tokenizer", "reponeedle.core.signatures", _CODECS_MODULE),
    "semantic": ("reponeedle.core.semantic", "reponeedle.core.tokenizer", "reponeedle.core.signatures",
                 _CODECS_MODULE),
    "abstainer": ("reponeedle.core.abstention", "reponeedle.core.tokenizer", "reponeedle.core.signatures",
                  _CODECS_MODULE),
    "function_graph": ("reponeedle.core.function_graph", "reponeedle.core.signatures", _CODECS_MODULE),
}
_GLOBAL_MODULES = ("reponeedle.core.lexical", "reponeedle.core.semantic", "reponeedle.core.graph",
                   "reponeedle.core.function_graph", "reponeedle.core.abstention")


@functools.lru_cache(maxsize=None)
def module_source_digest(module_name: str) -> str:
    """SHA-256 of a module's source with normalised line endings, or a marker when the source is unavailable."""
    module = import_module(module_name)
    path = getattr(module, "__file__", None) or ""
    if path.endswith(".py") and os.path.isfile(path):
        with open(path, "rb") as fh:
            data = fh.read().replace(b"\r\n", b"\n")
        return stable_signature("module-source/1", module_name, data.decode("utf-8", "surrogateescape"))
    from reponeedle import __version__
    return stable_signature("module-source-unavailable/1", module_name, __version__)


def _environment() -> List[str]:
    return [f"{sys.version_info.major}.{sys.version_info.minor}", unicodedata.unidata_version]


def _sources(names) -> List[str]:
    return [module_source_digest(n) for n in names]


def extractor_fingerprints(engine) -> Dict[str, str]:
    """Per-kind extractor fingerprints for this engine's configuration (hex)."""
    lex, sem = engine.lexical_index, engine.semantic_index
    polyglot = bool(engine.ablation_config.enable_polyglot_symbols)
    config = {
        "doc_meta": [DECODING, f"polyglot_symbols={polyglot}"],
        "lexical": [json.dumps([lex.path_weight, lex.symbol_weight, lex.body_weight, lex.decouple_symbols])],
        "semantic": [json.dumps([sem.min_n, sem.max_n])],
        "abstainer": [],
        "function_graph": [f"structural_parser={engine.function_graph.structural_parser}"],
    }
    out = {}
    for kind, modules in _EXTRACTOR_MODULES.items():
        out[kind] = stable_signature(FINGERPRINT_VERSION, "extractor", kind, ARTIFACT_VERSIONS[kind], CODECS[kind],
                                     _environment(), _sources(modules), config[kind])
    return out


def doc_meta_fingerprint(engine) -> str:
    return extractor_fingerprints(engine)["doc_meta"]


def discovery_fingerprint(ignore_patterns: List[str], max_files: int, max_file_size_bytes: int) -> str:
    import pathspec

    return stable_signature(FINGERPRINT_VERSION, "discovery", list(ignore_patterns), max_files, max_file_size_bytes,
                            getattr(pathspec, "__version__", "unknown"), os.path.normcase("A") == "a",
                            module_source_digest("reponeedle.engine"))


def index_fingerprint(engine, extractor_fps: Dict[str, str]) -> str:
    lex, sem, fg = engine.lexical_index, engine.semantic_index, engine.function_graph
    params = json.dumps({"bm25": [lex.k1, lex.b], "semantic_max_features": sem.max_features,
                         "function_graph": [fg.enable_verified_calls, fg.enable_structural_edges, fg.min_confidence],
                         "repo_graph": [engine.repo_graph.enable_class_to_test,
                                        engine.repo_graph.enable_degree_matched_control]}, sort_keys=True)
    return stable_signature(FINGERPRINT_VERSION, "index", SCHEMA_VERSION, [extractor_fps[k] for k in sorted(
        extractor_fps)], params, _sources(_GLOBAL_MODULES))


def unsupported_configuration(engine) -> Optional[str]:
    """Stage 1 persists the default extractors only; optional components take the uncached route (Stage 4)."""
    if engine.function_graph.structural_parser != "regex":
        return "structural_parser='tree_sitter' is not persisted in Stage 1"
    if engine.scip_config is not None:
        return "SCIP ingestion is not persisted in Stage 1"
    return None
