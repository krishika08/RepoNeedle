"""
SCIP index ingestion (optional).

Consumes an existing SCIP index (``index.scip``) produced by an external indexer (scip-typescript,
scip-python, scip-java, scip-clang, rust-analyzer, ...) and turns its resolved symbol definitions and
references into evidence for RepoNeedle's function-level graph. This module is a SCIP *consumer*: it
never runs an indexer, a compiler or a build command, and it never needs the ``scip`` CLI.

Schema: the official ``scip.proto`` (scip-code/scip v0.10.0), via the vendored, generated bindings in
``reponeedle/core/_scip``. Protobuf is an optional dependency (``pip install -e ".[scip]"``) imported
only when an index is loaded.

Trust model: nothing in the index is trusted because it parsed. ``Metadata.project_root`` must match
the repository being indexed (unless the caller explicitly allows a mismatch); every document path must
be canonical, relative, inside the repository, not a symbolic link, and present in RepoNeedle's index;
ranges are bounds-checked against the current file contents; documents whose embedded text differs from
the current file are treated as stale and skipped. Source files are never opened here: the contents
compared are the ones RepoNeedle already indexed.
"""

from __future__ import annotations

import os
import re
import time
import urllib.parse
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple

DEFAULT_MAX_SCIP_INDEX_BYTES = 256 * 1024 * 1024

SCIP_REFERENCE_EDGE_TYPE = "scip_reference"
# Fixed, documented confidence for SCIP-derived edges. Deliberately not 1.0: producers differ in
# precision, and a reference to a callable is not proof of a call (it may be a function value).
SCIP_REFERENCE_CONFIDENCE = 0.9

_MAX_LISTED_PATHS = 200  # cap on per-category path lists in diagnostics

# SymbolRole bit flags (scip.proto `enum SymbolRole`).
ROLE_DEFINITION = 0x1
ROLE_IMPORT = 0x2
ROLE_WRITE_ACCESS = 0x4
ROLE_READ_ACCESS = 0x8
ROLE_GENERATED = 0x10
ROLE_TEST = 0x20
ROLE_FORWARD_DEFINITION = 0x40

# SymbolInformation.Kind values that denote something callable.
CALLABLE_KINDS = {
    "Function", "Method", "Constructor", "StaticMethod", "AbstractMethod", "PureVirtualMethod",
    "TraitMethod", "ProtocolMethod", "TypeClassMethod", "SingletonMethod", "MethodSpecification",
    "MethodAlias",
}

# PositionEncoding values.
ENC_UNSPECIFIED, ENC_UTF8, ENC_UTF16, ENC_UTF32 = 0, 1, 2, 3
_ENCODING_NAMES = {ENC_UNSPECIFIED: "unspecified", ENC_UTF8: "utf8", ENC_UTF16: "utf16", ENC_UTF32: "utf32"}


class ScipIngestionError(Exception):
    """Raised when a requested SCIP index cannot be used. The message says what to do."""


# ---------------------------------------------------------------------------
# Protobuf bindings (lazy)
# ---------------------------------------------------------------------------

def load_bindings():
    """Imports the vendored generated module; raises ScipIngestionError with install instructions."""
    try:
        from reponeedle.core._scip import scip_pb2
    except ImportError as exc:
        raise ScipIngestionError(
            "SCIP ingestion needs the optional 'scip' extra (protobuf>=5.29.0,<8). "
            'Install it with: pip install -e ".[scip]"   '
            f"(import failed: {type(exc).__name__}: {exc})"
        ) from exc
    except Exception as exc:  # e.g. google.protobuf.runtime_version.VersionError
        raise ScipIngestionError(
            "The installed protobuf runtime cannot load RepoNeedle's SCIP bindings "
            f"(generated for protobuf 5.29.0; supported: >=5.29.0,<8): {type(exc).__name__}: {exc}"
        ) from exc
    return scip_pb2


def protobuf_status() -> Dict[str, Any]:
    """Reports whether the SCIP bindings can be loaded, without reading any index."""
    from reponeedle.core import _scip
    status = {"schema_tag": _scip.SCHEMA_TAG, "schema_commit": _scip.SCHEMA_COMMIT}
    try:
        load_bindings()
        import google.protobuf
        from google.protobuf.internal import api_implementation
        status.update(available=True, protobuf_version=google.protobuf.__version__,
                      implementation=api_implementation.Type(), error=None)
    except ScipIngestionError as exc:
        status.update(available=False, protobuf_version=None, implementation=None, error=str(exc))
    return status


# ---------------------------------------------------------------------------
# Symbol grammar (scip.proto, `message Symbol`)
# ---------------------------------------------------------------------------

_IDENT_CHARS = set("_+-$abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


@dataclass(frozen=True)
class Descriptor:
    name: str
    suffix: str            # namespace, type, term, meta, macro, method, type_parameter, parameter
    disambiguator: str = ""


@dataclass(frozen=True)
class ParsedSymbol:
    is_local: bool
    scheme: str = ""
    manager: str = ""
    package: str = ""
    version: str = ""
    descriptors: Tuple[Descriptor, ...] = ()
    local_id: str = ""

    @property
    def name(self) -> str:
        return self.local_id if self.is_local else (self.descriptors[-1].name if self.descriptors else "")

    @property
    def suffix(self) -> str:
        return "local" if self.is_local else (self.descriptors[-1].suffix if self.descriptors else "")


_SIMPLE_IDENT = re.compile(r"[_+\-$A-Za-z0-9]+")


def _read_space_token(s: str, pos: int) -> Tuple[str, int]:
    """Reads up to the next single space; a double space is an escaped space."""
    i = pos
    while True:
        i = s.find(" ", i)
        if i < 0:
            raise ValueError("symbol ended before all space-separated parts were read")
        if i + 1 < len(s) and s[i + 1] == " ":
            i += 2
            continue
        return s[pos:i].replace("  ", " "), i + 1


def _read_name(s: str, i: int) -> Tuple[str, int]:
    if i < len(s) and s[i] != "`":
        m = _SIMPLE_IDENT.match(s, i)
        if m is None:
            raise ValueError(f"expected an identifier at offset {i}")
        return m.group(0), m.end()
    if i < len(s) and s[i] == "`":
        out = []
        i += 1
        while i < len(s):
            if s[i] == "`":
                if i + 1 < len(s) and s[i + 1] == "`":
                    out.append("`")
                    i += 2
                    continue
                if not out:
                    raise ValueError("empty escaped identifier")
                return "".join(out), i + 1
            out.append(s[i])
            i += 1
        raise ValueError("unterminated escaped identifier")
    start = i
    while i < len(s) and s[i] in _IDENT_CHARS:
        i += 1
    if i == start:
        raise ValueError(f"expected an identifier at offset {start}")
    return s[start:i], i


def _expect(s: str, i: int, ch: str) -> int:
    if i >= len(s) or s[i] != ch:
        raise ValueError(f"expected {ch!r} at offset {i}")
    return i + 1


def parse_symbol(symbol: str) -> ParsedSymbol:
    """Parses a SCIP symbol string according to the grammar in scip.proto. Raises ValueError."""
    if symbol.startswith("local "):
        local_id = symbol[len("local "):]
        if not local_id or any(c not in _IDENT_CHARS for c in local_id):
            raise ValueError("invalid local symbol id")
        return ParsedSymbol(is_local=True, local_id=local_id)
    pos = 0
    parts = []
    for _ in range(4):
        tok, pos = _read_space_token(symbol, pos)
        parts.append(tok)
    scheme, manager, package, version = parts
    if not scheme or scheme.startswith("local"):
        raise ValueError("scheme must be non-empty and must not start with 'local'")
    s, i, descriptors = symbol[pos:], 0, []
    while i < len(s):
        if s[i] == "[":
            name, i = _read_name(s, i + 1)
            i = _expect(s, i, "]")
            descriptors.append(Descriptor(name, "type_parameter"))
        elif s[i] == "(":
            name, i = _read_name(s, i + 1)
            i = _expect(s, i, ")")
            descriptors.append(Descriptor(name, "parameter"))
        else:
            name, i = _read_name(s, i)
            if i >= len(s):
                raise ValueError("descriptor without suffix")
            ch = s[i]
            if ch in "/#.:!":
                suffix = {"/": "namespace", "#": "type", ".": "term", ":": "meta", "!": "macro"}[ch]
                descriptors.append(Descriptor(name, suffix))
                i += 1
            elif ch == "(":
                j = i + 1
                while j < len(s) and s[j] in _IDENT_CHARS:
                    j += 1
                disambiguator = s[i + 1:j]
                j = _expect(s, j, ")")
                j = _expect(s, j, ".")
                descriptors.append(Descriptor(name, "method", disambiguator))
                i = j
            else:
                raise ValueError(f"unexpected descriptor suffix {ch!r}")
    if not descriptors:
        raise ValueError("global symbol without descriptors")
    return ParsedSymbol(is_local=False, scheme=scheme, manager=manager, package=package, version=version,
                        descriptors=tuple(descriptors))


# ---------------------------------------------------------------------------
# Ranges
# ---------------------------------------------------------------------------

class SourceRange(NamedTuple):
    """Half-open [start, end) range; lines and characters are zero-based, as in SCIP."""
    start_line: int
    start_character: int
    end_line: int
    end_character: int

    def contains(self, line: int, character: int) -> bool:
        """True if (line, character) is in [start, end): the end position is exclusive, so an empty range
        contains nothing and a position at one range's end belongs to an adjacent range starting there."""
        return (self.start_line, self.start_character) <= (line, character) < (self.end_line, self.end_character)

    @property
    def span(self) -> Tuple[int, int]:
        return (self.end_line - self.start_line, self.end_character - self.start_character)


def _checked(start_line: int, start_character: int, end_line: int, end_character: int) -> Optional[SourceRange]:
    if start_line < 0 or start_character < 0 or end_line < 0 or end_character < 0:
        return None
    if (end_line, end_character) < (start_line, start_character):
        return None
    return SourceRange(start_line, start_character, end_line, end_character)


def _decode(occ, oneof: str, single_field: str, multi_field: str, legacy_field: str) -> Optional[SourceRange]:
    # Only the populated field is read: touching an unset sub-message is not free.
    which = occ.WhichOneof(oneof)
    if which == single_field:
        t = getattr(occ, single_field)
        return _checked(t.line, t.start_character, t.line, t.end_character)
    if which == multi_field:
        t = getattr(occ, multi_field)
        return _checked(t.start_line, t.start_character, t.end_line, t.end_character)
    legacy = getattr(occ, legacy_field)
    n = len(legacy)
    if n == 3:
        return _checked(legacy[0], legacy[1], legacy[0], legacy[2])
    if n == 4:
        return _checked(legacy[0], legacy[1], legacy[2], legacy[3])
    return None


def occurrence_range(occ) -> Optional[SourceRange]:
    """Typed range if set (takes precedence), else the deprecated packed range; None if malformed/absent."""
    return _decode(occ, "typed_range", "single_line_range", "multi_line_range", "range")


def enclosing_range(occ) -> Optional[SourceRange]:
    """Typed enclosing range if set, else the deprecated packed one; None if absent or malformed."""
    return _decode(occ, "typed_enclosing_range", "single_line_enclosing_range", "multi_line_enclosing_range",
                   "enclosing_range")


def line_length(line: str, encoding: int) -> int:
    """Length of a line in the code units of a SCIP PositionEncoding (unspecified: the most permissive)."""
    utf8 = len(line.encode("utf-8", "surrogatepass"))
    if encoding == ENC_UTF8:
        return utf8
    utf16 = len(line.encode("utf-16-le", "surrogatepass")) // 2
    if encoding == ENC_UTF16:
        return utf16
    if encoding == ENC_UTF32:
        return len(line)
    return max(utf8, utf16, len(line))


def range_in_bounds(r: SourceRange, lines: Sequence[str], encoding: int) -> bool:
    if r.end_line >= len(lines):
        return False
    if r.start_character > line_length(lines[r.start_line], encoding):
        return False
    return r.end_character <= line_length(lines[r.end_line], encoding)


# ---------------------------------------------------------------------------
# Project root and document paths
# ---------------------------------------------------------------------------

def decode_project_root(project_root: str) -> Tuple[Optional[str], str]:
    """
    Decodes ``Metadata.project_root`` (a URI-encoded absolute path) to a local path.

    Accepts ``file:///abs``, ``file://localhost/abs``, ``file:///C:/x``, ``file:///c%3A/x``,
    ``file://server/share/x`` (UNC, Windows) and, leniently, a plain absolute path.
    Returns (path or None, description).
    """
    if not project_root:
        return None, "missing"
    parsed = urllib.parse.urlparse(project_root)
    if parsed.scheme.lower() == "file":
        path = urllib.parse.unquote(parsed.path)
        host = parsed.netloc
        if host and host.lower() != "localhost":
            if os.name != "nt":
                return None, f"remote host {host!r} in file URI"
            path = "\\\\" + host + path.replace("/", "\\")
        elif re.match(r"^/[A-Za-z]:([/\\]|$)", path):
            path = path[1:]  # /C:/x -> C:/x
        if not path:
            return None, "empty path in file URI"
        return os.path.normpath(path), "file-uri"
    if parsed.scheme and len(parsed.scheme) > 1:
        return None, f"unsupported URI scheme {parsed.scheme!r}"
    if os.path.isabs(project_root):
        return os.path.normpath(project_root), "plain-path"
    return None, "not an absolute path or file URI"


def is_windows_style_root(project_root: str) -> bool:
    """True if ``project_root`` names a Windows path (drive letter or UNC host), on any host OS."""
    if not project_root:
        return False
    parsed = urllib.parse.urlparse(project_root)
    if parsed.scheme.lower() == "file":
        path = urllib.parse.unquote(parsed.path)
        host = parsed.netloc
        return bool(re.match(r"^/?[A-Za-z]:([/\\]|$)", path)) or bool(host and host.lower() != "localhost")
    return bool(re.match(r"^[A-Za-z]:[/\\]", project_root)) or project_root.startswith("\\\\")


def _same_path(a: str, b: str) -> bool:
    ra, rb = os.path.realpath(a), os.path.realpath(b)
    return os.path.normcase(ra) == os.path.normcase(rb)


def validate_relative_path(path: str) -> Optional[str]:
    """Returns None if ``path`` is a canonical SCIP relative path, else the reason it is rejected."""
    if not path:
        return "empty path"
    if "\x00" in path:
        return "NUL byte in path"
    if "\\" in path:
        return "backslash separator (SCIP requires '/')"
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        return "absolute path"
    parts = path.split("/")
    if any(p == "" for p in parts):
        return "empty path component"
    if any(p in (".", "..") for p in parts):
        return "'.' or '..' component"
    return None


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

class ScipDefinition(NamedTuple):
    symbol: str
    path: str
    range: SourceRange
    enclosing: Optional[SourceRange]
    callable: bool
    name: str


class ScipReferenceEdge(NamedTuple):
    """A reference, in ``source_path``, to a callable defined in another repository file."""
    source_path: str
    source_symbol: Optional[str]     # innermost enclosing callable definition, if the producer gave ranges
    source_name: Optional[str]
    target_path: str
    target_symbol: str
    target_name: str
    first_line: int                  # 1-based line of the first reference


class ScipRelationship(NamedTuple):
    symbol: str
    related_symbol: str
    is_reference: bool
    is_implementation: bool
    is_type_definition: bool
    is_definition: bool
    path: Optional[str]              # document that declared the relationship (None: external_symbols)


@dataclass
class ScipResolution:
    edges: List[ScipReferenceEdge] = field(default_factory=list)
    relationships: List[ScipRelationship] = field(default_factory=list)
    definitions: Dict[str, List[ScipDefinition]] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

class ScipIndex:
    """A parsed, root-validated SCIP index. ``resolve()`` binds it to RepoNeedle's documents."""

    def __init__(self, message, index_path: str, file_bytes: int, parse_ms: float):
        self._msg = message
        self.index_path = index_path
        self.file_bytes = file_bytes
        self.parse_ms = parse_ms
        meta = message.metadata
        self.has_metadata = message.HasField("metadata")
        self.tool_name = meta.tool_info.name
        self.tool_version = meta.tool_info.version
        self.protocol_version = int(meta.version)
        self.project_root = meta.project_root
        self.text_document_encoding = int(meta.text_document_encoding)
        self.repo_root: Optional[str] = None
        self.root_status = "not_checked"
        self.decoded_root: Optional[str] = None
        self.root_detail = ""

    # -- loading -----------------------------------------------------------
    @classmethod
    def load(cls, index_path: str, max_bytes: int = DEFAULT_MAX_SCIP_INDEX_BYTES) -> "ScipIndex":
        pb = load_bindings()
        if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
            raise ScipIngestionError(f"max_index_bytes must be a positive integer, got {max_bytes!r}")
        try:
            size = os.stat(index_path).st_size
        except OSError as exc:
            raise ScipIngestionError(f"Cannot read SCIP index {index_path!r}: {exc.strerror or exc}") from exc
        if not os.path.isfile(index_path):
            raise ScipIngestionError(f"SCIP index {index_path!r} is not a regular file")
        if size > max_bytes:
            raise ScipIngestionError(
                f"SCIP index {index_path!r} is {size:,} bytes, above the limit of {max_bytes:,} bytes. "
                "Raise ScipConfig.max_index_bytes if this index is expected to be this large."
            )
        t0 = time.perf_counter()
        with open(index_path, "rb") as f:
            # Read at most one byte more than stat() reported: the buffer is sized by the file, not by the
            # limit, and a file that grew after stat() is still detected.
            data = f.read(size + 1)
        if len(data) > max_bytes or len(data) > size:
            raise ScipIngestionError(f"SCIP index {index_path!r} changed size while being read; retry once it is complete")
        try:
            message = pb.Index.FromString(data)
        except Exception as exc:  # google.protobuf.message.DecodeError and friends
            raise ScipIngestionError(
                f"{index_path!r} is not a valid SCIP index (Protobuf decoding failed: {exc}). "
                "Regenerate it with your SCIP indexer."
            ) from exc
        parse_ms = (time.perf_counter() - t0) * 1000
        if data and not message.HasField("metadata") and not message.documents and not message.external_symbols:
            raise ScipIngestionError(
                f"{index_path!r} decoded as Protobuf but contains no SCIP metadata, documents or symbols; "
                "it does not look like a SCIP index."
            )
        return cls(message, os.path.abspath(index_path), len(data), parse_ms)

    @classmethod
    def from_bytes(cls, data: bytes, label: str = "<bytes>") -> "ScipIndex":
        """Parses an in-memory index (tests and tooling). No size guard beyond the caller's."""
        pb = load_bindings()
        t0 = time.perf_counter()
        try:
            message = pb.Index.FromString(data)
        except Exception as exc:
            raise ScipIngestionError(f"{label} is not a valid SCIP index: {exc}") from exc
        return cls(message, label, len(data), (time.perf_counter() - t0) * 1000)

    # -- project root --------------------------------------------------------
    def validate_root(self, repo_root: str, allow_mismatch: bool = False) -> str:
        """Compares Metadata.project_root with ``repo_root``. Raises unless they match or a mismatch is allowed."""
        self.repo_root = os.path.realpath(repo_root)
        if not os.path.isdir(self.repo_root):
            raise ScipIngestionError(f"Repository root {repo_root!r} is not a directory")
        decoded, how = decode_project_root(self.project_root)
        self.decoded_root, self.root_detail = decoded, how
        if decoded is None:
            self.root_status = "unverifiable"
        elif _same_path(decoded, self.repo_root):
            self.root_status = "match"
        else:
            self.root_status = "mismatch"
        if self.root_status != "match" and not allow_mismatch:
            raise ScipIngestionError(
                f"SCIP index {self.index_path!r} was generated for project_root {self.project_root!r} "
                f"({self.root_status}: {how}), not for the repository {self.repo_root!r}. Regenerate the index "
                "in this checkout, or pass ScipConfig(allow_project_root_mismatch=True) if it was built "
                "from an identical checkout elsewhere (for example in CI); document paths are still "
                "validated against this repository."
            )
        return self.root_status

    # -- resolution ------------------------------------------------------------
    def resolve(self, docs: Sequence[Any]) -> ScipResolution:
        """
        Binds the index to RepoNeedle's documents (``FileDoc``-like objects with ``path`` and ``content``)
        under the validated repository root. Never reads source files.
        """
        if self.repo_root is None:
            raise ScipIngestionError("validate_root() must be called before resolve()")
        t0 = time.perf_counter()
        msg = self._msg
        real_root = self.repo_root

        doc_by_path = {d.path.replace("\\", "/"): d for d in docs}
        folded: Dict[str, List[str]] = defaultdict(list)
        if os.name == "nt":
            for p in doc_by_path:
                folded[p.casefold()].append(p)

        diag: Dict[str, Any] = {
            "requested": True,
            "index_path": self.index_path,
            "index_bytes": self.file_bytes,
            "schema": {"tag": "v0.10.0", "commit": "1c2b6db7e560d5233c944f36e4ac1377cc6963fc"},
            "producer": {"name": self.tool_name or None, "version": self.tool_version or None},
            "protocol_version": self.protocol_version,
            "metadata_present": self.has_metadata,
            "project_root": {"declared": self.project_root or None, "decoded": self.decoded_root,
                             "repository": real_root, "status": self.root_status, "detail": self.root_detail},
            "documents": {"in_index": len(msg.documents), "matched": 0, "matched_case_insensitive": 0,
                          "not_on_disk_in_memory_docs": 0, "stale": 0, "rejected": {}, "missing": [],
                          "not_indexed_by_reponeedle": [], "duplicate": []},
            "freshness": {"verified_identical": 0, "stale": 0, "unverified_no_text": 0, "status": "unverified"},
            "position_encoding": defaultdict(int),
            "occurrences": {"total": 0, "invalid_range": 0, "out_of_bounds": 0, "without_symbol": 0,
                            "malformed_symbol": 0},
            "symbols": {"unique": 0, "external_symbols": len(msg.external_symbols), "local": 0},
            "definitions": {"total": 0, "callable": 0, "forward_declarations": 0, "multiply_defined_symbols": 0},
            "references": {"total": 0, "import": 0, "local": 0, "to_repository_callables": 0,
                           "to_repository_non_callables": 0, "same_file": 0, "external": 0,
                           "external_package": 0, "unresolved": 0, "defined_in_unusable_documents": 0,
                           "ambiguous": 0,
                           "with_enclosing_definition": 0},
            "relationships": {"implementation": 0, "type_definition": 0, "reference": 0, "definition": 0},
            "edges": {"reference_edges": 0},
            "parse_ms": round(self.parse_ms, 2),
        }

        usable: List[Tuple[Any, str, List[str], int]] = []   # (document, repo path, lines, encoding)
        seen_paths = set()
        windows_index = is_windows_style_root(self.project_root)
        diag["documents"]["backslash_paths_normalized"] = 0
        for document in msg.documents:
            rel = document.relative_path
            if windows_index and "\\" in rel:
                # Non-compliant producers (observed: scip-typescript 0.6.2 on Windows) write '\'. In an index
                # whose project_root is a Windows path, '\' cannot be part of a file name, so it is a separator.
                rel = rel.replace("\\", "/")
                diag["documents"]["backslash_paths_normalized"] += 1
            reason = validate_relative_path(rel)
            if reason is None:
                abs_path = os.path.join(real_root, *rel.split("/"))
                if os.path.lexists(abs_path):
                    if os.path.islink(abs_path):
                        reason = "symbolic link (SCIP documents must be regular files)"
                    else:
                        try:
                            resolved = os.path.realpath(abs_path, strict=True)
                        except (OSError, RuntimeError, ValueError):
                            resolved = None
                        if resolved is None or not _within(resolved, real_root):
                            reason = "resolves outside the repository"
            if reason is not None:
                diag["documents"]["rejected"][_clip(rel)] = reason
                continue
            repo_path = rel if rel in doc_by_path else None
            if repo_path is None and folded:
                candidates = folded.get(rel.casefold(), [])
                if len(candidates) == 1:
                    repo_path = candidates[0]
                    diag["documents"]["matched_case_insensitive"] += 1
            if repo_path is None:
                key = "not_indexed_by_reponeedle" if os.path.isfile(os.path.join(real_root, *rel.split("/"))) else "missing"
                _append(diag["documents"][key], rel)
                continue
            if repo_path in seen_paths:
                _append(diag["documents"]["duplicate"], rel)
                continue
            seen_paths.add(repo_path)
            if not os.path.exists(os.path.join(real_root, *repo_path.split("/"))):
                diag["documents"]["not_on_disk_in_memory_docs"] += 1
            file_doc = doc_by_path[repo_path]
            content = _normalize(file_doc.content or "")
            if document.text:
                if _normalize(document.text) == content:
                    diag["freshness"]["verified_identical"] += 1
                else:
                    diag["freshness"]["stale"] += 1
                    diag["documents"]["stale"] += 1
                    continue
            else:
                diag["freshness"]["unverified_no_text"] += 1
            encoding = int(document.position_encoding)
            diag["position_encoding"][_ENCODING_NAMES.get(encoding, f"unknown({encoding})")] += 1
            diag["documents"]["matched"] += 1
            usable.append((document, file_doc.path, content.split("\n"), encoding))

        fr = diag["freshness"]
        fr["status"] = ("stale_documents_skipped" if fr["stale"] else
                        "verified" if fr["verified_identical"] and not fr["unverified_no_text"] else
                        "partially_verified" if fr["verified_identical"] else "unverified")

        usable_ids = {id(u[0]) for u in usable}
        defined_in_unusable = set()
        for document in msg.documents:
            if id(document) in usable_ids:
                continue
            for occ in document.occurrences:
                if occ.symbol and int(occ.symbol_roles) & ROLE_DEFINITION and not occ.symbol.startswith("local "):
                    defined_in_unusable.add(occ.symbol)

        # Symbol information: from usable documents and external_symbols only.
        info: Dict[str, Any] = {}
        relationships: List[ScipRelationship] = []
        external = {s.symbol for s in msg.external_symbols if s.symbol}
        for document, repo_path, _lines, _enc in usable:
            for si in document.symbols:
                if si.symbol and si.symbol not in info:
                    info[si.symbol] = si
                self._collect_relationships(si, repo_path, relationships, diag)
        for si in msg.external_symbols:
            if si.symbol and si.symbol not in info:
                info[si.symbol] = si
            self._collect_relationships(si, None, relationships, diag)

        parsed_cache: Dict[str, Optional[ParsedSymbol]] = {}

        def parsed(sym: str) -> Optional[ParsedSymbol]:
            if sym not in parsed_cache:
                try:
                    parsed_cache[sym] = parse_symbol(sym)
                except ValueError:
                    parsed_cache[sym] = None
            return parsed_cache[sym]

        pb = load_bindings()
        kind_names = {v.number: v.name for v in pb.SymbolInformation.DESCRIPTOR.enum_types_by_name["Kind"].values}

        def is_callable(sym: str) -> bool:
            si = info.get(sym)
            if si is not None and si.kind:
                name = kind_names.get(si.kind)
                if name is not None:  # a known kind is authoritative
                    return name in CALLABLE_KINDS
            ps = parsed(sym)  # unspecified (or newer-than-schema) kind: use the descriptor suffix
            return ps is not None and ps.suffix == "method"

        def display(sym: str) -> str:
            si = info.get(sym)
            if si is not None and si.display_name:
                return si.display_name
            ps = parsed(sym)
            return ps.name if ps is not None else sym

        # Pass 1: definitions. Each occurrence's fields are read once (Protobuf attribute access is not free).
        definitions: Dict[str, List[ScipDefinition]] = defaultdict(list)
        local_symbols = set()
        per_doc_occ: List[Tuple[str, List[Tuple[str, int, SourceRange, ParsedSymbol]]]] = []
        n_total = n_no_symbol = n_invalid = n_oob = n_malformed = n_defs = n_forward = 0
        for document, repo_path, lines, encoding in usable:
            occs: List[Tuple[str, int, SourceRange, ParsedSymbol]] = []
            lengths: Dict[int, int] = {}
            n_lines = len(lines)
            for occ in document.occurrences:
                n_total += 1
                symbol = occ.symbol
                if not symbol:
                    n_no_symbol += 1
                    continue
                r = occurrence_range(occ)
                if r is None:
                    n_invalid += 1
                    continue
                if r.end_line >= n_lines:
                    n_oob += 1
                    continue
                for ln in (r.start_line, r.end_line):
                    if ln not in lengths:
                        lengths[ln] = line_length(lines[ln], encoding)
                if r.start_character > lengths[r.start_line] or r.end_character > lengths[r.end_line]:
                    n_oob += 1
                    continue
                ps = parsed(symbol)
                if ps is None:
                    n_malformed += 1
                    continue
                if ps.is_local:
                    local_symbols.add((repo_path, symbol))
                roles = int(occ.symbol_roles)
                if roles & ROLE_DEFINITION:
                    key = symbol if not ps.is_local else f"{repo_path}\x00{symbol}"
                    definitions[key].append(ScipDefinition(symbol, repo_path, r, enclosing_range(occ),
                                                           is_callable(symbol), display(symbol)))
                    n_defs += 1
                elif roles & ROLE_FORWARD_DEFINITION:
                    n_forward += 1
                    continue
                occs.append((symbol, roles, r, ps))
            per_doc_occ.append((repo_path, occs))
        diag["occurrences"].update(total=n_total, without_symbol=n_no_symbol, invalid_range=n_invalid,
                                   out_of_bounds=n_oob, malformed_symbol=n_malformed)
        diag["definitions"].update(total=n_defs, forward_declarations=n_forward)
        diag["definitions"]["callable"] = sum(1 for ds in definitions.values() for d in ds if d.callable)
        diag["symbols"]["local"] = len(local_symbols)
        all_symbols = {d.symbol for ds in definitions.values() for d in ds}
        for _path, occs in per_doc_occ:
            all_symbols.update(o[0] for o in occs)
        diag["symbols"]["unique"] = len(all_symbols)
        diag["definitions"]["multiply_defined_symbols"] = sum(
            1 for k, ds in definitions.items() if "\x00" not in k and len({d.path for d in ds}) > 1)

        callable_defs_by_doc: Dict[str, List[ScipDefinition]] = defaultdict(list)
        for ds in definitions.values():
            for d in ds:
                if d.callable and d.enclosing is not None:
                    callable_defs_by_doc[d.path].append(d)

        # Packages that the repository itself defines symbols in (for classifying unlisted external symbols).
        local_packages = set()
        for key in definitions:
            if "\x00" not in key:
                ps_def = parsed(key)
                if ps_def is not None and not ps_def.is_local:
                    local_packages.add((ps_def.manager, ps_def.package, ps_def.version))

        def classify(symbol: str, ps: ParsedSymbol) -> Tuple[str, Optional[ScipDefinition]]:
            """What a global symbol's references resolve to (memoised: many references share a symbol)."""
            defs = definitions.get(symbol)
            if not defs:
                if symbol in external:
                    return "external", None
                if symbol in defined_in_unusable:
                    return "defined_in_unusable_documents", None
                if (ps.manager, ps.package, ps.version) not in local_packages:
                    return "external_package", None  # e.g. a standard library the producer did not list
                return "unresolved", None
            if len({d.path for d in defs}) > 1:
                return "ambiguous", None
            target = defs[0]
            return ("to_repository_callables" if target.callable else "to_repository_non_callables"), target

        # Pass 2: references.
        edges: Dict[Tuple[str, Optional[str], str, str], ScipReferenceEdge] = {}
        counts: Dict[str, int] = defaultdict(int)
        resolved: Dict[str, Tuple[str, Optional[ScipDefinition]]] = {}
        for repo_path, occs in per_doc_occ:
            doc_callables = callable_defs_by_doc.get(repo_path, [])
            for symbol, roles, r, ps in occs:
                if roles & ROLE_DEFINITION:
                    continue
                counts["total"] += 1
                if roles & ROLE_IMPORT:
                    counts["import"] += 1
                    continue
                if ps.is_local:
                    counts["local"] += 1
                    continue
                outcome = resolved.get(symbol)
                if outcome is None:
                    outcome = resolved[symbol] = classify(symbol, ps)
                category, target = outcome
                counts[category] += 1
                if category != "to_repository_callables":
                    continue
                if target.path == repo_path:
                    counts["same_file"] += 1
                    continue
                enclosing = _innermost(doc_callables, r)
                if enclosing is not None:
                    counts["with_enclosing_definition"] += 1
                key = (repo_path, enclosing.symbol if enclosing else None, target.path, target.symbol)
                if key not in edges:
                    edges[key] = ScipReferenceEdge(
                        source_path=repo_path,
                        source_symbol=enclosing.symbol if enclosing else None,
                        source_name=enclosing.name if enclosing else None,
                        target_path=target.path, target_symbol=target.symbol, target_name=target.name,
                        first_line=r.start_line + 1)
        diag["references"].update(counts)
        # A reference with no enclosing callable (for example on an import line) adds nothing when the same
        # file also references the same target from inside a function.
        attributed = {(e.source_path, e.target_symbol) for e in edges.values() if e.source_symbol is not None}
        kept = [e for e in edges.values() if e.source_symbol is not None or (e.source_path, e.target_symbol) not in attributed]
        diag["edges"]["unattributed_duplicates_dropped"] = len(edges) - len(kept)
        ordered = sorted(kept, key=lambda e: (e.source_path, e.source_symbol or "", e.target_path, e.target_symbol))
        diag["edges"]["reference_edges"] = len(ordered)
        diag["position_encoding"] = dict(sorted(diag["position_encoding"].items()))
        diag["ingest_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return ScipResolution(edges=ordered, relationships=relationships,
                              definitions={k: v for k, v in definitions.items()}, diagnostics=diag)

    @staticmethod
    def _collect_relationships(si, path, out: List[ScipRelationship], diag) -> None:
        for rel in si.relationships:
            if not rel.symbol:
                continue
            out.append(ScipRelationship(si.symbol, rel.symbol, rel.is_reference, rel.is_implementation,
                                        rel.is_type_definition, rel.is_definition, path))
            counts = diag["relationships"]
            counts["implementation"] += int(rel.is_implementation)
            counts["type_definition"] += int(rel.is_type_definition)
            counts["reference"] += int(rel.is_reference)
            counts["definition"] += int(rel.is_definition)


def _innermost(defs: Iterable[ScipDefinition], r: SourceRange) -> Optional[ScipDefinition]:
    best = None
    for d in defs:
        if d.enclosing is not None and d.enclosing.contains(r.start_line, r.start_character):
            if best is None or d.enclosing.span < best.enclosing.span:
                best = d
    return best


def _within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([os.path.normcase(path), os.path.normcase(root)]) == os.path.normcase(root)
    except ValueError:  # different drives
        return False


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _clip(s: str, limit: int = 300) -> str:
    return s if len(s) <= limit else s[:limit] + "..."


def _append(lst: List[str], item: str) -> None:
    if len(lst) < _MAX_LISTED_PATHS:
        lst.append(_clip(item))
