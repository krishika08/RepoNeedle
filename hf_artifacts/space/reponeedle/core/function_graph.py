"""
Production Function-Level Call Graph Engine for RepoNeedle.

Implements high-precision, language-aware AST extraction, call-site resolution,
symbol disambiguation, and directed call-graph construction for code retrieval.
"""

from __future__ import annotations

import os
import ast
import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Any
from collections import defaultdict
import networkx as nx

from reponeedle.models import FileDoc
from reponeedle.core.signatures import stable_signature

logger = logging.getLogger("reponeedle.function_graph")

# "regex": the 1.2.0 extraction (Python ast + regular expressions), the default.
# "tree_sitter": opt-in syntax-tree extraction for TypeScript/TSX, Go, Rust, Java and C++ when the optional
# `treesitter` extra is installed; every other file, and any file whose grammar is unavailable, uses "regex".
STRUCTURAL_PARSERS = ("regex", "tree_sitter")

GENERIC_METHOD_NAMES = {
    "get", "set", "run", "init", "exec", "call", "close", "read", "write",
    "test", "main", "start", "stop", "send", "parse", "update", "format",
    "error", "string", "add", "remove", "clear", "pop", "copy", "load",
    "save", "reset", "handle", "dispatch", "process", "emit", "on", "off",
    "render", "build", "create", "make", "delete", "destroy", "open",
    "connect", "disconnect", "listen", "accept", "bind", "check", "validate",
}

PYTHON_BUILTINS = {
    "len", "print", "range", "int", "str", "float", "bool", "dict", "list",
    "set", "tuple", "enumerate", "zip", "map", "filter", "any", "all",
    "min", "max", "sum", "sorted", "reversed", "isinstance", "issubclass",
    "getattr", "setattr", "hasattr", "delattr", "repr", "iter", "next",
    "open", "super", "type", "id", "hash", "callable", "vars", "dir",
}


@dataclass
class FunctionSymbol:
    name: str
    parent_class: Optional[str]
    filepath: str
    is_method: bool
    is_test: bool
    start_line: int
    arg_names: List[str] = field(default_factory=list)


@dataclass
class CallSite:
    caller_path: str
    caller_func: Optional[str]
    callee_name: str
    is_attribute: bool
    qualifier: Optional[str]
    start_line: int
    # Full qualifier as written (Tree-sitter extraction only): "a.b" for member access, "a::b::" for
    # path-qualified calls. None for unqualified calls and for the Python/regex extractors.
    qualifier_path: Optional[str] = None


@dataclass
class FunctionGraphEdge:
    source_path: str
    target_path: str
    source_func: Optional[str]
    target_func: Optional[str]
    edge_type: str  # 'verified_call', 'intra_file_call', 'unique_global_call', 'directory_local_call', 'structural_method_call', 'scip_reference'
    confidence: float
    # SCIP-derived edges only: the exact SCIP symbol identifiers and the producing indexer.
    source_symbol: Optional[str] = None
    target_symbol: Optional[str] = None
    provenance: Optional[str] = None


# Bump when an extractor changes its output for the same (path, content).
POLYGLOT_SIGNATURE_VERSION = "function-graph-polyglot/1"
TREE_SITTER_SIGNATURE_VERSION = "function-graph-tree-sitter/1"

# Typed lookup keys of the default (regex/AST) resolver (V2 Stage 2, design section 9.2). Every lookup the
# resolver makes into a structure built from OTHER files goes through ``_FunctionLookup``, which records the key.
# A file's resolved edges are therefore a function of its own extraction plus the values of the keys it consumed.
KEY_MODULE = "fg.module:"      # module_to_path[q]                      -> path or None
KEY_DEFINES = "fg.def:"        # does file P define a function named n   -> bool          ("fg.def:P\0n")
KEY_CLASS_METHOD = "fg.cmeth:" # files of class q's methods named n      -> ordered paths ("fg.cmeth:q\0n")
KEY_FUNCTION = "fg.func:"      # every definition of a function named n  -> ordered paths (with multiplicity)
KEY_METHOD = "fg.meth:"        # files defining a method named n         -> sorted distinct paths
KEY_SEP = "\x00"
# Bump when the regex resolver's edges can change for the same inputs and key values.
RESOLVER_VERSION = "function-graph-resolver/2"


@dataclass
class FileResolution:
    """
    One caller file's resolved contribution: its edges, in resolution order, as
    (target_path, source_func, target_func, edge_type, confidence), plus the sorted typed keys the resolver consulted
    (empty unless resolution was tracked).
    """
    edges: List[Tuple[str, Optional[str], str, str, float]]
    consumed: Tuple[str, ...] = ()


class _FunctionLookup:
    """
    Read-only lookup indexes for one build, built once from the ordered document set. They replace the per-call scans
    of the 1.2.0 resolver (local functions, a module's functions, class methods and the scan of every class for an
    attribute call) with dictionary lookups that return exactly the same values in the same order.
    """

    def __init__(self, module_to_path, doc_functions, func_name_to_defs, class_to_methods):
        self.module_to_path = module_to_path
        self.names_of = {p: frozenset(f.name for f in fs) for p, fs in doc_functions.items()}
        self.func_paths = {n: tuple(f.filepath for f in defs) for n, defs in func_name_to_defs.items()}
        class_method: Dict[Tuple[str, str], List[str]] = {}
        method_paths: Dict[str, Dict[str, None]] = {}
        for cls, pairs in class_to_methods.items():          # class insertion order, then definition order
            for m, p in pairs:
                class_method.setdefault((cls, m), []).append(p)
                method_paths.setdefault(m, {})[p] = None
        self.class_method = {k: tuple(v) for k, v in class_method.items()}
        # Step E only asks whether exactly ONE file defines the method; the files are kept as a sorted set, so the
        # value depends only on which files define it (not on the global class order).
        self.method_paths = {k: tuple(sorted(v)) for k, v in method_paths.items()}
        self.track: Optional[Set[str]] = None

    def module(self, q: str) -> Optional[str]:
        if self.track is not None:
            self.track.add(KEY_MODULE + q)
        return self.module_to_path.get(q)

    def defines(self, path: str, name: str) -> bool:
        if self.track is not None:
            self.track.add(KEY_DEFINES + path + KEY_SEP + name)
        return name in self.names_of.get(path, ())

    def class_methods(self, cls: str, name: str) -> Tuple[str, ...]:
        if self.track is not None:
            self.track.add(KEY_CLASS_METHOD + cls + KEY_SEP + name)
        return self.class_method.get((cls, name), ())

    def function_paths(self, name: str) -> Tuple[str, ...]:
        if self.track is not None:
            self.track.add(KEY_FUNCTION + name)
        return self.func_paths.get(name, ())

    def method_files(self, name: str) -> Tuple[str, ...]:
        if self.track is not None:
            self.track.add(KEY_METHOD + name)
        return self.method_paths.get(name, ())

    def value(self, key: str) -> Any:
        """The current value of a typed key, exactly as the resolver sees it (JSON-compatible)."""
        if key.startswith(KEY_MODULE):
            return self.module_to_path.get(key[len(KEY_MODULE):])
        if key.startswith(KEY_DEFINES):
            path, name = key[len(KEY_DEFINES):].split(KEY_SEP, 1)
            return name in self.names_of.get(path, ())
        if key.startswith(KEY_CLASS_METHOD):
            cls, name = key[len(KEY_CLASS_METHOD):].split(KEY_SEP, 1)
            return list(self.class_method.get((cls, name), ()))
        if key.startswith(KEY_FUNCTION):
            return list(self.func_paths.get(key[len(KEY_FUNCTION):], ()))
        if key.startswith(KEY_METHOD):
            return list(self.method_paths.get(key[len(KEY_METHOD):], ()))
        raise KeyError(f"unknown function-graph key {key!r}")


def _module_keys(path: str, normalize) -> List[str]:
    norm_p = path.replace("\\", "/")
    raw_p = norm_p[:-3] if norm_p.endswith(".py") else norm_p
    mod_name = normalize(path)
    keys = [raw_p.replace("/", "."), mod_name]
    if "." in mod_name:
        keys.append(mod_name.split(".")[-1])
    return keys


def function_graph_provides(path: str, funcs: List["FunctionSymbol"], normalize) -> List[Tuple[str, str]]:
    """
    The provider events of one file, in emission order: (typed key, contributed value). For every key, the
    concatenation of all files' events in discovery order determines the value the resolver reads (last-wins module
    map, ordered definition lists, class-method lists, method files).
    """
    events = [(KEY_MODULE + k, path) for k in _module_keys(path, normalize)]
    for f in funcs:
        events.append((KEY_FUNCTION + f.name, f.filepath))
        events.append((KEY_DEFINES + path + KEY_SEP + f.name, path))
        if f.parent_class:
            events.append((KEY_CLASS_METHOD + f.parent_class + KEY_SEP + f.name, path))
            events.append((KEY_METHOD + f.name, path))
    return events


class FunctionGraphEngine:
    """
    Constructs fine-grained function-level call graphs across repositories.
    """

    def __init__(
        self,
        enable_verified_calls: bool = True,
        enable_structural_edges: bool = True,
        min_confidence: float = 0.60,
        structural_parser: str = "regex",
    ):
        if structural_parser not in STRUCTURAL_PARSERS:
            raise ValueError(
                f"structural_parser must be one of {STRUCTURAL_PARSERS}, got {structural_parser!r}"
            )
        self.enable_verified_calls = enable_verified_calls
        self.enable_structural_edges = enable_structural_edges
        self.min_confidence = min_confidence
        self.structural_parser = structural_parser
        self._ts_cache: Dict[str, Tuple[str, Any]] = {}
        # Optional SCIP evidence (reponeedle.core.scip_ingestion.ScipIndex, root already validated).
        self.scip_index: Optional[Any] = None
        self.scip_relationships: List[Any] = []

        self.graph = nx.DiGraph()
        self.docs: List[FileDoc] = []
        self.doc_paths: List[str] = []
        self.path_to_idx: Dict[str, int] = {}
        self.module_to_path: Dict[str, str] = {}
        self.package_to_files: Dict[str, List[str]] = {}

        # Symbol registries
        self.functions: List[FunctionSymbol] = []
        self.call_sites: List[CallSite] = []
        self.edges: List[FunctionGraphEdge] = []
        self.file_to_file_edges: Dict[Tuple[str, str], List[FunctionGraphEdge]] = defaultdict(list)

        # Adjacency caches for fast retrieval propagation
        self.callers_map: Dict[str, Dict[str, float]] = defaultdict(dict)  # callee -> {caller: conf}
        self.callees_map: Dict[str, Dict[str, float]] = defaultdict(dict)  # caller -> {callee: conf}

        self.diagnostics: Dict[str, Any] = {}
        # Set by RepoNeedleEngine when a requested SCIP index could not be loaded; kept across builds.
        self.scip_load_diagnostics: Optional[Dict[str, Any]] = None
        self._ts_norm_to_path: Dict[str, str] = {}
        self._ts_resolver: Optional[Any] = None
        self._polyglot_cache: Dict[str, Tuple[str, Tuple[List[FunctionSymbol], List[CallSite], List[str], List[str]]]] = {}
        # Per-build state of the default resolver (V2 Stage 2): lookup indexes and, when a build is tracked or given a
        # reuse hook, each caller file's resolution. Neither is part of the index's retrieval state.
        self._lookup: Optional[_FunctionLookup] = None
        self.file_resolutions: Dict[str, FileResolution] = {}
        self.resolution_stats: Dict[str, int] = {}

    def _normalize_module_name(self, path: str) -> str:
        norm = path.replace("\\", "/")
        if norm.endswith(".py"):
            norm = norm[:-3]
        if norm.endswith("/__init__"):
            norm = norm[:-9]
        parts = [p for p in norm.split("/") if p]
        while parts and parts[0] in ("src", "lib", "python"):
            parts.pop(0)
        return ".".join(parts)

    def extract_python_ast(
        self, content: str, filepath: str
    ) -> Tuple[List[FunctionSymbol], List[CallSite], List[str], List[str]]:
        funcs: List[FunctionSymbol] = []
        calls: List[CallSite] = []
        symbols: List[str] = []
        imports: List[str] = []
        is_test = "test" in filepath.lower()

        try:
            tree = ast.parse(content, filename=filepath)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    mod_pfx = node.module or ""
                    if mod_pfx:
                        imports.append(mod_pfx)
                    for alias in node.names:
                        symbols.append(alias.name)
                        if mod_pfx:
                            imports.append(f"{mod_pfx}.{alias.name}")
                        else:
                            imports.append(alias.name)

            class FuncVisitor(ast.NodeVisitor):
                def __init__(self):
                    self.current_class: Optional[str] = None
                    self.current_func: Optional[str] = None

                def visit_ClassDef(self, node: ast.ClassDef):
                    old_class = self.current_class
                    self.current_class = node.name
                    symbols.append(node.name)
                    self.generic_visit(node)
                    self.current_class = old_class

                def visit_FunctionDef(self, node: ast.FunctionDef):
                    self._handle_func(node)

                def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                    self._handle_func(node)

                def _handle_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
                    old_func = self.current_func
                    self.current_func = node.name
                    is_method = self.current_class is not None
                    args = [getattr(a, "arg", str(a)) for a in node.args.args]
                    funcs.append(FunctionSymbol(
                        name=node.name,
                        parent_class=self.current_class,
                        filepath=filepath,
                        is_method=is_method,
                        is_test=is_test,
                        start_line=node.lineno,
                        arg_names=args,
                    ))
                    symbols.append(node.name)
                    self.generic_visit(node)
                    self.current_func = old_func

                def visit_Call(self, node: ast.Call):
                    callee_name = ""
                    qualifier = None
                    is_attr = False

                    if isinstance(node.func, ast.Name):
                        callee_name = node.func.id
                        is_attr = False
                    elif isinstance(node.func, ast.Attribute):
                        callee_name = node.func.attr
                        is_attr = True
                        if isinstance(node.func.value, ast.Name):
                            qualifier = node.func.value.id
                        elif isinstance(node.func.value, ast.Attribute):
                            qualifier = node.func.value.attr

                    if callee_name and callee_name not in PYTHON_BUILTINS:
                        calls.append(CallSite(
                            caller_path=filepath,
                            caller_func=self.current_func,
                            callee_name=callee_name,
                            is_attribute=is_attr,
                            qualifier=qualifier,
                            start_line=getattr(node, "lineno", 0),
                        ))
                    self.generic_visit(node)

            FuncVisitor().visit(tree)

        except Exception:
            # Fallback regex extraction on syntax error
            for m in re.finditer(r"^\s*def\s+([a-zA-Z0-9_]+)\s*\(([^)\r\n]*)\)", content, re.MULTILINE):
                fn = m.group(1)
                funcs.append(FunctionSymbol(
                    name=fn,
                    parent_class=None,
                    filepath=filepath,
                    is_method=False,
                    is_test=is_test,
                    start_line=1,
                    arg_names=[a.strip() for a in m.group(2).split(",") if a.strip()],
                ))
                symbols.append(fn)

            for m in re.finditer(r"\b([a-zA-Z0-9_]+)\s*\(", content):
                fn = m.group(1)
                if fn not in PYTHON_BUILTINS:
                    calls.append(CallSite(
                        caller_path=filepath,
                        caller_func=None,
                        callee_name=fn,
                        is_attribute=False,
                        qualifier=None,
                        start_line=1,
                    ))

        return funcs, calls, list(dict.fromkeys(symbols)), list(dict.fromkeys(imports))

    def extract_polyglot(
        self, content: str, filepath: str
    ) -> Tuple[List[FunctionSymbol], List[CallSite], List[str], List[str]]:
        norm_p = filepath.replace("\\", "/").lower()
        if norm_p.endswith(".py"):
            return self.extract_python_ast(content, filepath)

        funcs: List[FunctionSymbol] = []
        calls: List[CallSite] = []
        symbols: List[str] = []
        imports: List[str] = []
        is_test = "test" in filepath.lower()

        # Go (.go)
        if norm_p.endswith(".go"):
            for m in re.finditer(r"^\s*func\s+(?:\(\s*[^)]*?\s*(\*?[a-zA-Z0-9_]+)\s*\)\s+)?([a-zA-Z0-9_]+)\s*\(", content, re.MULTILINE):
                recv = m.group(1).lstrip("*") if m.group(1) else None
                fn = m.group(2)
                funcs.append(FunctionSymbol(
                    name=fn,
                    parent_class=recv,
                    filepath=filepath,
                    is_method=recv is not None,
                    is_test=is_test,
                    start_line=1,
                ))
                symbols.append(fn)

            for m in re.finditer(r"(?:([a-zA-Z0-9_]+)\.)?([A-Z][a-zA-Z0-9_]*)\s*\(", content):
                pkg_or_var = m.group(1)
                fn = m.group(2)
                calls.append(CallSite(
                    caller_path=filepath,
                    caller_func=None,
                    callee_name=fn,
                    is_attribute=pkg_or_var is not None,
                    qualifier=pkg_or_var,
                    start_line=1,
                ))

            for m in re.finditer(r'^\s*import\s+["\']([^"\']+)["\']', content, re.MULTILINE):
                imp = m.group(1)
                imports.append(imp)
                imports.append(imp.split("/")[-1])

        # Rust (.rs)
        elif norm_p.endswith(".rs"):
            for m in re.finditer(r"^\s*(?:pub(?:\s*\([^)]*\))?\s+)?(?:async\s+)?fn\s+([a-zA-Z0-9_]+)", content, re.MULTILINE):
                fn = m.group(1)
                funcs.append(FunctionSymbol(
                    name=fn,
                    parent_class=None,
                    filepath=filepath,
                    is_method=False,
                    is_test=is_test,
                    start_line=1,
                ))
                symbols.append(fn)

            for m in re.finditer(r"\b([a-zA-Z0-9_]+)::([a-zA-Z0-9_]+)\s*\(", content):
                mod = m.group(1)
                fn = m.group(2)
                calls.append(CallSite(
                    caller_path=filepath,
                    caller_func=None,
                    callee_name=fn,
                    is_attribute=True,
                    qualifier=mod,
                    start_line=1,
                ))

        # JS / TS
        elif norm_p.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")):
            for m in re.finditer(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_]+)", content, re.MULTILINE):
                fn = m.group(1)
                funcs.append(FunctionSymbol(
                    name=fn,
                    parent_class=None,
                    filepath=filepath,
                    is_method=False,
                    is_test=is_test,
                    start_line=1,
                ))
                symbols.append(fn)

            for m in re.finditer(r"\b([a-zA-Z0-9_]+)\s*\(", content):
                fn = m.group(1)
                if fn not in ("require", "import", "describe", "it", "test", "expect"):
                    calls.append(CallSite(
                        caller_path=filepath,
                        caller_func=None,
                        callee_name=fn,
                        is_attribute=False,
                        qualifier=None,
                        start_line=1,
                    ))

        # Java (.java)
        elif norm_p.endswith(".java"):
            for m in re.finditer(r"(?:public|protected|private|static|\s)+[\w<>\[\]]+\s+([a-zA-Z0-9_]+)\s*\([^)]*\)\s*\{", content):
                fn = m.group(1)
                if fn not in ("if", "for", "while", "switch", "catch"):
                    funcs.append(FunctionSymbol(
                        name=fn,
                        parent_class=None,
                        filepath=filepath,
                        is_method=True,
                        is_test=is_test,
                        start_line=1,
                    ))
                    symbols.append(fn)

        return funcs, calls, list(dict.fromkeys(symbols)), list(dict.fromkeys(imports))

    @staticmethod
    def polyglot_signature(doc: FileDoc) -> str:
        """Deterministic signature of the regex/AST extraction inputs: path and content."""
        return stable_signature(POLYGLOT_SIGNATURE_VERSION, doc.path, doc.content)

    @staticmethod
    def tree_sitter_signature(doc: FileDoc) -> str:
        """Deterministic signature of the Tree-sitter extraction inputs: path (language, is_test) and content."""
        return stable_signature(TREE_SITTER_SIGNATURE_VERSION, doc.path, doc.content)

    def _reset_build_state(self) -> None:
        """
        Clears everything derived from a document collection, so a rebuild on this instance equals a build on a
        fresh instance. Configuration, the loaded SCIP index and the signature-validated per-document extraction
        caches (``_polyglot_cache``, ``_ts_cache``) are kept.
        """
        self.graph.clear()
        self.module_to_path.clear()
        self.package_to_files.clear()
        self.functions.clear()
        self.call_sites.clear()
        self.edges.clear()
        self.file_to_file_edges.clear()
        self.callers_map.clear()
        self.callees_map.clear()
        self.scip_relationships = []
        self._ts_norm_to_path = {}
        self._ts_resolver = None
        self._lookup = None
        self.file_resolutions = {}
        self.resolution_stats = {}
        self.diagnostics.clear()
        if self.scip_index is None and self.scip_load_diagnostics is not None:
            self.diagnostics["scip"] = self.scip_load_diagnostics

    def build_graph(self, docs: List[FileDoc], reuse=None, track: bool = False) -> "FunctionGraphEngine":
        """
        Builds the function graph. The default extractor uses indexed lookups (``_build_graph_regex``);
        ``structural_parser="tree_sitter"`` keeps the original resolution loop unchanged.

        ``reuse`` (persistent index cache only): ``reuse(engine, doc) -> Optional[FileResolution]`` may supply a
        caller file's previously resolved edges once the lookup indexes exist; files for which it returns None are
        resolved. ``track=True`` records every caller's consulted keys in ``file_resolutions``.
        """
        if self.structural_parser != "tree_sitter":
            return self._build_graph_regex(docs, reuse, track)
        return self._build_graph_tree_sitter(docs)

    def _extract_regex(self, doc: FileDoc):
        content_sig = self.polyglot_signature(doc)
        cached = self._polyglot_cache.get(doc.path)
        if cached is not None and cached[0] == content_sig:
            return cached[1]
        result = self.extract_polyglot(doc.content, doc.path)
        self._polyglot_cache[doc.path] = (content_sig, result)
        return result

    def _build_graph_regex(self, docs: List[FileDoc], reuse, track: bool) -> "FunctionGraphEngine":
        """
        The default resolver. Same maps, steps A-E, edge order and graph insertion order as the 1.2.0 loop, but every
        cross-file lookup is a dictionary lookup through ``_FunctionLookup`` and each caller file is resolved on its
        own (``_resolve_file``), then its edges are replayed in discovery order (``_replay_edges``).
        """
        self._reset_build_state()
        self.docs = docs
        self.doc_paths = [d.path for d in docs]
        self.path_to_idx = {d.path: idx for idx, d in enumerate(docs)}

        for doc in docs:
            self.graph.add_node(doc.path, is_test=doc.is_test)

        # 1. Map modules and namespaces
        for doc in docs:
            norm_p = doc.path.replace("\\", "/")
            cur_dir = os.path.dirname(norm_p)
            raw_p = norm_p[:-3] if norm_p.endswith(".py") else norm_p
            self.module_to_path[raw_p.replace("/", ".")] = doc.path
            mod_name = self._normalize_module_name(doc.path)
            self.module_to_path[mod_name] = doc.path
            if "." in mod_name:
                self.module_to_path[mod_name.split(".")[-1]] = doc.path

            if cur_dir:
                self.package_to_files.setdefault(cur_dir, []).append(doc.path)
                pkg_name = os.path.basename(cur_dir)
                if pkg_name:
                    self.package_to_files.setdefault(pkg_name, []).append(doc.path)

        # 2. Extract functions and call sites per doc
        doc_functions: Dict[str, List[FunctionSymbol]] = {}
        doc_calls: Dict[str, List[CallSite]] = {}
        doc_imports: Dict[str, List[str]] = {}
        func_name_to_defs: Dict[str, List[FunctionSymbol]] = defaultdict(list)
        class_to_methods: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        for doc in docs:
            funcs, calls, _syms, imps = self._extract_regex(doc)
            doc_functions[doc.path] = funcs
            doc_calls[doc.path] = calls
            doc_imports[doc.path] = list(dict.fromkeys(doc.imports + imps))
            self.functions.extend(funcs)
            self.call_sites.extend(calls)
            for f in funcs:
                func_name_to_defs[f.name].append(f)
                if f.parent_class:
                    class_to_methods[f.parent_class].append((f.name, doc.path))

        self._lookup = _FunctionLookup(self.module_to_path, doc_functions, func_name_to_defs, class_to_methods)

        # 3. Resolve (or reuse) each caller file's edges, then replay them in discovery order
        resolved = reused = calls_resolved = edges_replayed = edges_reused = 0
        for doc in docs:
            res = reuse(self, doc) if reuse is not None else None
            if res is None:
                res = self._resolve_file(doc.path, doc_calls[doc.path], doc_imports[doc.path], track)
                resolved += 1
                calls_resolved += len(doc_calls[doc.path])
            else:
                reused += 1
                edges_reused += len(res.edges)
            if track or reuse is not None:
                self.file_resolutions[doc.path] = res
            self._replay_edges(doc.path, res.edges)
            edges_replayed += len(res.edges)
        self.resolution_stats = {"files_resolved": resolved, "files_reused": reused,
                                 "calls_resolved": calls_resolved, "calls_total": len(self.call_sites),
                                 "edges_replayed": edges_replayed, "edges_reused": edges_reused}
        if self.scip_index is not None:
            self._apply_scip(docs)
        return self

    def _resolve_file(self, caller_p: str, calls: List[CallSite], doc_imports: List[str],
                      track: bool) -> FileResolution:
        """Steps A-E of the 1.2.0 resolver for one caller file, with indexed lookups."""
        lk = self._lookup
        consumed: Optional[Set[str]] = set() if track else None
        lk.track = consumed
        local = lk.names_of.get(caller_p, frozenset())
        caller_dir = os.path.dirname(caller_p.replace("\\", "/"))
        import_bases: Dict[str, Tuple[str, ...]] = {}
        min_conf, structural = self.min_confidence, self.enable_structural_edges
        edges: List[Tuple[str, Optional[str], str, str, float]] = []
        try:
            for call in calls:
                callee_name = call.callee_name
                qualifier = call.qualifier
                is_attr = call.is_attribute
                target_file = None
                conf = 0.0
                edge_type = ""

                # A. Intra-file calls
                if callee_name in local:
                    target_file = caller_p
                    conf = 1.0
                    edge_type = "intra_file_call"

                # B. Qualified module calls
                elif is_attr and qualifier:
                    cand_file = lk.module(qualifier)
                    if cand_file is not None:
                        if lk.defines(cand_file, callee_name):
                            target_file = cand_file
                            conf = 1.0
                            edge_type = "verified_call"
                    else:
                        matching = lk.class_methods(qualifier, callee_name)
                        if len(matching) == 1:
                            target_file = matching[0]
                            conf = 0.90
                            edge_type = "verified_call"

                # C. Unqualified calls with active imports (the first matching import whose module is known)
                if not target_file and not is_attr:
                    bases = import_bases.get(callee_name)
                    if bases is None:
                        suffix = f".{callee_name}"
                        bases = tuple((imp.rsplit(".", 1)[0] if "." in imp else imp) for imp in doc_imports
                                      if imp.endswith(suffix) or imp == callee_name)
                        import_bases[callee_name] = bases
                    for base_mod in bases:
                        cand_file = lk.module(base_mod)
                        if cand_file is not None:
                            target_file = cand_file
                            conf = 1.0
                            edge_type = "verified_call"
                            break

                # D. Globally unique functions in the repository
                if not target_file:
                    defs = lk.function_paths(callee_name)
                    if defs:
                        if len(defs) == 1:
                            target_file = defs[0]
                            conf = 0.90
                            edge_type = "unique_global_call"
                        elif len(defs) <= 3:
                            same_dir = [p for p in defs if os.path.dirname(p.replace("\\", "/")) == caller_dir]
                            if len(same_dir) == 1:
                                target_file = same_dir[0]
                                conf = 0.75
                                edge_type = "directory_local_call"

                # E. Unique method name across all classes (structural)
                if not target_file and is_attr and callee_name not in GENERIC_METHOD_NAMES and len(callee_name) >= 4:
                    files = lk.method_files(callee_name)
                    if len(files) == 1:
                        target_file = files[0]
                        conf = 0.70
                        edge_type = "structural_method_call"

                # Filter by confidence and configuration
                if target_file and target_file != caller_p:
                    if conf < min_conf:
                        continue
                    if edge_type in ("structural_method_call", "directory_local_call") and not structural:
                        continue
                    edges.append((target_file, call.caller_func, callee_name, edge_type, conf))
        finally:
            lk.track = None
        return FileResolution(edges, tuple(sorted(consumed)) if consumed is not None else ())

    def _replay_edges(self, caller_p: str, edges) -> None:
        """Adds one caller file's resolved edges exactly as the 1.2.0 loop did, in order."""
        for target_file, source_func, target_func, edge_type, conf in edges:
            e = FunctionGraphEdge(
                source_path=caller_p,
                target_path=target_file,
                source_func=source_func,
                target_func=target_func,
                edge_type=edge_type,
                confidence=conf,
            )
            self.edges.append(e)
            self.file_to_file_edges[(caller_p, target_file)].append(e)
            self.graph.add_edge(caller_p, target_file, weight=conf)
            self.callees_map[caller_p][target_file] = max(self.callees_map[caller_p].get(target_file, 0.0), conf)
            self.callers_map[target_file][caller_p] = max(self.callers_map[target_file].get(caller_p, 0.0), conf)

    def key_value(self, key: str) -> Any:
        """The value of a typed lookup key in the current build (see ``_FunctionLookup.value``)."""
        if self._lookup is None:
            raise RuntimeError("no default-resolver build is available")
        return self._lookup.value(key)

    def provides(self, doc: FileDoc) -> List[Tuple[str, str]]:
        """Provider events of one document for the current build's extraction (``function_graph_provides``)."""
        funcs = self._extract_regex(doc)[0]
        return function_graph_provides(doc.path, funcs, self._normalize_module_name)

    def _build_graph_tree_sitter(self, docs: List[FileDoc]) -> "FunctionGraphEngine":
        """The original resolution loop, used unchanged for ``structural_parser="tree_sitter"``."""
        self._reset_build_state()
        self.docs = docs
        self.doc_paths = [d.path for d in docs]
        self.path_to_idx = {d.path: idx for idx, d in enumerate(docs)}

        for doc in docs:
            self.graph.add_node(doc.path, is_test=doc.is_test)

        # 1. Map modules and namespaces
        for doc in docs:
            norm_p = doc.path.replace("\\", "/")
            cur_dir = os.path.dirname(norm_p)
            raw_p = norm_p[:-3] if norm_p.endswith(".py") else norm_p
            self.module_to_path[raw_p.replace("/", ".")] = doc.path
            mod_name = self._normalize_module_name(doc.path)
            self.module_to_path[mod_name] = doc.path
            if "." in mod_name:
                self.module_to_path[mod_name.split(".")[-1]] = doc.path

            if cur_dir:
                self.package_to_files.setdefault(cur_dir, []).append(doc.path)
                pkg_name = os.path.basename(cur_dir)
                if pkg_name:
                    self.package_to_files.setdefault(pkg_name, []).append(doc.path)

        # 2. Extract functions and call sites per doc
        doc_functions: Dict[str, List[FunctionSymbol]] = {}
        doc_calls: Dict[str, List[CallSite]] = {}
        doc_imports: Dict[str, List[str]] = {}
        func_name_to_defs: Dict[str, List[FunctionSymbol]] = defaultdict(list)
        class_to_methods: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

        ts_mode = self.structural_parser == "tree_sitter"
        ts_extractions: Dict[str, Any] = {}
        if ts_mode:
            ts_diag = self._ts_begin_diagnostics()

        for doc in docs:
            cache_key = doc.path
            extraction = None
            if ts_mode:
                extraction, regex_result = self._ts_extract_doc(doc, ts_diag)
                if extraction is not None:
                    ts_extractions[doc.path] = extraction
                    funcs, calls, syms, imps = (extraction.functions, extraction.calls,
                                                extraction.symbols, extraction.imports)
                else:
                    funcs, calls, syms, imps = regex_result
            if extraction is None and not ts_mode:
                content_sig = self.polyglot_signature(doc)
                if cache_key in self._polyglot_cache and self._polyglot_cache[cache_key][0] == content_sig:
                    funcs, calls, syms, imps = self._polyglot_cache[cache_key][1]
                else:
                    funcs, calls, syms, imps = self.extract_polyglot(doc.content, doc.path)
                    self._polyglot_cache[cache_key] = (content_sig, (funcs, calls, syms, imps))

            doc_functions[doc.path] = funcs
            doc_calls[doc.path] = calls
            doc_imports[doc.path] = list(dict.fromkeys(doc.imports + imps))
            self.functions.extend(funcs)
            self.call_sites.extend(calls)

            for f in funcs:
                func_name_to_defs[f.name].append(f)
                if f.parent_class:
                    class_to_methods[f.parent_class].append((f.name, doc.path))

        # 3. Resolve call sites into directed function edges
        if ts_mode:
            bindings = self._ts_bindings(docs, ts_extractions, ts_diag)
            defined_names = {p: set(ex.symbols) for p, ex in ts_extractions.items()}
            seen_edges: Set[Tuple[str, str, Optional[str], Optional[str], str]] = set()

        for doc in docs:
            caller_p = doc.path
            caller_dir = os.path.dirname(caller_p.replace("\\", "/"))
            calls = doc_calls.get(caller_p, [])

            for call in calls:
                callee_name = call.callee_name
                qualifier = call.qualifier
                is_attr = call.is_attribute

                target_file = None
                conf = 0.0
                edge_type = ""

                # Tree-sitter mode: calls whose qualifier or name is bound by an import declaration are
                # resolved through that import only. Everything else uses the unchanged steps A-E.
                if ts_mode and caller_p in ts_extractions:
                    outcome = self._ts_resolve_bound_call(
                        caller_p, call, bindings.get(caller_p, {}), doc_functions, defined_names, ts_diag
                    )
                    if outcome is not None:
                        if outcome[0] is None:
                            continue
                        target_file, conf, edge_type, target_func = outcome
                        if target_file == caller_p or conf < self.min_confidence:
                            continue
                        self._ts_add_edge(caller_p, target_file, call, edge_type, conf, seen_edges, target_func)
                        continue

                # A. Intra-file calls
                matching_local = [f for f in doc_functions.get(caller_p, []) if f.name == callee_name]
                if matching_local:
                    target_file = caller_p
                    conf = 1.0
                    edge_type = "intra_file_call"

                # B. Qualified module calls
                elif is_attr and qualifier:
                    if qualifier in self.module_to_path:
                        cand_file = self.module_to_path[qualifier]
                        if cand_file in doc_functions and any(f.name == callee_name for f in doc_functions[cand_file]):
                            target_file = cand_file
                            conf = 1.0
                            edge_type = "verified_call"
                    elif qualifier in class_to_methods:
                        method_pairs = class_to_methods[qualifier]
                        matching = [p for m, p in method_pairs if m == callee_name]
                        if len(matching) == 1:
                            target_file = matching[0]
                            conf = 0.90
                            edge_type = "verified_call"

                # C. Unqualified calls with active imports
                if not target_file and not is_attr:
                    for imp in doc_imports.get(caller_p, []):
                        if imp.endswith(f".{callee_name}") or imp == callee_name:
                            base_mod = imp.rsplit(".", 1)[0] if "." in imp else imp
                            if base_mod in self.module_to_path:
                                target_file = self.module_to_path[base_mod]
                                conf = 1.0
                                edge_type = "verified_call"
                                break

                # D. Globally unique functions in the repository
                if not target_file and callee_name in func_name_to_defs:
                    defs = func_name_to_defs[callee_name]
                    if ts_mode and not is_attr and caller_p in ts_extractions:
                        # Tree-sitter also extracts methods. An unqualified call in these languages cannot
                        # reach another file's method (other than a constructor) by name alone, so only
                        # free functions and constructors are candidates.
                        defs = [d for d in defs if not d.is_method or d.name == d.parent_class]
                    if ts_mode and caller_p in ts_extractions and len(defs) > 1 \
                            and len({d.filepath for d in defs}) == 1:
                        defs = defs[:1]  # overloads (e.g. Java/C++ constructors) in one file: one target file
                    if len(defs) == 1:
                        target_file = defs[0].filepath
                        conf = 0.90
                        edge_type = "unique_global_call"
                    elif len(defs) <= 3:
                        same_dir = [d.filepath for d in defs if os.path.dirname(d.filepath.replace("\\", "/")) == caller_dir]
                        if len(same_dir) == 1:
                            target_file = same_dir[0]
                            conf = 0.75
                            edge_type = "directory_local_call"

                # E. Unique method name across all classes (structural)
                if not target_file and is_attr and callee_name not in GENERIC_METHOD_NAMES and len(callee_name) >= 4:
                    all_methods_matching = []
                    for cls_name, m_list in class_to_methods.items():
                        for m_name, f_path in m_list:
                            if m_name == callee_name:
                                all_methods_matching.append(f_path)
                    all_methods_matching = list(dict.fromkeys(all_methods_matching))
                    if len(all_methods_matching) == 1:
                        target_file = all_methods_matching[0]
                        conf = 0.70
                        edge_type = "structural_method_call"

                # Filter by confidence and configuration
                if target_file and target_file != caller_p:
                    if conf < self.min_confidence:
                        continue
                    if edge_type in ("structural_method_call", "directory_local_call") and not self.enable_structural_edges:
                        continue
                    if ts_mode and caller_p in ts_extractions:
                        # Tree-sitter-extracted callers: one edge per (caller, callee, kind). Callers that
                        # fell back to regex keep the 1.2.0 edge behaviour below unchanged.
                        self._ts_add_edge(caller_p, target_file, call, edge_type, conf, seen_edges)
                        continue

                    e = FunctionGraphEdge(
                        source_path=caller_p,
                        target_path=target_file,
                        source_func=call.caller_func,
                        target_func=callee_name,
                        edge_type=edge_type,
                        confidence=conf,
                    )
                    self.edges.append(e)
                    self.file_to_file_edges[(caller_p, target_file)].append(e)
                    self.graph.add_edge(caller_p, target_file, weight=conf)
                    self.callees_map[caller_p][target_file] = max(self.callees_map[caller_p].get(target_file, 0.0), conf)
                    self.callers_map[target_file][caller_p] = max(self.callers_map[target_file].get(caller_p, 0.0), conf)

        if ts_mode:
            self._ts_finish_diagnostics(ts_diag)
        if self.scip_index is not None:
            self._apply_scip(docs)
        return self

    # ------------------------------------------------------------------
    # SCIP evidence (opt-in: RepoNeedleEngine(..., scip_config=ScipConfig(...)))
    # ------------------------------------------------------------------

    def _apply_scip(self, docs: List[FileDoc]) -> None:
        """
        Adds a ``scip_reference`` edge for each SCIP reference from one repository file to a callable
        defined in another, unless an extracted edge already links the same files and function name.
        Relationships (implementation, type definition, ...) are stored separately, never as edges.
        """
        from reponeedle.core.scip_ingestion import SCIP_REFERENCE_CONFIDENCE, SCIP_REFERENCE_EDGE_TYPE

        resolution = self.scip_index.resolve(docs)
        provenance = "scip:" + "@".join(p for p in (self.scip_index.tool_name, self.scip_index.tool_version) if p)
        existing = {(e.source_path, e.target_path, e.target_func) for e in self.edges}
        known_paths = set(self.path_to_idx)
        added = corroborated = 0
        for ref in resolution.edges:
            if ref.source_path not in known_paths or ref.target_path not in known_paths:
                continue
            if (ref.source_path, ref.target_path, ref.target_name) in existing:
                corroborated += 1
                continue
            e = FunctionGraphEdge(
                source_path=ref.source_path,
                target_path=ref.target_path,
                source_func=ref.source_name,
                target_func=ref.target_name,
                edge_type=SCIP_REFERENCE_EDGE_TYPE,
                confidence=SCIP_REFERENCE_CONFIDENCE,
                source_symbol=ref.source_symbol,
                target_symbol=ref.target_symbol,
                provenance=provenance,
            )
            self.edges.append(e)
            self.file_to_file_edges[(ref.source_path, ref.target_path)].append(e)
            prev = self.graph.get_edge_data(ref.source_path, ref.target_path, default={}).get("weight", 0.0)
            self.graph.add_edge(ref.source_path, ref.target_path, weight=max(prev, e.confidence))
            self.callees_map[ref.source_path][ref.target_path] = max(
                self.callees_map[ref.source_path].get(ref.target_path, 0.0), e.confidence)
            self.callers_map[ref.target_path][ref.source_path] = max(
                self.callers_map[ref.target_path].get(ref.source_path, 0.0), e.confidence)
            added += 1
        self.scip_relationships = resolution.relationships
        diag = resolution.diagnostics
        diag["status"] = "ingested"
        diag["edges"].update(added_to_graph=added, already_present_from_extraction=corroborated,
                             edge_type=SCIP_REFERENCE_EDGE_TYPE, confidence=SCIP_REFERENCE_CONFIDENCE,
                             provenance=provenance)
        self.diagnostics["scip"] = diag

    # ------------------------------------------------------------------
    # Tree-sitter structural extraction (opt-in: structural_parser="tree_sitter")
    # ------------------------------------------------------------------

    _TS_ITEM_BINDINGS = ("symbol", "default", "class", "static_member", "path")

    def _ts_begin_diagnostics(self) -> Dict[str, Any]:
        from reponeedle.core import tree_sitter_extraction as tse

        runtime = tse.tree_sitter_status(languages=[])["runtime"]
        return {
            "requested": "tree_sitter",
            "runtime_available": runtime["available"],
            "runtime_version": runtime["version"],
            "runtime_error": runtime["error"],
            # language -> files parsed with Tree-sitter / files that fell back to regex, plus grammar status
            "languages": {},
            "files": {
                "tree_sitter": [],
                "tree_sitter_with_syntax_errors": [],
                "regex_fallback": {},           # path -> reason
                "python_ast": 0,
                "regex_other_languages": 0,     # e.g. .js, .c: not handled by the Tree-sitter path
            },
            "imports": {"resolved": 0, "external": 0, "unresolved": 0, "not_applicable": 0},
            "calls": {
                "import_bound_resolved": 0,
                "import_bound_external": 0,
                "import_bound_unresolved": 0,
                "import_bound_not_defined": 0,
                "import_bound_ambiguous": 0,
                "import_bound_unverifiable": 0,
            },
        }

    def _regex_extract_cached(self, doc: FileDoc):
        return self._extract_regex(doc)

    def _ts_extract_doc(self, doc: FileDoc, diag: Dict[str, Any]):
        """Returns (TreeSitterExtraction, None) or (None, regex/AST extraction tuple)."""
        from reponeedle.core import tree_sitter_extraction as tse

        path = doc.path
        if path.replace("\\", "/").lower().endswith(".py"):
            diag["files"]["python_ast"] += 1
            return None, self._regex_extract_cached(doc)
        language = tse.detect_language(path)
        if language is None:
            diag["files"]["regex_other_languages"] += 1
            return None, self._regex_extract_cached(doc)

        lang_diag = diag["languages"].setdefault(language, {"tree_sitter_files": 0, "regex_fallback_files": 0})
        content_sig = self.tree_sitter_signature(doc)
        cached = self._ts_cache.get(path)
        reason = None
        if cached is not None and cached[0] == content_sig:
            extraction = cached[1]
        else:
            try:
                extraction = tse.extract(doc.content, path, language, is_test="test" in path.lower())
            except Exception as exc:  # defensive: never let one file break graph construction
                extraction = None
                reason = f"extraction error: {type(exc).__name__}: {exc}"
            if extraction is not None:
                self._ts_cache[path] = (content_sig, extraction)

        if extraction is None:
            reason = reason or tse.load_errors().get(language, "parser unavailable")
            diag["files"]["regex_fallback"][path] = reason
            lang_diag["regex_fallback_files"] += 1
            return None, self._regex_extract_cached(doc)

        lang_diag["tree_sitter_files"] += 1
        diag["files"]["tree_sitter"].append(path)
        if extraction.has_error:
            diag["files"]["tree_sitter_with_syntax_errors"].append(path)
        return extraction, None

    def _ts_bindings(self, docs: List[FileDoc], extractions: Dict[str, Any], diag: Dict[str, Any]):
        """Resolves every import record; returns {file: {local name: (record, resolution, rust item)}}."""
        import posixpath
        from reponeedle.core.tree_sitter_extraction import ImportResolver

        self._ts_norm_to_path = {d.path.replace("\\", "/"): d.path for d in docs}
        go_modules = []
        for d in docs:
            norm = d.path.replace("\\", "/")
            if norm == "go.mod" or norm.endswith("/go.mod"):
                m = re.search(r"^\s*module\s+(\S+)", d.content, re.MULTILINE)
                if m:
                    go_modules.append((posixpath.dirname(norm), m.group(1).strip('"')))
        rust_crates = []
        for d in docs:
            norm = d.path.replace("\\", "/")
            if norm.lower() == "cargo.toml" or norm.lower().endswith("/cargo.toml"):
                m = re.search(r'^\[package\][^\[]*?^\s*name\s*=\s*"([^"]+)"', d.content, re.MULTILINE | re.DOTALL)
                if m:
                    base = posixpath.dirname(norm)
                    rust_crates.append((m.group(1).replace("-", "_"), posixpath.join(base, "src") if base else "src"))
        self._ts_resolver = ImportResolver(list(self._ts_norm_to_path), extractions, go_modules, rust_crates)

        bindings: Dict[str, Dict[str, Any]] = {}
        for path, ex in extractions.items():
            norm = path.replace("\\", "/")
            file_bindings: Dict[str, Any] = {}
            for rec in ex.import_records:
                item = None
                if ex.language == "rust" and rec.kind == "path":
                    resolution, item = self._ts_resolver.resolve_rust_path(norm, rec.spec.split("::"))
                else:
                    resolution = self._ts_resolver.resolve(norm, ex.language, rec)
                diag["imports"][resolution.status] = diag["imports"].get(resolution.status, 0) + 1
                if rec.local_name:
                    # A later declaration of the same name replaces an earlier one, as in the languages.
                    file_bindings[rec.local_name] = (rec, resolution, item)
            bindings[path] = file_bindings
        return bindings

    def _ts_names_in(self, path: str, doc_functions, defined_names) -> Set[str]:
        names = defined_names.get(path)
        if names is not None:
            return names
        return {f.name for f in doc_functions.get(path, [])}

    def _ts_verify(self, resolution, name: Optional[str], doc_functions, defined_names, diag,
                   target_func: Optional[str] = None):
        """
        Turns an import resolution into an edge target. The edge is verified only if exactly one resolved
        file defines ``name``; otherwise the call gets no edge (it is never passed to the fuzzy resolver).
        """
        if resolution.status == "external":
            diag["calls"]["import_bound_external"] += 1
            return (None,)
        if resolution.status != "resolved" or not resolution.files:
            diag["calls"]["import_bound_unresolved"] += 1
            return (None,)
        files = [self._ts_norm_to_path.get(f, f) for f in resolution.files]
        if name is None:
            candidates = files if len(files) == 1 else []
        else:
            candidates = [f for f in files if name in self._ts_names_in(f, doc_functions, defined_names)]
        if len(candidates) == 1:
            diag["calls"]["import_bound_resolved"] += 1
            return candidates[0], 1.0, "verified_call", target_func or name
        diag["calls"]["import_bound_ambiguous" if candidates else "import_bound_not_defined"] += 1
        return (None,)

    def _ts_resolve_bound_call(self, caller_p, call, file_bindings, doc_functions, defined_names, diag):
        """
        None: the call is not bound by an import; resolve it with the existing steps.
        (None,): bound, but no verifiable target (external, unresolved, ambiguous); no edge.
        (target, confidence, edge_type): verified edge.
        """
        caller_norm = caller_p.replace("\\", "/")
        language = self._ts_cache[caller_p][1].language if caller_p in self._ts_cache else None
        qpath = call.qualifier_path

        if call.is_attribute and qpath:
            path_style = qpath.endswith("::")
            segs = qpath[:-2].split("::") if path_style else qpath.split(".")
            root = segs[0]
            if language == "rust" and path_style and root in ("crate", "self", "super"):
                resolution, _item = self._ts_resolver.resolve_rust_path(caller_norm, segs)
                return self._ts_verify(resolution, call.callee_name, doc_functions, defined_names, diag)
            binding = file_bindings.get(root)
            if binding is None:
                return None
            rec, resolution, _item = binding
            if language == "rust" and path_style and len(segs) > 1 and rec.kind in ("path", "module_decl"):
                resolution, _item = self._ts_resolver.resolve_rust_path(
                    caller_norm, rec.spec.split("::") + segs[1:])
                return self._ts_verify(resolution, call.callee_name, doc_functions, defined_names, diag)
            if len(segs) > 1:
                diag["calls"]["import_bound_unverifiable"] += 1
                return (None,)
            return self._ts_verify(resolution, call.callee_name, doc_functions, defined_names, diag)

        if call.is_attribute:
            return None
        # Unqualified call: a local definition shadows any import (step A handles it).
        if any(f.name == call.callee_name for f in doc_functions.get(caller_p, [])):
            return None
        binding = file_bindings.get(call.callee_name)
        if binding is None:
            return None
        rec, resolution, item = binding
        if rec.kind not in self._TS_ITEM_BINDINGS:
            return None
        if rec.kind == "path":
            if item is None:  # bound to a module, not a callable item
                return None
            return self._ts_verify(resolution, item, doc_functions, defined_names, diag)
        if rec.kind == "default":
            return self._ts_verify(resolution, None, doc_functions, defined_names, diag,
                                   target_func=call.callee_name)
        return self._ts_verify(resolution, rec.imported_name or call.callee_name, doc_functions, defined_names, diag)

    def _ts_add_edge(self, caller_p, target_file, call, edge_type, conf, seen_edges,
                     target_func: Optional[str] = None) -> None:
        target_func = target_func or call.callee_name
        key = (caller_p, target_file, call.caller_func, target_func, edge_type)
        if key in seen_edges:
            return
        seen_edges.add(key)
        e = FunctionGraphEdge(
            source_path=caller_p,
            target_path=target_file,
            source_func=call.caller_func,
            target_func=target_func,
            edge_type=edge_type,
            confidence=conf,
        )
        self.edges.append(e)
        self.file_to_file_edges[(caller_p, target_file)].append(e)
        prev = self.graph.get_edge_data(caller_p, target_file, default={}).get("weight", 0.0)
        self.graph.add_edge(caller_p, target_file, weight=max(prev, conf))
        self.callees_map[caller_p][target_file] = max(self.callees_map[caller_p].get(target_file, 0.0), conf)
        self.callers_map[target_file][caller_p] = max(self.callers_map[target_file].get(caller_p, 0.0), conf)

    def _ts_finish_diagnostics(self, diag: Dict[str, Any]) -> None:
        from reponeedle.core import tree_sitter_extraction as tse

        status = tse.tree_sitter_status(languages=sorted(diag["languages"]))["languages"]
        for language, entry in diag["languages"].items():
            entry.update({k: v for k, v in status.get(language, {}).items() if k != "available"})
            entry["parser_available"] = status.get(language, {}).get("available", False)
        diag["files"]["tree_sitter"].sort()
        diag["files"]["tree_sitter_with_syntax_errors"].sort()
        diag["files"]["regex_fallback"] = dict(sorted(diag["files"]["regex_fallback"].items()))
        diag["edges"] = len(self.edges)
        fallback = diag["files"]["regex_fallback"]
        if fallback:
            reasons = sorted(set(fallback.values()))
            logger.warning(
                "Tree-sitter structural extraction was requested, but %d file(s) used the regex fallback: %s",
                len(fallback), "; ".join(reasons[:5]),
            )
        self.diagnostics["structural_parser"] = diag
