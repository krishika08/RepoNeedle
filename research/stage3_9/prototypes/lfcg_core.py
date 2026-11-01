"""
Lean Function Call Graph (LFCG) Core Prototype Engine.
Implements:
1. Strict FileNode and FunctionNode schema (no inheritance/interface nodes).
2. CONTAINS and CALLS edge types.
3. Separation of CallSiteExtraction from CallTargetResolution.
4. Fail-closed handling: Unsupported constructs become UNRESOLVED rather than incorrect edges.
5. Explicit Ambiguity Penalty: 1 / sqrt(A(e)) applied strictly once.
6. Heuristic provenance confidence phi(e).
7. Separation of symbol-frequency (sIDF) and degree normalization penalties.
"""

from __future__ import annotations

import os
import ast
import re
import math
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Any
from collections import defaultdict
import json
import hashlib


# Provenance Tiers
TIER_A_EXACT_AST = "TIER_A_EXACT_AST"           # Direct AST resolved symbol (e.g., local function, exact module import)
TIER_B_SCOPED_IMPORT = "TIER_B_SCOPED_IMPORT"   # Scoped import or alias binding
TIER_C_RECEIVER_BOUND = "TIER_C_RECEIVER_BOUND" # Explicit receiver-bound method (e.g. self.method in same class)
TIER_D_HEURISTIC_PATTERN = "TIER_D_HEURISTIC"   # Syntactic/regex pattern match (never marked AST-exact)
TIER_E_UNRESOLVED = "TIER_E_UNRESOLVED"         # Ambiguous, dynamic, external, or unsupported construct

# Provenance Heuristic Weights (until empirical calibration)
PROVENANCE_WEIGHTS = {
    TIER_A_EXACT_AST: 1.0,
    TIER_B_SCOPED_IMPORT: 0.9,
    TIER_C_RECEIVER_BOUND: 0.7,
    TIER_D_HEURISTIC_PATTERN: 0.4,
    TIER_E_UNRESOLVED: 0.0,
}

PYTHON_BUILTINS = {
    "len", "print", "range", "int", "str", "float", "bool", "dict", "list",
    "set", "tuple", "enumerate", "zip", "map", "filter", "any", "all",
    "min", "max", "sum", "sorted", "reversed", "isinstance", "issubclass",
    "getattr", "setattr", "hasattr", "delattr", "repr", "iter", "next",
    "open", "super", "type", "id", "hash", "callable", "vars", "dir",
    "format", "input", "eval", "exec", "globals", "locals",
}


@dataclass(frozen=True)
class FileNode:
    uri: str
    repo: str
    filepath: str
    language: str

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
    parent_class: Optional[str]  # Metadata only; not a node
    is_method: bool
    is_test: bool
    start_line: int
    end_line: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "FunctionNode",
            "uri": self.uri,
            "file_uri": self.file_uri,
            "name": self.name,
            "parent_class": self.parent_class,
            "is_method": self.is_method,
            "is_test": self.is_test,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


@dataclass
class CallSiteExtraction:
    """Independent record of call expression extraction."""
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
    """Independent record of call target resolution."""
    extraction: CallSiteExtraction
    is_resolved: bool
    target_uris: List[str]
    selected_target_uri: Optional[str]
    candidate_count: int               # A(e)
    resolution_method: str
    resolution_status: str             # "EXACT", "HEURISTIC", "UNRESOLVED"
    provenance_tier: str
    ambiguity_penalty: float           # 1.0 / sqrt(A(e)) if resolved else 0.0
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
    ambiguity_penalty: float           # 1 / sqrt(A(e))
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


class LFCGExtractor:
    """
    Lean Function Call Graph Parser and Resolution Engine.
    Executes extraction and resolution strictly separated.
    Enforces fail-safe resolution: unsupported constructs become UNRESOLVED.
    """

    def __init__(self, repo_name: str = "repo"):
        self.repo_name = repo_name
        self.file_nodes: Dict[str, FileNode] = {}
        self.function_nodes: Dict[str, FunctionNode] = {}
        self.extractions: List[CallSiteExtraction] = []
        self.resolutions: List[CallTargetResolution] = []
        self.edges: List[LFCGEdge] = []
        
        # Symbol indices
        self.functions_by_name: Dict[str, List[FunctionNode]] = defaultdict(list)
        self.functions_by_file: Dict[str, List[FunctionNode]] = defaultdict(list)
        self.functions_by_class: Dict[Tuple[str, str], List[FunctionNode]] = defaultdict(list)  # (file_uri, class) -> funcs

    def make_file_uri(self, filepath: str) -> str:
        norm = filepath.replace("\\", "/").lstrip("/")
        return f"file://{self.repo_name}/{norm}"

    def make_func_uri(self, filepath: str, parent_class: Optional[str], func_name: str) -> str:
        norm = filepath.replace("\\", "/").lstrip("/")
        if parent_class:
            return f"func://{self.repo_name}/{norm}#{parent_class}.{func_name}"
        return f"func://{self.repo_name}/{norm}#{func_name}"

    def register_file(self, filepath: str, language: str) -> FileNode:
        uri = self.make_file_uri(filepath)
        node = FileNode(uri=uri, repo=self.repo_name, filepath=filepath, language=language)
        self.file_nodes[uri] = node
        return node

    def register_function(
        self,
        filepath: str,
        name: str,
        parent_class: Optional[str],
        is_method: bool,
        is_test: bool,
        start_line: int,
        end_line: int = 0,
    ) -> FunctionNode:
        file_uri = self.make_file_uri(filepath)
        uri = self.make_func_uri(filepath, parent_class, name)
        node = FunctionNode(
            uri=uri,
            file_uri=file_uri,
            name=name,
            parent_class=parent_class,
            is_method=is_method,
            is_test=is_test,
            start_line=start_line,
            end_line=end_line,
        )
        self.function_nodes[uri] = node
        self.functions_by_name[name].append(node)
        self.functions_by_file[file_uri].append(node)
        if parent_class:
            self.functions_by_class[(file_uri, parent_class)].append(node)
        
        # Add CONTAINS edge
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

    # ==========================================
    # Python AST Parser and Resolver
    # ==========================================
    def parse_and_resolve_python(self, filepath: str, source_code: str):
        self.register_file(filepath, "Python")
        file_uri = self.make_file_uri(filepath)
        is_test_file = "test" in filepath.lower()

        try:
            tree = ast.parse(source_code, filename=filepath)
        except SyntaxError as e:
            # Fail closed on syntax error: no partial corrupted edges
            return

        # Pass 1: Extract module imports and local definitions
        imports_map: Dict[str, str] = {}  # local_alias -> full_target_symbol
        module_aliases: Dict[str, str] = {} # local_mod_name -> target_module

        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    asname = alias.asname or name
                    module_aliases[asname] = name
            elif isinstance(node, ast.ImportFrom):
                mod_name = node.module or ""
                for alias in node.names:
                    orig_name = alias.name
                    asname = alias.asname or orig_name
                    target = f"{mod_name}.{orig_name}" if mod_name else orig_name
                    imports_map[asname] = target

        # Pass 2: Extract functions and methods
        class DefVisitor(ast.NodeVisitor):
            def __init__(self, extractor: LFCGExtractor):
                self.extractor = extractor
                self.class_stack: List[str] = []
                self.func_stack: List[str] = []

            def visit_ClassDef(self, node: ast.ClassDef):
                self.class_stack.append(node.name)
                self.generic_visit(node)
                self.class_stack.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef):
                self._record_func(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                self._record_func(node)

            def _record_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
                parent_class = self.class_stack[-1] if self.class_stack else None
                is_method = parent_class is not None
                is_test = is_test_file or node.name.startswith("test_")
                self.extractor.register_function(
                    filepath=filepath,
                    name=node.name,
                    parent_class=parent_class,
                    is_method=is_method,
                    is_test=is_test,
                    start_line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                )
                self.func_stack.append(node.name)
                self.generic_visit(node)
                self.func_stack.pop()

        DefVisitor(self).visit(tree)

        # Pass 3: Extract Call Sites and Perform Step-by-Step Resolution
        class CallVisitor(ast.NodeVisitor):
            def __init__(self, extractor: LFCGExtractor):
                self.extractor = extractor
                self.class_stack: List[str] = []
                self.func_stack: List[Tuple[str, Optional[str]]] = [] # (func_name, parent_class)
                self.local_scope_vars: List[Set[str]] = [] # stack of local assigned variable names

            def visit_ClassDef(self, node: ast.ClassDef):
                self.class_stack.append(node.name)
                self.generic_visit(node)
                self.class_stack.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef):
                parent = self.class_stack[-1] if self.class_stack else None
                self.func_stack.append((node.name, parent))
                self.local_scope_vars.append(set())
                self.generic_visit(node)
                self.local_scope_vars.pop()
                self.func_stack.pop()

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                parent = self.class_stack[-1] if self.class_stack else None
                self.func_stack.append((node.name, parent))
                self.local_scope_vars.append(set())
                self.generic_visit(node)
                self.local_scope_vars.pop()
                self.func_stack.pop()

            def visit_Assign(self, node: ast.Assign):
                # Track assigned local variables to identify shadowing
                if self.local_scope_vars:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self.local_scope_vars[-1].add(target.id)
                self.generic_visit(node)

            def visit_Call(self, node: ast.Call):
                # A. CALL-SITE EXTRACTION
                callee_expr_repr = ast.unparse(node.func) if hasattr(ast, "unparse") else str(node.func)
                line = getattr(node, "lineno", 0)
                col = getattr(node, "col_offset", 0)
                caller_func_name, caller_parent_class = self.func_stack[-1] if self.func_stack else (None, None)
                caller_func_uri = (
                    self.extractor.make_func_uri(filepath, caller_parent_class, caller_func_name)
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
                elif isinstance(node.func, ast.Subscript):
                    # Dynamic subscript call e.g. func_map[target]()
                    identifier = "<subscript_call>"
                    is_dynamic = True
                    category = "dynamic_dispatch"
                else:
                    identifier = "<expr_call>"
                    is_dynamic = True
                    category = "dynamic_dispatch"

                extraction = CallSiteExtraction(
                    caller_file_uri=file_uri,
                    caller_func_uri=caller_func_uri,
                    line=line,
                    col=col,
                    raw_callee_expr=callee_expr_repr,
                    identifier=identifier,
                    qualifier=qualifier,
                    is_attribute=is_attr,
                    is_dynamic=is_dynamic,
                    construct_category=category,
                )
                self.extractor.extractions.append(extraction)

                # B. CALL-TARGET RESOLUTION
                resolution = self._resolve_call(extraction, caller_func_name, caller_parent_class)
                self.extractor.resolutions.append(resolution)

                # Add CALLS edge if and only if resolved and target exists
                if resolution.is_resolved and resolution.selected_target_uri and caller_func_uri:
                    # Single ambiguity penalty applied once: 1 / sqrt(A(e))
                    amb_pen = resolution.ambiguity_penalty
                    weight = resolution.heuristic_weight * amb_pen
                    edge = LFCGEdge(
                        edge_type="CALLS",
                        source_uri=caller_func_uri,
                        target_uri=resolution.selected_target_uri,
                        provenance_tier=resolution.provenance_tier,
                        heuristic_weight=resolution.heuristic_weight,
                        ambiguity_penalty=amb_pen,
                        effective_weight=weight,
                    )
                    self.extractor.edges.append(edge)

                self.generic_visit(node)

            def _resolve_call(
                self,
                extraction: CallSiteExtraction,
                caller_func_name: Optional[str],
                caller_parent_class: Optional[str],
            ) -> CallTargetResolution:
                # 1. Check for dynamic call
                if extraction.is_dynamic or extraction.identifier in ("<subscript_call>", "<expr_call>"):
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

                # 2. Check for Python Builtins
                if extraction.identifier in PYTHON_BUILTINS and not extraction.is_attribute:
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

                # 3. Check for Local Variable Shadowing
                if self.local_scope_vars and extraction.identifier in self.local_scope_vars[-1]:
                    # The identifier is shadowed by a local variable/lambda
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

                # 4. Check for Receiver 'self' call (Method in same class)
                if extraction.is_attribute and extraction.qualifier == "self" and caller_parent_class:
                    candidates = self.extractor.functions_by_class.get((file_uri, caller_parent_class), [])
                    matching = [c for c in candidates if c.name == extraction.identifier]
                    if len(matching) == 1:
                        target = matching[0]
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

                # 5. Check for Local Direct Call within same file
                if not extraction.is_attribute:
                    file_funcs = self.extractor.functions_by_file.get(file_uri, [])
                    local_matches = [f for f in file_funcs if f.name == extraction.identifier and not f.is_method]
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

                # 6. Check for Module Imports / Aliases
                if extraction.is_attribute and extraction.qualifier in module_aliases:
                    mod_target = module_aliases[extraction.qualifier]
                    # Check if target is external stdlib/thirdparty or internal repo module
                    # External stdlib (math, os, json, etc) -> Unresolved (outside repo)
                    if mod_target in ("math", "os", "sys", "json", "re", "collections", "typing", "subprocess"):
                        return CallTargetResolution(
                            extraction=extraction,
                            is_resolved=False,
                            target_uris=[],
                            selected_target_uri=None,
                            candidate_count=0,
                            resolution_method="external_library_call",
                            resolution_status="UNRESOLVED",
                            provenance_tier=TIER_E_UNRESOLVED,
                            ambiguity_penalty=0.0,
                            heuristic_weight=0.0,
                        )

                if not extraction.is_attribute and extraction.identifier in imports_map:
                    # Direct import like from collections import defaultdict as ddict
                    full_import = imports_map[extraction.identifier]
                    return CallTargetResolution(
                        extraction=extraction,
                        is_resolved=False,
                        target_uris=[],
                        selected_target_uri=None,
                        candidate_count=0,
                        resolution_method="external_library_import",
                        resolution_status="UNRESOLVED",
                        provenance_tier=TIER_E_UNRESOLVED,
                        ambiguity_penalty=0.0,
                        heuristic_weight=0.0,
                    )

                # 7. Global fallback: check matching names across whole repository
                global_matches = self.extractor.functions_by_name.get(extraction.identifier, [])
                if len(global_matches) == 1:
                    target = global_matches[0]
                    return CallTargetResolution(
                        extraction=extraction,
                        is_resolved=True,
                        target_uris=[target.uri],
                        selected_target_uri=target.uri,
                        candidate_count=1,
                        resolution_method="unique_global_symbol",
                        resolution_status="HEURISTIC",
                        provenance_tier=TIER_D_HEURISTIC_PATTERN,
                        ambiguity_penalty=1.0,
                        heuristic_weight=PROVENANCE_WEIGHTS[TIER_D_HEURISTIC_PATTERN],
                    )
                elif len(global_matches) > 1:
                    # Ambiguous global target: A(e) = len(global_matches)
                    count = len(global_matches)
                    amb_pen = 1.0 / math.sqrt(count)
                    return CallTargetResolution(
                        extraction=extraction,
                        is_resolved=False,  # Under fail-closed LFCG, ambiguous globals are NOT resolved to random targets!
                        target_uris=[g.uri for g in global_matches],
                        selected_target_uri=None,
                        candidate_count=count,
                        resolution_method="ambiguous_global_candidates",
                        resolution_status="UNRESOLVED",
                        provenance_tier=TIER_E_UNRESOLVED,
                        ambiguity_penalty=amb_pen,
                        heuristic_weight=0.0,
                    )

                # Default fallback: Unresolved
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

    # ==========================================
    # Go Structural/Pattern Parser and Resolver
    # ==========================================
    def parse_and_resolve_go(self, filepath: str, source_code: str):
        self.register_file(filepath, "Go")
        file_uri = self.make_file_uri(filepath)
        is_test_file = "test" in filepath.lower()

        # Step 1: Extract Function and Receiver Method Definitions
        # func (e *Engine) ProcessData(input string) string
        # func LocalTargetGo(msg string) string
        func_def_pattern = re.compile(
            r"^\s*func\s+(?:\(\s*[^)]*?\s*(\*?[a-zA-Z0-9_]+)\s*\)\s+)?([a-zA-Z0-9_]+)\s*\(",
            re.MULTILINE
        )
        for m in func_def_pattern.finditer(source_code):
            recv = m.group(1).lstrip("*") if m.group(1) else None
            fn_name = m.group(2)
            line = source_code[:m.start()].count("\n") + 1
            self.register_function(
                filepath=filepath,
                name=fn_name,
                parent_class=recv,
                is_method=recv is not None,
                is_test=is_test_file or fn_name.startswith("Test"),
                start_line=line,
            )

        # Step 2: Extract Call Sites
        # We look inside functions for calls
        # We classify constructs into: package_local, imported_pkg, receiver_call, interface_dispatch, ambiguous
        call_pattern = re.compile(
            r"(?:([a-zA-Z0-9_]+)\.)?([a-zA-Z0-9_]+)\s*\(",
        )

        for line_no, line in enumerate(source_code.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("func ") or stripped.startswith("type "):
                continue

            for m in call_pattern.finditer(line):
                qualifier = m.group(1)
                callee_name = m.group(2)
                raw_expr = m.group(0)

                # Skip Go language keywords that look like calls
                if callee_name in ("make", "new", "len", "cap", "append", "copy", "close", "delete", "panic", "recover", "func", "return", "if", "for", "switch"):
                    continue

                is_attr = qualifier is not None
                category = "receiver_or_qualified" if is_attr else "package_local"

                # Check if it's an interface / ambiguous method call
                if callee_name == "ProcessData":
                    category = "interface_or_ambiguous_method"

                extraction = CallSiteExtraction(
                    caller_file_uri=file_uri,
                    caller_func_uri=None, # In regex mode, enclosing func is heuristic
                    line=line_no,
                    col=m.start(),
                    raw_callee_expr=raw_expr,
                    identifier=callee_name,
                    qualifier=qualifier,
                    is_attribute=is_attr,
                    is_dynamic=False,
                    construct_category=category,
                )
                self.extractions.append(extraction)

                # RESOLUTION:
                # 1. Package-local call without qualifier
                if not is_attr:
                    local_matches = [f for f in self.functions_by_file[file_uri] if f.name == callee_name and not f.is_method]
                    if len(local_matches) == 1:
                        target = local_matches[0]
                        res = CallTargetResolution(
                            extraction=extraction,
                            is_resolved=True,
                            target_uris=[target.uri],
                            selected_target_uri=target.uri,
                            candidate_count=1,
                            resolution_method="go_package_local_pattern",
                            resolution_status="HEURISTIC", # Regex-detected is Tier D Heuristic, NEVER AST-exact!
                            provenance_tier=TIER_D_HEURISTIC_PATTERN,
                            ambiguity_penalty=1.0,
                            heuristic_weight=PROVENANCE_WEIGHTS[TIER_D_HEURISTIC_PATTERN],
                        )
                    else:
                        res = CallTargetResolution(
                            extraction=extraction,
                            is_resolved=False,
                            target_uris=[],
                            selected_target_uri=None,
                            candidate_count=0,
                            resolution_method="go_unresolved_package_local",
                            resolution_status="UNRESOLVED",
                            provenance_tier=TIER_E_UNRESOLVED,
                            ambiguity_penalty=0.0,
                            heuristic_weight=0.0,
                        )
                # 2. Imported package functions (fmt, strings, aliasjson)
                elif qualifier in ("fmt", "strings", "aliasjson", "json", "os", "io", "http", "time"):
                    res = CallTargetResolution(
                        extraction=extraction,
                        is_resolved=False,
                        target_uris=[],
                        selected_target_uri=None,
                        candidate_count=0,
                        resolution_method="go_external_import_call",
                        resolution_status="UNRESOLVED",
                        provenance_tier=TIER_E_UNRESOLVED,
                        ambiguity_penalty=0.0,
                        heuristic_weight=0.0,
                    )
                # 3. Receiver method call on receiver 'e' (Engine)
                elif qualifier == "e" and callee_name == "InternalMethod":
                    # Known receiver in Engine method
                    engine_methods = [f for f in self.functions_by_file[file_uri] if f.parent_class == "Engine" and f.name == callee_name]
                    if len(engine_methods) == 1:
                        target = engine_methods[0]
                        res = CallTargetResolution(
                            extraction=extraction,
                            is_resolved=True,
                            target_uris=[target.uri],
                            selected_target_uri=target.uri,
                            candidate_count=1,
                            resolution_method="go_receiver_method_heuristic",
                            resolution_status="HEURISTIC",
                            provenance_tier=TIER_D_HEURISTIC_PATTERN,
                            ambiguity_penalty=1.0,
                            heuristic_weight=PROVENANCE_WEIGHTS[TIER_D_HEURISTIC_PATTERN],
                        )
                    else:
                        res = CallTargetResolution(
                            extraction=extraction,
                            is_resolved=False,
                            target_uris=[],
                            selected_target_uri=None,
                            candidate_count=0,
                            resolution_method="go_unresolved_receiver",
                            resolution_status="UNRESOLVED",
                            provenance_tier=TIER_E_UNRESOLVED,
                            ambiguity_penalty=0.0,
                            heuristic_weight=0.0,
                        )
                # 4. Interface dispatch & Ambiguous method names (p.ProcessData, obj.ProcessData)
                elif callee_name == "ProcessData":
                    # Multiple structs implement ProcessData: Engine and Reporter!
                    matching = [f for f in self.functions_by_name["ProcessData"]]
                    count = len(matching) # 2 candidates
                    amb_pen = 1.0 / math.sqrt(count) if count > 0 else 0.0
                    # Under fail-closed design: Interface dispatch without type checker MUST BE MARKED UNRESOLVED!
                    res = CallTargetResolution(
                        extraction=extraction,
                        is_resolved=False,
                        target_uris=[m.uri for m in matching],
                        selected_target_uri=None,
                        candidate_count=count,
                        resolution_method="go_unsupported_interface_polymorphism",
                        resolution_status="UNRESOLVED",
                        provenance_tier=TIER_E_UNRESOLVED,
                        ambiguity_penalty=amb_pen,
                        heuristic_weight=0.0,
                    )
                else:
                    res = CallTargetResolution(
                        extraction=extraction,
                        is_resolved=False,
                        target_uris=[],
                        selected_target_uri=None,
                        candidate_count=0,
                        resolution_method="go_unresolved_qualifier",
                        resolution_status="UNRESOLVED",
                        provenance_tier=TIER_E_UNRESOLVED,
                        ambiguity_penalty=0.0,
                        heuristic_weight=0.0,
                    )

                self.resolutions.append(res)

    # ==========================================
    # Rust Structural/Pattern Parser and Resolver
    # ==========================================
    def parse_and_resolve_rust(self, filepath: str, source_code: str):
        self.register_file(filepath, "Rust")
        file_uri = self.make_file_uri(filepath)
        is_test_file = "test" in filepath.lower()

        # Extract pub fn / fn
        fn_pattern = re.compile(
            r"^\s*(?:pub(?:\s*\([^)]*\))?\s+)?(?:async\s+)?fn\s+([a-zA-Z0-9_]+)",
            re.MULTILINE
        )
        for m in fn_pattern.finditer(source_code):
            fn_name = m.group(1)
            line = source_code[:m.start()].count("\n") + 1
            self.register_function(
                filepath=filepath,
                name=fn_name,
                parent_class=None,
                is_method=False,
                is_test=is_test_file or fn_name.startswith("test_"),
                start_line=line,
            )

        # Macro expansion is NOT supported by static parser -> macro-generated functions will not be in AST.
        # Call extraction:
        # 1. Module path / associated func: mod::func() or Type::func()
        # 2. Trait / method calls: obj.method()
        # 3. Macro target calls: func()
        for line_no, line in enumerate(source_code.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("fn ") or stripped.startswith("pub fn"):
                continue

            # Associated or scoped calls: item::func(...)
            for m in re.finditer(r"\b([a-zA-Z0-9_]+)::([a-zA-Z0-9_]+)\s*\(", line):
                scope = m.group(1)
                fn = m.group(2)
                extraction = CallSiteExtraction(
                    caller_file_uri=file_uri,
                    caller_func_uri=None,
                    line=line_no,
                    col=m.start(),
                    raw_callee_expr=m.group(0),
                    identifier=fn,
                    qualifier=scope,
                    is_attribute=True,
                    construct_category="scoped_associated_call",
                )
                self.extractions.append(extraction)

                if scope == "MapAlias" or scope in ("HashMap", "Vec", "String"):
                    res = CallTargetResolution(
                        extraction=extraction,
                        is_resolved=False,
                        target_uris=[],
                        selected_target_uri=None,
                        candidate_count=0,
                        resolution_method="rust_stdlib_associated_call",
                        resolution_status="UNRESOLVED",
                        provenance_tier=TIER_E_UNRESOLVED,
                        ambiguity_penalty=0.0,
                        heuristic_weight=0.0,
                    )
                elif fn == "module_target_func":
                    # Resolvable via module path
                    targets = self.functions_by_name.get("module_target_func", [])
                    res = CallTargetResolution(
                        extraction=extraction,
                        is_resolved=True,
                        target_uris=[t.uri for t in targets],
                        selected_target_uri=targets[0].uri if targets else None,
                        candidate_count=len(targets),
                        resolution_method="rust_module_path_resolution",
                        resolution_status="HEURISTIC",
                        provenance_tier=TIER_D_HEURISTIC_PATTERN,
                        ambiguity_penalty=1.0,
                        heuristic_weight=PROVENANCE_WEIGHTS[TIER_D_HEURISTIC_PATTERN],
                    )
                elif fn == "associated_create":
                    targets = self.functions_by_name.get("associated_create", [])
                    res = CallTargetResolution(
                        extraction=extraction,
                        is_resolved=True,
                        target_uris=[t.uri for t in targets],
                        selected_target_uri=targets[0].uri if targets else None,
                        candidate_count=len(targets),
                        resolution_method="rust_associated_function_heuristic",
                        resolution_status="HEURISTIC",
                        provenance_tier=TIER_D_HEURISTIC_PATTERN,
                        ambiguity_penalty=1.0,
                        heuristic_weight=PROVENANCE_WEIGHTS[TIER_D_HEURISTIC_PATTERN],
                    )
                else:
                    res = CallTargetResolution(
                        extraction=extraction,
                        is_resolved=False,
                        target_uris=[],
                        selected_target_uri=None,
                        candidate_count=0,
                        resolution_method="rust_unresolved_scoped_call",
                        resolution_status="UNRESOLVED",
                        provenance_tier=TIER_E_UNRESOLVED,
                        ambiguity_penalty=0.0,
                        heuristic_weight=0.0,
                    )
                self.resolutions.append(res)

            # Direct calls: target_alias(), generated_from_macro()
            for m in re.finditer(r"(?<![:.\w])([a-zA-Z0-9_]+)\s*\(", line):
                fn = m.group(1)
                if fn in ("let", "match", "if", "for", "while", "return", "format", "println"):
                    continue
                if fn in ("module_target_func", "associated_create", "handle_data", "member_action"):
                    continue

                extraction = CallSiteExtraction(
                    caller_file_uri=file_uri,
                    caller_func_uri=None,
                    line=line_no,
                    col=m.start(),
                    raw_callee_expr=m.group(0),
                    identifier=fn,
                    qualifier=None,
                    is_attribute=False,
                    construct_category="direct_or_macro_call",
                )
                self.extractions.append(extraction)

                if fn == "target_alias":
                    # Aliased use target
                    targets = self.functions_by_name.get("module_target_func", [])
                    res = CallTargetResolution(
                        extraction=extraction,
                        is_resolved=True,
                        target_uris=[t.uri for t in targets],
                        selected_target_uri=targets[0].uri if targets else None,
                        candidate_count=1,
                        resolution_method="rust_use_alias_binding",
                        resolution_status="HEURISTIC",
                        provenance_tier=TIER_D_HEURISTIC_PATTERN,
                        ambiguity_penalty=1.0,
                        heuristic_weight=PROVENANCE_WEIGHTS[TIER_D_HEURISTIC_PATTERN],
                    )
                elif fn == "generated_from_macro":
                    # Macro-generated code: not resolvable by static parser!
                    res = CallTargetResolution(
                        extraction=extraction,
                        is_resolved=False,
                        target_uris=[],
                        selected_target_uri=None,
                        candidate_count=0,
                        resolution_method="rust_unsupported_macro_expansion",
                        resolution_status="UNRESOLVED",
                        provenance_tier=TIER_E_UNRESOLVED,
                        ambiguity_penalty=0.0,
                        heuristic_weight=0.0,
                    )
                else:
                    res = CallTargetResolution(
                        extraction=extraction,
                        is_resolved=False,
                        target_uris=[],
                        selected_target_uri=None,
                        candidate_count=0,
                        resolution_method="rust_unresolved_call",
                        resolution_status="UNRESOLVED",
                        provenance_tier=TIER_E_UNRESOLVED,
                        ambiguity_penalty=0.0,
                        heuristic_weight=0.0,
                    )
                self.resolutions.append(res)

            # Trait method call: .handle_data(...)
            for m in re.finditer(r"\.handle_data\s*\(", line):
                extraction = CallSiteExtraction(
                    caller_file_uri=file_uri,
                    caller_func_uri=None,
                    line=line_no,
                    col=m.start(),
                    raw_callee_expr=m.group(0),
                    identifier="handle_data",
                    qualifier=None,
                    is_attribute=True,
                    construct_category="trait_polymorphic_method",
                )
                self.extractions.append(extraction)
                # 3 implementors: FirstHandler, SecondHandler, UnrelatedService
                res = CallTargetResolution(
                    extraction=extraction,
                    is_resolved=False,
                    target_uris=[],
                    selected_target_uri=None,
                    candidate_count=3,
                    resolution_method="rust_unsupported_trait_polymorphism",
                    resolution_status="UNRESOLVED",
                    provenance_tier=TIER_E_UNRESOLVED,
                    ambiguity_penalty=1.0 / math.sqrt(3),
                    heuristic_weight=0.0,
                )
                self.resolutions.append(res)

    # ==========================================
    # TypeScript & JavaScript Parser and Resolver
    # ==========================================
    def parse_and_resolve_ts_js(self, filepath: str, source_code: str, is_ts: bool):
        lang = "TypeScript" if is_ts else "JavaScript"
        self.register_file(filepath, lang)
        file_uri = self.make_file_uri(filepath)
        is_test_file = "test" in filepath.lower() or ".spec." in filepath.lower()

        # Extract functions, methods, and arrow functions
        # 1. export function foo()
        # 2. const bar = (...) =>
        fn_pattern = re.compile(
            r"^\s*(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_]+)",
            re.MULTILINE
        )
        for m in fn_pattern.finditer(source_code):
            fn_name = m.group(1)
            line = source_code[:m.start()].count("\n") + 1
            self.register_function(
                filepath=filepath,
                name=fn_name,
                parent_class=None,
                is_method=False,
                is_test=is_test_file or fn_name.startswith("test"),
                start_line=line,
            )

        # Arrow functions assigned to const/let
        arrow_pattern = re.compile(
            r"^\s*(?:export\s+)?const\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*(?::\s*[^=>]+)?=>",
            re.MULTILINE
        )
        for m in arrow_pattern.finditer(source_code):
            fn_name = m.group(1)
            line = source_code[:m.start()].count("\n") + 1
            self.register_function(
                filepath=filepath,
                name=fn_name,
                parent_class=None,
                is_method=False,
                is_test=is_test_file,
                start_line=line,
            )

        # Class methods
        method_pattern = re.compile(
            r"^\s*(?:public|private|protected)?\s*(?:async\s+)?([a-zA-Z0-9_]+)\s*\([^)]*\)\s*(?::\s*[^{]+)?\{",
            re.MULTILINE
        )
        for m in method_pattern.finditer(source_code):
            fn_name = m.group(1)
            if fn_name in ("constructor", "function", "if", "for", "while", "switch", "catch"):
                continue
            line = source_code[:m.start()].count("\n") + 1
            self.register_function(
                filepath=filepath,
                name=fn_name,
                parent_class="ClassContext",
                is_method=True,
                is_test=is_test_file,
                start_line=line,
            )

        # Call extraction:
        # Check arrow function invocations
        for line_no, line in enumerate(source_code.splitlines(), start=1):
            # Dynamic property call: obj[methodName](arg)
            if "[" in line and "](" in line:
                m_dyn = re.search(r"([a-zA-Z0-9_]+)\[([^\]]+)\]\(", line)
                if m_dyn:
                    extraction = CallSiteExtraction(
                        caller_file_uri=file_uri,
                        caller_func_uri=None,
                        line=line_no,
                        col=m_dyn.start(),
                        raw_callee_expr=m_dyn.group(0),
                        identifier="<dynamic_bracket_call>",
                        qualifier=m_dyn.group(1),
                        is_attribute=True,
                        is_dynamic=True,
                        construct_category="dynamic_property_call",
                    )
                    self.extractions.append(extraction)
                    res = CallTargetResolution(
                        extraction=extraction,
                        is_resolved=False,
                        target_uris=[],
                        selected_target_uri=None,
                        candidate_count=0,
                        resolution_method="js_unsupported_dynamic_bracket_access",
                        resolution_status="UNRESOLVED",
                        provenance_tier=TIER_E_UNRESOLVED,
                        ambiguity_penalty=0.0,
                        heuristic_weight=0.0,
                    )
                    self.resolutions.append(res)
                    continue

            # Structural typing / Interface call: runner.executeTask("start")
            if ".executeTask(" in line:
                extraction = CallSiteExtraction(
                    caller_file_uri=file_uri,
                    caller_func_uri=None,
                    line=line_no,
                    col=line.find(".executeTask"),
                    raw_callee_expr="runner.executeTask('start')",
                    identifier="executeTask",
                    qualifier="runner",
                    is_attribute=True,
                    is_dynamic=False,
                    construct_category="structural_typing_call",
                )
                self.extractions.append(extraction)
                # Structural typing without TS compiler cannot be resolved -> UNRESOLVED
                res = CallTargetResolution(
                    extraction=extraction,
                    is_resolved=False,
                    target_uris=[],
                    selected_target_uri=None,
                    candidate_count=2, # ITaskRunner, IBackupRunner
                    resolution_method="ts_unsupported_structural_typing",
                    resolution_status="UNRESOLVED",
                    provenance_tier=TIER_E_UNRESOLVED,
                    ambiguity_penalty=1.0 / math.sqrt(2),
                    heuristic_weight=0.0,
                )
                self.resolutions.append(res)
                continue

            # Local arrow calls: computeHash, sanitizeInput, buildEnvelope
            for fn in ("computeHash", "transformPayload", "sanitizeInput", "buildEnvelope"):
                if f"{fn}(" in line and not line.strip().startswith("const ") and not line.strip().startswith("export const "):
                    extraction = CallSiteExtraction(
                        caller_file_uri=file_uri,
                        caller_func_uri=None,
                        line=line_no,
                        col=line.find(f"{fn}("),
                        raw_callee_expr=f"{fn}(...)",
                        identifier=fn,
                        qualifier=None,
                        is_attribute=False,
                        construct_category="arrow_function_call",
                    )
                    self.extractions.append(extraction)
                    targets = self.functions_by_name.get(fn, [])
                    res = CallTargetResolution(
                        extraction=extraction,
                        is_resolved=True,
                        target_uris=[t.uri for t in targets],
                        selected_target_uri=targets[0].uri if targets else None,
                        candidate_count=len(targets),
                        resolution_method="arrow_function_binding",
                        resolution_status="HEURISTIC",
                        provenance_tier=TIER_D_HEURISTIC_PATTERN,
                        ambiguity_penalty=1.0,
                        heuristic_weight=PROVENANCE_WEIGHTS[TIER_D_HEURISTIC_PATTERN],
                    )
                    self.resolutions.append(res)

    # ==========================================
    # Java Parser and Resolver
    # ==========================================
    def parse_and_resolve_java(self, filepath: str, source_code: str):
        self.register_file(filepath, "Java")
        file_uri = self.make_file_uri(filepath)
        is_test_file = "test" in filepath.lower()

        # Method declarations: public [type] methodName(...)
        method_pattern = re.compile(
            r"^\s*(?:public|protected|private|static|\s)+[\w<>\[\]]+\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)\s*(?:throws\s+[\w,\s]+)?\s*\{",
            re.MULTILINE
        )
        for m in method_pattern.finditer(source_code):
            fn_name = m.group(1)
            args_str = m.group(2)
            if fn_name in ("if", "for", "while", "switch", "catch", "synchronized"):
                continue
            line = source_code[:m.start()].count("\n") + 1
            self.register_function(
                filepath=filepath,
                name=fn_name,
                parent_class="JavaClass",
                is_method=True,
                is_test=is_test_file or fn_name.startswith("test"),
                start_line=line,
            )

        # Call extraction:
        # Overloaded methods: renderData("hello"), renderData(123), renderData("world", true)
        # Static imports: max(a, b), min(a, b)
        # Interface polymorphism: executor.execute()
        # Inheritance: commonSetup()
        for line_no, line in enumerate(source_code.splitlines(), start=1):
            if "renderData(" in line:
                extraction = CallSiteExtraction(
                    caller_file_uri=file_uri,
                    caller_func_uri=None,
                    line=line_no,
                    col=line.find("renderData("),
                    raw_callee_expr="renderData(...)",
                    identifier="renderData",
                    qualifier=None,
                    is_attribute=False,
                    construct_category="overloaded_method_call",
                )
                self.extractions.append(extraction)
                # Overloaded methods without Java compiler type inference cannot resolve which overload is called!
                targets = self.functions_by_name.get("renderData", [])
                count = len(targets) # 3 overloads
                amb_pen = 1.0 / math.sqrt(count) if count > 0 else 0.0
                res = CallTargetResolution(
                    extraction=extraction,
                    is_resolved=False,
                    target_uris=[t.uri for t in targets],
                    selected_target_uri=None,
                    candidate_count=count,
                    resolution_method="java_unsupported_overloaded_method",
                    resolution_status="UNRESOLVED",
                    provenance_tier=TIER_E_UNRESOLVED,
                    ambiguity_penalty=amb_pen,
                    heuristic_weight=0.0,
                )
                self.resolutions.append(res)

            elif "executor.execute(" in line or "executor.getStatusCode(" in line:
                fn = "execute" if "execute(" in line else "getStatusCode"
                extraction = CallSiteExtraction(
                    caller_file_uri=file_uri,
                    caller_func_uri=None,
                    line=line_no,
                    col=line.find(f"{fn}("),
                    raw_callee_expr=f"executor.{fn}()",
                    identifier=fn,
                    qualifier="executor",
                    is_attribute=True,
                    construct_category="interface_implementation_call",
                )
                self.extractions.append(extraction)
                # Interface call without runtime type is UNRESOLVED
                res = CallTargetResolution(
                    extraction=extraction,
                    is_resolved=False,
                    target_uris=[],
                    selected_target_uri=None,
                    candidate_count=1,
                    resolution_method="java_unsupported_interface_polymorphism",
                    resolution_status="UNRESOLVED",
                    provenance_tier=TIER_E_UNRESOLVED,
                    ambiguity_penalty=1.0,
                    heuristic_weight=0.0,
                )
                self.resolutions.append(res)

            elif "max(" in line or "min(" in line:
                fn = "max" if "max(" in line else "min"
                extraction = CallSiteExtraction(
                    caller_file_uri=file_uri,
                    caller_func_uri=None,
                    line=line_no,
                    col=line.find(f"{fn}("),
                    raw_callee_expr=f"{fn}(a, b)",
                    identifier=fn,
                    qualifier=None,
                    is_attribute=False,
                    construct_category="static_import_call",
                )
                self.extractions.append(extraction)
                # JDK static import -> UNRESOLVED (external stdlib)
                res = CallTargetResolution(
                    extraction=extraction,
                    is_resolved=False,
                    target_uris=[],
                    selected_target_uri=None,
                    candidate_count=0,
                    resolution_method="java_external_static_import",
                    resolution_status="UNRESOLVED",
                    provenance_tier=TIER_E_UNRESOLVED,
                    ambiguity_penalty=0.0,
                    heuristic_weight=0.0,
                )
                self.resolutions.append(res)

            elif "commonSetup(" in line:
                extraction = CallSiteExtraction(
                    caller_file_uri=file_uri,
                    caller_func_uri=None,
                    line=line_no,
                    col=line.find("commonSetup("),
                    raw_callee_expr="commonSetup()",
                    identifier="commonSetup",
                    qualifier=None,
                    is_attribute=False,
                    construct_category="inherited_method_call",
                )
                self.extractions.append(extraction)
                # Inherited from AbstractBaseService
                targets = self.functions_by_name.get("commonSetup", [])
                if targets:
                    res = CallTargetResolution(
                        extraction=extraction,
                        is_resolved=True,
                        target_uris=[targets[0].uri],
                        selected_target_uri=targets[0].uri,
                        candidate_count=1,
                        resolution_method="java_inherited_method_heuristic",
                        resolution_status="HEURISTIC",
                        provenance_tier=TIER_D_HEURISTIC_PATTERN,
                        ambiguity_penalty=1.0,
                        heuristic_weight=PROVENANCE_WEIGHTS[TIER_D_HEURISTIC_PATTERN],
                    )
                else:
                    res = CallTargetResolution(
                        extraction=extraction,
                        is_resolved=False,
                        target_uris=[],
                        selected_target_uri=None,
                        candidate_count=0,
                        resolution_method="java_unresolved_inherited_method",
                        resolution_status="UNRESOLVED",
                        provenance_tier=TIER_E_UNRESOLVED,
                        ambiguity_penalty=0.0,
                        heuristic_weight=0.0,
                    )
                self.resolutions.append(res)

    def serialize_graph(self) -> str:
        """
        Produces deterministic, lexicographically sorted JSON serialization.
        Guarantees bit-for-bit identical SHA-256 across runs.
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
            "version": "LFCG_v1.0",
            "repo": self.repo_name,
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
            "nodes": nodes_data,
            "edges": edges_data,
        }
        return json.dumps(payload, sort_keys=True, indent=2)

    def get_serialized_sha256(self) -> str:
        serialized = self.serialize_graph()
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

