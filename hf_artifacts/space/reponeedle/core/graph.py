"""
AST parsing and repository dependency graph engine.
Constructs directed dependency graphs, calculates structural centrality, and resolves
inter-file call/import relationships and test linkages.
"""

import ast
import os
import re
from typing import List, Dict, Set, Tuple, Optional
import networkx as nx
import numpy as np

from reponeedle.models import FileDoc

# Multi-language regex patterns for fallback parsing
IMPORT_REGEX = re.compile(
    r"^(?:from\s+([a-zA-Z0-9_\.]+)\s+import|import\s+([a-zA-Z0-9_\.]+)|const\s+.*\s*=\s*require\(['\"]([^'\"]+)['\"]\)|import\s+.*\s+from\s+['\"]([^'\"]+)['\"])",
    re.MULTILINE,
)
DEF_REGEX = re.compile(
    r"^(?:def\s+([a-zA-Z0-9_]+)|class\s+([a-zA-Z0-9_]+)|function\s+([a-zA-Z0-9_]+))",
    re.MULTILINE,
)


class RepoGraph:
    """
    Repository dependency and symbol graph built using AST analysis and networkx.
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self.docs: List[FileDoc] = []
        self.doc_paths: List[str] = []
        self.path_to_idx: Dict[str, int] = {}
        self.module_to_path: Dict[str, str] = {}
        self.test_to_target_map: Dict[str, Set[str]] = {}
        self.target_to_test_map: Dict[str, Set[str]] = {}
        self.pagerank_scores: np.ndarray = np.array([], dtype=np.float32)

    @staticmethod
    def extract_python_ast(content: str, filepath: str) -> Tuple[List[str], List[str]]:
        """
        Extracts defined symbols and imported module names from Python code using ast.
        Falls back to regex if syntax error occurs.
        """
        symbols: List[str] = []
        imports: List[str] = []

        try:
            tree = ast.parse(content, filename=filepath)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    symbols.append(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
                    for alias in node.names:
                        symbols.append(alias.name)
        except Exception:
            # Fallback regex extraction
            for match in DEF_REGEX.finditer(content):
                sym = match.group(1) or match.group(2) or match.group(3)
                if sym:
                    symbols.append(sym)
            for match in IMPORT_REGEX.finditer(content):
                imp = match.group(1) or match.group(2) or match.group(3) or match.group(4)
                if imp:
                    imports.append(imp)

        return list(dict.fromkeys(symbols)), list(dict.fromkeys(imports))

    def _normalize_module_name(self, path: str) -> str:
        """
        Converts file path to Python dot-separated module name.
        e.g., 'src/flask/app.py' -> 'flask.app'
        """
        norm = path.replace("\\", "/")
        if norm.endswith(".py"):
            norm = norm[:-3]
        if norm.endswith("/__init__"):
            norm = norm[:-9]
        
        # Remove common root prefixes like src/, lib/, etc.
        parts = [p for p in norm.split("/") if p]
        while parts and parts[0] in ("src", "lib", "python"):
            parts.pop(0)
        return ".".join(parts)

    def fit(self, docs: List[FileDoc]) -> "RepoGraph":
        """
        Builds the repository graph from indexed documents.
        """
        self.docs = docs
        self.num_docs = len(docs)
        self.doc_paths = [d.path for d in docs]
        self.path_to_idx = {d.path: idx for idx, d in enumerate(docs)}
        self.graph.clear()
        self.module_to_path.clear()
        self.test_to_target_map.clear()
        self.target_to_test_map.clear()

        # Add all files as nodes
        for doc in docs:
            self.graph.add_node(doc.path, is_test=doc.is_test)
            # Register full path without extension
            raw_norm = doc.path.replace("\\", "/")
            if raw_norm.endswith(".py"):
                raw_norm = raw_norm[:-3]
            raw_mod = raw_norm.replace("/", ".")
            self.module_to_path[raw_mod] = doc.path

            # Register normalized module name
            mod_name = self._normalize_module_name(doc.path)
            self.module_to_path[mod_name] = doc.path
            # Also register suffix module (e.g. 'app' for 'flask.app')
            if "." in mod_name:
                short_name = mod_name.split(".")[-1]
                if short_name not in self.module_to_path:
                    self.module_to_path[short_name] = doc.path

        # Add directed edges for imports: File A -> File B (A imports B)
        for doc in docs:
            for imp in doc.imports:
                target_path = None
                # Check exact module match
                if imp in self.module_to_path:
                    target_path = self.module_to_path[imp]
                else:
                    # Strip leading src. if present
                    clean_imp = imp
                    if clean_imp.startswith("src."):
                        clean_imp = clean_imp[4:]
                    if clean_imp in self.module_to_path:
                        target_path = self.module_to_path[clean_imp]
                    else:
                        # Check parent module prefix match
                        parts = clean_imp.split(".")
                        for i in range(len(parts), 0, -1):
                            sub_mod = ".".join(parts[:i])
                            if sub_mod in self.module_to_path:
                                target_path = self.module_to_path[sub_mod]
                                break

                if target_path and target_path != doc.path:
                    self.graph.add_edge(doc.path, target_path)

        # Build bidirectional test <-> target linkages
        for doc in docs:
            if doc.is_test:
                tested_targets: Set[str] = set()
                # 1. Any file imported by the test file that is NOT another test file
                for neighbor in self.graph.successors(doc.path):
                    if neighbor in self.path_to_idx and not self.docs[self.path_to_idx[neighbor]].is_test:
                        tested_targets.add(neighbor)

                # 2. Heuristic naming matching: test_<stem>.py -> <stem>.py
                norm = doc.path.replace("\\", "/").lower()
                base = os.path.basename(norm)
                stem = base
                if stem.endswith(".py"):
                    stem = stem[:-3]
                if stem.startswith("test_"):
                    stem = stem[5:]
                elif stem.endswith("_test"):
                    stem = stem[:-5]

                for other_path, o_idx in self.path_to_idx.items():
                    if not self.docs[o_idx].is_test:
                        o_base = os.path.basename(other_path.replace("\\", "/").lower())
                        o_stem = o_base[:-3] if o_base.endswith(".py") else o_base
                        if o_stem == stem or stem in o_stem:
                            tested_targets.add(other_path)

                self.test_to_target_map[doc.path] = tested_targets
                for t in tested_targets:
                    if t not in self.target_to_test_map:
                        self.target_to_test_map[t] = set()
                    self.target_to_test_map[t].add(doc.path)

        # Compute PageRank for structural centrality
        if self.num_docs > 0:
            try:
                # Add small self-loops to ensure connectivity for dangling nodes
                pr_dict = nx.pagerank(self.graph, alpha=0.85, max_iter=100)
                scores = np.array([pr_dict.get(p, 0.0) for p in self.doc_paths], dtype=np.float32)
                max_pr = float(np.max(scores)) if len(scores) > 0 else 0.0
                if max_pr > 0:
                    scores = scores / max_pr
                self.pagerank_scores = scores
            except Exception:
                self.pagerank_scores = np.ones(self.num_docs, dtype=np.float32) / max(1, self.num_docs)
        else:
            self.pagerank_scores = np.array([], dtype=np.float32)

        return self

    def get_ripple_scores(self, anchor_files: List[str]) -> np.ndarray:
        """
        Computes ripple / impact propagation scores starting from anchor files.
        Traverses both reverse (callers/importers) and forward (callees/dependencies).
        Resolves anchor files flexibly (by full path, relative path, or basename).
        """
        scores = np.zeros(self.num_docs, dtype=np.float32)
        if not anchor_files or self.num_docs == 0:
            return scores

        resolved_anchors = []
        for a in anchor_files:
            a_norm = a.replace("\\", "/").lower()
            if a in self.graph:
                resolved_anchors.append(a)
            else:
                # Find matching doc by suffix or basename
                for doc_path in self.doc_paths:
                    d_norm = doc_path.replace("\\", "/").lower()
                    if d_norm.endswith(a_norm) or os.path.basename(d_norm) == os.path.basename(a_norm):
                        resolved_anchors.append(doc_path)
                        break

        visited: Dict[str, float] = {}
        for anchor in resolved_anchors:
            if anchor in self.graph:
                # In ripple tasks, the callers and dependents are the primary targets:
                # 1. Reverse traversal (who imports anchor) - direct callers get top score 1.0
                for caller in self.graph.predecessors(anchor):
                    visited[caller] = max(visited.get(caller, 0.0), 1.0)
                    for caller2 in self.graph.predecessors(caller):
                        visited[caller2] = max(visited.get(caller2, 0.0), 0.7)

                # 2. Forward traversal (what anchor imports)
                for dep in self.graph.successors(anchor):
                    visited[dep] = max(visited.get(dep, 0.0), 0.8)

                # The anchor itself is the origin of change, assigned lower priority than its affected callers
                visited[anchor] = max(visited.get(anchor, 0.0), 0.3)

        for path, impact in visited.items():
            if path in self.path_to_idx:
                scores[self.path_to_idx[path]] = impact

        return scores

    def get_test_scores_for_target(self, target_files: List[str]) -> np.ndarray:
        """
        Given implementation target files, returns test file scores via inverted test map.
        """
        scores = np.zeros(self.num_docs, dtype=np.float32)
        if not target_files or self.num_docs == 0:
            return scores

        for target in target_files:
            tests = self.target_to_test_map.get(target, set())
            for t in tests:
                if t in self.path_to_idx:
                    scores[self.path_to_idx[t]] = 1.0

        return scores
