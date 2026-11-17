"""
Helpers for the SCIP tests (not a test module): build real SCIP indexes with the vendored, official
generated bindings and write them to disk next to a matching repository.
"""

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "scip"


def require_protobuf():
    """Skips (visibly) unless the optional 'scip' extra is installed; returns the scip_pb2 module."""
    pytest.importorskip("google.protobuf", reason="optional 'scip' extra (protobuf) not installed")
    from reponeedle.core._scip import scip_pb2
    return scip_pb2


def pkg(path: str, name: str, suffix: str = "().") -> str:
    """A global SCIP symbol in the synthetic package `synthetic npm repo 1.0`."""
    return f"synthetic npm repo 1.0 {path}/{name}{suffix}"


def occ(symbol: str, rng: Sequence[int], roles: int = 0, enclosing: Optional[Sequence[int]] = None,
        legacy: bool = False) -> Dict:
    return {"symbol": symbol, "range": list(rng), "roles": roles,
            "enclosing": list(enclosing) if enclosing else None, "legacy": legacy}


def sym(symbol: str, kind: Optional[str] = "Function", relationships: Iterable[Dict] = (),
        display_name: str = "") -> Dict:
    return {"symbol": symbol, "kind": kind, "relationships": list(relationships), "display_name": display_name}


def rel(symbol: str, **flags) -> Dict:
    return {"symbol": symbol, **flags}


def doc(path: str, occurrences: List[Dict] = (), symbols: List[Dict] = (), text: Optional[str] = None,
        encoding: str = "UTF8CodeUnitOffsetFromLineStart", language: str = "typescript") -> Dict:
    return {"path": path, "occurrences": list(occurrences), "symbols": list(symbols), "text": text,
            "encoding": encoding, "language": language}


def _set_range(pb, target_occ, field_single: str, field_multi: str, legacy_field: str, rng, legacy: bool):
    if legacy:
        getattr(target_occ, legacy_field).extend(rng)
    elif len(rng) == 3:
        r = getattr(target_occ, field_single)
        r.line, r.start_character, r.end_character = rng
    else:
        r = getattr(target_occ, field_multi)
        r.start_line, r.start_character, r.end_line, r.end_character = rng


def build_index(project_root: Optional[str], documents: List[Dict], external: Iterable[Dict] = (),
                tool: Sequence[str] = ("synthetic-indexer", "1.0"), with_metadata: bool = True) -> bytes:
    pb = require_protobuf()
    index = pb.Index()
    if with_metadata:
        index.metadata.version = pb.UnspecifiedProtocolVersion
        index.metadata.tool_info.name, index.metadata.tool_info.version = tool
        index.metadata.project_root = project_root or ""
        index.metadata.text_document_encoding = pb.UTF8
    for d in documents:
        out = index.documents.add(relative_path=d["path"], language=d["language"],
                                  position_encoding=pb.PositionEncoding.Value(d["encoding"]))
        if d["text"] is not None:
            out.text = d["text"]
        for o in d["occurrences"]:
            po = out.occurrences.add(symbol=o["symbol"], symbol_roles=o["roles"])
            _set_range(pb, po, "single_line_range", "multi_line_range", "range", o["range"], o["legacy"])
            if o["enclosing"]:
                _set_range(pb, po, "single_line_enclosing_range", "multi_line_enclosing_range", "enclosing_range",
                           o["enclosing"], o["legacy"])
        for s in d["symbols"]:
            _add_symbol(pb, out.symbols.add(), s)
    for s in external:
        _add_symbol(pb, index.external_symbols.add(), s)
    return index.SerializeToString()


def _add_symbol(pb, target, s: Dict) -> None:
    target.symbol = s["symbol"]
    if s["kind"]:
        target.kind = pb.SymbolInformation.Kind.Value(s["kind"])
    if s["display_name"]:
        target.display_name = s["display_name"]
    for r in s["relationships"]:
        target.relationships.add(**r)


def write_repo(root: Path, files: Dict[str, str]) -> Path:
    for rel_path, content in files.items():
        p = root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="\n")
    return root


def write_index(root: Path, data: bytes, name: str = "index.scip") -> str:
    path = root / name
    path.write_bytes(data)
    return str(path)
