"""
SCIP Protobuf parsing with the vendored official bindings (optional `scip` extra): schema pin, valid,
empty and malformed indexes, unknown fields, missing metadata, size guard and range decoding.
"""

import hashlib
import re

import pytest

from scip_support import FIXTURES, build_index, doc, occ, require_protobuf, sym

pb = require_protobuf()

from reponeedle.core import _scip  # noqa: E402
from reponeedle.core import scip_ingestion as si  # noqa: E402
from reponeedle.core.scip_ingestion import ScipIndex, ScipIngestionError  # noqa: E402

PROTO = (si.__file__.rsplit("scip_ingestion.py", 1)[0] + "_scip/scip.proto")


def test_vendored_schema_is_the_pinned_official_file():
    data = open(PROTO, "rb").read()
    assert hashlib.sha256(data).hexdigest() == _scip.SCHEMA_SHA256
    assert b'option go_package = "github.com/scip-code/scip/bindings/go/scip/";' in data


def test_generated_bindings_match_the_vendored_schema():
    text = open(PROTO, encoding="utf-8").read()
    messages = set(re.findall(r"^message (\w+)", text, re.M))
    enums = set(re.findall(r"^enum (\w+)", text, re.M))
    fd = pb.DESCRIPTOR
    assert fd.name == "scip.proto" and fd.package == "scip"
    assert set(fd.message_types_by_name) == messages
    assert set(fd.enum_types_by_name) == enums
    occ_fields = {f.name for f in fd.message_types_by_name["Occurrence"].fields}
    assert {"range", "single_line_range", "multi_line_range", "enclosing_range",
            "single_line_enclosing_range", "multi_line_enclosing_range"} <= occ_fields
    assert "Odin" in pb.Language.keys()  # last schema change before v0.10.0


def test_role_constants_match_the_schema():
    assert (si.ROLE_DEFINITION, si.ROLE_IMPORT, si.ROLE_WRITE_ACCESS, si.ROLE_READ_ACCESS, si.ROLE_GENERATED,
            si.ROLE_TEST, si.ROLE_FORWARD_DEFINITION) == (pb.Definition, pb.Import, pb.WriteAccess, pb.ReadAccess,
                                                          pb.Generated, pb.Test, pb.ForwardDefinition)
    for kind in si.CALLABLE_KINDS:
        assert kind in pb.SymbolInformation.Kind.keys()


def _write(tmp_path, data, name="index.scip"):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


def test_valid_index_with_documents_and_external_symbols(tmp_path):
    data = build_index("file:///nowhere", [
        doc("a.ts", [occ("synthetic npm repo 1.0 a/f().", [0, 0, 1], roles=1)], [sym("synthetic npm repo 1.0 a/f().")]),
        doc("b.ts"),
    ], external=[sym("other npm lib 2.0 lib/g().")])
    index = ScipIndex.load(_write(tmp_path, data))
    assert (index.tool_name, index.tool_version, index.protocol_version) == ("synthetic-indexer", "1.0", 0)
    assert index.has_metadata and index.project_root == "file:///nowhere"
    assert len(index._msg.documents) == 2 and len(index._msg.external_symbols) == 1
    assert index.file_bytes == len(data) and index.parse_ms >= 0


def test_empty_file_is_an_empty_index_without_a_root(tmp_path):
    index = ScipIndex.load(_write(tmp_path, b""))
    assert not index.has_metadata and index.project_root == ""
    with pytest.raises(ScipIngestionError, match="unverifiable"):
        index.validate_root(str(tmp_path))
    assert index.validate_root(str(tmp_path), allow_mismatch=True) == "unverifiable"
    assert index.resolve([]).diagnostics["documents"]["in_index"] == 0


@pytest.mark.parametrize("payload", [b"\xff\xff\xff\xff", b"\x0a\x05abc", b"not a protobuf at all \x00\x01"])
def test_malformed_files_are_rejected_with_a_clear_error(tmp_path, payload):
    with pytest.raises(ScipIngestionError, match="not a valid SCIP index|does not look like a SCIP index"):
        ScipIndex.load(_write(tmp_path, payload))


def test_protobuf_with_only_unknown_fields_is_not_a_scip_index(tmp_path):
    with pytest.raises(ScipIngestionError, match="does not look like a SCIP index"):
        ScipIndex.load(_write(tmp_path, b"\xf8\x07\x2a"))  # field 127, varint 42


def test_unknown_fields_are_tolerated(tmp_path):
    data = build_index("file:///r", [doc("a.ts")]) + b"\xf8\x07\x2a"
    index = ScipIndex.load(_write(tmp_path, data))
    assert len(index._msg.documents) == 1


def test_missing_metadata_with_documents(tmp_path):
    index = ScipIndex.load(_write(tmp_path, build_index(None, [doc("a.ts")], with_metadata=False)))
    assert not index.has_metadata and index.tool_name == ""
    with pytest.raises(ScipIngestionError):
        index.validate_root(str(tmp_path))


def test_unknown_protocol_version_is_recorded(tmp_path):
    message = pb.Index.FromString(build_index("file:///r", []))
    message.metadata.version = 7  # a future value: enums are open in proto3
    index = ScipIndex.load(_write(tmp_path, message.SerializeToString()))
    assert index.protocol_version == 7


def test_size_guard_rejects_before_reading(tmp_path, monkeypatch):
    path = _write(tmp_path, build_index("file:///r", [doc("a.ts")]))
    opened = []
    real_open = open
    monkeypatch.setattr("builtins.open", lambda *a, **k: opened.append(a[0]) or real_open(*a, **k))
    with pytest.raises(ScipIngestionError, match="above the limit"):
        ScipIndex.load(path, max_bytes=5)
    assert path not in opened


@pytest.mark.parametrize("bad", [0, -1, 1.5, True])
def test_size_guard_must_be_positive_integer(tmp_path, bad):
    with pytest.raises(ScipIngestionError, match="positive integer"):
        ScipIndex.load(_write(tmp_path, b""), max_bytes=bad)


def test_missing_file_and_directory(tmp_path):
    with pytest.raises(ScipIngestionError, match="Cannot read"):
        ScipIndex.load(str(tmp_path / "absent.scip"))
    with pytest.raises(ScipIngestionError, match="not a regular file"):
        ScipIndex.load(str(tmp_path))


# --- ranges ----------------------------------------------------------------------------------------

def _occ(**kwargs):
    return pb.Occurrence(**kwargs)


def test_typed_single_and_multi_line_ranges():
    assert si.occurrence_range(_occ(single_line_range=pb.SingleLineRange(line=3, start_character=1, end_character=4))) \
        == si.SourceRange(3, 1, 3, 4)
    assert si.occurrence_range(_occ(multi_line_range=pb.MultiLineRange(start_line=1, start_character=2, end_line=5,
                                                                       end_character=0))) == si.SourceRange(1, 2, 5, 0)


def test_legacy_three_and_four_element_ranges():
    assert si.occurrence_range(_occ(range=[2, 4, 9])) == si.SourceRange(2, 4, 2, 9)
    assert si.occurrence_range(_occ(range=[2, 4, 6, 1])) == si.SourceRange(2, 4, 6, 1)


def test_typed_range_takes_precedence_over_legacy():
    o = _occ(range=[9, 9, 9], single_line_range=pb.SingleLineRange(line=1, start_character=0, end_character=2))
    assert si.occurrence_range(o) == si.SourceRange(1, 0, 1, 2)


@pytest.mark.parametrize("legacy", [[], [1], [1, 2], [1, 2, 3, 4, 5], [-1, 0, 1], [3, 5, 2], [4, 0, 2, 9]])
def test_invalid_ranges(legacy):
    assert si.occurrence_range(_occ(range=legacy)) is None


def test_empty_range_is_allowed():
    assert si.occurrence_range(_occ(range=[1, 3, 3])) == si.SourceRange(1, 3, 1, 3)


def test_enclosing_ranges_typed_and_legacy():
    assert si.enclosing_range(_occ()) is None
    assert si.enclosing_range(_occ(enclosing_range=[1, 0, 4, 1])) == si.SourceRange(1, 0, 4, 1)
    o = _occ(enclosing_range=[0, 0, 1], multi_line_enclosing_range=pb.MultiLineRange(
        start_line=2, start_character=0, end_line=7, end_character=1))
    assert si.enclosing_range(o) == si.SourceRange(2, 0, 7, 1)


def test_real_index_parses(tmp_path):
    index = ScipIndex.load(str(FIXTURES / "real" / "typescript" / "index.scip"))
    assert (index.tool_name, index.tool_version) == ("scip-typescript", "0.6.2")
    assert index.project_root == "file:///F:/scipfix/ts-shop"
    assert len(index._msg.documents) == 7
