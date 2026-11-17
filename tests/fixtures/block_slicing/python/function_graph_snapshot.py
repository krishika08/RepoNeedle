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
        self._polyglot_cache: Dict[str, Tuple[str, Tuple[List[FunctionSymbol], List[CallSite], List[str], List[str]]]] = {}

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

    def build_graph(self, docs: List[FileDoc]) -> "FunctionGraphEngine":
        self.docs = docs
        self.doc_paths = [d.path for d in docs]
        self.path_to_idx = {d.path: idx for idx, d in enumerate(docs)}
        self.graph.clear()
        self.functions.clear()
        self.call_sites.clear()
        self.edges.clear()
        self.file_to_file_edges.clear()
        self.callers_map.clear()
        self.callees_map.clear()

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
            sym_str = ",".join(doc.symbols) if doc.symbols else ""
            content_sig = f"{doc.path}::{len(doc.content)}::{hash(doc.content)}::{sym_str}"
            extraction = None
            if ts_mode:
                extraction, regex_result = self._ts_extract_doc(doc, content_sig, ts_diag)
                if extraction is not None:
                    ts_extractions[doc.path] = extraction
                    funcs, calls, syms, imps = (extraction.functions, extraction.calls,
                                                extraction.symbols, extraction.imports)
                else:
                    funcs, calls, syms, imps = regex_result
            if extraction is None and not ts_mode:
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

    def _regex_extract_cached(self, doc: FileDoc, content_sig: str):
        cached = self._polyglot_cache.get(doc.path)
        if cached is not None and cached[0] == content_sig:
            return cached[1]
        result = self.extract_polyglot(doc.content, doc.path)
        self._polyglot_cache[doc.path] = (content_sig, result)
        return result

    def _ts_extract_doc(self, doc: FileDoc, content_sig: str, diag: Dict[str, Any]):
        """Returns (TreeSitterExtraction, None) or (None, regex/AST extraction tuple)."""
        from reponeedle.core import tree_sitter_extraction as tse

        path = doc.path
        if path.replace("\\", "/").lower().endswith(".py"):
            diag["files"]["python_ast"] += 1
            return None, self._regex_extract_cached(doc, content_sig)
        language = tse.detect_language(path)
        if language is None:
            diag["files"]["regex_other_languages"] += 1
            return None, self._regex_extract_cached(doc, content_sig)

        lang_diag = diag["languages"].setdefault(language, {"tree_sitter_files": 0, "regex_fallback_files": 0})
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
            return None, self._regex_extract_cached(doc, content_sig)

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
