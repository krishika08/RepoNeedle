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

`CodeSpanExtractor.extract_block_span(content, path, query_terms, cap_lines=None)` wraps `slice_blocks`. It returns `(text, tokens)` like `extract_focus_span`, and falls back to `extract_focus_span` when slicing does not apply.

**`cap_lines`** is a soft selection budget, passed as `slice_blocks(max_total_lines=cap_lines)`. The best block is always rendered whole, and more blocks are added only while the total stays within the budget. The argument has these properties:
- `None` keeps the defaults: 160 lines for slicing, and the legacy 65 for the fallback.
- An integer is also passed to the legacy fallback unchanged.
- Values that are not positive integers raise `ValueError`.

Both the parsed structure and the result are cached; see §4.

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
3. Blocks are taken greedily up to `max_blocks` (5).
4. `max_total_lines` (160, or `cap_lines` when given) is a **soft** budget. The highest-ranked block is always taken whole, even if it alone is longer; further blocks are added only while the total stays within the budget. No limit ever truncates a block.
5. A block longer than `max_block_lines` (120) is never selected. Only its header (signature) is shown, followed by an ordinary `[lines a-b elided]` marker. If nothing selectable remains, the legacy extractor is used.

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

### Caching and memory

Each `CodeSpanExtractor` keeps two deterministic LRU caches (`reponeedle/core/bounded_cache.py`). Neither cache retains source text.

| Cache | Key | Value | Entry limit | Estimated-byte budget |
| :--- | :--- | :--- | ---: | ---: |
| Parsed structure | `(path, SHA-256(content))` | the `StructureResult` (blocks, scopes, imports, line owner map) | 512 | 32 MiB |
| Result | `(path, SHA-256(content), query terms, cap_lines)` | the rendered span, its token count and the `BlockSlice` | 4,096 | 16 MiB |

**Keys.**
- Keys hold a 32-byte digest, never the content, so a changed file can never hit an old entry and the cache never keeps old file versions alive.
- Paths, contents, query-term sets and `cap_lines` values are all kept apart.

**Eviction.**
- After each insert, least-recently-used entries are evicted until both the entry limit and the byte budget hold.
- Evicted values are dropped, so the cache no longer references them.

**Oversized entries.** An entry estimated at more than one eighth of its cache's budget (`BLOCK_CACHE_MAX_ENTRY_FRACTION`) is computed and returned but not cached, so one huge file cannot flush the cache.

**Accounting.** Each entry's size is an **estimate**: `sys.getsizeof` summed over the objects the entry keeps alive, plus a fixed per-entry allowance for the LRU bookkeeping. The objects counted are:
- the slotted block, scope and import records;
- their tuples, frozensets and name strings;
- the owner map;
- the rendered text;
- the key's path, digest and terms.

Interned literals, small integers and allocator overhead are not counted. This estimates retained Python objects; it is **not** process memory (RSS). Measured against tracemalloc, estimates were within 0.9–1.4× of the bytes actually retained (see the report).

**Configuration.**
- Budgets: `CodeSpanExtractor(structure_cache_bytes=..., span_cache_bytes=...)`, or the class attributes `BLOCK_STRUCTURE_CACHE_BYTES`, `BLOCK_SPAN_CACHE_BYTES`, `BLOCK_STRUCTURE_CACHE_SIZE`, `BLOCK_SPAN_CACHE_SIZE` and `BLOCK_CACHE_MAX_ENTRY_FRACTION`.
- Statistics: `CodeSpanExtractor.block_cache_stats()` reports entries, estimated bytes, limits, hits, misses, evictions and rejected entries.

The legacy extractor's own caches (`_span_cache`, `_skel_cache`) and the tokenizer cache are unchanged.

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
- Results and parsed structures are cached per extractor (§4). A new query on an already parsed file costs about 0.5–2 ms per 1,000 lines. A repeated query costs one SHA-256 digest of the content, about 0.25–0.5 ms for a 600 KB file.
