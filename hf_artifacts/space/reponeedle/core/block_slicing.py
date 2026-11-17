"""
AST block slicing: syntax-aware focus spans for CUD-Pack (opt-in, ``BudgetConfig.focus_span_strategy``).

Given a file and the query terms, this module finds the smallest *complete* syntactic block that contains
each query match (a function, method, nested function, or a declaration directly inside a module or class
body) and renders the selected blocks with the file's relevant imports, its package declaration and the
headers of every enclosing class/function, in source order, with explicit markers for elided lines.

* Python uses the standard-library ``ast`` module.
* TypeScript/TSX, Go, Rust, Java and C++ use Tree-sitter through the existing lazy loader and parser cache in
  :mod:`reponeedle.core.tree_sitter_extraction` (optional ``treesitter`` extra).
* Anything else, a missing parser, any syntax error, or a query that matches no block returns no slice
  (``BlockSlice.text is None``) with a ``fallback_reason``; the caller then uses the legacy extractor.

All positions are whole source lines. Lines are split on ``\\r\\n``, ``\\r`` and ``\\n`` (the same rule as
Python's ``ast``); Tree-sitter positions are mapped from byte offsets, so multibyte text and CRLF files keep
exact boundaries. Output lines are exact source lines; blocks are never cut.
"""

from __future__ import annotations

import ast
import bisect
import re
import sys
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

from reponeedle.core import tree_sitter_extraction as tse

DEFAULT_MAX_BLOCK_LINES = 120
DEFAULT_MAX_TOTAL_LINES = 160
DEFAULT_MAX_BLOCKS = 5
MAX_IMPORT_LINES = 25
MAX_ATTACHED_LINES = 20

PYTHON_PARSER = "python-ast"
TREE_SITTER_PARSER = "tree-sitter"

_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_LINE_BREAK_BYTES = re.compile(rb"\r\n|\r|\n")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def split_lines(content: str) -> List[str]:
    """Source lines without terminators; a trailing line break does not create an extra empty line."""
    lines = _LINE_BREAK.split(content)
    if len(lines) > 1 and lines[-1] == "":
        lines.pop()
    return lines


def detect_language(path: str) -> Optional[str]:
    clean = path.replace("\\", "/").lower()
    if clean.endswith(".py"):
        return "python"
    return tse.detect_language(clean)


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CodeBlock:
    """A selectable unit. Lines are 1-based and inclusive."""
    kind: str                       # "callable" | "declaration"
    name: Optional[str]
    start_line: int                 # first decorator / attribute / attached comment line
    end_line: int
    header_end_line: int            # last line of the signature (callables), else end_line
    close_line: Optional[int]       # closing-brace line of the body (brace languages), else None
    scope_chain: Tuple[int, ...]    # indices into FileStructure.scopes, outermost first

    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1


@dataclass(frozen=True, slots=True)
class ScopeHeader:
    """An enclosing class / impl / namespace / function, rendered as its header (and closing line)."""
    kind: str
    name: Optional[str]
    start_line: int
    header_end_line: int
    close_line: Optional[int]


@dataclass(frozen=True, slots=True)
class ImportUnit:
    start_line: int
    end_line: int
    names: FrozenSet[str]
    always: bool = False
    # Grouped imports (Go ``import ( ... )``): (start, end, names) per spec. The first and last lines of the
    # declaration are kept and only the relevant specs between them are rendered.
    parts: Tuple[Tuple[int, int, FrozenSet[str]], ...] = ()


@dataclass(frozen=True, slots=True)
class FileStructure:
    language: str
    parser: str
    line_count: int
    blocks: Tuple[CodeBlock, ...]
    scopes: Tuple[ScopeHeader, ...]
    imports: Tuple[ImportUnit, ...]
    preamble: Tuple[Tuple[int, int], ...]
    owner: Tuple[int, ...]          # owner[line] = index of the innermost block containing it, or -1


@dataclass(frozen=True)
class StructureResult:
    structure: Optional[FileStructure]
    fallback_reason: Optional[str] = None


@dataclass(frozen=True)
class BlockSlice:
    text: Optional[str]                                      # None -> use the legacy extractor
    language: Optional[str]
    parser: Optional[str]
    selected: Tuple[Tuple[str, Optional[str], int, int], ...] = ()      # (kind, name, start, end)
    header_only: Tuple[Tuple[str, Optional[str], int, int], ...] = ()   # oversized: signature only
    blocks_considered: int = 0
    matched_blocks: int = 0
    fallback_reason: Optional[str] = None

    def note(self) -> str:
        if self.text is None:
            return f"ast_blocks fallback: {self.fallback_reason}"
        extra = f", {len(self.header_only)} oversized shown as header" if self.header_only else ""
        return f"ast_blocks: {self.language}, {len(self.selected)} block(s){extra}"


def _owner_map(blocks: Sequence[CodeBlock], line_count: int) -> Tuple[int, ...]:
    """Innermost block per line: paint larger blocks first so nested (smaller) blocks win."""
    owner = [-1] * (line_count + 2)
    order = sorted(range(len(blocks)), key=lambda i: (-blocks[i].line_count, -blocks[i].start_line, -i))
    for i in order:
        b = blocks[i]
        for ln in range(b.start_line, min(b.end_line, line_count) + 1):
            owner[ln] = i
    return tuple(owner)


# ---------------------------------------------------------------------------
# Python (ast)
# ---------------------------------------------------------------------------

_PY_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef)


def _py_start(node: ast.AST) -> int:
    decorators = getattr(node, "decorator_list", None) or []
    return min([node.lineno] + [d.lineno for d in decorators])


def _py_header_end(node: ast.AST) -> int:
    body = getattr(node, "body", None)
    if not body:
        return node.end_lineno or node.lineno
    first = _py_start(body[0])
    return max(node.lineno, first - 1)


def _py_nested_defs(stmts: Iterable[ast.stmt]) -> List[ast.stmt]:
    """Function/class definitions inside compound statements (if/for/while/with/try/match), not inside defs."""
    found: List[ast.stmt] = []
    stack = list(reversed(list(stmts)))
    while stack:
        s = stack.pop()
        if isinstance(s, _PY_DEFS + (ast.ClassDef,)):
            found.append(s)
            continue
        children: List[ast.stmt] = []
        for attr in ("body", "orelse", "finalbody"):
            children.extend(getattr(s, attr, None) or [])
        for handler in getattr(s, "handlers", None) or []:
            children.extend(handler.body)
        for case in getattr(s, "cases", None) or []:
            children.extend(case.body)
        stack.extend(reversed(children))
    found.sort(key=lambda n: (n.lineno, n.col_offset))
    return found


def _py_decl_name(stmt: ast.stmt) -> Optional[str]:
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
        return stmt.targets[0].id
    if isinstance(stmt, (ast.AnnAssign, ast.AugAssign)) and isinstance(stmt.target, ast.Name):
        return stmt.target.id
    return None


class _PythonAnalyzer:
    def __init__(self, content: str, lines: List[str]):
        self.content = content
        self.lines = lines
        self.blocks: List[CodeBlock] = []
        self.scopes: List[ScopeHeader] = []
        self.imports: List[ImportUnit] = []

    def _attach(self, start: int, floor: int) -> int:
        """Extends ``start`` upward over directly adjacent comment lines (no blank line, above ``floor``)."""
        ln = start
        while ln - 1 > floor and start - (ln - 1) <= MAX_ATTACHED_LINES \
                and self.lines[ln - 2].lstrip().startswith("#"):
            ln -= 1
        return ln

    def run(self) -> FileStructure:
        tree = ast.parse(self.content)
        self._visit_body(tree.body, (), 0, top_level=True)
        n = len(self.lines)
        blocks = tuple(sorted(self.blocks, key=lambda b: (b.start_line, -b.end_line)))
        return FileStructure("python", PYTHON_PARSER, n, blocks, tuple(self.scopes), tuple(self.imports), (),
                             _owner_map(blocks, n))

    def _visit_def(self, node: ast.stmt, chain: Tuple[int, ...], floor: int) -> None:
        start = _py_start(node)
        header_end = _py_header_end(node)
        if isinstance(node, ast.ClassDef):
            idx = len(self.scopes)
            self.scopes.append(ScopeHeader("class", node.name, start, header_end, None))
            self._visit_body(node.body, chain + (idx,), header_end, in_class=True)
            return
        self.blocks.append(CodeBlock("callable", node.name, self._attach(start, floor), node.end_lineno,
                                     header_end, None, chain))
        idx = len(self.scopes)
        self.scopes.append(ScopeHeader("function", node.name, start, header_end, None))
        for nested in _py_nested_defs(node.body):
            self._visit_def(nested, chain + (idx,), header_end)

    def _visit_body(self, body: Sequence[ast.stmt], chain: Tuple[int, ...], floor: int,
                    top_level: bool = False, in_class: bool = False) -> None:
        prev_end = floor
        for stmt in body:
            if isinstance(stmt, _PY_DEFS + (ast.ClassDef,)):
                self._visit_def(stmt, chain, prev_end)
            elif top_level and isinstance(stmt, (ast.Import, ast.ImportFrom)):
                self.imports.append(self._import(stmt))
            else:
                nested = _py_nested_defs([stmt])
                if nested:                       # e.g. `if TYPE_CHECKING:` / `try:` holding definitions
                    for d in nested:
                        self._visit_def(d, chain, prev_end)
                elif top_level or in_class:
                    self.blocks.append(CodeBlock("declaration", _py_decl_name(stmt),
                                                 self._attach(stmt.lineno, prev_end), stmt.end_lineno,
                                                 stmt.end_lineno, None, chain))
            prev_end = stmt.end_lineno or prev_end

    @staticmethod
    def _import(stmt: ast.stmt) -> ImportUnit:
        names: Set[str] = set()
        always = False
        if isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__":
            always = True
        for alias in stmt.names:
            if alias.name == "*":
                always = True
            elif alias.asname:
                names.add(alias.asname)
            elif isinstance(stmt, ast.Import):
                names.add(alias.name.split(".")[0])
            else:
                names.add(alias.name)
        return ImportUnit(stmt.lineno, stmt.end_lineno or stmt.lineno, frozenset(names), always)


# ---------------------------------------------------------------------------
# Tree-sitter languages
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _LangSpec:
    named_callables: FrozenSet[str]          # declarations with a body: function/method/constructor
    function_values: FrozenSet[str]          # function expressions that may be named by a declarator
    anonymous_blocks: bool                   # top-level statements holding callbacks become blocks
    scopes: FrozenSet[str]                   # containers rendered as headers (need a body)
    wrappers: FrozenSet[str]                 # export / template wrappers around a declaration
    imports: FrozenSet[str]
    always_imports: FrozenSet[str]
    preamble: FrozenSet[str]
    attached: FrozenSet[str]                 # decorators / attributes / comments attached when adjacent
    comment: str = "//"


_TS = _LangSpec(
    named_callables=frozenset({"function_declaration", "generator_function_declaration", "method_definition"}),
    function_values=frozenset({"arrow_function", "function_expression", "function", "generator_function"}),
    anonymous_blocks=True,
    scopes=frozenset({"class_declaration", "abstract_class_declaration", "class", "internal_module", "module"}),
    wrappers=frozenset({"export_statement", "ambient_declaration"}),
    imports=frozenset({"import_statement"}),
    always_imports=frozenset(),
    preamble=frozenset(),
    attached=frozenset({"decorator", "comment"}),
)

_SPECS: Dict[str, _LangSpec] = {
    "typescript": _TS,
    "tsx": _TS,
    "go": _LangSpec(
        named_callables=frozenset({"function_declaration", "method_declaration"}),
        function_values=frozenset({"func_literal"}),
        anonymous_blocks=True,
        scopes=frozenset(),
        wrappers=frozenset(),
        imports=frozenset({"import_declaration"}),
        always_imports=frozenset(),
        preamble=frozenset({"package_clause"}),
        attached=frozenset({"comment"}),
    ),
    "rust": _LangSpec(
        named_callables=frozenset({"function_item"}),
        function_values=frozenset(),
        anonymous_blocks=False,
        scopes=frozenset({"impl_item", "trait_item", "mod_item"}),
        wrappers=frozenset(),
        imports=frozenset({"use_declaration", "extern_crate_declaration"}),
        always_imports=frozenset({"extern_crate_declaration"}),
        preamble=frozenset(),
        attached=frozenset({"attribute_item", "line_comment", "block_comment"}),
    ),
    "java": _LangSpec(
        named_callables=frozenset({"method_declaration", "constructor_declaration",
                                   "compact_constructor_declaration"}),
        function_values=frozenset(),
        anonymous_blocks=False,
        scopes=frozenset({"class_declaration", "interface_declaration", "enum_declaration", "record_declaration",
                          "annotation_type_declaration"}),
        wrappers=frozenset(),
        imports=frozenset({"import_declaration"}),
        always_imports=frozenset(),
        preamble=frozenset({"package_declaration"}),
        attached=frozenset({"line_comment", "block_comment"}),
    ),
    "cpp": _LangSpec(
        named_callables=frozenset({"function_definition"}),
        function_values=frozenset(),
        anonymous_blocks=False,
        scopes=frozenset({"class_specifier", "struct_specifier", "union_specifier", "namespace_definition",
                          "linkage_specification"}),
        wrappers=frozenset({"template_declaration"}),
        imports=frozenset({"preproc_include", "using_declaration", "namespace_alias_definition"}),
        always_imports=frozenset({"preproc_include", "using_declaration", "namespace_alias_definition"}),
        preamble=frozenset(),
        attached=frozenset({"comment"}),
    ),
}

_STRING_TYPES = frozenset({"string", "string_literal", "interpreted_string_literal", "raw_string_literal",
                           "system_lib_string", "template_string", "string_fragment", "char_literal"})
_NAME_TYPES = frozenset({"identifier", "type_identifier", "package_identifier", "namespace_identifier",
                         "field_identifier", "property_identifier", "scoped_type_identifier"})
_BLOCK_BODIES = frozenset({"statement_block", "block", "compound_statement", "constructor_body", "class_body",
                           "declaration_list", "field_declaration_list", "interface_body", "enum_body",
                           "record_body", "annotation_type_body"})
_VAR_DECLS = frozenset({"lexical_declaration", "variable_declaration"})
_VALUE_DECLS = _VAR_DECLS | {"variable_declarator", "public_field_definition", "var_declaration"}


class _TreeSitterAnalyzer:
    def __init__(self, language: str, tree, src: bytes, lines: List[str]):
        self.language = language
        self.spec = _SPECS[language]
        self.root = tree.root_node
        self.src = src
        self.lines = lines
        self.line_starts = [0] + [m.end() for m in _LINE_BREAK_BYTES.finditer(src)]
        self.blocks: List[CodeBlock] = []
        self.scopes: List[ScopeHeader] = []
        self.imports: List[ImportUnit] = []
        self.preamble: List[Tuple[int, int]] = []
        self._nested_candidates = (self.spec.named_callables | self.spec.scopes | self.spec.wrappers
                                   | _VALUE_DECLS)

    # -- positions ---------------------------------------------------------
    def first(self, node) -> int:
        return bisect.bisect_right(self.line_starts, node.start_byte)

    def last(self, node) -> int:
        return bisect.bisect_right(self.line_starts, max(node.start_byte, node.end_byte - 1))

    def text(self, node) -> str:
        return self.src[node.start_byte:node.end_byte].decode("utf-8", "replace")

    # -- classification ----------------------------------------------------
    def unwrap(self, node):
        """Strips export/template wrappers down to the declaration they carry."""
        while node.type in self.spec.wrappers:
            inner = node.child_by_field_name("declaration") or node.child_by_field_name("value")
            if inner is None:
                rest = [c for c in node.named_children
                        if c.type not in self.spec.attached and c.type not in ("template_parameter_list",
                                                                               "requires_clause")]
                inner = rest[-1] if rest else None
            if inner is None:
                return node
            node = inner
        return node

    def body_of(self, node):
        body = node.child_by_field_name("body")
        if body is None and node.type == "variable_declarator":
            value = node.child_by_field_name("value")
            body = value.child_by_field_name("body") if value is not None else None
        return body

    def named_value_function(self, core):
        """For `const f = () => {}`, `handler = () => {}` (class field), `var h = func() {}`: (name, fn)."""
        if core.type in _VAR_DECLS:
            decls = [c for c in core.named_children if c.type == "variable_declarator"]
            if len(decls) == 1:
                return self.named_value_function(decls[0])
            return None
        if core.type in ("variable_declarator", "public_field_definition"):
            value = core.child_by_field_name("value")
            name = core.child_by_field_name("name")
            if value is not None and value.type in self.spec.function_values and name is not None:
                return self.text(name), value
            return None
        if core.type == "var_declaration":           # Go: var h = func() { ... }
            specs = [c for c in core.named_children if c.type == "var_spec"]
            if len(specs) == 1:
                names = specs[0].child_by_field_name("name")
                value = specs[0].child_by_field_name("value")
                funcs = [c for c in (value.named_children if value is not None else []) if c.type == "func_literal"]
                if names is not None and len(funcs) == 1:
                    return self.text(names), funcs[0]
        return None

    def callable_name(self, core) -> Optional[str]:
        if self.language == "cpp" and core.type == "function_definition":
            decl = core.child_by_field_name("declarator")
            while decl is not None and decl.type != "function_declarator":
                decl = decl.child_by_field_name("declarator")
            target = decl.child_by_field_name("declarator") if decl is not None else None
            return self.text(target).split("::")[-1] if target is not None else None
        name = core.child_by_field_name("name")
        return self.text(name) if name is not None else None

    def scope_name(self, core) -> Optional[str]:
        name = core.child_by_field_name("name") or core.child_by_field_name("type")
        return self.text(name) if name is not None else None

    # -- spans -------------------------------------------------------------
    def attached_start(self, anchor, comments: bool = True) -> int:
        """First line of the anchor, extended over directly preceding decorators/attributes (and comments)."""
        start = self.first(anchor)
        node = anchor
        while True:
            prev = node.prev_named_sibling
            if prev is None or prev.type not in self.spec.attached or (not comments and "comment" in prev.type):
                break
            if self.last(prev) < start - 1 or start - self.first(prev) > MAX_ATTACHED_LINES:
                break                                   # blank line in between, or too long
            before = prev.prev_named_sibling
            if before is not None and self.last(before) >= self.first(prev):
                break                                   # trailing comment of the previous statement
            start = self.first(prev)
            node = prev
        return start

    def add_block(self, kind: str, name: Optional[str], anchor, body, chain: Tuple[int, ...]) -> Tuple[int, int, int]:
        start = self.attached_start(anchor)
        end = self.last(anchor)
        header_end, close = end, None
        if body is not None:
            header_end = max(self.first(anchor), self.first(body))
            if body.type in _BLOCK_BODIES and self.last(body) > header_end:
                close = self.last(body)
        self.blocks.append(CodeBlock(kind, name, start, end, header_end, close, chain))
        return start, header_end, close if close is not None else -1

    def add_scope(self, kind: str, name: Optional[str], anchor, body) -> int:
        start = self.attached_start(anchor, comments=False)
        header_end = max(start, self.first(body)) if body is not None else self.last(anchor)
        close = self.last(body) if body is not None and self.last(body) > header_end else None
        self.scopes.append(ScopeHeader(kind, name, start, header_end, close))
        return len(self.scopes) - 1

    # -- traversal ---------------------------------------------------------
    def run(self) -> FileStructure:
        self.visit_list(self.root.named_children, (), "module")
        n = len(self.lines)
        blocks = tuple(sorted(self.blocks, key=lambda b: (b.start_line, -b.end_line)))
        return FileStructure(self.language, TREE_SITTER_PARSER, n, blocks, tuple(self.scopes),
                             tuple(self.imports), tuple(self.preamble), _owner_map(blocks, n))

    def visit_list(self, nodes, chain: Tuple[int, ...], context: str) -> None:
        for node in nodes:
            self.visit(node, chain, context)

    def visit(self, node, chain: Tuple[int, ...], context: str) -> None:
        t = node.type
        if t in self.spec.attached or "comment" in t:
            return
        if t in self.spec.preamble:
            self.preamble.append((self.first(node), self.last(node)))
            return
        if t in self.spec.imports:
            if context == "module" or t in self.spec.always_imports:
                self.imports.append(self.import_unit(node))
            return
        core = self.unwrap(node)
        if core.type in self.spec.scopes and core.child_by_field_name("body") is not None:
            body = core.child_by_field_name("body")
            idx = self.add_scope(core.type, self.scope_name(core), node, body)
            self.visit_list(body.named_children, chain + (idx,), "scope")
            return
        if core.type in self.spec.named_callables:
            self.add_callable(self.callable_name(core), node, core.child_by_field_name("body"), chain)
            return
        named = self.named_value_function(core)
        if named is None and core.type in self.spec.function_values and node.type in self.spec.wrappers:
            named = ("default", core)                  # `export default function () {}`
        if named is not None:
            self.add_callable(named[0], node, named[1].child_by_field_name("body"), chain)
            return
        if context in ("module", "scope", "callback") and self.spec.anonymous_blocks:
            funcs = self.outer_functions(node)
            if funcs:
                self.add_callback_statement(node, funcs, chain)
                return
        if context in ("module", "scope"):
            self.add_block("declaration", self.decl_name(core), node, None, chain)

    def add_callable(self, name: Optional[str], anchor, body, chain: Tuple[int, ...]) -> None:
        start, header_end, close = self.add_block("callable", name, anchor, body, chain)
        if body is None:
            return
        idx = len(self.scopes)
        self.scopes.append(ScopeHeader("function", name, start, header_end, close if close > 0 else None))
        self.find_nested(body, chain + (idx,))

    def add_callback_statement(self, node, funcs, chain: Tuple[int, ...]) -> None:
        """A statement such as `it("adds", () => {...})` or `router.get("/", handler)`: one block, and a scope
        whose body (each callback's statements) may hold further callback statements."""
        first_body = next((f.child_by_field_name("body") for f in funcs
                           if f.child_by_field_name("body") is not None), None)
        name = self.callback_name(node)
        start, header_end, _ = self.add_block("callable", name, node, first_body, chain)
        close_line = self.last(node)
        idx = len(self.scopes)
        self.scopes.append(ScopeHeader("callback", name, start, header_end,
                                       close_line if close_line > header_end else None))
        for f in funcs:
            body = f.child_by_field_name("body")
            if body is not None and body.type in _BLOCK_BODIES:
                self.visit_list(body.named_children, chain + (idx,), "callback")

    def outer_functions(self, node) -> list:
        """Outermost anonymous function expressions inside ``node`` (not inside another function)."""
        found = []
        stack = [node]
        while stack:
            cur = stack.pop()
            if cur is not node and (cur.type in self.spec.function_values or cur.type in self.spec.named_callables):
                if cur.type in self.spec.function_values:
                    found.append(cur)
                continue
            if cur is not node and cur.type in self.spec.scopes:
                continue
            stack.extend(reversed(cur.named_children))
        return found

    def find_nested(self, body, chain: Tuple[int, ...]) -> None:
        """
        Multi-line named functions and classes declared inside a function body (anonymous callbacks stay inline).
        Single-line subtrees are not searched: a one-line nested function is attributed to its enclosing function,
        which is still a complete block, and skipping them keeps the walk proportional to multi-line structure.
        """
        candidates = self._nested_candidates
        stack = list(reversed(body.named_children))
        while stack:
            node = stack.pop()
            if node.type in candidates:
                core = self.unwrap(node)
                if core.type in self.spec.scopes and core.child_by_field_name("body") is not None:
                    b = core.child_by_field_name("body")
                    idx = self.add_scope(core.type, self.scope_name(core), node, b)
                    self.visit_list(b.named_children, chain + (idx,), "scope")
                    continue
                if core.type in self.spec.named_callables:
                    self.add_callable(self.callable_name(core), node, core.child_by_field_name("body"), chain)
                    continue
                named = self.named_value_function(core)
                if named is not None and node.end_point[0] > node.start_point[0]:   # multi-line function value
                    self.add_callable(named[0], node, named[1].child_by_field_name("body"), chain)
                    continue
            if node.end_point[0] > node.start_point[0]:
                stack.extend(reversed(node.named_children))

    def callback_name(self, node) -> Optional[str]:
        call = node
        while call is not None and call.type != "call_expression":
            call = call.named_children[0] if call.named_children else None
        if call is None:
            return None
        func = call.child_by_field_name("function")
        label = self.text(func) if func is not None else ""
        args = call.child_by_field_name("arguments")
        first = args.named_children[0] if args is not None and args.named_children else None
        if first is not None and first.type in _STRING_TYPES:
            label = f"{label} {self.text(first).strip(chr(34) + chr(39) + '`')}"
        return label[:80] or None

    def decl_name(self, core) -> Optional[str]:
        name = core.child_by_field_name("name")
        if name is not None:
            return self.text(name)
        for child in core.named_children:
            inner = child.child_by_field_name("name") or child.child_by_field_name("declarator")
            if inner is not None and inner.type in _NAME_TYPES:
                return self.text(inner)
        return None

    def names_in(self, node) -> FrozenSet[str]:
        names: Set[str] = set()
        stack = [node]
        while stack:
            cur = stack.pop()
            if cur.type in _STRING_TYPES:
                continue
            if cur.type in _NAME_TYPES and not cur.named_children:
                names.add(self.text(cur))
            stack.extend(cur.named_children)
        return frozenset(names)

    def import_unit(self, node) -> ImportUnit:
        start, end = self.first(node), self.last(node)
        always = node.type in self.spec.always_imports or self._is_wildcard(node)
        if self.language == "go":
            specs = [s for s in self._descendants(node, "import_spec")]
            parts = tuple((self.first(s), self.last(s), self._go_import_names(s)) for s in specs)
            names = frozenset().union(*(p[2] for p in parts)) if parts else frozenset()
            always = always or any(not p[2] for p in parts)
            grouped = bool(parts) and (start < parts[0][0] or end > parts[-1][1])
            return ImportUnit(start, end, names, always, parts if grouped else ())
        return ImportUnit(start, end, self.names_in(node), always)

    def _descendants(self, node, node_type: str):
        stack = [node]
        while stack:
            cur = stack.pop()
            if cur.type == node_type:
                yield cur
                continue
            stack.extend(reversed(cur.named_children))

    def _go_import_names(self, spec) -> FrozenSet[str]:
        alias = spec.child_by_field_name("name")
        if alias is not None:
            if alias.type in ("blank_identifier", "dot"):
                return frozenset()               # side-effect / dot imports: always kept
            return frozenset({self.text(alias)})
        path = spec.child_by_field_name("path")
        if path is None:
            return frozenset()
        last = self.text(path).strip('"`').rsplit("/", 1)[-1]
        return frozenset({last, last.replace("-", "_")})

    def _is_wildcard(self, node) -> bool:
        stack = [node]
        while stack:
            cur = stack.pop()
            if cur.type in ("use_wildcard", "asterisk", "namespace_import"):
                return cur.type != "namespace_import"
            stack.extend(cur.children)
        return False


# ---------------------------------------------------------------------------
# Analysis entry point
# ---------------------------------------------------------------------------

def analyze_structure(content: str, path: str) -> StructureResult:
    """Parses one file into blocks, scopes and imports, or reports why it cannot (never raises)."""
    language = detect_language(path)
    if language is None:
        return StructureResult(None, "unsupported_language")
    lines = split_lines(content)
    if language == "python":
        try:
            return StructureResult(_PythonAnalyzer(content, lines).run())
        except (SyntaxError, ValueError):
            return StructureResult(None, "syntax_error")
        except (RecursionError, MemoryError):
            return StructureResult(None, "parse_limit")
    try:
        parsed = tse.parse_source(content, language)
    except Exception as exc:  # broken native installation: treat like a missing parser
        return StructureResult(None, f"parser_error: {type(exc).__name__}")
    if parsed is None:
        return StructureResult(None, "parser_unavailable")
    tree, src = parsed
    if tree.root_node.has_error:
        return StructureResult(None, "syntax_error")
    try:
        return StructureResult(_TreeSitterAnalyzer(language, tree, src, lines).run())
    except RecursionError:
        return StructureResult(None, "parse_limit")


# ---------------------------------------------------------------------------
# Selection and rendering
# ---------------------------------------------------------------------------

def _overlaps(a: CodeBlock, b: CodeBlock) -> bool:
    return a.start_line <= b.end_line and b.start_line <= a.end_line


def slice_blocks(
    content: str,
    path: str,
    query_terms: Iterable[str],
    *,
    max_block_lines: int = DEFAULT_MAX_BLOCK_LINES,
    max_total_lines: int = DEFAULT_MAX_TOTAL_LINES,
    max_blocks: int = DEFAULT_MAX_BLOCKS,
    structure: Optional[StructureResult] = None,
) -> BlockSlice:
    """
    Selects and renders the blocks relevant to ``query_terms`` (see the module docstring).

    Limits never cut a block:

    * ``max_block_lines`` (hard): a longer block is never selected. It is shown as its signature only, or the file
      falls back (``oversized_block``) when nothing else matches.
    * ``max_total_lines`` (soft): the highest-ranked eligible block is always selected whole, even if it alone
      exceeds this budget; further blocks are added only while the total stays within it.
    * ``max_blocks`` (hard): at most this many blocks.
    """
    result = structure if structure is not None else analyze_structure(content, path)
    fs = result.structure
    if fs is None:
        return BlockSlice(None, detect_language(path), None, fallback_reason=result.fallback_reason)
    terms = sorted({t.lower() for t in query_terms if t})
    if not terms:
        return BlockSlice(None, fs.language, fs.parser, blocks_considered=len(fs.blocks),
                          fallback_reason="no_query_terms")
    lines = split_lines(content)

    # 1. Attribute every matching line to its innermost block.
    hits: Dict[int, List] = {}
    for ln, line in enumerate(lines, 1):
        low = line.lower()
        matched = [t for t in terms if t in low]
        if not matched:
            continue
        owner = fs.owner[ln] if ln < len(fs.owner) else -1
        if owner < 0:
            continue
        entry = hits.setdefault(owner, [set(), 0])
        entry[0].update(matched)
        entry[1] += 1
    if not hits:
        return BlockSlice(None, fs.language, fs.parser, blocks_considered=len(fs.blocks),
                          fallback_reason="no_block_match")

    # 2. Rank deterministically: distinct terms, name match, matching lines, source order.
    def key(i: int):
        b = fs.blocks[i]
        name = (b.name or "").lower()
        return (-len(hits[i][0]), -int(any(t in name for t in terms)), -hits[i][1], b.start_line, i)

    selected: List[CodeBlock] = []
    oversized: List[CodeBlock] = []
    total = 0
    for i in sorted(hits, key=key):
        b = fs.blocks[i]
        if any(_overlaps(b, s) for s in selected):
            continue
        if b.line_count > max_block_lines:
            if len(oversized) < max_blocks:
                oversized.append(b)
            continue
        # max_total_lines is a soft budget: the first (highest-ranked) block is always taken whole; later blocks
        # only while the total stays within it. Blocks are never truncated to meet it.
        if len(selected) >= max_blocks or (selected and total + b.line_count > max_total_lines):
            continue
        selected.append(b)
        total += b.line_count
    oversized = [b for b in oversized if not any(_overlaps(b, s) for s in selected)][: max(0, max_blocks - len(selected))]
    if not selected:
        return BlockSlice(None, fs.language, fs.parser, blocks_considered=len(fs.blocks), matched_blocks=len(hits),
                          fallback_reason="oversized_block" if oversized else "no_block_match")

    # 3. Collect line intervals: blocks, enclosing scope headers/closings, then relevant imports.
    intervals: List[Tuple[int, int]] = []

    def add_scopes(block: CodeBlock) -> None:
        for idx in block.scope_chain:
            sc = fs.scopes[idx]
            intervals.append((sc.start_line, sc.header_end_line))
            if sc.close_line is not None:
                intervals.append((sc.close_line, sc.close_line))

    for b in selected:
        add_scopes(b)
        intervals.append((b.start_line, b.end_line))
    for b in oversized:
        add_scopes(b)
        intervals.append((b.start_line, b.header_end_line))
        if b.close_line is not None:
            intervals.append((b.close_line, b.close_line))
    intervals.extend(fs.preamble)

    used: Set[str] = set()
    for s, e in intervals:
        for ln in range(s, e + 1):
            used.update(_IDENT.findall(lines[ln - 1]))
    import_lines = 0
    for imp in fs.imports:
        if imp.parts:
            parts = [(s, e) for s, e, names in imp.parts if imp.always and not names or names & used]
            if not parts:
                continue
            chunk = [(imp.start_line, imp.start_line)] + parts + [(imp.end_line, imp.end_line)]
        elif imp.always or imp.names & used:
            chunk = [(imp.start_line, imp.end_line)]
        else:
            continue
        size = sum(e - s + 1 for s, e in chunk)
        if import_lines + size > MAX_IMPORT_LINES:
            continue
        import_lines += size
        intervals.extend(chunk)

    text = _render(lines, intervals, _SPECS[fs.language].comment if fs.language in _SPECS else "#")
    sel = tuple((b.kind, b.name, b.start_line, b.end_line) for b in sorted(selected, key=lambda b: b.start_line))
    hdr = tuple((b.kind, b.name, b.start_line, b.end_line) for b in sorted(oversized, key=lambda b: b.start_line))
    return BlockSlice(text, fs.language, fs.parser, sel, hdr, len(fs.blocks), len(hits))


def _render(lines: List[str], intervals: List[Tuple[int, int]], comment: str) -> str:
    n = len(lines)
    merged: List[List[int]] = []
    for s, e in sorted((max(1, s), min(n, e)) for s, e in intervals if s <= e):
        if s > n:
            continue
        if merged and s <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])

    def gap(a: int, b: int) -> List[str]:
        hidden = lines[a - 1:b]
        first = next((h for h in hidden if h.strip()), None)
        if first is None:                           # only blank lines: keep them verbatim, no marker
            return hidden
        indent = first[: len(first) - len(first.lstrip())]   # indented like the code it replaces
        span = f"line {a}" if a == b else f"lines {a}-{b}"
        return [f"{indent}{comment} ... [{span} elided] ..."]

    out: List[str] = []
    prev_end = 0
    for s, e in merged:
        if s > prev_end + 1:
            out.extend(gap(prev_end + 1, s - 1))
        out.extend(lines[s - 1:e])
        prev_end = e
    if prev_end < n:
        out.extend(gap(prev_end + 1, n))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Retained-size estimates (used by the bounded caches in CodeSpanExtractor)
# ---------------------------------------------------------------------------
#
# Each estimate sums ``sys.getsizeof`` over the objects a cache entry keeps alive: the record instances (slotted,
# so ``getsizeof`` covers all their fields), their tuples, frozensets, name strings and rendered text, plus the
# integer objects of the per-line owner map. Objects shared with the rest of the program (string literals such as
# block kinds, interned short strings, small ints) are not counted. Allocator overhead is not included. It is an
# estimate of retained Python object bytes, not a measurement of process memory.

def _obj_bytes(obj) -> int:
    size = sys.getsizeof(obj)
    if hasattr(obj, "__dict__"):                  # non-slotted dataclass: count its instance dict once
        size += _INSTANCE_DICT_BYTES
    return size


def _opt_str(value: Optional[str]) -> int:
    return sys.getsizeof(value) if value else 0


def estimate_structure_bytes(result: StructureResult) -> int:
    """Approximate bytes retained by one cached :class:`StructureResult` (see the note above)."""
    total = _obj_bytes(result)
    fs = result.structure
    if fs is None:
        return total
    total += sys.getsizeof(fs) + sys.getsizeof(fs.blocks) + sys.getsizeof(fs.scopes) + sys.getsizeof(fs.imports)
    total += sys.getsizeof(fs.preamble) + sum(sys.getsizeof(p) for p in fs.preamble) + sys.getsizeof(fs.owner)
    total += _INT_BYTES * max(0, len(fs.blocks) - 256)      # owner-map indices above the small-int cache
    for b in fs.blocks:
        total += sys.getsizeof(b) + sys.getsizeof(b.scope_chain) + _opt_str(b.name)
    for sc in fs.scopes:
        total += sys.getsizeof(sc) + _opt_str(sc.name)
    for imp in fs.imports:
        total += sys.getsizeof(imp) + sys.getsizeof(imp.names) + sum(sys.getsizeof(n) for n in imp.names)
        total += sys.getsizeof(imp.parts) + sum(sys.getsizeof(p) + sys.getsizeof(p[2]) for p in imp.parts)
    return total


def estimate_slice_bytes(sliced: BlockSlice, rendered: Optional[str] = None) -> int:
    """Approximate bytes retained by one cached :class:`BlockSlice` and its rendered span (if different)."""
    total = _obj_bytes(sliced) + _opt_str(sliced.text)
    for group in (sliced.selected, sliced.header_only):
        total += sys.getsizeof(group) + sum(sys.getsizeof(s) + _opt_str(s[1]) for s in group)
    if rendered is not None and rendered is not sliced.text:
        total += sys.getsizeof(rendered)
    return total


_INT_BYTES = sys.getsizeof(10 ** 6)
_INSTANCE_DICT_BYTES = sys.getsizeof(BlockSlice(None, None, None).__dict__)   # materialised on a sample only
