"""
Production Function-Level Call Graph Engine for RepoNeedle.

Implements high-precision, language-aware AST extraction, call-site resolution,
symbol disambiguation, and directed call-graph construction for code retrieval.
"""

from __future__ import annotations

import os
import ast
import re
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Any
from collections import defaultdict
import networkx as nx

from reponeedle.models import FileDoc

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


@dataclass
class FunctionGraphEdge:
    source_path: str
    target_path: str
    source_func: Optional[str]
    target_func: Optional[str]
    edge_type: str  # 'verified_call', 'intra_file_call', 'unique_global_call', 'directory_local_call', 'structural_method_call'
    confidence: float


class FunctionGraphEngine:
    """
    Constructs fine-grained function-level call graphs across repositories.
    """

    def __init__(
        self,
        enable_verified_calls: bool = True,
        enable_structural_edges: bool = True,
        min_confidence: float = 0.60,
    ):
        self.enable_verified_calls = enable_verified_calls
        self.enable_structural_edges = enable_structural_edges
        self.min_confidence = min_confidence

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
            for m in re.finditer(r"^\s*def\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)", content, re.MULTILINE):
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

        for doc in docs:
            funcs, calls, syms, imps = self.extract_polyglot(doc.content, doc.path)
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

        return self
