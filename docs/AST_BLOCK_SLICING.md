# AST Block Slicing (opt-in)

**Status**: opt-in, on `main` once merged, **not in a published release yet**. Default packing is unchanged.
**What it is**: an alternative focus-span extractor for CUD-Pack. When a query term matches code inside a large file, it renders the smallest **complete** syntactic block (function, method, nested function, or top-level declaration) that contains the match. It keeps the file's relevant imports and package declaration, and the headers of enclosing classes and functions. Every elided region is marked with its line range.
**Validation report**: [reports/v2_completion/ast_block_slicing/REPORT.md](../reports/v2_completion/ast_block_slicing/REPORT.md)

## 1. Enabling it

```python
from reponeedle import RepoNeedleEngine
from reponeedle.models import BudgetConfig

engine = RepoNeedleEngine.from_directory(
    "path/to/repo",
    budget_config=BudgetConfig(focus_span_strategy="ast_blocks"),   # default: "legacy"
)
```

The same `BudgetConfig` works with `CUDPackOptimizer` directly. `"legacy"` (the default) is byte-for-byte the previous focus-span behaviour.

| Language | Parser | Needs |
| :--- | :--- | :--- |
| Python (`.py`) | standard-library `ast` | nothing |
| TypeScript (`.ts`, `.mts`, `.cts`), TSX (`.tsx`) | Tree-sitter | `pip install -e ".[treesitter]"` |
| Go, Rust, Java | Tree-sitter | `treesitter` extra |
| C++ (`.cpp`, `.cc`, `.cxx`, `.hpp`, `.hh`, `.hxx`, `.h`) | Tree-sitter | `treesitter` extra |
| JavaScript, C, everything else | none | Legacy focus span (unchanged) |

## 2. Internal interface

Everything lives in `reponeedle/core/block_slicing.py`. Tree-sitter parsing goes through the existing lazy loader and parser cache in `reponeedle/core/tree_sitter_extraction.py`, via a new `parse_source()` helper that `extract()` now also uses. There is no second grammar loader.

```python
analyze_structure(content: str, path: str) -> StructureResult
    # StructureResult.structure: Optional[FileStructure]; StructureResult.fallback_reason: Optional[str]

@dataclass(frozen=True)
class FileStructure:
    language: str                 # "python", "typescript", "tsx", "go", "rust", "java", "cpp"
    parser: str                   # "python-ast" | "tree-sitter"
    line_count: int
    blocks: Tuple[CodeBlock, ...]          # selectable units, in source order
    scopes: Tuple[ScopeHeader, ...]        # classes, impls, namespaces, enclosing callables
    imports: Tuple[ImportUnit, ...]        # imports / includes / `use`
    preamble: Tuple[Tuple[int, int], ...]  # package declarations: always kept

@dataclass(frozen=True)
class CodeBlock:
    kind: str                     # "callable" | "declaration"
    name: Optional[str]
    start_line: int               # 1-based, inclusive; includes decorators/attributes/annotations
    end_line: int                 #   and directly attached doc comments
    scope_chain: Tuple[int, ...]  # indices into FileStructure.scopes, outermost first

@dataclass(frozen=True)
class ScopeHeader:
    kind: str; name: Optional[str]
    start_line: int; header_end_line: int    # e.g. `export class Cart extends Base {`
    close_line: Optional[int]                # e.g. the closing `}` line (brace languages)

slice_blocks(content, path, query_terms, *, max_block_lines=120,
             max_total_lines=160, max_blocks=5) -> BlockSlice
    # BlockSlice.text (or None on fallback), .selected (block spans), .fallback_reason,
    # .language, .parser, .blocks_considered
```

`CodeSpanExtractor.extract_block_span(content, path, query_terms)` wraps `slice_blocks`. It returns `(text, tokens)` like `extract_focus_span`, falls back to `extract_focus_span` when slicing does not apply, and caches both the parsed structure (per path and content) and the result (per path, content and query terms).

## 3. Behaviour

**Line model.**
- Lines are split on `\r\n`, `\r` and `\n`, matching Python's `ast` line numbering.
- Tree-sitter positions are mapped from **byte offsets** to lines, so multibyte characters and CRLF files keep exact boundaries.
- Output lines are exact source lines, joined with `\n` as in the legacy extractor.

**Blocks.**
- **Python:** `def` and `async def` (methods and nested functions included). A block starts at its first decorator.
- **Tree-sitter:** functions, methods, constructors and named function values (`const f = () => {}`). The block is widened to its enclosing `export`, `template <…>` or single-declarator declaration. Directly preceding decorators, attributes and comments with no blank line between are included.
- **Anonymous functions** (TypeScript callbacks such as `it("…", () => {…})`, Go `func` literals) are blocks only when they are not inside a named function. Callbacks passed inside a function stay part of that function.
- **Nested functions:** named functions and classes declared inside a function body are blocks when they span more than one line.
- **Declarations:** non-callable statements directly in a module or class body (constants, fields, structs, interfaces, enums) are blocks too.
- **Scopes, not blocks:** classes, interfaces with bodies, `impl`, `trait`, `mod`, namespaces and `extern "C"`. A match inside a class never returns the whole class.

**Selection.**
1. Lines matching a query term (the same case-insensitive substring test as the legacy extractor) are attributed to the **innermost** block containing them.
2. Blocks are ranked by distinct query terms matched, then whether the block's name contains a term, then the number of matching lines, then source order. The ordering is fully deterministic.
3. Blocks are taken greedily up to `max_blocks` (5) and `max_total_lines` (160).
4. A block longer than `max_block_lines` (120) is never cut. Only its header (signature) is shown, with a `[… body elided: block too large …]` marker. If nothing selectable remains, the legacy extractor is used.

**Rendering.** The output contains:
- package declarations;
- imports whose bound names occur in the selected blocks (C/C++ `#include`s and wildcard imports are always kept, up to 25 lines);
- the header and closing line of every enclosing scope;
- the selected blocks.

All of it is in source order, and each gap is marked `// ... [lines a-b elided] ...` (`#` for Python), indented like the following line.

**Fallbacks** (the legacy focus span is used, and the reason is recorded):
- unsupported language;
- the `treesitter` extra is not installed or a grammar fails to load;
- a Python `SyntaxError`, or a Tree-sitter tree containing errors (recoverable errors included);
- no query term matches inside any block;
- every matching block is oversized.

Files of 45 lines or fewer are returned whole, exactly as in the legacy extractor. Empty files give `("", 0)`.

## 4. CUD-Pack integration

`CUDPackOptimizer.pack_context` chooses the focus-span extractor from `BudgetConfig.focus_span_strategy`. Nothing else in packing changes:
- the tier rules;
- exact token counting with packaging overhead;
- the `sum(token_count) <= budget` assertion.

A larger block span is simply a larger `FOCUS_SPAN` candidate, so it is chosen only when it fits, otherwise the existing skeleton or next tier is used. The `ScoredFile.explanation` of an AST block span names the language and the number of blocks.

## 5. Limitations

**Scope.**
- Block slicing changes **what is shown** from a file, not which files are retrieved. No retrieval-quality evaluation has been run, and none is claimed.
- Relevance is lexical (query-term substrings), like the legacy extractor. There is no semantic matching inside a file.

**Token cost.** Complete blocks cost more tokens than ±3-line windows. On frozen candidate lists from the CUD-Pack suites, compact packs (4,096 tokens) held about 10 files instead of about 13, and one curated gold file was no longer packed. This is the main reason the strategy is opt-in.

**Fallbacks.**
- Whole-file fallback on any syntax error (Tree-sitter error or missing nodes, or a Python `SyntaxError`) is deliberately conservative: one unrelated error, or a truncated file, disables slicing for that file.
- In the Agent Retrieval Bench corpus most long files are stored truncated, so most gold files there used the fallback.

**Unsupported constructs.**
- One-line nested functions inside a function body are not separate blocks; they belong to the enclosing function.
- Anonymous callbacks are blocks only outside named functions.
- JavaScript and C are not handled; they use the legacy extractor.

**Performance.**
- Python slicing is faster than the legacy extractor on large files.
- Tree-sitter languages cost roughly 6–15 ms per 1,000 lines on the first (cold) call, against about 1 ms per 1,000 lines for the legacy regex scan.
- Results and parsed structures are cached per extractor; a new query on an already parsed file costs about 0.5–2 ms per 1,000 lines.
