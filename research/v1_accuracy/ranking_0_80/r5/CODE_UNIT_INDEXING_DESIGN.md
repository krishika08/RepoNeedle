# RepoNeedle — Phase R5: Code-Unit Indexing Architecture

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R5 — Function-Level, Change-Aware Code Retrieval  
**Date**: November 2, 2026  
**Status**: Architecture & Design Specification  

---

## 1. System Motivation & Architectural Foundations

Prior retrieval architectures in RepoNeedle (M1 through R4) operated at **file-level granularity**. While file-level retrieval successfully retrieves coarse candidates, it suffers from two major information retrieval pathologies:
1. **Vocabulary Dilution**: A 3,000-line file containing 40 utility functions averages out query-relevant terms. A query seeking a specific argument parser function will produce low lexical density against the entire file.
2. **Lack of Actionable Source Localization**: AI coding agents require precise function signatures, method bodies, and line spans rather than entire files. Whole-file context packing wastes token budgets on irrelevant functions.

Phase R5 introduces **hierarchical code-unit indexing**: parsing code into structured, typed semantic units while preserving file-to-unit lineages.

---

## 2. Multi-Tier Code-Unit Schema

Each indexed entity in the repository is represented as a structured `CodeUnit`:

```python
class CodeUnit:
    unit_id: str             # Globally unique key (e.g. "src/parser.py::ArgumentParser.parse_args")
    file_path: str           # Source file path
    unit_type: CodeUnitType  # MODULE, CLASS, INTERFACE, FUNCTION, METHOD, CODE_BLOCK, SOURCE_SPAN
    symbol_name: str         # Simple identifier (e.g. "parse_args")
    qualified_name: str      # Scoped identifier (e.g. "ArgumentParser.parse_args")
    signature: str           # Canonical definition signature (e.g. "def parse_args(self, args: List[str]) -> Namespace")
    parent_name: Optional[str] # Enclosing class or module
    start_line: int          # 1-indexed start line in source file
    end_line: int            # 1-indexed end line in source file
    content: str             # Source code snippet (bounded to avoid token overflow)
    docstring: str           # Extracted docstring / comments
    tokens: List[str]        # Extracted identifier tokens
    subwords: List[str]      # Decomposed camelCase and snake_case subwords
    calls: List[str]         # Callees invoked inside this unit
    imports: List[str]       # Module imports active in scope
    language: str            # Programming language ("python", "rust", "javascript", "generic")
```

---

## 3. Polyglot Parsing Strategy

### 3.1 Python AST Parser (`PythonASTVisitor`)
- Leverages Python's standard `ast` module.
- Visits `ast.ClassDef`, `ast.FunctionDef`, `ast.AsyncFunctionDef`, `ast.Import`, `ast.ImportFrom`.
- Extracts:
  - Exact 1-indexed `lineno` to `end_lineno` line ranges.
  - Full docstrings via `ast.get_docstring(node)`.
  - Class inheritance hierarchies (`node.bases`).
  - Function invocation call-sites (`ast.Call`) inside each function body.
  - Distinguishes top-level functions (`unit_type = FUNCTION`) from class methods (`unit_type = METHOD`, with `parent_name = class_name`).

### 3.2 Rust and JavaScript / TypeScript Parsers
- High-throughput regex parsers that identify:
  - Rust: `pub fn`, `fn`, `struct`, `enum`, `trait`, `impl`.
  - JavaScript / TypeScript: `function`, `class`, arrow function expressions (`const x = () =>`), `interface`.
- Extracts signatures and calculates source line offsets.

### 3.3 Lexical Chunking Fallback
- For unsupported file formats (C, C++, Go, Shell, Markdown, YAML) or files with syntax errors that fail AST parsing:
  - Applies a sliding-window lexical block chunker (default: 40 lines with 10-line overlap).
  - Assigns `unit_type = SOURCE_SPAN` with qualified names like `config.yaml:L31-L70`.
- **Zero-Failure Guarantee**: Every file in the repository produces at least one code unit (the module unit) plus chunked spans.

---

## 4. Incremental Re-Indexing & Mutation Handling

Real-world development workflows involve frequent edits to a subset of files:
- `add_or_update_file(file_path, content)`:
  1. Purges all previous code units registered under `file_path`.
  2. Cleans inverted index mappings (`symbol_to_units`).
  3. Re-parses and inserts updated code units.
  4. Cost is $O(L)$ where $L$ is lines of code in the modified file, completing in $< 5\text{ ms}$ on standard CPUs.
- `remove_file(file_path)`:
  - Purges file references and removes dangling symbol mappings.

---

## 5. Memory & Storage Complexity

- For a repository of $N$ files containing an average of 15 code units per file:
  - Total code units: $15N$.
  - Inverted symbol table: $O(15N)$ keys.
  - Memory footprint: $\approx 1.2\text{ KB}$ per code unit in Python heap memory.
  - For a typical 500-file repository ($\approx 7,500$ code units): RAM consumption is under **12 MB**.

