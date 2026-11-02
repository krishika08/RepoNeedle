"""
R5.1: Hierarchical Code-Unit Indexing Engine.
Extracts, indexes, and manages fine-grained code representations at:
- Module
- Class / Struct / Interface
- Function / Method
- Code Block / AST-Derived Source Span

Supports polyglot source parsing (Python AST, JS/TS regex, Rust regex) with
lexical block fallback for unsupported languages and syntax errors.
Supports incremental addition, update, and removal of files.
"""
import ast
import re
import os
import math
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict

from reponeedle.models import FileDoc
from reponeedle.core.tokenizer import CodeTokenizer

CAMEL_CASE_REGEX = re.compile(r"([a-z0-9])([A-Z])")
SNAKE_CASE_REGEX = re.compile(r"[_\-/\\\s]+")


class CodeUnitType(str, Enum):
    MODULE = "module"
    CLASS = "class"
    INTERFACE = "interface"
    FUNCTION = "function"
    METHOD = "method"
    CODE_BLOCK = "code_block"
    SOURCE_SPAN = "source_span"


class CodeUnit:
    """Represents a fine-grained structural code unit with AST and token lineage."""

    def __init__(
        self,
        unit_id: str,
        file_path: str,
        unit_type: CodeUnitType,
        symbol_name: str,
        qualified_name: str,
        signature: str,
        parent_name: Optional[str] = None,
        start_line: int = 1,
        end_line: int = 1,
        content: str = "",
        docstring: Optional[str] = None,
        tokens: Optional[List[str]] = None,
        subwords: Optional[List[str]] = None,
        calls: Optional[List[str]] = None,
        imports: Optional[List[str]] = None,
        language: str = "python",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.unit_id = unit_id
        self.file_path = file_path
        self.unit_type = unit_type
        self.symbol_name = symbol_name
        self.qualified_name = qualified_name
        self.signature = signature
        self.parent_name = parent_name
        self.start_line = start_line
        self.end_line = end_line
        self.content = content
        self.docstring = docstring or ""
        self.tokens = tokens or []
        self.subwords = subwords or []
        self.calls = calls or []
        self.imports = imports or []
        self.language = language
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "file_path": self.file_path,
            "unit_type": self.unit_type.value,
            "symbol_name": self.symbol_name,
            "qualified_name": self.qualified_name,
            "signature": self.signature,
            "parent_name": self.parent_name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "docstring": self.docstring,
            "tokens": self.tokens,
            "subwords": self.subwords,
            "calls": self.calls,
            "imports": self.imports,
            "language": self.language,
        }


class PythonASTVisitor(ast.NodeVisitor):
    """Extracts classes, functions, methods, calls, and imports using Python AST."""

    def __init__(self, file_path: str, source_code: str, lines: List[str]):
        self.file_path = file_path
        self.source_code = source_code
        self.lines = lines
        self.units: List[CodeUnit] = []
        self.current_class: Optional[str] = None
        self.current_class_node: Optional[ast.ClassDef] = None
        self.module_imports: List[str] = []

    def _get_source_span(self, node: ast.AST) -> Tuple[int, int, str]:
        start = getattr(node, "lineno", 1)
        end = getattr(node, "end_lineno", start)
        span_lines = self.lines[start - 1 : end]
        return start, end, "\n".join(span_lines)

    def _extract_calls(self, node: ast.AST) -> List[str]:
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        return list(dict.fromkeys(calls))

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.module_imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod = node.module or ""
        for alias in node.names:
            self.module_imports.append(f"{mod}.{alias.name}" if mod else alias.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        start, end, content = self._get_source_span(node)
        docstring = ast.get_docstring(node) or ""
        calls = self._extract_calls(node)
        bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
        sig = f"class {node.name}({', '.join(bases)})"

        unit_id = f"{self.file_path}::{node.name}"
        tokens = CodeUnitIndexer.tokenize_identifiers(f"{node.name} {sig} {docstring}")
        subwords = CodeUnitIndexer.decompose_subwords(tokens)

        unit = CodeUnit(
            unit_id=unit_id,
            file_path=self.file_path,
            unit_type=CodeUnitType.CLASS,
            symbol_name=node.name,
            qualified_name=node.name,
            signature=sig,
            parent_name=None,
            start_line=start,
            end_line=end,
            content=content[:4000],
            docstring=docstring,
            tokens=tokens,
            subwords=subwords,
            calls=calls,
            imports=list(self.module_imports),
            language="python",
        )
        self.units.append(unit)

        prev_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._process_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._process_function(node, is_async=True)

    def _process_function(self, node: Any, is_async: bool):
        start, end, content = self._get_source_span(node)
        docstring = ast.get_docstring(node) or ""
        calls = self._extract_calls(node)

        # Build signature
        args = [a.arg for a in node.args.args]
        async_prefix = "async " if is_async else ""
        sig = f"{async_prefix}def {node.name}({', '.join(args)})"

        if self.current_class:
            unit_type = CodeUnitType.METHOD
            qualified = f"{self.current_class}.{node.name}"
            parent = self.current_class
        else:
            unit_type = CodeUnitType.FUNCTION
            qualified = node.name
            parent = None

        unit_id = f"{self.file_path}::{qualified}"
        tokens = CodeUnitIndexer.tokenize_identifiers(f"{node.name} {sig} {docstring} {' '.join(calls)}")
        subwords = CodeUnitIndexer.decompose_subwords(tokens)

        unit = CodeUnit(
            unit_id=unit_id,
            file_path=self.file_path,
            unit_type=unit_type,
            symbol_name=node.name,
            qualified_name=qualified,
            signature=sig,
            parent_name=parent,
            start_line=start,
            end_line=end,
            content=content[:3000],
            docstring=docstring,
            tokens=tokens,
            subwords=subwords,
            calls=calls,
            imports=list(self.module_imports),
            language="python",
        )
        self.units.append(unit)
        self.generic_visit(node)


class CodeUnitIndexer:
    """Polyglot parser and indexer for repository code units."""

    def __init__(self):
        self.units_by_id: Dict[str, CodeUnit] = {}
        self.file_to_units: Dict[str, List[str]] = defaultdict(list)
        self.symbol_to_units: Dict[str, List[str]] = defaultdict(list)
        self.tokenizer = CodeTokenizer()

    @staticmethod
    def tokenize_identifiers(text: str) -> List[str]:
        raw_words = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{1,}\b", text)
        return [w.lower() for w in raw_words]

    @staticmethod
    def decompose_subwords(tokens: List[str]) -> List[str]:
        subwords = []
        for t in tokens:
            s1 = CAMEL_CASE_REGEX.sub(r"\1 \2", t)
            parts = SNAKE_CASE_REGEX.split(s1)
            for p in parts:
                p_clean = p.strip().lower()
                if len(p_clean) > 1:
                    subwords.append(p_clean)
        return list(dict.fromkeys(subwords))

    def parse_python(self, file_path: str, content: str) -> List[CodeUnit]:
        lines = content.splitlines()
        try:
            tree = ast.parse(content, filename=file_path)
            visitor = PythonASTVisitor(file_path, content, lines)
            visitor.visit(tree)
            units = visitor.units
        except Exception:
            # Fallback to lexical chunking on syntax error
            units = self.chunk_lexical(file_path, content, language="python")

        # Always include a top-level module unit
        mod_tokens = self.tokenize_identifiers(file_path)
        mod_unit = CodeUnit(
            unit_id=f"{file_path}::[module]",
            file_path=file_path,
            unit_type=CodeUnitType.MODULE,
            symbol_name=os.path.basename(file_path),
            qualified_name=file_path,
            signature=f"module {os.path.basename(file_path)}",
            start_line=1,
            end_line=len(lines) if lines else 1,
            content=content[:2000],
            tokens=mod_tokens,
            subwords=self.decompose_subwords(mod_tokens),
            language="python",
        )
        return [mod_unit] + units

    def parse_rust(self, file_path: str, content: str) -> List[CodeUnit]:
        lines = content.splitlines()
        units: List[CodeUnit] = []
        fn_pattern = re.compile(r"^\s*(?:pub(?:\([^)]+\))?\s+)?(?:async\s+)?fn\s+([A-Za-z0-9_]+)\s*(?:<[^>]+>)?\s*\(([^)]*)\)", re.M)
        struct_pattern = re.compile(r"^\s*(?:pub(?:\([^)]+\))?\s+)?(?:struct|enum|trait)\s+([A-Za-z0-9_]+)", re.M)

        for match in struct_pattern.finditer(content):
            name = match.group(1)
            start_line = content[: match.start()].count("\n") + 1
            unit = CodeUnit(
                unit_id=f"{file_path}::{name}",
                file_path=file_path,
                unit_type=CodeUnitType.CLASS,
                symbol_name=name,
                qualified_name=name,
                signature=match.group(0).strip(),
                start_line=start_line,
                end_line=min(len(lines), start_line + 30),
                content="\n".join(lines[start_line - 1 : start_line + 29]),
                tokens=self.tokenize_identifiers(name),
                subwords=self.decompose_subwords([name]),
                language="rust",
            )
            units.append(unit)

        for match in fn_pattern.finditer(content):
            name = match.group(1)
            sig = match.group(0).strip()
            start_line = content[: match.start()].count("\n") + 1
            unit = CodeUnit(
                unit_id=f"{file_path}::{name}",
                file_path=file_path,
                unit_type=CodeUnitType.FUNCTION,
                symbol_name=name,
                qualified_name=name,
                signature=sig,
                start_line=start_line,
                end_line=min(len(lines), start_line + 40),
                content="\n".join(lines[start_line - 1 : start_line + 39]),
                tokens=self.tokenize_identifiers(f"{name} {sig}"),
                subwords=self.decompose_subwords([name]),
                language="rust",
            )
            units.append(unit)

        if not units:
            units = self.chunk_lexical(file_path, content, language="rust")

        mod_tokens = self.tokenize_identifiers(file_path)
        mod_unit = CodeUnit(
            unit_id=f"{file_path}::[module]",
            file_path=file_path,
            unit_type=CodeUnitType.MODULE,
            symbol_name=os.path.basename(file_path),
            qualified_name=file_path,
            signature=f"mod {os.path.basename(file_path)}",
            start_line=1,
            end_line=len(lines) if lines else 1,
            content=content[:2000],
            tokens=mod_tokens,
            subwords=self.decompose_subwords(mod_tokens),
            language="rust",
        )
        return [mod_unit] + units

    def parse_javascript(self, file_path: str, content: str) -> List[CodeUnit]:
        lines = content.splitlines()
        units: List[CodeUnit] = []
        fn_pattern = re.compile(r"(?:function\s+([A-Za-z0-9_]+)|(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)", re.M)
        class_pattern = re.compile(r"class\s+([A-Za-z0-9_]+)", re.M)

        for match in class_pattern.finditer(content):
            name = match.group(1)
            start_line = content[: match.start()].count("\n") + 1
            unit = CodeUnit(
                unit_id=f"{file_path}::{name}",
                file_path=file_path,
                unit_type=CodeUnitType.CLASS,
                symbol_name=name,
                qualified_name=name,
                signature=f"class {name}",
                start_line=start_line,
                end_line=min(len(lines), start_line + 30),
                content="\n".join(lines[start_line - 1 : start_line + 29]),
                tokens=self.tokenize_identifiers(name),
                subwords=self.decompose_subwords([name]),
                language="javascript",
            )
            units.append(unit)

        for match in fn_pattern.finditer(content):
            name = match.group(1) or match.group(2)
            if not name:
                continue
            sig = match.group(0).strip()
            start_line = content[: match.start()].count("\n") + 1
            unit = CodeUnit(
                unit_id=f"{file_path}::{name}",
                file_path=file_path,
                unit_type=CodeUnitType.FUNCTION,
                symbol_name=name,
                qualified_name=name,
                signature=sig,
                start_line=start_line,
                end_line=min(len(lines), start_line + 35),
                content="\n".join(lines[start_line - 1 : start_line + 34]),
                tokens=self.tokenize_identifiers(f"{name} {sig}"),
                subwords=self.decompose_subwords([name]),
                language="javascript",
            )
            units.append(unit)

        if not units:
            units = self.chunk_lexical(file_path, content, language="javascript")

        mod_tokens = self.tokenize_identifiers(file_path)
        mod_unit = CodeUnit(
            unit_id=f"{file_path}::[module]",
            file_path=file_path,
            unit_type=CodeUnitType.MODULE,
            symbol_name=os.path.basename(file_path),
            qualified_name=file_path,
            signature=f"module {os.path.basename(file_path)}",
            start_line=1,
            end_line=len(lines) if lines else 1,
            content=content[:2000],
            tokens=mod_tokens,
            subwords=self.decompose_subwords(mod_tokens),
            language="javascript",
        )
        return [mod_unit] + units

    def chunk_lexical(self, file_path: str, content: str, language: str = "generic", chunk_size: int = 40, overlap: int = 10) -> List[CodeUnit]:
        """Fallback chunker for unsupported languages and unparseable source files."""
        lines = content.splitlines()
        units: List[CodeUnit] = []
        if not lines:
            return units

        step = max(1, chunk_size - overlap)
        for i in range(0, len(lines), step):
            chunk_lines = lines[i : i + chunk_size]
            start_l = i + 1
            end_l = min(len(lines), i + len(chunk_lines))
            chunk_text = "\n".join(chunk_lines)

            tokens = self.tokenize_identifiers(chunk_text[:1000])
            subwords = self.decompose_subwords(tokens)
            sig = f"span L{start_l}-L{end_l}"
            unit = CodeUnit(
                unit_id=f"{file_path}::L{start_l}-L{end_l}",
                file_path=file_path,
                unit_type=CodeUnitType.SOURCE_SPAN,
                symbol_name=f"L{start_l}-L{end_l}",
                qualified_name=f"{os.path.basename(file_path)}:L{start_l}",
                signature=sig,
                start_line=start_l,
                end_line=end_l,
                content=chunk_text[:2000],
                tokens=tokens,
                subwords=subwords,
                language=language,
            )
            units.append(unit)
        return units

    def index_file(self, file_path: str, content: str, language: Optional[str] = None) -> List[CodeUnit]:
        """Parses and indexes all code units for a single file."""
        # 1. Clean existing units for this file if updating
        self.remove_file(file_path)

        # 2. Detect language
        ext = os.path.splitext(file_path)[1].lower()
        if not language:
            if ext in (".py", ".pyi"):
                language = "python"
            elif ext in (".rs",):
                language = "rust"
            elif ext in (".js", ".jsx", ".ts", ".tsx", ".mjs"):
                language = "javascript"
            else:
                language = "generic"

        # 3. Parse units by language
        if language == "python":
            units = self.parse_python(file_path, content)
        elif language == "rust":
            units = self.parse_rust(file_path, content)
        elif language == "javascript":
            units = self.parse_javascript(file_path, content)
        else:
            units = self.chunk_lexical(file_path, content, language=language)

        # 4. Store in registry
        for u in units:
            self.units_by_id[u.unit_id] = u
            self.file_to_units[file_path].append(u.unit_id)
            self.symbol_to_units[u.symbol_name.lower()].append(u.unit_id)

        return units

    def remove_file(self, file_path: str):
        """Removes all indexed code units associated with a file (incremental support)."""
        old_unit_ids = self.file_to_units.pop(file_path, [])
        for uid in old_unit_ids:
            unit = self.units_by_id.pop(uid, None)
            if unit:
                sym_list = self.symbol_to_units.get(unit.symbol_name.lower(), [])
                if uid in sym_list:
                    sym_list.remove(uid)

    def get_file_units(self, file_path: str) -> List[CodeUnit]:
        return [self.units_by_id[uid] for uid in self.file_to_units.get(file_path, []) if uid in self.units_by_id]

