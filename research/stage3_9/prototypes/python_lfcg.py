"""
Python-First Lean Function Call Graph (LFCG) Engine.
Implements:
1. Exact Python AST extraction preserving line and column info.
2. Deterministic FileNode and FunctionNode URIs.
3. CONTAINS and CALLS edges only.
4. Lexical scope resolution: local calls, nested scopes, self calls, imports, aliases, relative imports.
5. Strict fail-closed semantics:
   - Dynamic dispatch, unknown receivers, monkey patching, builtins, external stdlib -> UNRESOLVED.
   - Plausible method matches are NEVER converted into exact calls.
6. Bit-for-bit deterministic serialization across runs.
"""

from __future__ import annotations

import os
import ast
import json
import math
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Any
from collections import defaultdict


# Provenance Tiers
TIER_A_EXACT_AST = "TIER_A_EXACT_AST"           # Direct AST local lexical or nested scope resolution
TIER_B_SCOPED_IMPORT = "TIER_B_SCOPED_IMPORT"   # Scoped import, alias binding, or relative import
TIER_C_RECEIVER_BOUND = "TIER_C_RECEIVER_BOUND" # Explicit self.method or cls.method within class
TIER_D_HEURISTIC_PATTERN = "TIER_D_HEURISTIC"   # Syntactic pattern match (never marked AST-exact)
TIER_E_UNRESOLVED = "TIER_E_UNRESOLVED"         # Dynamic, unknown receiver, external, or ambiguous

# Provenance Heuristic Weights
PROVENANCE_WEIGHTS = {
    TIER_A_EXACT_AST: 1.0,
    TIER_B_SCOPED_IMPORT: 0.9,
    TIER_C_RECEIVER_BOUND: 0.7,
    TIER_D_HEURISTIC_PATTERN: 0.4,
    TIER_E_UNRESOLVED: 0.0,
}

PYTHON_BUILTINS = {
    "abs", "all", "any", "ascii", "bin", "bool", "breakpoint", "bytearray", "bytes",
    "callable", "chr", "classmethod", "compile", "complex", "delattr", "dict", "dir",
    "divmod", "enumerate", "eval", "exec", "filter", "float", "format", "frozenset",
    "getattr", "globals", "hasattr", "hash", "help", "hex", "id", "input", "int",
    "isinstance", "issubclass", "iter", "len", "list", "locals", "map", "max",
    "memoryview", "min", "next", "object", "oct", "open", "ord", "pow", "print",
    "property", "range", "repr", "reversed", "round", "set", "setattr", "slice",
    "sorted", "staticmethod", "str", "sum", "super", "tuple", "type", "vars", "zip",
}

STDLIB_MODULES = {
    "os", "sys", "math", "json", "re", "time", "datetime", "collections", "itertools",
    "functools", "pathlib", "typing", "subprocess", "logging", "unittest", "tempfile",
    "shutil", "io", "copy", "traceback", "inspect", "importlib", "random", "hashlib",
    "socket", "threading", "multiprocessing", "queue", "asyncio", "warnings", "contextlib",
    "enum", "dataclasses", "abc", "argparse", "optparse", "csv", "xml", "html", "http",
}


@dataclass(frozen=True)
class FileNode:
    uri: str
    repo: str
    filepath: str
    language: str = "Python"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "FileNode",
            "uri": self.uri,
            "repo": self.repo,
            "filepath": self.filepath,
            "language": self.language,
        }


@dataclass(frozen=True)
class FunctionNode:
    uri: str
    file_uri: str
    name: str
    parent_class: Optional[str]  # Class name string or None (metadata only)
    is_method: bool
    is_test: bool
    is_nested: bool
    decorators: Tuple[str, ...]
    start_line: int
    end_line: int
    col_offset: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "FunctionNode",
            "uri": self.uri,
            "file_uri": self.file_uri,
            "name": self.name,
            "parent_class": self.parent_class,
            "is_method": self.is_method,
            "is_test": self.is_test,
            "is_nested": self.is_nested,
            "decorators": list(self.decorators),
            "start_line": self.start_line,
            "end_line": self.end_line,
            "col_offset": self.col_offset,
        }


@dataclass
class CallSiteExtraction:
    caller_file_uri: str
    caller_func_uri: Optional[str]
    line: int
    col: int
    raw_callee_expr: str
    identifier: str
    qualifier: Optional[str] = None
    is_attribute: bool = False
    is_dynamic: bool = False
    construct_category: str = "general_call"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "caller_file_uri": self.caller_file_uri,
            "caller_func_uri": self.caller_func_uri,
            "line": self.line,
            "col": self.col,
            "raw_callee_expr": self.raw_callee_expr,
            "identifier": self.identifier,
            "qualifier": self.qualifier,
            "is_attribute": self.is_attribute,
            "is_dynamic": self.is_dynamic,
            "construct_category": self.construct_category,
        }


@dataclass
class CallTargetResolution:
    extraction: CallSiteExtraction
    is_resolved: bool
    target_uris: List[str]
    selected_target_uri: Optional[str]
    candidate_count: int               # A(e)
    resolution_method: str
    resolution_status: str             # "EXACT", "HEURISTIC", "UNRESOLVED"
    provenance_tier: str
    ambiguity_penalty: float           # 1.0 / sqrt(A(e))
    heuristic_weight: float            # phi(e)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "extraction": self.extraction.to_dict(),
            "is_resolved": self.is_resolved,
            "target_uris": self.target_uris,
            "selected_target_uri": self.selected_target_uri,
            "candidate_count": self.candidate_count,
            "resolution_method": self.resolution_method,
            "resolution_status": self.resolution_status,
            "provenance_tier": self.provenance_tier,
            "ambiguity_penalty": round(self.ambiguity_penalty, 4),
            "heuristic_weight": round(self.heuristic_weight, 4),
        }


@dataclass
class LFCGEdge:
    edge_type: str                     # "CONTAINS" or "CALLS"
    source_uri: str
    target_uri: str
    provenance_tier: str
    heuristic_weight: float
    ambiguity_penalty: float
    effective_weight: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_type": self.edge_type,
            "source_uri": self.source_uri,
            "target_uri": self.target_uri,
            "provenance_tier": self.provenance_tier,
            "heuristic_weight": round(self.heuristic_weight, 4),
            "ambiguity_penalty": round(self.ambiguity_penalty, 4),
            "effective_weight": round(self.effective_weight, 4),
        }


class PythonLFCGEngine:
    """
    Dedicated Python-First Lean Function Call Graph (LFCG) Engine.
    Executes compiler-grade AST parsing, lexical scoping, import tracking,
    and strict fail-closed resolution.
    """

    def __init__(self, repo_name: str = "repo"):
        self.repo_name = repo_name
        self.file_nodes: Dict[str, FileNode] = {}
        self.function_nodes: Dict[str, FunctionNode] = {}
        self.extractions: List[CallSiteExtraction] = []
        self.resolutions: List[CallTargetResolution] = []
        self.edges: List[LFCGEdge] = []

        # Indices
        self.functions_by_name: Dict[str, List[FunctionNode]] = defaultdict(list)
        self.functions_by_file: Dict[str, List[FunctionNode]] = defaultdict(list)
        self.functions_by_class: Dict[Tuple[str, str], List[FunctionNode]] = defaultdict(list)
        self.files_by_module_path: Dict[str, str] = {}  # module dot path -> file_uri

        # Per-file parse metadata: file_uri -> dict of imports, aliases, scopes
        self.file_metadata: Dict[str, Dict[str, Any]] = {}

    def normalize_path(self, filepath: str) -> str:
        return filepath.replace("\\", "/").lstrip("/")

    def make_file_uri(self, filepath: str) -> str:
        norm = self.normalize_path(filepath)
        return f"file://{self.repo_name}/{norm}"

    def make_func_uri(self, filepath: str, parent_class: Optional[str], func_name: str, scope_prefix: str = "") -> str:
        norm = self.normalize_path(filepath)
        if parent_class:
            return f"func://{self.repo_name}/{norm}#{parent_class}.{func_name}"
        if scope_prefix:
            return f"func://{self.repo_name}/{norm}#{scope_prefix}.{func_name}"
        return f"func://{self.repo_name}/{norm}#{func_name}"

    def register_file(self, filepath: str) -> FileNode:
        norm = self.normalize_path(filepath)
        uri = self.make_file_uri(norm)
        if uri not in self.file_nodes:
            node = FileNode(uri=uri, repo=self.repo_name, filepath=norm, language="Python")
            self.file_nodes[uri] = node

            # Module dot-path registration (e.g. src/click/core.py -> click.core)
            mod_path = norm
            if mod_path.endswith(".py"):
                mod_path = mod_path[:-3]
            if mod_path.endswith("/__init__"):
                mod_path = mod_path[:-9]
            parts = [p for p in mod_path.split("/") if p]
            while parts and parts[0] in ("src", "lib", "python"):
                parts.pop(0)
            dot_path = ".".join(parts)
            if dot_path:
                self.files_by_module_path[dot_path] = uri
                # Also index bare filename without package prefix
                if parts:
                    self.files_by_module_path[parts[-1]] = uri

        return self.file_nodes[uri]

    def register_function(
        self,
        filepath: str,
        name: str,
        parent_class: Optional[str],
        is_method: bool,
        is_test: bool,
        is_nested: bool,
        decorators: List[str],
        start_line: int,
        end_line: int,
        col_offset: int,
        scope_prefix: str = "",
    ) -> FunctionNode:
        file_uri = self.make_file_uri(filepath)
        uri = self.make_func_uri(filepath, parent_class, name, scope_prefix)
        node = FunctionNode(
            uri=uri,
            file_uri=file_uri,
            name=name,
            parent_class=parent_class,
            is_method=is_method,
            is_test=is_test,
            is_nested=is_nested,
            decorators=tuple(decorators),
            start_line=start_line,
            end_line=end_line,
            col_offset=col_offset,
        )
        self.function_nodes[uri] = node
        self.functions_by_name[name].append(node)
        self.functions_by_file[file_uri].append(node)
        if parent_class:
            self.functions_by_class[(file_uri, parent_class)].append(node)

        # Emit CONTAINS edge
        contains_edge = LFCGEdge(
            edge_type="CONTAINS",
            source_uri=file_uri,
            target_uri=uri,
            provenance_tier=TIER_A_EXACT_AST,
            heuristic_weight=1.0,
            ambiguity_penalty=1.0,
            effective_weight=1.0,
        )
        self.edges.append(contains_edge)
        return node

    def resolve_relative_import_file(self, current_file_path: str, module_name: Optional[str], level: int) -> Optional[str]:
        """
        Resolves relative import syntax (e.g. from .utils import x, from ..models import y)
        to a concrete module path.
        """
        curr_dir = os.path.dirname(self.normalize_path(current_file_path))
        # level 1 is current dir (.), level 2 is parent (..), etc.
        parts = [p for p in curr_dir.split("/") if p]
        pop_count = level - 1
        if pop_count > len(parts):
            return None
        if pop_count > 0:
            parts = parts[:-pop_count]

        base_dir = "/".join(parts)
        sub_path = module_name.replace(".", "/") if module_name else ""
        target_mod = f"{base_dir}/{sub_path}" if sub_path else base_dir
        target_mod = target_mod.strip("/")

        # Check candidate file paths
        candidates = [
            f"{target_mod}.py",
            f"{target_mod}/__init__.py",
        ]
        for c in candidates:
            uri = self.make_file_uri(c)
            if uri in self.file_nodes:
                return uri

        # Fallback to dot path lookup
        dot = target_mod.replace("/", ".")
        if dot in self.files_by_module_path:
            return self.files_by_module_path[dot]

        return None

    def parse_source(self, filepath: str, source_code: str):
        """
        Pass 1: Syntax tree validation, function registration, import table construction.
        Catches syntax errors and logs fail-closed without crashing.
        """
        self.register_file(filepath)
        file_uri = self.make_file_uri(filepath)
        is_test_file = "test" in filepath.lower()

        try:
            tree = ast.parse(source_code, filename=filepath)
        except SyntaxError:
            # Fail closed on syntax error: file registered, 0 functions/edges
            self.file_metadata[file_uri] = {"syntax_error": True}
            return

        imports_map: Dict[str, Dict[str, Any]] = {}
        # alias -> {"type": "direct"|"from"|"relative", "mod": ..., "orig": ..., "level": ...}

        # Extract Imports
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    asname = alias.asname or name
                    imports_map[asname] = {
                        "type": "direct",
                        "mod": name,
                        "orig": name,
                        "level": 0,
                    }
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                level = node.level or 0
                for alias in node.names:
                    orig = alias.name
                    asname = alias.asname or orig
                    imports_map[asname] = {
                        "type": "from" if level == 0 else "relative",
                        "mod": mod,
                        "orig": orig,
                        "level": level,
                    }

        # Extract Function Definitions & Scopes
        class DefVisitor(ast.NodeVisitor):
            def __init__(self, engine: PythonLFCGEngine):
                self.engine = engine
                self.class_stack: List[str] = []
                self.func_stack: List[str] = []

            def visit_ClassDef(self, node: ast.ClassDef):
                self.class_stack.append(node.name)
                self.generic_visit(node)
                self.class_stack.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef):
                self._record(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                self._record(node)

            def _record(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
                parent_class = self.class_stack[-1] if self.class_stack else None
                is_method = parent_class is not None
                is_nested = len(self.func_stack) > 0
                scope_prefix = ".".join(self.func_stack) if is_nested else ""
                is_test = is_test_file or node.name.startswith("test_") or node.name.endswith("_test")

                # Decorators
                decorators = []
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Name):
                        decorators.append(dec.id)
                    elif isinstance(dec, ast.Attribute):
                        decorators.append(dec.attr)
                    elif isinstance(dec, ast.Call):
                        if isinstance(dec.func, ast.Name):
                            decorators.append(dec.func.id)
                        elif isinstance(dec.func, ast.Attribute):
                            decorators.append(dec.func.attr)

                self.engine.register_function(
                    filepath=filepath,
                    name=node.name,
                    parent_class=parent_class,
                    is_method=is_method,
                    is_test=is_test,
                    is_nested=is_nested,
                    decorators=decorators,
                    start_line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    col_offset=getattr(node, "col_offset", 0),
                    scope_prefix=scope_prefix,
                )

                self.func_stack.append(node.name)
                self.generic_visit(node)
                self.func_stack.pop()

        DefVisitor(self).visit(tree)

        self.file_metadata[file_uri] = {
            "syntax_error": False,
            "tree": tree,
            "imports_map": imports_map,
        }

    def resolve_all_calls(self):
        """
        Pass 2: Call-site extraction and step-by-step resolution across all indexed files.
        """
        for file_uri, meta in self.file_metadata.items():
            if meta.get("syntax_error", False):
                continue
            tree = meta["tree"]
            imports_map = meta["imports_map"]
            filepath = self.file_nodes[file_uri].filepath

            class CallVisitor(ast.NodeVisitor):
                def __init__(self, engine: PythonLFCGEngine):
                    self.engine = engine
                    self.class_stack: List[str] = []
                    self.func_stack: List[Tuple[str, Optional[str], str]] = []  # (name, parent_class, scope_prefix)
                    self.scope_local_vars: List[Set[str]] = []

                def visit_ClassDef(self, node: ast.ClassDef):
                    self.class_stack.append(node.name)
                    self.generic_visit(node)
                    self.class_stack.pop()

                def visit_FunctionDef(self, node: ast.FunctionDef):
                    self._handle_scope(node)

                def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                    self._handle_scope(node)

                def _handle_scope(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
                    parent = self.class_stack[-1] if self.class_stack else None
                    is_nested = len(self.func_stack) > 0
                    scope_prefix = ".".join([f[0] for f in self.func_stack]) if is_nested else ""
                    self.func_stack.append((node.name, parent, scope_prefix))
                    self.scope_local_vars.append(set())
                    self.generic_visit(node)
                    self.scope_local_vars.pop()
                    self.func_stack.pop()

                def visit_Assign(self, node: ast.Assign):
                    # Track assigned variables in local function scope
                    if self.scope_local_vars:
                        for tgt in node.targets:
                            if isinstance(tgt, ast.Name):
                                self.scope_local_vars[-1].add(tgt.id)
                    self.generic_visit(node)

                def visit_Call(self, node: ast.Call):
                    # 1. CALL-SITE EXTRACTION
                    line = getattr(node, "lineno", 0)
                    col = getattr(node, "col_offset", 0)
                    callee_repr = ast.unparse(node.func) if hasattr(ast, "unparse") else str(node.func)

                    caller_func_name, caller_parent_class, caller_scope_pfx = (
                        self.func_stack[-1] if self.func_stack else (None, None, "")
                    )
                    caller_func_uri = (
                        self.engine.make_func_uri(filepath, caller_parent_class, caller_func_name, caller_scope_pfx)
                        if caller_func_name else None
                    )

                    identifier = ""
                    qualifier = None
                    is_attr = False
                    is_dynamic = False
                    category = "general"

                    if isinstance(node.func, ast.Name):
                        identifier = node.func.id
                        category = "direct_identifier"
                    elif isinstance(node.func, ast.Attribute):
                        identifier = node.func.attr
                        is_attr = True
                        category = "attribute_call"
                        if isinstance(node.func.value, ast.Name):
                            qualifier = node.func.value.id
                        elif isinstance(node.func.value, ast.Attribute):
                            qualifier = node.func.value.attr
                        else:
                            qualifier = "<expr>"
                    elif isinstance(node.func, (ast.Subscript, ast.Call)):
                        identifier = "<dynamic_call>"
                        is_dynamic = True
                        category = "dynamic_dispatch"
                    else:
                        identifier = "<dynamic_call>"
                        is_dynamic = True
                        category = "dynamic_dispatch"

                    extraction = CallSiteExtraction(
                        caller_file_uri=file_uri,
                        caller_func_uri=caller_func_uri,
                        line=line,
                        col=col,
                        raw_callee_expr=callee_repr,
                        identifier=identifier,
                        qualifier=qualifier,
                        is_attribute=is_attr,
                        is_dynamic=is_dynamic,
                        construct_category=category,
                    )
                    self.engine.extractions.append(extraction)

                    # 2. CALL-TARGET RESOLUTION
                    res = self._resolve_target(
                        extraction,
                        caller_func_name,
                        caller_parent_class,
                        caller_scope_pfx,
                        imports_map,
                    )
                    self.engine.resolutions.append(res)

                    # Emit CALLS edge if resolved
                    if res.is_resolved and res.selected_target_uri and caller_func_uri:
                        amb_pen = res.ambiguity_penalty
                        weight = res.heuristic_weight * amb_pen
                        edge = LFCGEdge(
                            edge_type="CALLS",
                            source_uri=caller_func_uri,
                            target_uri=res.selected_target_uri,
                            provenance_tier=res.provenance_tier,
                            heuristic_weight=res.heuristic_weight,
                            ambiguity_penalty=amb_pen,
                            effective_weight=weight,
                        )
                        self.engine.edges.append(edge)

                    self.generic_visit(node)

                def _resolve_target(
                    self,
                    extraction: CallSiteExtraction,
                    caller_func_name: Optional[str],
                    caller_parent_class: Optional[str],
                    caller_scope_pfx: str,
                    imports: Dict[str, Dict[str, Any]],
                ) -> CallTargetResolution:
                    ident = extraction.identifier

                    # Rule 1: Dynamic dispatch
                    if extraction.is_dynamic or ident in ("<dynamic_call>", "<expr>"):
                        return CallTargetResolution(
                            extraction=extraction,
                            is_resolved=False,
                            target_uris=[],
                            selected_target_uri=None,
                            candidate_count=0,
                            resolution_method="unsupported_dynamic_dispatch",
                            resolution_status="UNRESOLVED",
                            provenance_tier=TIER_E_UNRESOLVED,
                            ambiguity_penalty=0.0,
                            heuristic_weight=0.0,
                        )

                    # Rule 2: Python Builtins
                    if ident in PYTHON_BUILTINS and not extraction.is_attribute:
                        return CallTargetResolution(
                            extraction=extraction,
                            is_resolved=False,
                            target_uris=[],
                            selected_target_uri=None,
                            candidate_count=0,
                            resolution_method="builtin_filter",
                            resolution_status="UNRESOLVED",
                            provenance_tier=TIER_E_UNRESOLVED,
                            ambiguity_penalty=0.0,
                            heuristic_weight=0.0,
                        )

                    # Rule 3: Function Shadowing by Local Variable Assignment
                    if self.scope_local_vars and ident in self.scope_local_vars[-1]:
                        return CallTargetResolution(
                            extraction=extraction,
                            is_resolved=False,
                            target_uris=[],
                            selected_target_uri=None,
                            candidate_count=0,
                            resolution_method="shadowed_by_local_scope",
                            resolution_status="UNRESOLVED",
                            provenance_tier=TIER_E_UNRESOLVED,
                            ambiguity_penalty=0.0,
                            heuristic_weight=0.0,
                        )

                    # Rule 4: Recursive call to current enclosing function
                    if not extraction.is_attribute and caller_func_name and ident == caller_func_name:
                        cur_uri = self.engine.make_func_uri(filepath, caller_parent_class, caller_func_name, caller_scope_pfx)
                        return CallTargetResolution(
                            extraction=extraction,
                            is_resolved=True,
                            target_uris=[cur_uri],
                            selected_target_uri=cur_uri,
                            candidate_count=1,
                            resolution_method="ast_recursive_self_call",
                            resolution_status="EXACT",
                            provenance_tier=TIER_A_EXACT_AST,
                            ambiguity_penalty=1.0,
                            heuristic_weight=PROVENANCE_WEIGHTS[TIER_A_EXACT_AST],
                        )

                    # Rule 5: Self / Cls method call in same class
                    if extraction.is_attribute and extraction.qualifier in ("self", "cls") and caller_parent_class:
                        class_funcs = self.engine.functions_by_class.get((file_uri, caller_parent_class), [])
                        matches = [f for f in class_funcs if f.name == ident]
                        if len(matches) == 1:
                            target = matches[0]
                            return CallTargetResolution(
                                extraction=extraction,
                                is_resolved=True,
                                target_uris=[target.uri],
                                selected_target_uri=target.uri,
                                candidate_count=1,
                                resolution_method="ast_self_method_binding",
                                resolution_status="EXACT",
                                provenance_tier=TIER_C_RECEIVER_BOUND,
                                ambiguity_penalty=1.0,
                                heuristic_weight=PROVENANCE_WEIGHTS[TIER_C_RECEIVER_BOUND],
                            )

                    # Rule 6: Nested function call within outer function
                    if not extraction.is_attribute and caller_func_name:
                        file_funcs = self.engine.functions_by_file.get(file_uri, [])
                        nested_matches = [
                            f for f in file_funcs
                            if f.name == ident and f.is_nested and f.start_line > (
                                getattr(self.engine.function_nodes.get(
                                    self.engine.make_func_uri(filepath, caller_parent_class, caller_func_name, caller_scope_pfx)
                                ), "start_line", 0)
                            )
                        ]
                        if len(nested_matches) == 1:
                            target = nested_matches[0]
                            return CallTargetResolution(
                                extraction=extraction,
                                is_resolved=True,
                                target_uris=[target.uri],
                                selected_target_uri=target.uri,
                                candidate_count=1,
                                resolution_method="ast_nested_scope_binding",
                                resolution_status="EXACT",
                                provenance_tier=TIER_A_EXACT_AST,
                                ambiguity_penalty=1.0,
                                heuristic_weight=PROVENANCE_WEIGHTS[TIER_A_EXACT_AST],
                            )

                    # Rule 7: Local module-level function call in same file
                    if not extraction.is_attribute:
                        file_funcs = self.engine.functions_by_file.get(file_uri, [])
                        local_matches = [f for f in file_funcs if f.name == ident and not f.is_method and not f.is_nested]
                        if len(local_matches) == 1:
                            target = local_matches[0]
                            return CallTargetResolution(
                                extraction=extraction,
                                is_resolved=True,
                                target_uris=[target.uri],
                                selected_target_uri=target.uri,
                                candidate_count=1,
                                resolution_method="ast_local_lexical_binding",
                                resolution_status="EXACT",
                                provenance_tier=TIER_A_EXACT_AST,
                                ambiguity_penalty=1.0,
                                heuristic_weight=PROVENANCE_WEIGHTS[TIER_A_EXACT_AST],
                            )

                    # Rule 8: Scoped Imports (Direct, Aliased, and Relative)
                    # Case A: Unqualified name imported from module
                    if not extraction.is_attribute and ident in imports:
                        imp = imports[ident]
                        # Relative import
                        if imp["type"] == "relative":
                            target_file_uri = self.engine.resolve_relative_import_file(filepath, imp["mod"], imp["level"])
                            if target_file_uri:
                                target_funcs = self.engine.functions_by_file.get(target_file_uri, [])
                                matches = [f for f in target_funcs if f.name == imp["orig"]]
                                if len(matches) == 1:
                                    target = matches[0]
                                    return CallTargetResolution(
                                        extraction=extraction,
                                        is_resolved=True,
                                        target_uris=[target.uri],
                                        selected_target_uri=target.uri,
                                        candidate_count=1,
                                        resolution_method="ast_relative_import_binding",
                                        resolution_status="EXACT",
                                        provenance_tier=TIER_B_SCOPED_IMPORT,
                                        ambiguity_penalty=1.0,
                                        heuristic_weight=PROVENANCE_WEIGHTS[TIER_B_SCOPED_IMPORT],
                                    )
                        elif imp["type"] == "from":
                            # e.g. from click.utils import echo
                            mod = imp["mod"]
                            orig = imp["orig"]
                            # Check if mod is standard library
                            root_mod = mod.split(".")[0]
                            if root_mod in STDLIB_MODULES:
                                return CallTargetResolution(
                                    extraction=extraction,
                                    is_resolved=False,
                                    target_uris=[],
                                    selected_target_uri=None,
                                    candidate_count=0,
                                    resolution_method="external_stdlib_import",
                                    resolution_status="UNRESOLVED",
                                    provenance_tier=TIER_E_UNRESOLVED,
                                    ambiguity_penalty=0.0,
                                    heuristic_weight=0.0,
                                )
                            # Internal repo lookup
                            if mod in self.engine.files_by_module_path:
                                target_f_uri = self.engine.files_by_module_path[mod]
                                target_funcs = self.engine.functions_by_file.get(target_f_uri, [])
                                matches = [f for f in target_funcs if f.name == orig]
                                if len(matches) == 1:
                                    target = matches[0]
                                    return CallTargetResolution(
                                        extraction=extraction,
                                        is_resolved=True,
                                        target_uris=[target.uri],
                                        selected_target_uri=target.uri,
                                        candidate_count=1,
                                        resolution_method="ast_import_symbol_binding",
                                        resolution_status="EXACT",
                                        provenance_tier=TIER_B_SCOPED_IMPORT,
                                        ambiguity_penalty=1.0,
                                        heuristic_weight=PROVENANCE_WEIGHTS[TIER_B_SCOPED_IMPORT],
                                    )

                    # Case B: Qualified module call (e.g. math.sqrt() or helper.run())
                    if extraction.is_attribute and extraction.qualifier in imports:
                        imp = imports[extraction.qualifier]
                        root_mod = imp["mod"].split(".")[0]
                        if root_mod in STDLIB_MODULES:
                            return CallTargetResolution(
                                extraction=extraction,
                                is_resolved=False,
                                target_uris=[],
                                selected_target_uri=None,
                                candidate_count=0,
                                resolution_method="external_stdlib_call",
                                resolution_status="UNRESOLVED",
                                provenance_tier=TIER_E_UNRESOLVED,
                                ambiguity_penalty=0.0,
                                heuristic_weight=0.0,
                            )
                        if imp["mod"] in self.engine.files_by_module_path:
                            target_f_uri = self.engine.files_by_module_path[imp["mod"]]
                            target_funcs = self.engine.functions_by_file.get(target_f_uri, [])
                            matches = [f for f in target_funcs if f.name == ident]
                            if len(matches) == 1:
                                target = matches[0]
                                return CallTargetResolution(
                                    extraction=extraction,
                                    is_resolved=True,
                                    target_uris=[target.uri],
                                    selected_target_uri=target.uri,
                                    candidate_count=1,
                                    resolution_method="ast_module_qualified_call",
                                    resolution_status="EXACT",
                                    provenance_tier=TIER_B_SCOPED_IMPORT,
                                    ambiguity_penalty=1.0,
                                    heuristic_weight=PROVENANCE_WEIGHTS[TIER_B_SCOPED_IMPORT],
                                )

                    # Rule 9: Unknown Receiver Calls (e.g. obj.method())
                    # Invariant: Never convert a plausible method-name match into an exact call!
                    if extraction.is_attribute and extraction.qualifier not in ("self", "cls"):
                        global_matches = self.engine.functions_by_name.get(ident, [])
                        method_matches = [m for m in global_matches if m.is_method]
                        count = len(method_matches)
                        # Unknown receiver is marked UNRESOLVED (Tier E) to prevent false positive edges
                        amb_pen = (1.0 / math.sqrt(count)) if count > 0 else 0.0
                        return CallTargetResolution(
                            extraction=extraction,
                            is_resolved=False,
                            target_uris=[m.uri for m in method_matches],
                            selected_target_uri=None,
                            candidate_count=count,
                            resolution_method="unknown_receiver_unresolved",
                            resolution_status="UNRESOLVED",
                            provenance_tier=TIER_E_UNRESOLVED,
                            ambiguity_penalty=amb_pen,
                            heuristic_weight=0.0,
                        )

                    # Rule 10: Unqualified Global Symbol Match (Only if unique across entire repo)
                    if not extraction.is_attribute:
                        global_matches = [
                            f for f in self.engine.functions_by_name.get(ident, [])
                            if not f.is_method
                        ]
                        if len(global_matches) == 1:
                            target = global_matches[0]
                            return CallTargetResolution(
                                extraction=extraction,
                                is_resolved=True,
                                target_uris=[target.uri],
                                selected_target_uri=target.uri,
                                candidate_count=1,
                                resolution_method="unique_global_symbol_match",
                                resolution_status="HEURISTIC",
                                provenance_tier=TIER_D_HEURISTIC_PATTERN,
                                ambiguity_penalty=1.0,
                                heuristic_weight=PROVENANCE_WEIGHTS[TIER_D_HEURISTIC_PATTERN],
                            )
                        elif len(global_matches) > 1:
                            count = len(global_matches)
                            return CallTargetResolution(
                                extraction=extraction,
                                is_resolved=False,
                                target_uris=[m.uri for m in global_matches],
                                selected_target_uri=None,
                                candidate_count=count,
                                resolution_method="ambiguous_global_symbols",
                                resolution_status="UNRESOLVED",
                                provenance_tier=TIER_E_UNRESOLVED,
                                ambiguity_penalty=1.0 / math.sqrt(count),
                                heuristic_weight=0.0,
                            )

                    # Default: Unresolved
                    return CallTargetResolution(
                        extraction=extraction,
                        is_resolved=False,
                        target_uris=[],
                        selected_target_uri=None,
                        candidate_count=0,
                        resolution_method="unresolved_identifier",
                        resolution_status="UNRESOLVED",
                        provenance_tier=TIER_E_UNRESOLVED,
                        ambiguity_penalty=0.0,
                        heuristic_weight=0.0,
                    )

            CallVisitor(self).visit(tree)

    def serialize_graph(self) -> str:
        """
        Produces bit-for-bit deterministic JSON serialization.
        Guarantees SHA256(Run 1) == SHA256(Run 2) == SHA256(Run 3).
        """
        nodes_data = [
            node.to_dict() for _, node in sorted(self.file_nodes.items(), key=lambda x: x[0])
        ] + [
            node.to_dict() for _, node in sorted(self.function_nodes.items(), key=lambda x: x[0])
        ]

        edges_data = [
            edge.to_dict() for edge in sorted(
                self.edges,
                key=lambda e: (e.edge_type, e.source_uri, e.target_uri, e.provenance_tier)
            )
        ]

        payload = {
            "schema_version": "PYTHON_LFCG_v1.0",
            "repo": self.repo_name,
            "counts": {
                "file_nodes": len(self.file_nodes),
                "function_nodes": len(self.function_nodes),
                "contains_edges": sum(1 for e in self.edges if e.edge_type == "CONTAINS"),
                "calls_edges": sum(1 for e in self.edges if e.edge_type == "CALLS"),
                "total_extractions": len(self.extractions),
                "total_resolutions": len(self.resolutions),
            },
            "nodes": nodes_data,
            "edges": edges_data,
        }
        return json.dumps(payload, sort_keys=True, indent=2)

    def get_serialized_sha256(self) -> str:
        serialized = self.serialize_graph()
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
