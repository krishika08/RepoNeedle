# RepoNeedle V1.0.0 — Exact Symbol Index Design Specification

## 1. Symbol Extraction & Normalization

`ExactSymbolIndex` operates as a deterministic, bitwise inverted index for source code definitions.

### Extracted Elements
1. **AST Function and Method Definitions**:
   - `def foo(a, b)` -> function `foo`, signature parameters `['a', 'b']`.
   - `class Bar: def baz(self)` -> method `baz`, qualified name `Bar.baz`.
2. **Chunk Symbols**:
   - High-confidence symbol annotations from corpus chunk metadata.
3. **File Paths & Suffixes**:
   - Full relative paths (e.g., `src/transformers/conversion_mapping.py`).
   - Basenames (e.g., `conversion_mapping.py`).
   - Stems (e.g., `conversion_mapping`).
4. **Polyglot Declarations**:
   - Rust: `fn foo(...)`, `struct Foo`, `trait Foo`, `enum Foo`.
   - Go: `func (r *Receiver) Foo(...)`, `func Foo(...)`.
   - TypeScript/JavaScript: `function foo(...)`, `class Foo`, `interface Foo`.

## 2. Inverted Index Data Structures

```python
self.exact_symbol_to_docs: Dict[str, Set[int]]
self.exact_symbol_lower_to_docs: Dict[str, Set[int]]
self.qualified_name_to_docs: Dict[str, Set[int]]
self.token_to_docs: Dict[str, Set[int]]
```

## 3. Query Retrieval & Scoring

When matching against query text:
- **Backticked Symbols** (`foo`): Weight = 5.0 (exact case) / 4.0 (case-insensitive).
- **Direct File Paths**: Weight = 10.0 (exact match) / 6.0 (basename match).
- **Qualified Names** (`module.Class.method`): Weight = 4.5 / 3.5.
- **Rarity-Weighted Symbol Names**:

$$W(sym) = \frac{3.0}{\log_2(\text{DF}(sym) + 1.0)}$$

This ensures that rare, highly diagnostic symbols (e.g., `SecureCookieSessionInterface`) yield massive candidate boosts, while ubiquitous symbols (e.g., `get`, `init`) do not flood the candidate pool.
