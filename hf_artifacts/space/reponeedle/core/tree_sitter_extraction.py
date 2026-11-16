"""
Optional Tree-sitter structural extraction for the function-level call graph.

This module converts Tree-sitter syntax trees for TypeScript/TSX, Go, Rust, Java and C++ into the
records used by :class:`reponeedle.core.function_graph.FunctionGraphEngine` (``FunctionSymbol``,
``CallSite``), plus import records that the graph engine resolves against repository files.

It is syntax-aware extraction, not semantic code intelligence: there is no type inference, overload
resolution, macro expansion or build-system awareness. Python is never handled here; it keeps the
existing ``ast``-based extraction.

The Tree-sitter runtime and grammars are optional dependencies (``pip install "reponeedle[treesitter]"``).
Nothing is imported until a parser is first requested, nothing is ever downloaded, and every load
failure is recorded so callers can fall back to the existing regex extraction and report why.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import os
import posixpath
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

# language id -> (grammar module, language factory, distribution name)
GRAMMARS: Dict[str, Tuple[str, str, str]] = {
    "typescript": ("tree_sitter_typescript", "language_typescript", "tree-sitter-typescript"),
    "tsx": ("tree_sitter_typescript", "language_tsx", "tree-sitter-typescript"),
    "go": ("tree_sitter_go", "language", "tree-sitter-go"),
    "rust": ("tree_sitter_rust", "language", "tree-sitter-rust"),
    "java": ("tree_sitter_java", "language", "tree-sitter-java"),
    "cpp": ("tree_sitter_cpp", "language", "tree-sitter-cpp"),
}

# Single source of truth for which files the Tree-sitter path handles.
EXTENSION_TO_LANGUAGE: Dict[str, str] = {
    ".ts": "typescript", ".mts": "typescript", ".cts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp", ".h": "cpp",
}

RUNTIME_DISTRIBUTION = "tree-sitter"


def detect_language(path: str) -> Optional[str]:
    """Returns the Tree-sitter language id for a file path, or None if this module does not handle it."""
    return EXTENSION_TO_LANGUAGE.get(os.path.splitext(path.replace("\\", "/").lower())[1])


def _dist_version(name: str) -> Optional[str]:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _import_module(name: str):
    """Indirection point so tests can simulate missing packages."""
    return importlib.import_module(name)


# ---------------------------------------------------------------------------
# Parser loading (lazy, cached per process, failures recorded)
# ---------------------------------------------------------------------------

_RUNTIME: Dict[str, Any] = {}
_LANGUAGES: Dict[str, Any] = {}
_LOAD_ERRORS: Dict[str, str] = {}
_PARSERS: Dict[str, Any] = {}


def _runtime():
    if "module" in _RUNTIME:
        return _RUNTIME["module"]
    if "error" in _RUNTIME:
        return None
    try:
        module = _import_module("tree_sitter")
        module.Parser  # noqa: B018 - attribute check
        module.Language  # noqa: B018
    except Exception as exc:  # ImportError, or an incompatible/broken installation
        _RUNTIME["error"] = f"{type(exc).__name__}: {exc}"
        return None
    _RUNTIME["module"] = module
    return module


def load_language(language: str):
    """Returns a tree_sitter.Language for ``language`` or None (the reason is in ``load_errors()``)."""
    if language in _LANGUAGES:
        return _LANGUAGES[language]
    if language in _LOAD_ERRORS:
        return None
    if language not in GRAMMARS:
        _LOAD_ERRORS[language] = "unsupported language"
        return None
    ts = _runtime()
    if ts is None:
        _LOAD_ERRORS[language] = f"tree-sitter runtime unavailable ({_RUNTIME.get('error')})"
        return None
    module_name, factory, dist = GRAMMARS[language]
    try:
        grammar = _import_module(module_name)
        lang = ts.Language(getattr(grammar, factory)())
    except Exception as exc:  # missing grammar package, or ABI incompatible with the runtime
        _LOAD_ERRORS[language] = f"{dist}: {type(exc).__name__}: {exc}"
        return None
    _LANGUAGES[language] = lang
    return lang


def load_errors() -> Dict[str, str]:
    return dict(_LOAD_ERRORS)


def reset_parser_cache() -> None:
    """Forgets loaded parsers and load failures (used by tests and after installing packages)."""
    _RUNTIME.clear()
    _LANGUAGES.clear()
    _LOAD_ERRORS.clear()
    _PARSERS.clear()


def tree_sitter_status(languages: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """
    Reports runtime and grammar availability without parsing anything.

    Returns ``{"runtime": {...}, "languages": {lang: {"available": bool, ...}}}``.
    """
    ts = _runtime()
    status: Dict[str, Any] = {
        "runtime": {
            "available": ts is not None,
            "version": _dist_version(RUNTIME_DISTRIBUTION),
            "error": _RUNTIME.get("error"),
        },
        "languages": {},
    }
    for lang in (GRAMMARS if languages is None else languages):
        loaded = load_language(lang)
        entry: Dict[str, Any] = {"available": loaded is not None,
                                 "grammar_version": _dist_version(GRAMMARS[lang][2]) if lang in GRAMMARS else None}
        if loaded is None:
            entry["error"] = _LOAD_ERRORS.get(lang)
        else:
            entry["abi_version"] = getattr(loaded, "abi_version", None)
        status["languages"][lang] = entry
    return status


# ---------------------------------------------------------------------------
# Extraction records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImportRecord:
    """
    One import-like declaration.

    kind:
        "module"         local_name is bound to a module/package (TS ``* as ns``, Go import, Rust module path)
        "symbol"         local_name is bound to a named item ``imported_name`` of the module ``spec``
        "default"        TS default import bound to local_name
        "class"          Java single-type import (local_name = simple class name)
        "static_member"  Java static import (local_name = member name, spec = class path)
        "path"           Rust ``use`` path; the last segment may name a module or an item
        "module_decl"    Rust ``mod name;`` (module in another file)
        "inline_module"  Rust ``mod name { ... }`` (module defined in this file)
        "wildcard"       glob import (Java ``.*``, Rust ``::*``, Go ``.``); recorded, never resolved
        "side_effect"    import without bindings (TS ``import "x"``, Go ``_``)
        "include"        C/C++ ``#include "x"``
        "system_include" C/C++ ``#include <x>``
    """
    spec: str
    kind: str
    local_name: Optional[str]
    imported_name: Optional[str]
    line: int


@dataclass
class TreeSitterExtraction:
    language: str
    functions: list = field(default_factory=list)   # List[FunctionSymbol]
    calls: list = field(default_factory=list)       # List[CallSite]
    symbols: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    import_records: List[ImportRecord] = field(default_factory=list)
    package: Optional[str] = None
    has_error: bool = False
    error_nodes: int = 0


# Node types that hold a dotted/scoped name chain for qualifiers.
_CHAIN_TYPES = {
    "member_expression", "selector_expression", "field_expression", "scoped_identifier",
    "qualified_identifier", "field_access", "scoped_type_identifier", "nested_namespace_specifier",
}
_LEAF_NAME_TYPES = {
    "identifier", "property_identifier", "field_identifier", "type_identifier", "package_identifier",
    "namespace_identifier", "this", "self", "super", "crate", "private_property_identifier",
}


class _Walker:
    """Language-specific conversion of one syntax tree into extraction records."""

    def __init__(self, language: str, src: bytes, filepath: str, is_test: bool):
        from reponeedle.core.function_graph import CallSite, FunctionSymbol  # local import: avoids a cycle
        self.CallSite = CallSite
        self.FunctionSymbol = FunctionSymbol
        self.language = language
        self.src = src
        self.filepath = filepath
        self.is_test = is_test
        self.out = TreeSitterExtraction(language=language)
        self._namespaces: Set[str] = set()

    # -- helpers -----------------------------------------------------------
    def text(self, node) -> str:
        return self.src[node.start_byte:node.end_byte].decode("utf-8", "replace")

    @staticmethod
    def line(node) -> int:
        return node.start_point[0] + 1

    def qual_path(self, node) -> Optional[List[str]]:
        """Splits a pure name chain (``a.b``, ``a::b``, ``a->b``, ``this.x``) into segments; None otherwise."""
        if node is None:
            return None
        t = node.type
        if t in _LEAF_NAME_TYPES:
            return [self.text(node)]
        if t in ("generic_type", "template_type"):
            inner = (node.child_by_field_name("type") or node.child_by_field_name("name")
                     or (node.named_children[0] if node.named_children else None))
            return self.qual_path(inner)
        if t in _CHAIN_TYPES:
            left = (node.child_by_field_name("object") or node.child_by_field_name("operand")
                    or node.child_by_field_name("value") or node.child_by_field_name("argument")
                    or node.child_by_field_name("path") or node.child_by_field_name("scope"))
            right = (node.child_by_field_name("property") or node.child_by_field_name("field")
                     or node.child_by_field_name("name"))
            if right is None:
                return None
            right_segs = self.qual_path(right)
            if right_segs is None:
                return None
            if left is None:  # e.g. C++ "::name" (global scope) or Rust "::name"
                return right_segs
            left_segs = self.qual_path(left)
            return None if left_segs is None else left_segs + right_segs
        return None

    def add_function(self, name: str, node, parent: Optional[str], is_method: bool, params) -> None:
        if not name:
            return
        self.out.functions.append(self.FunctionSymbol(
            name=name, parent_class=parent, filepath=self.filepath, is_method=is_method,
            is_test=self.is_test, start_line=self.line(node), arg_names=self.param_names(params),
        ))
        self.out.symbols.append(name)

    def add_call(self, callee: str, node, caller: Optional[str], qualifier_segs: Optional[List[str]],
                 is_attribute: bool, path_style: bool = False) -> None:
        """
        Records a call site. ``qualifier_path`` keeps the whole qualifier: member access is joined with
        "." (``this.repo``); path-style qualifiers (Rust/C++ ``a::b::f()``) are joined with "::" and end
        with "::" (``a::b::``), so that ``self::f()`` and ``self.f()`` stay distinguishable.
        """
        if not callee:
            return
        qualifier = qualifier_segs[-1] if qualifier_segs else None
        if qualifier_segs:
            qpath = ("::".join(qualifier_segs) + "::") if path_style else ".".join(qualifier_segs)
        else:
            qpath = None
        self.out.calls.append(self.CallSite(
            caller_path=self.filepath, caller_func=caller, callee_name=callee, is_attribute=is_attribute,
            qualifier=qualifier, start_line=self.line(node), qualifier_path=qpath,
        ))

    def param_names(self, params) -> List[str]:
        if params is None:
            return []
        names: List[str] = []
        for child in params.named_children:
            if self.language == "go" and child.type in ("parameter_declaration", "variadic_parameter_declaration"):
                names.extend(self.text(c) for c in child.named_children if c.type == "identifier")
                continue
            if child.type == "identifier":
                names.append(self.text(child))
                continue
            target = (child.child_by_field_name("pattern") or child.child_by_field_name("name")
                      or child.child_by_field_name("declarator"))
            while target is not None and target.type in ("pointer_declarator", "reference_declarator",
                                                         "array_declarator"):
                target = target.child_by_field_name("declarator") or (
                    target.named_children[-1] if target.named_children else None)
            if target is not None and target.type in ("identifier", "field_identifier"):
                names.append(self.text(target))
        return names

    # -- traversal ---------------------------------------------------------
    def run(self, root) -> TreeSitterExtraction:
        handler = getattr(self, f"_visit_{'typescript' if self.language == 'tsx' else self.language}")
        # (node, enclosing class name, enclosing function name)
        stack: List[Tuple[Any, Optional[str], Optional[str]]] = [(root, None, None)]
        while stack:
            node, cls, fn = stack.pop()
            if node.is_error:
                self.out.error_nodes += 1
            elif node.is_missing:
                self.out.error_nodes += 1
                continue
            new_cls, new_fn = handler(node, cls, fn)
            for child in reversed(node.named_children):
                stack.append((child, new_cls, new_fn))
        out = self.out
        out.symbols = list(dict.fromkeys(out.symbols))
        out.imports = list(dict.fromkeys(r.spec for r in out.import_records))
        return out

    def _container_class(self, node, cls: Optional[str], body_types: Set[str]) -> Optional[str]:
        """The enclosing class if ``node`` sits directly in a class body; otherwise None."""
        parent = node.parent
        while parent is not None and parent.type == "template_declaration":
            parent = parent.parent
        if parent is not None and parent.type in body_types:
            return cls
        return None

    # -- TypeScript / TSX --------------------------------------------------
    _TS_CLASS_TYPES = {"class_declaration", "abstract_class_declaration", "class"}
    _TS_FUNCTION_VALUES = {"arrow_function", "function_expression", "function", "generator_function"}

    def _visit_typescript(self, node, cls, fn):
        t = node.type
        if t in self._TS_CLASS_TYPES:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = self.text(name_node)
                self.out.symbols.append(name)
                return name, fn
            return cls, fn
        if t in ("interface_declaration", "enum_declaration", "type_alias_declaration"):
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                self.out.symbols.append(self.text(name_node))
            return cls, fn
        if t in ("function_declaration", "generator_function_declaration"):
            name_node = node.child_by_field_name("name")
            name = self.text(name_node) if name_node is not None else ""
            self.add_function(name, node, None, False, node.child_by_field_name("parameters"))
            return cls, (name or fn)
        if t == "method_definition":
            name = self.text(node.child_by_field_name("name"))
            parent = self._container_class(node, cls, {"class_body"})
            self.add_function(name, node, parent, parent is not None, node.child_by_field_name("parameters"))
            return cls, name
        if t in ("variable_declarator", "public_field_definition"):
            value = node.child_by_field_name("value")
            name_node = node.child_by_field_name("name")
            if value is not None and value.type in self._TS_FUNCTION_VALUES and name_node is not None \
                    and name_node.type in ("identifier", "property_identifier", "private_property_identifier"):
                name = self.text(name_node)
                parent = self._container_class(node, cls, {"class_body"}) if t == "public_field_definition" else None
                self.add_function(name, node, parent, parent is not None, value.child_by_field_name("parameters"))
                return cls, name
            return cls, fn
        if t == "call_expression":
            func = node.child_by_field_name("function")
            if func is None:
                return cls, fn
            if func.type == "identifier":
                self.add_call(self.text(func), node, fn, None, False)
            elif func.type == "member_expression":
                prop = func.child_by_field_name("property")
                if prop is not None:
                    self.add_call(self.text(prop), node, fn, self.qual_path(func.child_by_field_name("object")), True)
            return cls, fn
        if t == "new_expression":
            ctor = node.child_by_field_name("constructor")
            segs = self.qual_path(ctor)
            if segs:
                self.add_call(segs[-1], node, fn, segs[:-1] or None, len(segs) > 1)
            return cls, fn
        if t == "import_statement":
            self._ts_import(node)
            return cls, fn
        return cls, fn

    def _ts_import(self, node) -> None:
        line = self.line(node)
        require = next((c for c in node.named_children if c.type == "import_require_clause"), None)
        if require is not None:  # import x = require("y")
            source = require.child_by_field_name("source")
            ident = next((c for c in require.named_children if c.type == "identifier"), None)
            if source is not None and ident is not None:
                spec = self.text(source).strip("'\"`")
                self.out.import_records.append(ImportRecord(spec, "module", self.text(ident), None, line))
            return
        source = node.child_by_field_name("source")
        if source is None:
            return
        spec = self.text(source).strip("'\"`")
        clause = next((c for c in node.named_children if c.type == "import_clause"), None)
        if clause is None:
            self.out.import_records.append(ImportRecord(spec, "side_effect", None, None, line))
            return
        for part in clause.named_children:
            if part.type == "identifier":
                self.out.import_records.append(ImportRecord(spec, "default", self.text(part), "default", line))
            elif part.type == "namespace_import":
                ident = next((c for c in part.named_children if c.type == "identifier"), None)
                if ident is not None:
                    self.out.import_records.append(ImportRecord(spec, "module", self.text(ident), None, line))
            elif part.type == "named_imports":
                for spec_node in part.named_children:
                    if spec_node.type != "import_specifier":
                        continue
                    name = spec_node.child_by_field_name("name")
                    alias = spec_node.child_by_field_name("alias")
                    if name is None:
                        continue
                    imported = self.text(name)
                    local = self.text(alias) if alias is not None else imported
                    self.out.import_records.append(ImportRecord(spec, "symbol", local, imported, line))

    # -- Go ----------------------------------------------------------------
    def _visit_go(self, node, cls, fn):
        t = node.type
        if t == "package_clause":
            ident = next((c for c in node.named_children if c.type == "package_identifier"), None)
            if ident is not None:
                self.out.package = self.text(ident)
            return cls, fn
        if t == "function_declaration":
            name = self.text(node.child_by_field_name("name"))
            self.add_function(name, node, None, False, node.child_by_field_name("parameters"))
            return cls, name
        if t == "method_declaration":
            name = self.text(node.child_by_field_name("name"))
            receiver = self._go_receiver_type(node.child_by_field_name("receiver"))
            self.add_function(name, node, receiver, True, node.child_by_field_name("parameters"))
            return cls, name
        if t == "type_spec" or t == "type_alias":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                self.out.symbols.append(self.text(name_node))
            return cls, fn
        if t == "call_expression":
            func = node.child_by_field_name("function")
            if func is not None and func.type == "identifier":
                self.add_call(self.text(func), node, fn, None, False)
            elif func is not None and func.type == "selector_expression":
                fld = func.child_by_field_name("field")
                if fld is not None:
                    self.add_call(self.text(fld), node, fn, self.qual_path(func.child_by_field_name("operand")), True)
            return cls, fn
        if t == "import_spec":
            path_node = node.child_by_field_name("path")
            if path_node is None:
                return cls, fn
            spec = self.text(path_node).strip('"`')
            name_node = node.child_by_field_name("name")
            line = self.line(node)
            if name_node is None:
                self.out.import_records.append(ImportRecord(spec, "module", spec.rsplit("/", 1)[-1], None, line))
            elif name_node.type == "blank_identifier":
                self.out.import_records.append(ImportRecord(spec, "side_effect", None, None, line))
            elif name_node.type == "dot":
                self.out.import_records.append(ImportRecord(spec, "wildcard", None, None, line))
            else:
                self.out.import_records.append(ImportRecord(spec, "module", self.text(name_node), None, line))
            return cls, fn
        return cls, fn

    def _go_receiver_type(self, receiver) -> Optional[str]:
        if receiver is None:
            return None
        decl = next((c for c in receiver.named_children if c.type == "parameter_declaration"), None)
        typ = decl.child_by_field_name("type") if decl is not None else None
        while typ is not None and typ.type in ("pointer_type", "generic_type", "parenthesized_type"):
            typ = typ.child_by_field_name("type") or (typ.named_children[0] if typ.named_children else None)
        return self.text(typ) if typ is not None and typ.type == "type_identifier" else None

    # -- Rust --------------------------------------------------------------
    def _visit_rust(self, node, cls, fn):
        t = node.type
        if t == "impl_item":
            typ = node.child_by_field_name("type")
            segs = self.qual_path(typ)
            return (segs[-1] if segs else cls), fn
        if t == "trait_item":
            name = self.text(node.child_by_field_name("name"))
            self.out.symbols.append(name)
            return name, fn
        if t in ("struct_item", "enum_item", "union_item", "type_item"):
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                self.out.symbols.append(self.text(name_node))
            return cls, fn
        if t == "function_item":
            name = self.text(node.child_by_field_name("name"))
            parent = self._container_class(node, cls, {"declaration_list"})
            if parent is not None and node.parent is not None and node.parent.parent is not None \
                    and node.parent.parent.type not in ("impl_item", "trait_item"):
                parent = None  # function inside `mod { }`, not an impl/trait
            self.add_function(name, node, parent, parent is not None, node.child_by_field_name("parameters"))
            return cls, name
        if t == "mod_item":
            name = self.text(node.child_by_field_name("name"))
            kind = "inline_module" if node.child_by_field_name("body") is not None else "module_decl"
            self.out.import_records.append(ImportRecord(f"self::{name}", kind, name, None, self.line(node)))
            return None, fn
        if t == "call_expression":
            func = node.child_by_field_name("function")
            if func is not None and func.type == "generic_function":
                func = func.child_by_field_name("function")
            if func is None:
                return cls, fn
            if func.type == "identifier":
                self.add_call(self.text(func), node, fn, None, False)
            elif func.type == "scoped_identifier":
                segs = self.qual_path(func)
                if segs and len(segs) >= 2:
                    qual = segs[:-1]
                    if qual == ["Self"] and cls:
                        qual = [cls]
                    self.add_call(segs[-1], node, fn, qual, True, path_style=True)
            elif func.type == "field_expression":
                fld = func.child_by_field_name("field")
                if fld is not None:
                    self.add_call(self.text(fld), node, fn, self.qual_path(func.child_by_field_name("value")), True)
            return cls, fn
        if t == "use_declaration":
            arg = node.child_by_field_name("argument")
            for segs, local, wildcard in self._rust_use_paths(arg, []):
                spec = "::".join(segs)
                if wildcard:
                    self.out.import_records.append(ImportRecord(spec + "::*", "wildcard", None, None, self.line(node)))
                elif segs:
                    self.out.import_records.append(ImportRecord(spec, "path", local, segs[-1], self.line(node)))
            return cls, fn
        return cls, fn

    def _rust_use_paths(self, node, prefix: List[str]):
        """Expands a use-tree into (segments, local name, is_wildcard) triples."""
        if node is None:
            return []
        t = node.type
        if t in ("identifier", "crate", "self", "super", "metavariable"):
            seg = self.text(node)
            if seg == "self" and prefix:  # `use a::{self}` binds `a`
                return [(list(prefix), prefix[-1], False)]
            return [(prefix + [seg], seg, False)]
        if t == "scoped_identifier":
            segs = self.qual_path(node) or []
            return [(prefix + segs, segs[-1] if segs else None, False)]
        if t == "use_as_clause":
            path = node.child_by_field_name("path")
            alias = node.child_by_field_name("alias")
            segs = self.qual_path(path) or []
            return [(prefix + segs, self.text(alias) if alias is not None else (segs[-1] if segs else None), False)]
        if t == "scoped_use_list":
            path = node.child_by_field_name("path")
            new_prefix = prefix + (self.qual_path(path) or []) if path is not None else prefix
            return self._rust_use_paths(node.child_by_field_name("list"), new_prefix)
        if t == "use_list":
            out = []
            for child in node.named_children:
                out.extend(self._rust_use_paths(child, prefix))
            return out
        if t == "use_wildcard":
            inner = node.named_children[0] if node.named_children else None
            segs = prefix + (self.qual_path(inner) or []) if inner is not None else prefix
            return [(segs, None, True)]
        return []

    # -- Java --------------------------------------------------------------
    _JAVA_CLASS_TYPES = {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration",
                         "annotation_type_declaration"}
    _JAVA_BODY_TYPES = {"class_body", "interface_body", "enum_body_declarations", "enum_body", "record_body",
                        "annotation_type_body"}

    def _visit_java(self, node, cls, fn):
        t = node.type
        if t == "package_declaration":
            name = next((c for c in node.named_children if c.type in ("scoped_identifier", "identifier")), None)
            if name is not None:
                self.out.package = self.text(name)
            return cls, fn
        if t in self._JAVA_CLASS_TYPES:
            name = self.text(node.child_by_field_name("name"))
            self.out.symbols.append(name)
            return name, fn
        if t in ("method_declaration", "constructor_declaration", "compact_constructor_declaration"):
            name = self.text(node.child_by_field_name("name"))
            parent = self._container_class(node, cls, self._JAVA_BODY_TYPES) or cls
            self.add_function(name, node, parent, parent is not None, node.child_by_field_name("parameters"))
            return cls, name
        if t == "method_invocation":
            name = node.child_by_field_name("name")
            obj = node.child_by_field_name("object")
            if name is not None:
                segs = self.qual_path(obj) if obj is not None else None
                self.add_call(self.text(name), node, fn, segs, obj is not None)
            return cls, fn
        if t == "object_creation_expression":
            segs = self.qual_path(node.child_by_field_name("type"))
            if segs:
                self.add_call(segs[-1], node, fn, segs[:-1] or None, len(segs) > 1)
            return cls, fn
        if t == "import_declaration":
            path_node = next((c for c in node.named_children if c.type in ("scoped_identifier", "identifier")), None)
            if path_node is None:
                return cls, fn
            path = self.text(path_node)
            is_static = any(c.type == "static" for c in node.children)
            wildcard = any(c.type == "asterisk" for c in node.children)
            line = self.line(node)
            last = path.rsplit(".", 1)[-1]
            if wildcard:
                self.out.import_records.append(ImportRecord(path + ".*", "wildcard", None, None, line))
            elif is_static:
                self.out.import_records.append(ImportRecord(path.rsplit(".", 1)[0], "static_member", last, last, line))
            else:
                self.out.import_records.append(ImportRecord(path, "class", last, last, line))
            return cls, fn
        return cls, fn

    # -- C++ ---------------------------------------------------------------
    def _visit_cpp(self, node, cls, fn):
        t = node.type
        if t == "namespace_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                self._namespaces.update((self.qual_path(name_node) or [self.text(name_node)]))
            return cls, fn
        if t in ("class_specifier", "struct_specifier", "union_specifier"):
            name_node = node.child_by_field_name("name")
            if name_node is not None and node.child_by_field_name("body") is not None:
                segs = self.qual_path(name_node) or [self.text(name_node)]
                self.out.symbols.append(segs[-1])
                return segs[-1], fn
            return cls, fn
        if t == "enum_specifier":
            name_node = node.child_by_field_name("name")
            if name_node is not None and node.child_by_field_name("body") is not None:
                self.out.symbols.append(self.text(name_node))
            return cls, fn
        if t == "function_definition":
            decl = self._cpp_function_declarator(node.child_by_field_name("declarator"))
            if decl is None:
                return cls, fn
            name, parent = self._cpp_function_name(decl.child_by_field_name("declarator"), node, cls)
            self.add_function(name, node, parent, parent is not None, decl.child_by_field_name("parameters"))
            return cls, (name or fn)
        if t == "call_expression":
            func = node.child_by_field_name("function")
            if func is not None and func.type == "template_function":
                func = func.child_by_field_name("name")
            if func is None:
                return cls, fn
            if func.type == "identifier":
                self.add_call(self.text(func), node, fn, None, False)
            elif func.type == "qualified_identifier":
                segs = self.qual_path(func)
                if segs:
                    self.add_call(segs[-1], node, fn, segs[:-1] or None, len(segs) > 1, path_style=True)
            elif func.type == "field_expression":
                fld = func.child_by_field_name("field")
                if fld is not None:
                    self.add_call(self.text(fld), node, fn, self.qual_path(func.child_by_field_name("argument")), True)
            return cls, fn
        if t == "new_expression":
            segs = self.qual_path(node.child_by_field_name("type"))
            if segs:
                self.add_call(segs[-1], node, fn, segs[:-1] or None, len(segs) > 1, path_style=True)
            return cls, fn
        if t == "preproc_include":
            path_node = node.child_by_field_name("path")
            if path_node is not None:
                raw = self.text(path_node)
                kind = "system_include" if path_node.type == "system_lib_string" else "include"
                self.out.import_records.append(ImportRecord(raw.strip('"<>'), kind, None, None, self.line(node)))
            return cls, fn
        return cls, fn

    @staticmethod
    def _cpp_function_declarator(decl):
        while decl is not None and decl.type in ("pointer_declarator", "reference_declarator", "attributed_declarator",
                                                 "parenthesized_declarator"):
            decl = decl.child_by_field_name("declarator") or (decl.named_children[-1] if decl.named_children else None)
        return decl if decl is not None and decl.type == "function_declarator" else None

    def _cpp_function_name(self, target, node, cls) -> Tuple[str, Optional[str]]:
        if target is None:
            return "", None
        if target.type == "qualified_identifier":
            scope_segs: List[str] = []
            cur = target
            while cur is not None and cur.type == "qualified_identifier":
                scope = cur.child_by_field_name("scope")
                if scope is not None:
                    scope_segs.extend(self.qual_path(scope) or [self.text(scope)])
                cur = cur.child_by_field_name("name")
            name = self.text(cur) if cur is not None else ""
            if cur is not None and cur.type == "template_function":
                name = self.text(cur.child_by_field_name("name"))
            parent = scope_segs[-1] if scope_segs else None
            if parent is not None and parent in self._namespaces:
                parent = None  # `ns::free_function()` — a namespace, not a class
            return name, parent
        if target.type == "template_function":
            return self.text(target.child_by_field_name("name")), self._container_class(node, cls, {"field_declaration_list"})
        # identifier, field_identifier, destructor_name, operator_name
        return self.text(target), self._container_class(node, cls, {"field_declaration_list"})


def extract(content: str, filepath: str, language: str, is_test: bool) -> Optional[TreeSitterExtraction]:
    """
    Parses ``content`` and returns the extraction, or None if no parser is available for ``language``.
    Syntax errors do not raise: Tree-sitter returns a partial tree, which is extracted and flagged.
    """
    lang = load_language(language)
    if lang is None:
        return None
    parser = _PARSERS.get(language)
    if parser is None:
        parser = _PARSERS[language] = _runtime().Parser(lang)
    src = content.encode("utf-8", "surrogatepass")
    tree = parser.parse(src)
    out = _Walker(language, src, filepath, is_test).run(tree.root_node)
    out.has_error = bool(tree.root_node.has_error)
    return out


# ---------------------------------------------------------------------------
# Import resolution against repository files
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImportResolution:
    status: str               # "resolved", "external", "unresolved", "not_applicable"
    files: Tuple[str, ...] = ()


_TS_EXTENSIONS = (".ts", ".tsx", ".d.ts", ".mts", ".cts")


class ImportResolver:
    """Maps import records to repository files. Purely syntactic and path-based; never guesses."""

    def __init__(self, doc_paths: Sequence[str], extractions: Dict[str, TreeSitterExtraction],
                 go_modules: Sequence[Tuple[str, str]], rust_crates: Sequence[Tuple[str, str]] = ()):
        self.paths = [p.replace("\\", "/") for p in doc_paths]
        self.path_set = set(self.paths)
        self._by_basename: Dict[str, List[str]] = {}
        for p in self.paths:
            self._by_basename.setdefault(posixpath.basename(p), []).append(p)
        self.extractions = extractions
        self.go_modules = sorted(go_modules, key=lambda m: -len(m[1]))  # (module dir, module path)
        self._go_dirs: Dict[str, List[str]] = {}
        for p in self.paths:
            if p.endswith(".go"):
                self._go_dirs.setdefault(posixpath.dirname(p), []).append(p)
        self._rust_crates = {name: root for name, root in rust_crates}  # crate name -> crate root dir
        self._rust_modules = self._index_rust_modules()
        self._rust_module_by_path = {p: key for key, p in self._rust_modules.items()}

    # TypeScript ----------------------------------------------------------
    def _resolve_ts(self, importer: str, spec: str) -> ImportResolution:
        if not spec.startswith("."):
            return ImportResolution("external")
        base = posixpath.normpath(posixpath.join(posixpath.dirname(importer), spec))
        stem = base
        for js_ext, ts_exts in ((".js", (".ts", ".tsx")), (".jsx", (".tsx",)), (".mjs", (".mts",)), (".cjs", (".cts",))):
            if base.endswith(js_ext):
                stem = base[: -len(js_ext)]
                for ext in ts_exts:
                    if stem + ext in self.path_set:
                        return ImportResolution("resolved", (stem + ext,))
        candidates = [base] if base in self.path_set else []
        candidates += [stem + ext for ext in _TS_EXTENSIONS] + [f"{stem}/index{ext}" for ext in (".ts", ".tsx")]
        for cand in candidates:
            if cand in self.path_set:
                return ImportResolution("resolved", (cand,))
        return ImportResolution("unresolved")

    # Go --------------------------------------------------------------------
    def _resolve_go(self, spec: str) -> ImportResolution:
        for mod_dir, mod_path in self.go_modules:
            if spec == mod_path or spec.startswith(mod_path + "/"):
                rel = spec[len(mod_path):].lstrip("/")
                pkg_dir = posixpath.normpath(posixpath.join(mod_dir, rel)) if rel else (mod_dir or ".")
                pkg_dir = "" if pkg_dir == "." else pkg_dir
                files = tuple(sorted(self._go_dirs.get(pkg_dir, [])))
                return ImportResolution("resolved", files) if files else ImportResolution("unresolved")
        if self.go_modules or "/" not in spec:
            return ImportResolution("external")
        # No go.mod in the repository: match multi-segment import paths by directory suffix.
        matches = [d for d in self._go_dirs if d and (spec == d or spec.endswith("/" + d))]
        if len(matches) == 1:
            return ImportResolution("resolved", tuple(sorted(self._go_dirs[matches[0]])))
        return ImportResolution("unresolved" if matches else "external")

    # Java -------------------------------------------------------------------
    def _resolve_java_class(self, class_path: str) -> ImportResolution:
        suffix = class_path.replace(".", "/") + ".java"
        matches = [p for p in self._by_basename.get(posixpath.basename(suffix), [])
                   if p == suffix or p.endswith("/" + suffix)]
        if len(matches) == 1:
            return ImportResolution("resolved", (matches[0],))
        return ImportResolution("unresolved" if matches else "external")

    # Rust -------------------------------------------------------------------
    def _index_rust_modules(self) -> Dict[Tuple[str, Tuple[str, ...]], str]:
        index: Dict[Tuple[str, Tuple[str, ...]], str] = {}
        for p in self.paths:
            if not p.endswith(".rs"):
                continue
            root = self._rust_crate_root(p)
            rel = p[len(root) + 1:] if root else p
            segs = rel[:-3].split("/")
            if segs[-1] in ("mod", "lib", "main") and (segs[-1] == "mod" or len(segs) == 1):
                segs = segs[:-1]
            index[(root, tuple(segs))] = p
        return index

    def _rust_crate_root(self, path: str) -> str:
        d = posixpath.dirname(path)
        while True:
            if f"{d}/lib.rs" in self.path_set or f"{d}/main.rs" in self.path_set or \
                    (not d and ("lib.rs" in self.path_set or "main.rs" in self.path_set)):
                return d
            if not d:
                return posixpath.dirname(path)
            d = posixpath.dirname(d)

    def _rust_module_of(self, path: str) -> Tuple[str, Tuple[str, ...]]:
        key = self._rust_module_by_path.get(path)
        return key if key is not None else (self._rust_crate_root(path), ())

    def resolve_rust_path(self, importer: str, segs: Sequence[str]) -> Tuple[ImportResolution, Optional[str]]:
        """Resolves a Rust path to (module file, item name or None if the path names the module itself)."""
        if not segs:
            return ImportResolution("unresolved"), None
        root, current = self._rust_module_of(importer)
        segs = list(segs)
        if segs[0] == "crate":
            absolute = segs[1:]
        elif segs[0] in self._rust_crates and (self._rust_crates[segs[0]], ()) in self._rust_modules:
            root = self._rust_crates[segs[0]]  # `use mycrate::a::b` from tests/, examples/, other crates
            absolute = segs[1:]
        elif segs[0] == "self":
            absolute = list(current) + segs[1:]
        elif segs[0] == "super":
            base = list(current)
            while segs and segs[0] == "super":
                base = base[:-1]
                segs = segs[1:]
            absolute = base + segs
        elif (root, tuple(current) + (segs[0],)) in self._rust_modules:
            absolute = list(current) + segs
        elif (root, (segs[0],)) in self._rust_modules:
            absolute = segs
        else:
            return ImportResolution("external"), None
        if (root, tuple(absolute)) in self._rust_modules:
            return ImportResolution("resolved", (self._rust_modules[(root, tuple(absolute))],)), None
        if absolute and (root, tuple(absolute[:-1])) in self._rust_modules:
            return ImportResolution("resolved", (self._rust_modules[(root, tuple(absolute[:-1]))],)), absolute[-1]
        return ImportResolution("unresolved"), None

    # C++ ----------------------------------------------------------------------
    def _resolve_include(self, importer: str, spec: str) -> ImportResolution:
        local = posixpath.normpath(posixpath.join(posixpath.dirname(importer), spec))
        if local in self.path_set:
            return ImportResolution("resolved", (local,))
        matches = [p for p in self._by_basename.get(posixpath.basename(spec), [])
                   if p == spec or p.endswith("/" + spec)]
        if len(matches) == 1:
            return ImportResolution("resolved", (matches[0],))
        return ImportResolution("unresolved" if matches else "external")

    # Public ----------------------------------------------------------------------
    def resolve(self, importer: str, language: str, record: ImportRecord) -> ImportResolution:
        if record.kind in ("wildcard", "side_effect", "system_include"):
            return ImportResolution("not_applicable" if record.kind != "system_include" else "external")
        if language in ("typescript", "tsx"):
            return self._resolve_ts(importer, record.spec)
        if language == "go":
            return self._resolve_go(record.spec)
        if language == "java":
            return self._resolve_java_class(record.spec)
        if language == "cpp":
            return self._resolve_include(importer, record.spec)
        if language == "rust":
            if record.kind == "inline_module":
                return ImportResolution("resolved", (importer,))
            resolution, _item = self.resolve_rust_path(importer, record.spec.split("::"))
            return resolution
        return ImportResolution("not_applicable")
