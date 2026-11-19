import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning)

"""
AST parsing and repository dependency graph engine.
Constructs directed dependency graphs, calculates structural centrality, and resolves
inter-file call/import relationships and test linkages.
"""

import ast
import os
import re
import json
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None
from dataclasses import dataclass
from typing import List, Dict, Set, Tuple, Optional, Any
import networkx as nx
import numpy as np

from reponeedle.models import FileDoc
from reponeedle.core.signatures import stable_signature

# Bump when the per-document class-to-test extraction changes its output for the same inputs.
DOC_FACTS_SIGNATURE_VERSION = "repo-graph-doc-facts/1"
# Bump when the import-edge resolver's edges can change for the same inputs and key values.
RESOLVER_VERSION = "repo-graph-resolver/2"

# Typed lookup keys of the import-edge resolver (V2 Stage 2, design section 9.1). Every lookup into a structure built
# from OTHER files goes through ``_RepoLookup``, which records the key.
KEY_MODULE = "rg.module:"        # module_to_path[k]                               -> path or None
KEY_PATH = "rg.path:"            # is the path indexed                              -> bool
KEY_SYMBOL = "rg.symbol:"        # symbol_to_paths[s]                               -> ordered paths
KEY_PACKAGE = "rg.package:"      # package_to_files[p]                              -> ordered paths
KEY_CRATE = "rg.crate:"          # manifest_crates[c]                               -> directory or None
KEY_CRATE_DEPS = "rg.cdeps:"     # crate_dependencies[c]                            -> sorted directories or None
KEY_ENTRYPOINTS = "rg.entry:"    # crate/package entrypoints under crates/ or packages/ -> ordered paths
ENTRYPOINT_SUFFIXES = ("/src/lib.rs", "/src/main.rs", "/src/index.ts", "/src/index.js", "/lib.rs", "/main.rs")
ENTRYPOINT_PREFIXES = ("crates", "packages")

# Per-document class-to-test facts. A production file contributes ("class", name, methods) catalog entries; a test
# file contributes invocation candidates, in the order the 1.2.0 code discovered them:
#   "C": class name, a construction if the class is a production class
#   "A": attribute call: a module-qualified class use if the name is a production class, else a method call
#   "I": an imported name, a class import if it is a production class
#   "M": a method call (unconditional)
#   "K": class.method(...), a method call if the class is a production class
FACT_CLASS, FACT_CONSTRUCT, FACT_ATTRIBUTE, FACT_IMPORT, FACT_METHOD, FACT_CLASS_METHOD = "class", "C", "A", "I", "M", "K"


@dataclass
class DocResolution:
    """One file's import-edge contribution: its (source, target) edges in insertion order plus consulted keys."""
    edges: List[Tuple[str, str]]
    consumed: Tuple[str, ...] = ()


class _RepoLookup:
    """Read-only lookups over the maps built from the ordered document set; records keys while tracking."""

    def __init__(self, rg: "RepoGraph"):
        self.module_to_path = rg.module_to_path
        self.path_to_idx = rg.path_to_idx
        self.symbol_to_paths = rg.symbol_to_paths
        self.package_to_files = rg.package_to_files
        self.manifest_crates = rg.manifest_crates
        self.crate_dependencies = rg.crate_dependencies
        self.entrypoints: Dict[str, List[str]] = {}
        for o_path in rg.doc_paths:
            if o_path.endswith(ENTRYPOINT_SUFFIXES):
                for prefix in ENTRYPOINT_PREFIXES:
                    if o_path.startswith(f"{prefix}/"):
                        self.entrypoints.setdefault(prefix, []).append(o_path)
        self.track: Optional[Set[str]] = None

    def _t(self, key: str) -> None:
        if self.track is not None:
            self.track.add(key)

    def module(self, k: str) -> Optional[str]:
        self._t(KEY_MODULE + k)
        return self.module_to_path.get(k)

    def has_path(self, p: str) -> bool:
        self._t(KEY_PATH + p)
        return p in self.path_to_idx

    def symbol(self, s: str) -> List[str]:
        self._t(KEY_SYMBOL + s)
        return self.symbol_to_paths.get(s, ())

    def package(self, p: str) -> List[str]:
        self._t(KEY_PACKAGE + p)
        return self.package_to_files.get(p, ())

    def crate(self, c: str) -> Optional[str]:
        self._t(KEY_CRATE + c)
        return self.manifest_crates.get(c)

    def crate_deps(self, c: str) -> Optional[Set[str]]:
        self._t(KEY_CRATE_DEPS + c)
        return self.crate_dependencies.get(c)

    def entries(self, prefix: str) -> List[str]:
        self._t(KEY_ENTRYPOINTS + prefix)
        return self.entrypoints.get(prefix, ())

    def value(self, key: str) -> Any:
        """The current value of a typed key, exactly as the resolver sees it (JSON-compatible)."""
        for prefix, fn in ((KEY_MODULE, lambda k: self.module_to_path.get(k)),
                           (KEY_PATH, lambda k: k in self.path_to_idx),
                           (KEY_SYMBOL, lambda k: list(self.symbol_to_paths.get(k, ()))),
                           (KEY_PACKAGE, lambda k: list(self.package_to_files.get(k, ()))),
                           (KEY_CRATE, lambda k: self.manifest_crates.get(k)),
                           (KEY_CRATE_DEPS, lambda k: (sorted(self.crate_dependencies[k])
                                                       if k in self.crate_dependencies else None)),
                           (KEY_ENTRYPOINTS, lambda k: list(self.entrypoints.get(k, ())))):
            if key.startswith(prefix):
                return fn(key[len(prefix):])
        raise KeyError(f"unknown repository-graph key {key!r}")

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
        self.num_docs: int = 0
        self.path_to_idx: Dict[str, int] = {}
        self.module_to_path: Dict[str, str] = {}
        self.test_to_target_map: Dict[str, Set[str]] = {}
        self.target_to_test_map: Dict[str, Set[str]] = {}
        self.symbol_to_paths: Dict[str, List[str]] = {}
        self.package_to_files: Dict[str, List[str]] = {}
        self.manifest_crates: Dict[str, str] = {}
        self.crate_dependencies: Dict[str, Set[str]] = {}
        self.pagerank_scores: np.ndarray = np.array([], dtype=np.float32)
        # Stage 3.10: Class-to-Test Invocation Linkage
        self.enable_class_to_test: bool = False
        self.enable_degree_matched_control: bool = False
        self.invocation_edges: List[Dict[str, Any]] = []
        self.prod_to_test_invocations: Dict[str, Set[str]] = {}
        self.test_to_prod_invocations: Dict[str, Set[str]] = {}
        self.degree_matched_prod_to_test: Dict[str, Set[str]] = {}
        self.degree_matched_test_to_prod: Dict[str, Set[str]] = {}
        self.unresolved_diagnostics: List[Dict[str, Any]] = []
        # Signature-validated per-document class-to-test facts (V2 Stage 2): path -> (signature, facts).
        self._doc_facts_cache: Dict[str, Tuple[str, List[tuple]]] = {}
        # Per-build resolver state (not retrieval state): lookups, per-file import-edge resolutions, counters.
        self._lookup: Optional[_RepoLookup] = None
        self.file_resolutions: Dict[str, DocResolution] = {}
        self.resolution_stats: Dict[str, int] = {}

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

    @staticmethod
    def parse_cargo_manifest(content: str, filepath: str = "") -> Dict[str, Any]:
        """Parses Cargo.toml for package name, workspace members, and path dependencies."""
        res = {"name": "", "workspace_members": [], "path_dependencies": {}}
        parsed = False
        toml_parser = tomllib
        if not toml_parser:
            try:
                import tomli as toml_parser
            except ImportError:
                toml_parser = None
        if toml_parser:
            try:
                data = toml_parser.loads(content)
                res["name"] = data.get("package", {}).get("name", "")
                ws = data.get("workspace", {})
                if isinstance(ws, dict):
                    res["workspace_members"] = ws.get("members", [])
                for section in ("dependencies", "dev-dependencies", "build-dependencies"):
                    deps = data.get(section, {})
                    if isinstance(deps, dict):
                        for dep_name, dep_info in deps.items():
                            if isinstance(dep_info, dict) and "path" in dep_info:
                                res["path_dependencies"][dep_name] = dep_info["path"]
                parsed = True
            except Exception:
                pass
        if not parsed:
            # Fallback regex parsing when TOML parser is unavailable or on malformed TOML
            pkg_match = re.search(r'\[package\][^\[]*?name\s*=\s*["\']([^"\']+)["\']', content, re.DOTALL)
            if pkg_match:
                res["name"] = pkg_match.group(1).strip()
            ws_match = re.search(r'\[workspace\][^\[]*?members\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if ws_match:
                members = re.findall(r'["\']([^"\']+)["\']', ws_match.group(1))
                res["workspace_members"] = [m.strip() for m in members if m.strip()]
            path_deps = re.findall(r'(\w[\w-]*)\s*=\s*\{[^}]*path\s*=\s*["\']([^"\']+)["\']', content)
            for dep_name, dep_path in path_deps:
                res["path_dependencies"][dep_name] = dep_path
            table_deps = re.findall(
                r'\[(?:dependencies|dev-dependencies|build-dependencies)\.([\w-]+)\][^\[]*?path\s*=\s*["\']([^"\']+)["\']',
                content,
                re.DOTALL,
            )
            for dep_name, dep_path in table_deps:
                res["path_dependencies"][dep_name] = dep_path
        return res

    @staticmethod
    def parse_go_mod(content: str) -> str:
        """Extracts module path from go.mod."""
        m = re.search(r"^\s*module\s+([^\s\n]+)", content, re.MULTILINE)
        return m.group(1).strip() if m else ""

    @staticmethod
    def parse_package_json(content: str) -> Dict[str, Any]:
        """Extracts package name, workspaces, and dependencies from package.json."""
        res = {"name": "", "workspaces": [], "dependencies": []}
        try:
            data = json.loads(content)
            res["name"] = data.get("name", "")
            workspaces = data.get("workspaces", [])
            if isinstance(workspaces, list):
                res["workspaces"] = workspaces
            elif isinstance(workspaces, dict):
                res["workspaces"] = workspaces.get("packages", [])
            deps = data.get("dependencies", {})
            if isinstance(deps, dict):
                res["dependencies"] = list(deps.keys())
        except Exception:
            pass
        return res

    @staticmethod
    def extract_polyglot_symbols(content: str, filepath: str) -> Tuple[List[str], List[str]]:
        """
        Extracts defined symbols and imported identifiers across Python, Rust, Go, TypeScript, JavaScript.
        """
        norm_p = filepath.replace("\\", "/").lower()
        if norm_p.endswith(".py"):
            return RepoGraph.extract_python_ast(content, filepath)

        symbols: List[str] = []
        imports: List[str] = []

        # Rust (.rs)
        if norm_p.endswith(".rs"):
            fn_re = re.compile(r"^\s*(?:pub(?:\s*\([^)]*\))?\s+)?(?:async\s+)?fn\s+([a-zA-Z0-9_]+)", re.MULTILINE)
            type_re = re.compile(r"^\s*(?:pub(?:\s*\([^)]*\))?\s+)?(?:struct|enum|trait|type)\s+([a-zA-Z0-9_]+)", re.MULTILINE)
            mod_re = re.compile(r"^\s*(?:pub(?:\s*\([^)]*\))?\s+)?mod\s+([a-zA-Z0-9_]+);", re.MULTILINE)
            use_re = re.compile(r"^\s*use\s+([^;]+);", re.MULTILINE)
            for m in fn_re.finditer(content):
                symbols.append(m.group(1))
            for m in type_re.finditer(content):
                symbols.append(m.group(1))
            for m in mod_re.finditer(content):
                imports.append(f"mod:{m.group(1)}")
            for m in use_re.finditer(content):
                clean = m.group(1).strip()
                if "::{" in clean:
                    base_crate, rest = clean.split("::{", 1)
                    sub_items = rest.rstrip("}").split(",")
                    imports.append(base_crate.split("::")[-1])
                    for sub in sub_items:
                        sub_clean = sub.strip()
                        if sub_clean:
                            imports.append(sub_clean)
                else:
                    parts = clean.split("::")
                    imports.append(parts[-1])
                    if len(parts) > 1:
                        imports.append(parts[0])

        # Go (.go)
        elif norm_p.endswith(".go"):
            func_re = re.compile(r"^\s*func\s+(?:\([^)]*\)\s+)?([a-zA-Z0-9_]+)", re.MULTILINE)
            type_re = re.compile(r"^\s*type\s+([a-zA-Z0-9_]+)\s+(?:struct|interface)", re.MULTILINE)
            pkg_re = re.compile(r"^\s*package\s+([a-zA-Z0-9_]+)", re.MULTILINE)
            single_imp = re.compile(r'^\s*import\s+["\']([^"\']+)["\']', re.MULTILINE)
            multi_imp = re.compile(r'import\s+\(\s*([^)]+)\)', re.MULTILINE)
            for m in func_re.finditer(content):
                symbols.append(m.group(1))
            for m in type_re.finditer(content):
                symbols.append(m.group(1))
            for m in pkg_re.finditer(content):
                symbols.append(f"pkg:{m.group(1)}")
            for m in single_imp.finditer(content):
                imp_path = m.group(1)
                imports.append(imp_path)
                imports.append(imp_path.split("/")[-1])
            for m in multi_imp.finditer(content):
                for line in m.group(1).splitlines():
                    clean = line.strip().strip('"').strip("'")
                    if clean:
                        imports.append(clean)
                        imports.append(clean.split("/")[-1])

        # JS / TS (.js, .jsx, .ts, .tsx, .mjs)
        elif norm_p.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs")):
            fn_re = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_]+)", re.MULTILINE)
            class_re = re.compile(r"^\s*(?:export\s+)?(?:class|interface|type)\s+([a-zA-Z0-9_]+)", re.MULTILINE)
            const_fn_re = re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", re.MULTILINE)
            imp_re = re.compile(r'^\s*import\s+(?:\{([^}]+)\}|\*\s+as\s+([a-zA-Z0-9_]+)|([a-zA-Z0-9_]+))?\s*(?:from\s+)?["\']([^"\']+)["\']', re.MULTILINE)
            req_re = re.compile(r'(?:const|let|var)\s+(?:\{([^}]+)\}|([a-zA-Z0-9_]+))\s*=\s*require\(["\']([^"\']+)["\']\)', re.MULTILINE)
            for m in fn_re.finditer(content):
                symbols.append(m.group(1))
            for m in class_re.finditer(content):
                symbols.append(m.group(1))
            for m in const_fn_re.finditer(content):
                symbols.append(m.group(1))
            for m in imp_re.finditer(content):
                target = m.group(4)
                if target:
                    imports.append(target)
                named = m.group(1) or m.group(2) or m.group(3)
                if named:
                    for n in named.split(","):
                        clean_n = n.strip().split(" as ")[-1].strip()
                        if clean_n:
                            imports.append(clean_n)
            for m in req_re.finditer(content):
                target = m.group(3)
                if target:
                    imports.append(target)
                named = m.group(1) or m.group(2)
                if named:
                    for n in named.split(","):
                        clean_n = n.strip()
                        if clean_n:
                            imports.append(clean_n)

        else:
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

    def fit(self, docs: List[FileDoc], reuse=None, track: bool = False) -> "RepoGraph":
        """
        Builds the repository graph from indexed documents.

        ``reuse`` (persistent index cache only): ``reuse(graph, doc) -> Optional[DocResolution]`` may supply a file's
        previously resolved import edges once the lookup maps exist; other files are resolved. ``track=True``
        records every file's consulted keys in ``file_resolutions``.
        """
        self._lookup = None
        self.file_resolutions = {}
        self.resolution_stats = {}
        self.docs = docs
        self.num_docs = len(docs)
        self.doc_paths = [d.path for d in docs]
        self.path_to_idx = {d.path: idx for idx, d in enumerate(docs)}
        self.graph.clear()
        self.module_to_path.clear()
        self.test_to_target_map.clear()
        self.target_to_test_map.clear()
        self.symbol_to_paths.clear()
        self.package_to_files.clear()
        self.manifest_crates.clear()
        self.crate_dependencies.clear()
        self.invocation_edges.clear()
        self.prod_to_test_invocations.clear()
        self.test_to_prod_invocations.clear()
        self.degree_matched_prod_to_test.clear()
        self.degree_matched_test_to_prod.clear()
        self.unresolved_diagnostics.clear()

        # 1. Build symbol index and discover packages/manifests
        for doc in docs:
            norm_p = doc.path.replace("\\", "/")
            cur_dir = os.path.dirname(norm_p)
            for sym in doc.symbols:
                if not sym.startswith("pkg:"):
                    if sym not in self.symbol_to_paths:
                        self.symbol_to_paths[sym] = []
                    self.symbol_to_paths[sym].append(doc.path)

            # Discover Go packages
            if norm_p.endswith(".go"):
                if cur_dir not in self.package_to_files:
                    self.package_to_files[cur_dir] = []
                self.package_to_files[cur_dir].append(doc.path)
                pkg_name = os.path.basename(cur_dir)
                if pkg_name:
                    if pkg_name not in self.package_to_files:
                        self.package_to_files[pkg_name] = []
                    self.package_to_files[pkg_name].append(doc.path)
                for sym in doc.symbols:
                    if sym.startswith("pkg:"):
                        p_name = sym[4:]
                        if p_name not in self.package_to_files:
                            self.package_to_files[p_name] = []
                        self.package_to_files[p_name].append(doc.path)

            # Discover manifests
            lower_p = norm_p.lower()
            if lower_p.endswith("cargo.toml"):
                manifest = self.parse_cargo_manifest(doc.content, doc.path)
                if manifest.get("name"):
                    self.manifest_crates[manifest["name"]] = cur_dir
                for dep, dep_p in manifest.get("path_dependencies", {}).items():
                    target_dir = os.path.normpath(os.path.join(cur_dir, dep_p)).replace("\\", "/")
                    if manifest.get("name"):
                        self.crate_dependencies.setdefault(manifest["name"], set()).add(target_dir)
            elif lower_p.endswith("go.mod"):
                mod_name = self.parse_go_mod(doc.content)
                if mod_name:
                    self.manifest_crates[mod_name] = cur_dir
            elif lower_p.endswith("package.json"):
                pkg_info = self.parse_package_json(doc.content)
                if pkg_info.get("name"):
                    self.manifest_crates[pkg_info["name"]] = cur_dir

            # Layout heuristic inference for multi-crate/multi-package workspaces
            if norm_p.startswith("crates/"):
                parts = norm_p.split("/")
                if len(parts) >= 2:
                    c_name = parts[1]
                    self.manifest_crates[c_name] = f"crates/{c_name}"
            elif norm_p.startswith("packages/"):
                parts = norm_p.split("/")
                if len(parts) >= 2:
                    p_name = parts[1]
                    self.manifest_crates[p_name] = f"packages/{p_name}"

        # Add all files as nodes
        for doc in docs:
            self.graph.add_node(doc.path, is_test=doc.is_test)
            raw_norm = doc.path.replace("\\", "/")
            if raw_norm.endswith(".py"):
                raw_norm = raw_norm[:-3]
            raw_mod = raw_norm.replace("/", ".")
            self.module_to_path[raw_mod] = doc.path

            mod_name = self._normalize_module_name(doc.path)
            self.module_to_path[mod_name] = doc.path
            if "." in mod_name:
                short_name = mod_name.split(".")[-1]
                if short_name not in self.module_to_path:
                    self.module_to_path[short_name] = doc.path

        # Add directed edges for imports & cross-crate linkages: each file is resolved on its own (or reused), then
        # its edges are added in discovery order, exactly as the 1.2.0 loop added them.
        self._lookup = _RepoLookup(self)
        resolved = reused = edges_replayed = edges_reused = 0
        for doc in docs:
            res = reuse(self, doc) if reuse is not None else None
            if res is None:
                res = self._resolve_doc_edges(doc, track)
                resolved += 1
            else:
                reused += 1
                edges_reused += len(res.edges)
            if track or reuse is not None:
                self.file_resolutions[doc.path] = res
            for u, v in res.edges:
                self.graph.add_edge(u, v)
            edges_replayed += len(res.edges)
        self.resolution_stats = {"files_resolved": resolved, "files_reused": reused,
                                 "edges_replayed": edges_replayed, "edges_reused": edges_reused}

        # Build bidirectional test <-> target linkages
        # Precompute target stems: O(N) instead of O(N^2)
        stem_to_paths: Dict[str, List[str]] = {}
        for other_path, o_idx in self.path_to_idx.items():
            if not self.docs[o_idx].is_test:
                o_base = os.path.basename(other_path.replace("\\", "/").lower())
                o_stem = o_base[:-3] if o_base.endswith(".py") else o_base
                if o_stem not in stem_to_paths:
                    stem_to_paths[o_stem] = []
                stem_to_paths[o_stem].append(other_path)

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

                # Fast O(1) exact match lookup
                if stem in stem_to_paths:
                    tested_targets.update(stem_to_paths[stem])
                elif len(stem) >= 4:
                    # Suffix / substring fallback on precomputed stems
                    for o_stem, paths in stem_to_paths.items():
                        if stem in o_stem:
                            tested_targets.update(paths)

                self.test_to_target_map[doc.path] = tested_targets
                for t in tested_targets:
                    if t not in self.target_to_test_map:
                        self.target_to_test_map[t] = set()
                    self.target_to_test_map[t].add(doc.path)

        # Stage 3.10: Class-to-Test Invocation Linkage
        self._extract_class_to_test_linkages(docs)

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

    def _resolve_doc_edges(self, doc: FileDoc, track: bool) -> DocResolution:
        """Import resolution steps A-H of the 1.2.0 loop for one file, through ``_RepoLookup``."""
        lk = self._lookup
        consumed: Optional[Set[str]] = set() if track else None
        lk.track = consumed
        edges: List[Tuple[str, str]] = []
        try:
            norm_p = doc.path.replace("\\", "/")
            cur_dir = os.path.dirname(norm_p)

            for imp in doc.imports:
                target_path = None
                # A. Exact or relative Python module match
                found = lk.module(imp)
                if found is not None:
                    target_path = found
                else:
                    found = lk.module(imp[4:]) if imp.startswith("src.") else None
                    if found is not None:
                        target_path = found
                    else:
                        parts = imp.split(".")
                        for i in range(len(parts), 0, -1):
                            found = lk.module(".".join(parts[:i]))
                            if found is not None:
                                target_path = found
                                break

                # B. Rust submodule: mod <name>;
                if not target_path and imp.startswith("mod:"):
                    submod = imp[4:]
                    c1 = f"{cur_dir}/{submod}.rs" if cur_dir else f"{submod}.rs"
                    c2 = f"{cur_dir}/{submod}/mod.rs" if cur_dir else f"{submod}/mod.rs"
                    if lk.has_path(c1):
                        target_path = c1
                    elif lk.has_path(c2):
                        target_path = c2

                # C. Symbol-to-path resolution across languages
                if not target_path:
                    for def_path in lk.symbol(imp):
                        if def_path != doc.path:
                            edges.append((doc.path, def_path))

                # D. Go package import resolution
                if not target_path:
                    for pkg_file in lk.package(imp):
                        if pkg_file != doc.path:
                            edges.append((doc.path, pkg_file))

                # E. JS / TS relative import resolution
                if not target_path and imp.startswith(("./", "../")):
                    rel_target = os.path.normpath(os.path.join(cur_dir, imp)).replace("\\", "/")
                    for ext in ("", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.js"):
                        candidate = rel_target + ext
                        if lk.has_path(candidate):
                            target_path = candidate
                            break

                # F. Crate lookup in workspace: link to crate entrypoint
                if not target_path:
                    crate_dir = lk.crate(imp)
                    if crate_dir is not None:
                        for entry_name in ENTRYPOINT_SUFFIXES:
                            candidate = f"{crate_dir}{entry_name}"
                            if lk.has_path(candidate) and candidate != doc.path:
                                edges.append((doc.path, candidate))
                                break

                if target_path and target_path != doc.path:
                    edges.append((doc.path, target_path))

            # G. Intra-package coupling for Go: link to package primary file
            if norm_p.endswith(".go"):
                pkg_files = lk.package(cur_dir)
                if len(pkg_files) > 1:
                    primary = pkg_files[0]
                    if doc.path != primary:
                        edges.append((doc.path, primary))
                        edges.append((primary, doc.path))

            # H. Sibling crate coupling in workspace (e.g. crates/* or packages/*)
            # Link crate entrypoints to dependent crate entrypoints
            is_entrypoint = norm_p.endswith(ENTRYPOINT_SUFFIXES)
            if is_entrypoint and norm_p.startswith(("crates/", "packages/")):
                prefix = norm_p.split("/")[0]
                my_crate = norm_p.split("/")[1]
                deps = lk.crate_deps(my_crate)
                for o_path in lk.entries(prefix):
                    if o_path != doc.path:
                        o_crate = o_path.split("/")[1]
                        if o_crate != my_crate:
                            if (deps is not None and any(dep in o_path for dep in deps)) or \
                               any(s in o_path for s in doc.imports) or \
                               (o_crate in doc.imports):
                                edges.append((doc.path, o_path))
        finally:
            lk.track = None
        return DocResolution(edges, tuple(sorted(consumed)) if consumed is not None else ())

    def key_value(self, key: str) -> Any:
        """The value of a typed lookup key in the current build (see ``_RepoLookup.value``)."""
        if self._lookup is None:
            raise RuntimeError("no build is available")
        return self._lookup.value(key)

    def provides(self, doc: FileDoc) -> List[Tuple[str, str]]:
        """
        Provider events of one document: (typed key, contributed value) in emission order. For every key, the
        concatenation of all documents' events in discovery order determines the value ``_RepoLookup`` returns.
        Module-map events carry their role: "a:" (assigned, last wins) or "d:" (set only if absent).
        """
        events: List[Tuple[str, str]] = []
        norm_p = doc.path.replace("\\", "/")
        cur_dir = os.path.dirname(norm_p)
        for sym in doc.symbols:
            if not sym.startswith("pkg:"):
                events.append((KEY_SYMBOL + sym, doc.path))
        if norm_p.endswith(".go"):
            events.append((KEY_PACKAGE + cur_dir, doc.path))
            pkg_name = os.path.basename(cur_dir)
            if pkg_name:
                events.append((KEY_PACKAGE + pkg_name, doc.path))
            for sym in doc.symbols:
                if sym.startswith("pkg:"):
                    events.append((KEY_PACKAGE + sym[4:], doc.path))
        lower_p = norm_p.lower()
        if lower_p.endswith("cargo.toml"):
            manifest = self.parse_cargo_manifest(doc.content, doc.path)
            if manifest.get("name"):
                events.append((KEY_CRATE + str(manifest["name"]), cur_dir))
            for dep, dep_p in manifest.get("path_dependencies", {}).items():
                target_dir = os.path.normpath(os.path.join(cur_dir, dep_p)).replace("\\", "/")
                if manifest.get("name"):
                    events.append((KEY_CRATE_DEPS + str(manifest["name"]), target_dir))
        elif lower_p.endswith("go.mod"):
            mod_name = self.parse_go_mod(doc.content)
            if mod_name:
                events.append((KEY_CRATE + mod_name, cur_dir))
        elif lower_p.endswith("package.json"):
            pkg_info = self.parse_package_json(doc.content)
            if pkg_info.get("name"):
                events.append((KEY_CRATE + str(pkg_info["name"]), cur_dir))
        if norm_p.startswith("crates/"):
            parts = norm_p.split("/")
            if len(parts) >= 2:
                events.append((KEY_CRATE + parts[1], f"crates/{parts[1]}"))
        elif norm_p.startswith("packages/"):
            parts = norm_p.split("/")
            if len(parts) >= 2:
                events.append((KEY_CRATE + parts[1], f"packages/{parts[1]}"))
        raw_norm = norm_p[:-3] if norm_p.endswith(".py") else norm_p
        events.append((KEY_MODULE + raw_norm.replace("/", "."), "a:" + doc.path))
        mod_name = self._normalize_module_name(doc.path)
        events.append((KEY_MODULE + mod_name, "a:" + doc.path))
        if "." in mod_name:
            events.append((KEY_MODULE + mod_name.split(".")[-1], "d:" + doc.path))
        events.append((KEY_PATH + doc.path, "1"))
        if doc.path.endswith(ENTRYPOINT_SUFFIXES):
            for prefix in ENTRYPOINT_PREFIXES:
                if doc.path.startswith(f"{prefix}/"):
                    events.append((KEY_ENTRYPOINTS + prefix, doc.path))
        return events

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

    def facts_signature(self, doc: FileDoc) -> str:
        """Deterministic signature of everything the per-document class-to-test extraction reads."""
        return stable_signature(DOC_FACTS_SIGNATURE_VERSION, doc.path, doc.is_test, doc.content)

    def doc_facts(self, doc: FileDoc) -> List[tuple]:
        """Class-to-test facts of one document, from the signature-validated cache or extracted now."""
        sig = self.facts_signature(doc)
        cached = self._doc_facts_cache.get(doc.path)
        if cached is not None and cached[0] == sig:
            return cached[1]
        facts = self.extract_doc_facts(doc.path, doc.is_test, doc.content)
        self._doc_facts_cache[doc.path] = (sig, facts)
        return facts

    @staticmethod
    def extract_doc_facts(path: str, is_test: bool, content: str) -> List[tuple]:
        """
        The per-document part of the 1.2.0 class-to-test extraction, recorded in discovery order: production files
        give their class catalog entries, test files their invocation candidates (see the FACT_* constants). The
        repository-wide part (filtering candidates by the production catalog) runs in
        ``_extract_class_to_test_linkages``, so the result is identical to extracting everything there.
        """
        norm_p = path.replace("\\", "/").lower()
        facts: List[tuple] = []
        if not is_test:
            # A. Python
            if norm_p.endswith(".py"):
                if "class " not in content and "def " not in content:
                    return facts
                try:
                    tree = ast.parse(content, filename=path)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            methods = [
                                n.name for n in node.body
                                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                            ]
                            facts.append((FACT_CLASS, node.name, methods))
                except Exception:
                    for m in re.finditer(r"^\s*class\s+([a-zA-Z0-9_]+)", content, re.MULTILINE):
                        facts.append((FACT_CLASS, m.group(1), []))

            # B. Rust
            elif norm_p.endswith(".rs"):
                struct_re = re.compile(r"^\s*(?:pub(?:\s*\([^)]*\))?\s+)?(?:struct|enum|trait)\s+([a-zA-Z0-9_]+)", re.MULTILINE)
                impl_re = re.compile(r"^\s*impl(?:\s*<[^>]*>)?\s+([a-zA-Z0-9_]+)\s*\{([^}]*)\}", re.DOTALL)
                for m in struct_re.finditer(content):
                    facts.append((FACT_CLASS, m.group(1), []))
                for m in impl_re.finditer(content):
                    facts.append((FACT_CLASS, m.group(1), re.findall(r"fn\s+([a-zA-Z0-9_]+)", m.group(2))))

            # C. Go
            elif norm_p.endswith(".go"):
                type_re = re.compile(r"^\s*type\s+([a-zA-Z0-9_]+)\s+(?:struct|interface)", re.MULTILINE)
                method_re = re.compile(r"^\s*func\s+\(\s*[^)]*\*?\s*([a-zA-Z0-9_]+)\s*\)\s*([a-zA-Z0-9_]+)", re.MULTILINE)
                for m in type_re.finditer(content):
                    facts.append((FACT_CLASS, m.group(1), []))
                for m in method_re.finditer(content):
                    facts.append((FACT_CLASS, m.group(1), [m.group(2)]))

            # D. JS / TS
            elif norm_p.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs")):
                class_re = re.compile(r"^\s*(?:export\s+)?(?:class|interface)\s+([a-zA-Z0-9_]+)", re.MULTILINE)
                for m in class_re.finditer(content):
                    facts.append((FACT_CLASS, m.group(1), []))
            return facts

        # A. Python
        if norm_p.endswith(".py"):
            try:
                tree = ast.parse(content, filename=path)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name):
                            facts.append((FACT_CONSTRUCT, node.func.id))
                        elif isinstance(node.func, ast.Attribute):
                            facts.append((FACT_ATTRIBUTE, node.func.attr))
                    elif isinstance(node, ast.ImportFrom):
                        for alias in node.names:
                            facts.append((FACT_IMPORT, alias.name))
            except Exception:
                for m in re.finditer(r"\b([A-Z][a-zA-Z0-9_]+)\(", content):
                    facts.append((FACT_CONSTRUCT, m.group(1)))
                for m in re.finditer(r"\.([a-z0-9_]+)\(", content):
                    facts.append((FACT_METHOD, m.group(1)))

        # B. Rust
        elif norm_p.endswith(".rs"):
            for m in re.finditer(r"\b([A-Z][a-zA-Z0-9_]*)::(?:new|default|from)\b|\b([A-Z][a-zA-Z0-9_]*)\s*\{", content):
                facts.append((FACT_CONSTRUCT, m.group(1) or m.group(2)))
            for m in re.finditer(r"\.([a-z0-9_]+)\(", content):
                facts.append((FACT_METHOD, m.group(1)))
            for m in re.finditer(r"use\s+.*::([A-Z][a-zA-Z0-9_]*)\b", content):
                facts.append((FACT_IMPORT, m.group(1)))

        # C. Go
        elif norm_p.endswith(".go"):
            for m in re.finditer(r"&(?:[a-zA-Z0-9_]+\.)?([A-Z][a-zA-Z0-9_]*)\s*\{|\b(?:New|Make)([A-Z][a-zA-Z0-9_]*)\b", content):
                facts.append((FACT_CONSTRUCT, m.group(1) or m.group(2)))
            for m in re.finditer(r"\.([A-Z][a-zA-Z0-9_]*)\(", content):
                facts.append((FACT_METHOD, m.group(1)))

        # D. JS/TS
        elif norm_p.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs")):
            for m in re.finditer(r"\bnew\s+([A-Z][a-zA-Z0-9_]*)\b", content):
                facts.append((FACT_CONSTRUCT, m.group(1)))
            for m in re.finditer(r"\b([A-Z][a-zA-Z0-9_]*)\.([a-zA-Z0-9_]+)\(", content):
                facts.append((FACT_CLASS_METHOD, m.group(1), m.group(2)))
        return facts

    def _extract_class_to_test_linkages(self, docs: List[FileDoc]):
        """
        Extracts evidence-backed class-to-test invocation relationships across
        Python, Rust, Go, TypeScript/JavaScript.

        The per-document extraction comes from ``doc_facts`` (cached by signature); the method lookup and the
        existing-edge lookup use indexes built once, in the same order as the scans they replace.
        """
        GENERIC_NAMES = {
            "Config", "Options", "State", "Context", "Base", "Error", "Item",
            "Entry", "Node", "Handler", "Client", "Response", "Request",
            "Builder", "Helper", "Result", "Event", "Manager", "Data",
            "Value", "Info", "Model", "Service", "Session", "Task", "App",
            "Engine", "Parser", "Server", "Type", "Param", "Params"
        }

        # 1. Catalog production classes, types, and methods
        prod_classes: Dict[str, List[Tuple[str, List[str]]]] = {}
        class_to_defining_files: Dict[str, Set[str]] = {}

        for doc in docs:
            if doc.is_test:
                continue
            for _kind, cname, methods in self.doc_facts(doc):
                prod_classes.setdefault(cname, []).append((doc.path, methods))
                class_to_defining_files.setdefault(cname, set()).add(doc.path)

        # Classes defining each method name, in the order of the 1.2.0 scan (classes, then their entries).
        classes_by_method: Dict[str, List[Tuple[str, str]]] = {}
        for cls_name, pairs in prod_classes.items():
            for p, methods in pairs:
                for m_name in dict.fromkeys(methods):
                    classes_by_method.setdefault(m_name, []).append((cls_name, p))
        edge_by_key: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

        # 2. Inspect test files for invocations
        for doc in docs:
            if not doc.is_test:
                continue

            detected_calls: Set[Tuple[str, str, str]] = set()
            for fact in self.doc_facts(doc):
                kind = fact[0]
                if kind == FACT_CONSTRUCT:
                    if fact[1] in prod_classes:
                        detected_calls.add((fact[1], "", "DIRECT_CLASS_CONSTRUCTION"))
                elif kind == FACT_ATTRIBUTE:
                    if fact[1] in prod_classes:
                        detected_calls.add((fact[1], "", "IMPORTED_MODULE_CALL"))
                    else:
                        detected_calls.add(("", fact[1], "DIRECT_METHOD_CALL"))
                elif kind == FACT_IMPORT:
                    if fact[1] in prod_classes:
                        detected_calls.add((fact[1], "", "CLASS_IMPORT"))
                elif kind == FACT_METHOD:
                    detected_calls.add(("", fact[1], "DIRECT_METHOD_CALL"))
                elif kind == FACT_CLASS_METHOD:
                    if fact[1] in prod_classes:
                        detected_calls.add((fact[1], fact[2], "DIRECT_METHOD_CALL"))

            # 3. Disambiguate and link candidate calls
            for cname, mname, ev_type in detected_calls:
                target_paths = set()
                conf = 1.0

                if cname:
                    defining_files = class_to_defining_files.get(cname, set())
                    if len(defining_files) == 1:
                        target_paths = defining_files
                        conf = 1.0 if ev_type == "DIRECT_CLASS_CONSTRUCTION" else 0.90
                    elif len(defining_files) > 1:
                        if cname in GENERIC_NAMES or len(defining_files) > 3:
                            matching_imports = set()
                            for df in defining_files:
                                mod_name = self._normalize_module_name(df)
                                if any(imp == mod_name or imp.endswith(mod_name) or imp in df for imp in doc.imports):
                                    matching_imports.add(df)
                            if len(matching_imports) == 1:
                                target_paths = matching_imports
                                conf = 0.85
                                ev_type = "IMPORTED_MODULE_CALL"
                            else:
                                self.unresolved_diagnostics.append({
                                    "test_path": doc.path,
                                    "class_name": cname,
                                    "candidate_count": len(defining_files),
                                    "candidates": sorted(list(defining_files))[:5],
                                    "reason": "AMBIGUOUS_GENERIC_CLASS_WITHOUT_QUALIFYING_IMPORT",
                                })
                        else:
                            matching_dir = {df for df in defining_files if os.path.dirname(df.replace("\\", "/")) == os.path.dirname(doc.path.replace("\\", "/"))}
                            if len(matching_dir) == 1:
                                target_paths = matching_dir
                                conf = 0.80
                            else:
                                matching_imports = {df for df in defining_files if any(imp in df for imp in doc.imports)}
                                if len(matching_imports) == 1:
                                    target_paths = matching_imports
                                    conf = 0.80
                                else:
                                    self.unresolved_diagnostics.append({
                                        "test_path": doc.path,
                                        "class_name": cname,
                                        "candidate_count": len(defining_files),
                                        "candidates": sorted(list(defining_files))[:5],
                                        "reason": "MULTI_FILE_DEFINITION_UNRESOLVED",
                                    })

                elif mname and len(mname) > 3 and mname not in ("get", "set", "run", "init", "exec", "call", "close", "read", "write", "test", "main", "start", "stop"):
                    classes_with_method = classes_by_method.get(mname, ())
                    if len(classes_with_method) == 1:
                        cname, p = classes_with_method[0]
                        target_paths = {p}
                        conf = 0.75
                        ev_type = "DIRECT_METHOD_CALL"

                # Record resolved edges with evidence priority
                ev_prio = {"DIRECT_CLASS_CONSTRUCTION": 4, "DIRECT_METHOD_CALL": 3, "IMPORTED_MODULE_CALL": 2, "CLASS_IMPORT": 1}
                for t_path in target_paths:
                    if t_path != doc.path:
                        existing = edge_by_key.get((doc.path, t_path, cname))
                        if existing is not None:
                            if ev_prio.get(ev_type, 0) > ev_prio.get(existing["evidence_type"], 0):
                                existing["evidence_type"] = ev_type
                                existing["confidence"] = conf
                                if mname: existing["method_name"] = mname
                        else:
                            edge = {
                                "test_path": doc.path,
                                "prod_path": t_path,
                                "class_name": cname,
                                "method_name": mname,
                                "evidence_type": ev_type,
                                "confidence": conf,
                                "is_ambiguous": False,
                            }
                            self.invocation_edges.append(edge)
                            edge_by_key[(doc.path, t_path, cname)] = edge
                        self.prod_to_test_invocations.setdefault(t_path, set()).add(doc.path)
                        self.test_to_prod_invocations.setdefault(doc.path, set()).add(t_path)

                        if self.enable_class_to_test:
                            self.graph.add_edge(t_path, doc.path, edge_type="class_to_test", confidence=conf)
                            self.graph.add_edge(doc.path, t_path, edge_type="test_to_class", confidence=conf)

        # 4. Construct degree-matched control graph
        all_test_nodes = sorted(list(self.test_to_prod_invocations.keys()))
        all_prod_nodes = sorted(list(self.prod_to_test_invocations.keys()))
        if all_test_nodes and all_prod_nodes:
            rng = np.random.RandomState(42)
            for p, tests in self.prod_to_test_invocations.items():
                k = min(len(tests), len(all_test_nodes))
                matched_tests = set(rng.choice(all_test_nodes, size=k, replace=False))
                self.degree_matched_prod_to_test[p] = matched_tests
            for t, prods in self.test_to_prod_invocations.items():
                k = min(len(prods), len(all_prod_nodes))
                matched_prods = set(rng.choice(all_prod_nodes, size=k, replace=False))
                self.degree_matched_test_to_prod[t] = matched_prods
