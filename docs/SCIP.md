# SCIP Index Ingestion (optional)

**Status**: opt-in, on `main`, **not in a published release yet** (RepoNeedle 1.2.0 on PyPI does not include it).
**What it is**: a *consumer* of SCIP indexes (`index.scip`) produced by external indexers. RepoNeedle never runs an indexer, compiler or build command, and does not need the `scip` CLI.
**Schema**: the official `scip.proto` from [scip-code/scip](https://github.com/scip-code/scip), tag **v0.10.0** (commit `1c2b6db7`), vendored with generated Python bindings in `reponeedle/core/_scip/`.
**Validation report**: [reports/v2_completion/scip_ingestion/REPORT.md](../reports/v2_completion/scip_ingestion/REPORT.md)

## 1. Three different things

| | What RepoNeedle knows | Source |
| :--- | :--- | :--- |
| Regex / Python `ast` extraction (default) | Names of functions and calls; heuristic resolution by name | RepoNeedle |
| Tree-sitter extraction (optional, [TREE_SITTER.md](TREE_SITTER.md)) | Exact syntax: definitions, call sites, import bindings | RepoNeedle, syntax only |
| **SCIP ingestion** (this document) | Definitions and references **already resolved by an external indexer**, keyed by fully qualified symbol identifiers | The external indexer (compiler- or type-checker-backed for most producers) |

SCIP ingestion adds evidence to the function-level graph. It does not by itself improve retrieval, and no retrieval-quality measurement has been made with it.

## 2. Installation and use

```bash
git clone https://github.com/krishika08/RepoNeedle.git && cd RepoNeedle
pip install -e ".[scip]"                 # protobuf>=5.29.0,<8 (prebuilt wheels; no compiler)
pip install -e ".[scip,treesitter]"      # optional: combine with Tree-sitter extraction
```

Generate an index with your language's indexer. For example `scip-typescript index` produces `index.scip` in the project root.

```python
from reponeedle import RepoNeedleEngine, ScipConfig

engine = RepoNeedleEngine.from_directory(
    "path/to/repo",
    scip_config=ScipConfig(index_path="path/to/repo/index.scip"),
)
result = engine.retrieve("fix the discount rounding bug", ranker="arm101")
print(engine.scip_diagnostics)
```

`ScipConfig` fields:

| Field | Default | Meaning |
| :--- | :--- | :--- |
| `index_path` | required | The `.scip` file to read. It may live outside the repository; it is the only file SCIP ingestion opens. |
| `repo_root` | `None` | The repository the index must describe. `from_directory()` sets it to `repo_dir` and rejects a different value. It is **required** for `from_documents()` and `RepoNeedleEngine(docs=...)`. |
| `allow_project_root_mismatch` | `False` | Accept an index whose `Metadata.project_root` differs from `repo_root` (for example one built in CI from an identical checkout). Document paths are still validated against `repo_root`. |
| `max_index_bytes` | 256 MiB | Larger files are rejected **before** they are read. |
| `on_error` | `"raise"` | `"raise"` raises `ScipIngestionError` with an actionable message. `"skip"` builds the engine without SCIP, records the reason in `scip_diagnostics` and logs a warning. |

**Opt-in only.** Without `scip_config`, nothing changes: `engine.scip_diagnostics` is `None`, Protobuf is never imported, and the graph is identical to `main`.

`from reponeedle.core.scip_ingestion import protobuf_status` reports whether the bindings can load.

## 3. Repository validation

Nothing in an index is trusted because it decoded.

| Check | Behaviour |
| :--- | :--- |
| **`Metadata.project_root` vs `repo_root`** | It is decoded from URI form: `file:///abs`, `file://localhost/abs`, `file:///C:/x`, `file:///c%3A/x`, percent-encoded characters, UNC `file://server/share` (Windows only), or a plain absolute path. It is then compared after `realpath`, case-insensitively on Windows. A mismatch, or a missing or undecodable root, is refused unless `allow_project_root_mismatch=True`. |
| **Canonical paths** | The path must be relative and non-empty, use `/` separators, and have no empty, `.` or `..` component and no NUL. Otherwise the document is rejected with a reason. |
| **Backslashes** | They are accepted only when the index's `project_root` is a Windows path, where `\` cannot be part of a file name. This was observed in scip-typescript 0.6.2 on Windows and is counted as `backslash_paths_normalized`. |
| **Containment** | The path is resolved with `realpath`. Anything that resolves outside the repository (through a symlink or a junction in any component) is rejected. A document that is itself a symbolic link is rejected too, as the specification requires regular files. |
| **Repository index** | A document must correspond to a file RepoNeedle indexed. Otherwise it is listed as `missing` (no such file) or `not_indexed_by_reponeedle` (for example an ignored or non-source file). On Windows, a unique case-insensitive match is accepted and counted. |
| **Freshness** | If `Document.text` is present, it is compared with the indexed content (line endings normalised). A difference marks the document **stale**, and it is **skipped**. Without text, freshness is reported as **unverified**. |
| **Ranges** | Every occurrence range is bounds-checked against the current content, in the document's `PositionEncoding` (UTF-8 bytes, UTF-16 units or code points; the most permissive length when unspecified). Out-of-bounds occurrences are dropped and counted. |
| **No file reads** | Resolution never opens a source file. It compares against the contents RepoNeedle already indexed, and only `stat`/`realpath` touch the file system. |

> [!IMPORTANT]
> SCIP indexes rarely embed source text and never a commit SHA, so RepoNeedle usually **cannot prove that an index matches the current files**. Regenerate the index after source changes.

## 4. Resolution semantics

- **Identity.**
  - Symbols are identified **only by their exact SCIP symbol string**, never by display name. Overloads and same-named symbols in different files stay distinct.
  - `local N` symbols are scoped to their document and never produce cross-file edges.
  - Symbol strings are parsed with the grammar in `scip.proto` (escaped identifiers, double-space escapes, all descriptor suffixes). Malformed symbols are counted and ignored.
- **Roles are bit flags.**
  - `Definition` marks definitions.
  - `ForwardDefinition` (C/C++ declarations) occurrences are neither definitions nor references.
  - `Import` occurrences are counted but are never treated as calls.
- **What becomes an edge.**
  - A reference (no `Definition` bit), in a usable document, to a **callable** symbol defined in **exactly one** other usable document becomes a `scip_reference` edge.
  - *Callable* means a `SymbolInformation.kind` of Function, Method, Constructor, StaticMethod, AbstractMethod, PureVirtualMethod, TraitMethod, ProtocolMethod, TypeClassMethod, SingletonMethod, MethodSpecification or MethodAlias.
  - When the kind is unspecified or unknown to the pinned schema, a method descriptor `name().` counts as callable.
- **What never becomes an edge.**
  - References to classes, types, variables, constants, fields, namespaces and parameters.
  - References to external symbols: those listed in `external_symbols`, or in a package the repository does not define.
  - References to unresolved or ambiguous symbols (defined in more than one file), and to symbols defined only in rejected or stale documents.
  - Same-file references.
- **Caller attribution.**
  - The innermost callable definition whose enclosing range contains the reference becomes `source_func`. Enclosing ranges are optional in SCIP, so references can be unattributed (`source_func=None`).
  - An unattributed reference is dropped when the same file also references the same target from inside a function (for example the import line in TypeScript).
- **Edges.**
  - Type `scip_reference`, with a **fixed confidence of 0.9**.
  - Each edge carries `source_symbol`, `target_symbol` and `provenance` (`scip:<tool>@<version>`).
  - The confidence is deliberately not 1.0: producers differ, and a reference to a callable is not proof of a call (it can be a function value).
- **No duplicates.**
  - One edge per (source file, enclosing symbol, target file, target symbol).
  - If extraction (regex, `ast` or Tree-sitter) already produced an edge between the same files for the same function name, the SCIP edge is **not** added. It is counted as `already_present_from_extraction`.
- **Relationships.** `is_implementation`, `is_type_definition`, `is_reference` and `is_definition` relationships are kept in `engine.function_graph.scip_relationships`. They are **never** converted into call edges.
- **Ranking.**
  - The only ranking-side change is that the opt-in `arm101` ranker also propagates over `scip_reference` edges, which exist only when SCIP was ingested.
  - The default `legacy` ranker and all weights, routing, CUD-Pack packing and abstention are unchanged.
  - The MCP tools and the CLI have no SCIP option.

## 5. Diagnostics

`engine.scip_diagnostics` (also at `engine.function_graph.diagnostics["scip"]`) contains:
- `status` (`ingested` or `skipped` with `error`), `index_path`, `index_bytes`, `schema`;
- `producer` (name, version) and `protocol_version`;
- `project_root` (declared, decoded, repository, status `match` | `mismatch` | `unverifiable`);
- `documents`: in index, matched, case-insensitive matches, rejected (path → reason), missing, not indexed, duplicate, stale, backslash-normalised;
- `freshness`: verified identical, stale, unverified, and an overall status;
- `position_encoding` counts;
- `occurrences`: total, invalid range, out of bounds, without symbol, malformed symbol;
- `symbols`: unique, local, external;
- `definitions`: total, callable, forward declarations, symbols defined in several files;
- `references`: total, import, local, to repository callables or non-callables, same file, external, external package, unresolved, defined in unusable documents, ambiguous, with enclosing definition;
- `relationships`: implementation, type definition, reference, definition;
- `edges`: resolved, unattributed duplicates dropped, added to graph, already present from extraction, edge type, confidence, provenance;
- `parse_ms` and `ingest_ms`.

Diagnostics contain paths, counts and producer metadata, never source contents. Path lists are capped at 200 entries.

## 6. Limitations

- **Producers tested.** Only **scip-typescript 0.6.2** (on Windows) was validated with a real index. scip-python 0.6.8 crashes at startup on Windows. scip-java, scip-clang and rust-analyzer were **not tested**. Compatibility with other producers is expected from the schema but unverified.
- **References are not calls.** SCIP has no call role, so a `scip_reference` edge means "references a callable".
- **Producer classification is authoritative.** For example scip-typescript classifies `const f = () => …` as a `Constant`, so references to it produce no edge.
- **Freshness** is verifiable only when the producer embeds `Document.text`. Ranges are bounds-checked, but a changed file with in-bounds ranges is not detected.
- **Indexes are not merged.** One index per engine; there is no multi-index merging or cross-repository resolution.
- **No persistent cache.** The index is parsed when the engine is built, and resolution reruns on every `update_documents()`.
- **Performance.** On the development machine, parsing a 15 MB index took about 0.1 s. Resolution cost about 20–90 µs per occurrence and grew faster than linearly on this memory-constrained host; see the report. Very large indexes (millions of occurrences) will be slow, and `max_index_bytes` limits what is read.
- **Generated bindings.** They are checked in, generated by protoc 29.0 for `protobuf>=5.29.0,<8`. A future major Protobuf release needs new bindings.

## 7. Tests and CI

| File | Requires | Covers |
| :--- | :--- | :--- |
| `tests/test_scip_core.py` | nothing | Symbol grammar, URI and path validation, encodings, missing Protobuf, defaults, packaging |
| `tests/test_scip_parsing.py` | `scip` | Schema pin, valid, empty and malformed indexes, unknown fields, missing metadata, size guard, ranges |
| `tests/test_scip_security.py` | `scip` | Root matching, traversal, absolute and backslash paths, symlink and junction escapes, missing and unindexed files, freshness, no file reads |
| `tests/test_scip_graph.py` | `scip` | Resolution semantics, encodings, relationships, de-duplication, engine API, `arm101`, the real scip-typescript index |
| `tests/test_scip_tree_sitter.py` | `scip` + `treesitter` | Composition with Tree-sitter |

The test indexes are built with the vendored official bindings (`tests/scip_support.py`); the real index is checked in (`tests/fixtures/scip/real/`).

CI runs:
- the `scip-optional` job on Linux (Python 3.10, 3.11, 3.12, the protobuf 5.29.0 minimum, the pure-Python backend, and both extras), failing on any skip;
- the same job on Windows (Python 3.12);
- wheel installs with no extra, `[scip]`, and `[scip,treesitter]`;
- `test_scip_core.py` in the strict security job.
