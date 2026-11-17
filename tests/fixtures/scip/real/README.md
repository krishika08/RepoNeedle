# Real SCIP producer fixture

`typescript/index.scip` was produced by a real, unmodified SCIP indexer. The test suite does not run the indexer, so CI needs no Node.js or network access.

| Item | Value |
| :--- | :--- |
| Producer | `@sourcegraph/scip-typescript` **0.6.2** (Apache-2.0), with `typescript` 5.6.3 |
| Command | `scip-typescript index --output index.scip`, run in the project directory |
| Host | Windows 11, Node.js 22.23.2, 2026-11-17 |
| `Metadata.project_root` | `file:///F:/scipfix/ts-shop`, a neutral temporary directory deleted after generation. The tests use `allow_project_root_mismatch=True` because the checkout path differs. |
| Sources | Exactly the files in `typescript/`: RepoNeedle's synthetic Tree-sitter TypeScript fixture plus `src/models/shapes.ts` and `tests/shapes.test.ts`, which add an interface with two implementations and a UTF-16 case. All are written for this project and MIT-licensed like RepoNeedle. |
| SHA-256 | `e3ae31a4000f8c8863056ecca5b37bcc41a1477838edc3e34ecd2ac680649cc0` |

Observed producer behaviour that RepoNeedle relies on or handles:
- **Backslash paths.** `Document.relative_path` uses `\` on Windows (`src\util\format.ts`), which the SCIP specification forbids. RepoNeedle normalises `\` only when the index's `project_root` is a Windows path, and counts it in `backslash_paths_normalized`.
- **Legacy ranges.** All ranges use the deprecated packed `range` field; no typed ranges are set. Positions are `UTF16CodeUnitOffsetFromLineStart`.
- **Symbol kinds.** `SymbolInformation.kind` is set (Function, Method, Constructor, Constant, Property, …). `display_name` is empty, so names come from the symbol descriptors. Arrow functions assigned to `const` have kind `Constant`, so they are not treated as callables.
- **External symbols.** Standard-library symbols (`npm typescript 6.0.3 lib/...`) are referenced but not listed in `external_symbols`. RepoNeedle classifies them as `external_package`.
- **Relationships.** `is_implementation` relationships are emitted for `Square`/`Circle` → `Shape` and their `area()` methods.

Regenerate by copying `typescript/` (without `index.scip`) to a directory without personal information in its path, then running the command above there.

`scip-python` 0.6.8 was also attempted. It crashes at startup on Windows (`new RegExp(path.sep)` with `\`), so no Python producer fixture exists.
