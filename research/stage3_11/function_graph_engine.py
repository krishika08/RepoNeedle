"""
Stage 3.11: Function-Level Call Graph Engine.

Implements high-precision, language-aware function-level AST extraction,
call-site analysis, symbol disambiguation, and score diffusion for code retrieval.
"""

from __future__ import annotations

import os
import ast
import re
import math
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Any
from collections import defaultdict
import networkx as nx
import numpy as np

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
    qualifier: Optional[str]  # e.g., 'utils' in utils.helper() or 'self'
    start_line: int


@dataclass
class FunctionGraphEdge:
    source_path: str
    target_path: str
    source_func: Optional[str]
    target_func: Optional[str]
    edge_type: str  # 'verified_call', 'intra_file_call', 'unique_global_call', 'structural_method_call', 'directory_local_call'
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
        self.manifest_crates: Dict[str, str] = {}
        self.crate_dependencies: Dict[str, Set[str]] = {}

        # Symbol registries
        self.functions: List[FunctionSymbol] = []
        self.call_sites: List[CallSite] = []
        self.edges: List[FunctionGraphEdge] = []
        self.file_to_file_edges: Dict[Tuple[str, str], List[FunctionGraphEdge]] = defaultdict(list)

        # Adjacency caches for fast retrieval propagation
        self.callers_map: Dict[str, Dict[str, float]] = defaultdict(dict)  # callee -> {caller: conf}
        self.callees_map: Dict[str, Dict[str, float]] = defaultdict(dict)  # caller -> {callee: conf}

        # Stage 3.10 Class-to-test fallback linkages
        self.prod_to_test_invocations: Dict[str, Set[str]] = defaultdict(set)
        self.test_to_prod_invocations: Dict[str, Set[str]] = defaultdict(set)

        # Diagnostics
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

    def extract_python_ast(self, content: str, filepath: str) -> Tuple[List[FunctionSymbol], List[CallSite], List[str], List[str]]:
        """Extracts functions, call sites, symbols, and imports from Python code."""
        funcs: List[FunctionSymbol] = []
        calls: List[CallSite] = []
        symbols: List[str] = []
        imports: List[str] = []
        is_test = "test" in filepath.lower()

        try:
            tree = ast.parse(content, filename=filepath)
            
            # 1. Imports
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

            # 2. Function definitions with scope tracking
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
                    args = [a.arg for a in node.args.args]
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
            # Fallback regex extraction
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

    def extract_polyglot(self, content: str, filepath: str) -> Tuple[List[FunctionSymbol], List[CallSite], List[str], List[str]]:
        """Extracts functions, calls, and symbols for Go, Rust, TS/JS."""
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
            # Functions and methods
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

            # Calls
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

            # Imports
            for m in re.finditer(r'^\s*import\s+["\']([^"\']+)["\']', content, re.MULTILINE):
                imp = m.group(1)
                imports.append(imp)
                imports.append(imp.split("/")[-1])

        # Rust (.rs)
        elif norm_p.endswith(".rs"):
            # Functions
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

            # Calls
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
        elif norm_p.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs")):
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

        return funcs, calls, list(dict.fromkeys(symbols)), list(dict.fromkeys(imports))

    def build_graph(self, docs: List[FileDoc]) -> "FunctionGraphEngine":
        """
        Builds the repository function graph, resolves call sites, and precomputes adjacencies.
        """
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
        self.prod_to_test_invocations.clear()
        self.test_to_prod_invocations.clear()

        # Add all files as graph nodes
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

            # Package discovery
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
        class_to_methods: Dict[str, List[Tuple[str, str]]] = defaultdict(list)  # class -> [(method, file)]

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
        unresolved_count = 0
        ambiguous_count = 0

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

                # B. Qualified module calls: import utils; utils.helper()
                elif is_attr and qualifier:
                    if qualifier in self.module_to_path:
                        cand_file = self.module_to_path[qualifier]
                        if cand_file in doc_functions and any(f.name == callee_name for f in doc_functions[cand_file]):
                            target_file = cand_file
                            conf = 1.0
                            edge_type = "verified_call"
                    elif qualifier in class_to_methods:
                        # Method of known class
                        method_pairs = class_to_methods[qualifier]
                        matching = [p for m, p in method_pairs if m == callee_name]
                        if len(matching) == 1:
                            target_file = matching[0]
                            conf = 0.90
                            edge_type = "verified_call"

                # C. Unqualified calls with active imports
                if not target_file and not is_attr:
                    # Check if imported directly
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
                        # Check same directory / package
                        same_dir = [d.filepath for d in defs if os.path.dirname(d.filepath.replace("\\", "/")) == caller_dir]
                        if len(same_dir) == 1:
                            target_file = same_dir[0]
                            conf = 0.75
                            edge_type = "directory_local_call"
                        else:
                            ambiguous_count += 1
                    else:
                        ambiguous_count += 1
                elif not target_file:
                    unresolved_count += 1

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
                    if not self.enable_verified_calls and edge_type in ("verified_call", "unique_global_call"):
                        continue

                    edge = FunctionGraphEdge(
                        source_path=caller_p,
                        target_path=target_file,
                        source_func=call.caller_func,
                        target_func=callee_name,
                        edge_type=edge_type,
                        confidence=conf,
                    )
                    self.edges.append(edge)
                    self.file_to_file_edges[(caller_p, target_file)].append(edge)

                    # Update fast lookup maps (forward: caller -> callee; reverse: callee -> caller)
                    cur_conf = self.callees_map[caller_p].get(target_file, 0.0)
                    self.callees_map[caller_p][target_file] = max(cur_conf, conf)

                    cur_rev_conf = self.callers_map[target_file].get(caller_p, 0.0)
                    self.callers_map[target_file][caller_p] = max(cur_rev_conf, conf)

                    self.graph.add_edge(caller_p, target_file, edge_type=edge_type, confidence=conf)

                    # Test invocation tracking
                    if doc.is_test and not self.docs[self.path_to_idx[target_file]].is_test:
                        self.test_to_prod_invocations[caller_p].add(target_file)
                        self.prod_to_test_invocations[target_file].add(caller_p)
                    elif not doc.is_test and self.docs[self.path_to_idx[target_file]].is_test:
                        self.prod_to_test_invocations[caller_p].add(target_file)
                        self.test_to_prod_invocations[target_file].add(caller_p)

        # 4. Diagnostics summary
        verified_edges = sum(1 for e in self.edges if e.edge_type in ("verified_call", "unique_global_call", "intra_file_call"))
        structural_edges = sum(1 for e in self.edges if e.edge_type in ("structural_method_call", "directory_local_call"))

        self.diagnostics = {
            "num_docs": len(docs),
            "num_functions": len(self.functions),
            "num_call_sites": len(self.call_sites),
            "num_verified_edges": verified_edges,
            "num_structural_edges": structural_edges,
            "num_total_edges": len(self.edges),
            "num_unresolved_calls": unresolved_count,
            "num_ambiguous_calls": ambiguous_count,
        }

        return self


class FunctionCascadedRanker:
    """
    Cascaded retrieval ranker supporting function-level call graph propagation.
    """

    def __init__(
        self,
        mode: str = "full",  # 'full', 'verified', 'ablation', 'no_freeze', 'control', 'test_graph', 'degree_control', 'bm25'
        top_k_preserve: int = 3,
        forward_weight: float = 0.25,
        reverse_weight: float = 0.20,
        degree_normalized: bool = True,
        package_fencing: bool = True,
        doc_filter_penalty: float = 0.5,
        graph_weight: float = 0.25,
        class_to_test_weight: float = 0.35,
    ):
        self.mode = mode
        self.top_k_preserve = 0 if mode == "no_freeze" else top_k_preserve
        self.forward_weight = forward_weight
        self.reverse_weight = reverse_weight
        self.degree_normalized = degree_normalized
        self.package_fencing = package_fencing
        self.doc_filter_penalty = doc_filter_penalty
        self.graph_weight = graph_weight
        self.class_to_test_weight = class_to_test_weight

    def rank(
        self,
        docs: List[FileDoc],
        bm25_scores: np.ndarray,
        semantic_scores: Optional[np.ndarray] = None,
        function_graph: Optional[FunctionGraphEngine] = None,
        repo_graph: Optional[Any] = None,
        task_type: Optional[str] = None,
    ) -> List[int]:
        """Executes cascaded ranking over candidate documents."""
        n_docs = len(docs)
        if n_docs == 0:
            return []

        # 1. Deterministic BM25 base ranking
        bm25_order = sorted(range(n_docs), key=lambda i: (-float(bm25_scores[i]), docs[i].path))

        # Mode BM25: pure lexical
        if self.mode == "bm25":
            return bm25_order

        # 2. Determine protected vs eligible sets
        if self.top_k_preserve > 0 and n_docs <= self.top_k_preserve:
            return bm25_order

        if self.top_k_preserve > 0:
            k = min(self.top_k_preserve, n_docs)
            protected_indices = bm25_order[:k]
            eligible_indices = bm25_order[k:]
        else:
            protected_indices = []
            eligible_indices = bm25_order

        eligible_set = set(eligible_indices)
        graph_boost = np.zeros(n_docs, dtype=np.float32)

        # 3. Graph Diffusion from Seeds
        # Seeds are the top-3 lexical hits (or top-3 BM25 candidates in no_freeze)
        seeds = bm25_order[:3]

        # Mode CONTROL: uses file-level imports only (RepoGraph)
        if self.mode == "control" and repo_graph is not None and len(repo_graph.graph) > 0:
            self._propagate_repograph(seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost)

        # Mode TEST_GRAPH: uses class-to-test invocations
        elif self.mode == "test_graph" and repo_graph is not None and len(repo_graph.graph) > 0:
            self._propagate_repograph(seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost)
            self._propagate_class_to_test(seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost, is_control=False)

        # Mode DEGREE_CONTROL: uses degree-matched randomized graph
        elif self.mode == "degree_control" and repo_graph is not None and len(repo_graph.graph) > 0:
            self._propagate_repograph(seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost)
            self._propagate_class_to_test(seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost, is_control=True)

        # Function Graph modes: 'full', 'verified', 'ablation', 'no_freeze'
        elif function_graph is not None and len(function_graph.graph) > 0:
            # First apply file-level baseline cascade diffusion and class-to-test linkages
            if repo_graph is not None and len(repo_graph.graph) > 0:
                self._propagate_repograph(seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost)
                self._propagate_class_to_test(seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost, is_control=False)

            # Then apply function-level call graph propagation
            self._propagate_function_graph(seeds, docs, bm25_scores, eligible_set, function_graph, graph_boost)

        # 4. Score Fusion for Eligible Pool
        sem = semantic_scores if semantic_scores is not None else np.zeros(n_docs, dtype=np.float32)
        rerank_scores = {}
        for idx in eligible_indices:
            doc = docs[idx]
            b_score = float(bm25_scores[idx])
            s_score = float(sem[idx])
            g_score = float(graph_boost[idx])

            score = 0.60 * b_score + 0.15 * s_score + self.graph_weight * g_score

            p_lower = doc.path.lower()
            if any(seg in p_lower for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or p_lower.endswith((".md", ".rst", ".txt", ".adoc", ".html")):
                score *= self.doc_filter_penalty

            rerank_scores[idx] = score

        # 5. Deterministic sorting
        reranked_eligible = sorted(
            eligible_indices,
            key=lambda idx: (-rerank_scores[idx], docs[idx].path)
        )

        return protected_indices + reranked_eligible

    def _propagate_function_graph(
        self,
        seeds: List[int],
        docs: List[FileDoc],
        bm25_scores: np.ndarray,
        eligible_set: Set[int],
        fg: FunctionGraphEngine,
        graph_boost: np.ndarray,
    ):
        """Propagates scores along directed function-level call graph edges."""
        path_to_idx = fg.path_to_idx
        allowed_types = {"verified_call", "unique_global_call", "intra_file_call"}
        if self.mode in ("full", "no_freeze"):
            allowed_types.update({"structural_method_call", "directory_local_call"})

        for s_idx in seeds:
            seed_p = docs[s_idx].path
            seed_score = float(bm25_scores[s_idx])
            if seed_score <= 0.0 or seed_p not in fg.path_to_idx:
                continue

            seed_dir = os.path.dirname(seed_p.replace("\\", "/"))

            # 1. Forward propagation (Seed calls Callee: Caller -> Callee)
            callees = fg.callees_map.get(seed_p, {})
            out_deg = max(1, len(callees))
            for callee_p, conf in callees.items():
                if callee_p in path_to_idx:
                    c_idx = path_to_idx[callee_p]
                    if c_idx in eligible_set:
                        # Check edge type filter
                        edges = fg.file_to_file_edges.get((seed_p, callee_p), [])
                        if not any(e.edge_type in allowed_types for e in edges):
                            continue

                        # Package boundary fencing (exempt test-to-prod edges)
                        if self.package_fencing:
                            callee_dir = os.path.dirname(callee_p.replace("\\", "/"))
                            is_test_edge = docs[s_idx].is_test or docs[c_idx].is_test
                            if not is_test_edge and not self._is_package_compatible(seed_dir, callee_dir):
                                continue

                        in_deg = max(1, len(fg.callers_map.get(callee_p, {})))
                        norm_factor = 1.0 / math.sqrt(out_deg * in_deg) if self.degree_normalized else 1.0
                        boost = seed_score * self.forward_weight * conf * norm_factor
                        graph_boost[c_idx] = max(graph_boost[c_idx], float(boost))

            # 2. Reverse propagation (Caller calls Seed: Callee -> Caller)
            callers = fg.callers_map.get(seed_p, {})
            in_deg_seed = max(1, len(callers))
            for caller_p, conf in callers.items():
                if caller_p in path_to_idx:
                    c_idx = path_to_idx[caller_p]
                    if c_idx in eligible_set:
                        edges = fg.file_to_file_edges.get((caller_p, seed_p), [])
                        if not any(e.edge_type in allowed_types for e in edges):
                            continue

                        if self.package_fencing:
                            caller_dir = os.path.dirname(caller_p.replace("\\", "/"))
                            is_test_edge = docs[s_idx].is_test or docs[c_idx].is_test
                            if not is_test_edge and not self._is_package_compatible(seed_dir, caller_dir):
                                continue

                        out_deg_caller = max(1, len(fg.callees_map.get(caller_p, {})))
                        norm_factor = 1.0 / math.sqrt(in_deg_seed * out_deg_caller) if self.degree_normalized else 1.0
                        boost = seed_score * self.reverse_weight * conf * norm_factor
                        graph_boost[c_idx] = max(graph_boost[c_idx], float(boost))

    def _propagate_repograph(self, seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost):
        """Standard file-level import diffusion from CONTROL-CASCADE."""
        g = repo_graph.graph
        path_to_idx = repo_graph.path_to_idx

        for s_idx in seeds:
            seed_p = docs[s_idx].path
            seed_score = float(bm25_scores[s_idx])
            if seed_score <= 0.0 or seed_p not in g:
                continue

            seed_dir = os.path.dirname(seed_p.replace("\\", "/"))
            out_deg = max(1, g.out_degree(seed_p))
            in_deg_seed = max(1, g.in_degree(seed_p))

            for succ in g.successors(seed_p):
                if succ in path_to_idx:
                    n_idx = path_to_idx[succ]
                    if n_idx in eligible_set:
                        if self.package_fencing:
                            succ_dir = os.path.dirname(succ.replace("\\", "/"))
                            if not self._is_package_compatible(seed_dir, succ_dir):
                                continue
                        in_deg_succ = max(1, g.in_degree(succ))
                        norm = 1.0 / math.sqrt(out_deg * in_deg_succ) if self.degree_normalized else 1.0
                        graph_boost[n_idx] = max(graph_boost[n_idx], float(seed_score * 0.25 * norm))

            for pred in g.predecessors(seed_p):
                if pred in path_to_idx:
                    n_idx = path_to_idx[pred]
                    if n_idx in eligible_set:
                        if self.package_fencing:
                            pred_dir = os.path.dirname(pred.replace("\\", "/"))
                            if not self._is_package_compatible(seed_dir, pred_dir):
                                continue
                        out_deg_pred = max(1, g.out_degree(pred))
                        norm = 1.0 / math.sqrt(in_deg_seed * out_deg_pred) if self.degree_normalized else 1.0
                        graph_boost[n_idx] = max(graph_boost[n_idx], float(seed_score * 0.10 * norm))

            # Test discovery
            self._apply_test_discovery(seed_p, seed_score, eligible_set, path_to_idx, graph_boost)

    def _apply_test_discovery(self, seed_path, seed_score, eligible_set, path_to_idx, graph_boost):
        norm_p = seed_path.replace("\\", "/")
        stem = os.path.splitext(os.path.basename(norm_p))[0]
        ext = os.path.splitext(norm_p)[1].lower()
        cur_dir = os.path.dirname(norm_p)

        test_candidates = []
        if ext == ".go":
            test_candidates.append(f"{cur_dir}/{stem}_test.go" if cur_dir else f"{stem}_test.go")
        elif ext in (".py", ".pyi"):
            test_candidates.append(f"{cur_dir}/test_{stem}.py" if cur_dir else f"test_{stem}.py")
            test_candidates.append(f"tests/test_{stem}.py")
            test_candidates.append(f"tests/{stem}_test.py")
        elif ext in (".rs",):
            test_candidates.append(f"tests/{stem}.rs")
            test_candidates.append(f"tests/test_{stem}.rs")
        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            test_candidates.append(f"{cur_dir}/{stem}.test{ext}" if cur_dir else f"{stem}.test{ext}")
            test_candidates.append(f"{cur_dir}/__tests__/{stem}.test{ext}" if cur_dir else f"__tests__/{stem}.test{ext}")

        for tc in test_candidates:
            if tc in path_to_idx:
                idx = path_to_idx[tc]
                if idx in eligible_set:
                    graph_boost[idx] = max(graph_boost[idx], float(seed_score * 0.35))

    def _propagate_class_to_test(self, seeds, docs, bm25_scores, eligible_set, repo_graph, graph_boost, is_control=False):
        if is_control:
            prod_to_tests = getattr(repo_graph, "degree_matched_prod_to_test", {})
            test_to_prods = getattr(repo_graph, "degree_matched_test_to_prod", {})
        else:
            prod_to_tests = getattr(repo_graph, "prod_to_test_invocations", {})
            test_to_prods = getattr(repo_graph, "test_to_prod_invocations", {})

        path_to_idx = repo_graph.path_to_idx
        for s_idx in seeds:
            seed_p = docs[s_idx].path
            seed_score = float(bm25_scores[s_idx])
            if seed_score <= 0.0:
                continue

            if seed_p in prod_to_tests:
                target_tests = prod_to_tests[seed_p]
                out_deg = max(1, len(target_tests))
                for test_p in target_tests:
                    if test_p in path_to_idx:
                        t_idx = path_to_idx[test_p]
                        if t_idx in eligible_set:
                            in_deg = max(1, len(test_to_prods.get(test_p, {seed_p})))
                            norm = 1.0 / math.sqrt(out_deg * in_deg) if self.degree_normalized else 1.0
                            graph_boost[t_idx] = max(graph_boost[t_idx], float(seed_score * self.class_to_test_weight * norm))

            if seed_p in test_to_prods:
                target_prods = test_to_prods[seed_p]
                out_deg = max(1, len(target_prods))
                for prod_p in target_prods:
                    if prod_p in path_to_idx:
                        p_idx = path_to_idx[prod_p]
                        if p_idx in eligible_set:
                            in_deg = max(1, len(prod_to_tests.get(prod_p, {seed_p})))
                            norm = 1.0 / math.sqrt(out_deg * in_deg) if self.degree_normalized else 1.0
                            graph_boost[p_idx] = max(graph_boost[p_idx], float(seed_score * self.class_to_test_weight * norm))

    def _is_package_compatible(self, dir_a: str, dir_b: str) -> bool:
        if dir_a == dir_b:
            return True
        if dir_a.startswith(dir_b) or dir_b.startswith(dir_a):
            return True
        return False
