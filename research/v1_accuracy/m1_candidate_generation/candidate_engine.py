"""
Multi-Stage Candidate Generation Engine for RepoNeedle V1.0.0.

Implements:
- Channel A: ExactSymbolIndex (AST definitions, chunk symbols, qualified names, normalized identifiers)
- Channel B: FieldAwareBM25 (filepath, filename, symbol_names, qualified_names, signatures, docstrings, comments, body)
- Channel C: SubwordChannel (fast subword character n-grams over paths, filenames, and symbols)
- Channel D: BoundedStructuralExpansion (verified imports, test linkages, and caller/callee links)
- MultiChannelUnion: Deduplicated candidate pool with channel provenance, raw scores, and max-normalized combination.
"""

from __future__ import annotations

import re
import ast
import math
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Any
from collections import defaultdict
import numpy as np

from reponeedle.models import FileDoc
from reponeedle.core.tokenizer import CodeTokenizer, split_identifier


# --- IDENTIFIER NORMALIZATION UTILITIES ---

CAMEL_CASE_REGEX = re.compile(r"([a-z0-9])([A-Z])|([A-Z]+)([A-Z][a-z])")
BACKTICK_REGEX = re.compile(r"`([^`]+)`")
STACK_FRAME_REGEX = re.compile(r"File [\"']([^\"']+)[\"'], line \d+(?:, in ([a-zA-Z0-9_]+))?")
IDENTIFIER_CHAR_REGEX = re.compile(r"[A-Za-z0-9_]+")


def extract_normalized_identifiers(text: str) -> Dict[str, List[str]]:
    """
    Extracts and normalizes identifiers from query or code text.
    Returns:
        dict with:
        - 'exact_symbols': exact identifiers (e.g. 'SecureCookieSessionInterface')
        - 'qualified_names': dotted paths (e.g. 'session.interface.save')
        - 'tokens': lowercased component tokens (e.g. 'secure', 'cookie', 'session', 'interface')
        - 'backticked': explicit backtick-enclosed symbols
        - 'file_paths': potential file path mentions
    """
    exact_symbols: Set[str] = set()
    qualified_names: Set[str] = set()
    tokens: Set[str] = set()
    backticked: Set[str] = set()
    file_paths: Set[str] = set()

    # 1. Backticked symbols
    for b in BACKTICK_REGEX.findall(text):
        b_clean = b.strip()
        if b_clean:
            backticked.add(b_clean)
            exact_symbols.add(b_clean)

    # 2. Stack frame mentions
    for frame_match in STACK_FRAME_REGEX.finditer(text):
        fpath, func_name = frame_match.groups()
        if fpath:
            file_paths.add(fpath.replace("\\", "/"))
        if func_name:
            exact_symbols.add(func_name)

    # 3. Path-like strings (containing / or \)
    for word in text.split():
        cleaned_word = word.strip("()[]{},;:'\"`")
        if "/" in cleaned_word or "\\" in cleaned_word:
            norm_p = cleaned_word.replace("\\", "/")
            if any(norm_p.endswith(ext) for ext in [".py", ".rs", ".go", ".js", ".ts", ".c", ".cpp", ".h", ".toml", ".json", ".md"]):
                file_paths.add(norm_p)

    # 4. Word tokens and compound identifiers
    raw_words = IDENTIFIER_CHAR_REGEX.findall(text)
    for w in raw_words:
        if len(w) < 2:
            continue
        exact_symbols.add(w)
        # Component splitting
        sub_tokens = split_identifier(w)
        for st in sub_tokens:
            if len(st) > 1:
                tokens.add(st.lower())

    # 5. Dotted qualified names (e.g. module.submodule.func)
    dotted_matches = re.findall(r"\b[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+\b", text)
    for dm in dotted_matches:
        qualified_names.add(dm)
        for part in dm.split("."):
            exact_symbols.add(part)

    return {
        "exact_symbols": list(exact_symbols),
        "qualified_names": list(qualified_names),
        "tokens": list(tokens),
        "backticked": list(backticked),
        "file_paths": list(file_paths),
    }


# ==============================================================================
# CHANNEL A: EXACT SYMBOL INDEX
# ==============================================================================

@dataclass
class SymbolDefinition:
    name: str
    qualified_name: str
    kind: str  # 'function', 'method', 'class', 'const', 'file'
    filepath: str
    start_line: int
    parameters: List[str] = field(default_factory=list)
    signature: str = ""


class ExactSymbolIndex:
    """
    Bitwise/exact inverted index for source-code symbol definitions.
    Maps normalized symbol names, qualified names, and parameter signatures directly to file paths.
    """

    def __init__(self):
        self.doc_paths: List[str] = []
        self.path_to_idx: Dict[str, int] = {}
        self.exact_symbol_to_docs: Dict[str, Set[int]] = defaultdict(set)
        self.exact_symbol_lower_to_docs: Dict[str, Set[int]] = defaultdict(set)
        self.qualified_name_to_docs: Dict[str, Set[int]] = defaultdict(set)
        self.token_to_docs: Dict[str, Set[int]] = defaultdict(set)
        self.total_symbols_indexed: int = 0

    def fit_from_doc_info(
        self,
        doc_paths: List[str],
        doc_symbols: List[List[str]],
        doc_qualified: List[List[str]],
        doc_signatures: List[List[str]],
    ) -> "ExactSymbolIndex":
        self.doc_paths = doc_paths
        self.path_to_idx = {p: i for i, p in enumerate(doc_paths)}
        self.exact_symbol_to_docs.clear()
        self.exact_symbol_lower_to_docs.clear()
        self.qualified_name_to_docs.clear()
        self.token_to_docs.clear()
        self.total_symbols_indexed = 0

        for idx, p in enumerate(doc_paths):
            p_clean = p.replace("\\", "/")
            fname = p_clean.split("/")[-1]

            # Index file path itself
            self.exact_symbol_to_docs[fname].add(idx)
            self.exact_symbol_lower_to_docs[fname.lower()].add(idx)
            self.exact_symbol_to_docs[p_clean].add(idx)
            self.exact_symbol_lower_to_docs[p_clean.lower()].add(idx)

            # Component tokens of path
            for st in split_identifier(p_clean):
                if len(st) > 1:
                    self.token_to_docs[st.lower()].add(idx)

            # Symbols
            for sym in doc_symbols[idx]:
                self.exact_symbol_to_docs[sym].add(idx)
                self.exact_symbol_lower_to_docs[sym.lower()].add(idx)
                self.total_symbols_indexed += 1
                for st in split_identifier(sym):
                    if len(st) > 1:
                        self.token_to_docs[st.lower()].add(idx)

            # Qualified names
            for qn in doc_qualified[idx]:
                self.qualified_name_to_docs[qn].add(idx)
                self.qualified_name_to_docs[qn.lower()].add(idx)
                for part in qn.split("."):
                    self.exact_symbol_to_docs[part].add(idx)
                    self.exact_symbol_lower_to_docs[part.lower()].add(idx)

            # Signatures
            for sig in doc_signatures[idx]:
                for st in split_identifier(sig):
                    if len(st) > 1:
                        self.token_to_docs[st.lower()].add(idx)

        return self

    def retrieve_candidates(self, query: str) -> Dict[int, float]:
        """
        Retrieves candidates matching extracted query identifiers.
        Returns dict of {doc_idx: exact_symbol_score}.
        """
        info = extract_normalized_identifiers(query)
        scores: Dict[int, float] = defaultdict(float)

        # 1. Backticked exact identifiers (highest precision signal)
        for b in info["backticked"]:
            if b in self.exact_symbol_to_docs:
                for doc_idx in self.exact_symbol_to_docs[b]:
                    scores[doc_idx] += 5.0
            elif b.lower() in self.exact_symbol_lower_to_docs:
                for doc_idx in self.exact_symbol_lower_to_docs[b.lower()]:
                    scores[doc_idx] += 4.0

        # 2. File path direct matches
        for fp in info["file_paths"]:
            fp_clean = fp.lower()
            for doc_idx, path in enumerate(self.doc_paths):
                p_lower = path.lower()
                if fp_clean == p_lower or p_lower.endswith(fp_clean) or fp_clean.endswith(p_lower):
                    scores[doc_idx] += 10.0
                elif fp_clean.split("/")[-1] == p_lower.split("/")[-1]:
                    scores[doc_idx] += 6.0

        # 3. Qualified names (e.g. Class.method)
        for qn in info["qualified_names"]:
            if qn in self.qualified_name_to_docs:
                for doc_idx in self.qualified_name_to_docs[qn]:
                    scores[doc_idx] += 4.5
            elif qn.lower() in self.qualified_name_to_docs:
                for doc_idx in self.qualified_name_to_docs[qn.lower()]:
                    scores[doc_idx] += 3.5

        # 4. Exact symbol names (function/class definitions)
        for sym in info["exact_symbols"]:
            if len(sym) < 3:
                continue
            if sym in self.exact_symbol_to_docs:
                doc_count = len(self.exact_symbol_to_docs[sym])
                weight = 3.0 / math.log2(doc_count + 1.0)
                for doc_idx in self.exact_symbol_to_docs[sym]:
                    scores[doc_idx] += weight
            elif sym.lower() in self.exact_symbol_lower_to_docs:
                doc_count = len(self.exact_symbol_lower_to_docs[sym.lower()])
                weight = 2.0 / math.log2(doc_count + 1.0)
                for doc_idx in self.exact_symbol_lower_to_docs[sym.lower()]:
                    scores[doc_idx] += weight

        # 5. Token matches
        for tok in info["tokens"]:
            if len(tok) < 3:
                continue
            if tok in self.token_to_docs:
                doc_count = len(self.token_to_docs[tok])
                if doc_count < len(self.doc_paths) * 0.4:
                    weight = 0.5 / math.log2(doc_count + 1.0)
                    for doc_idx in self.token_to_docs[tok]:
                        scores[doc_idx] += weight

        return dict(scores)


# ==============================================================================
# CHANNEL B: FIELD-AWARE BM25
# ==============================================================================

class SingleFieldBM25:
    """
    Standard Okapi BM25 index over a single designated field with precomputed length normalization.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_len: np.ndarray = np.array([], dtype=np.float32)
        self.doc_norm: np.ndarray = np.array([], dtype=np.float32)
        self.avg_doc_len: float = 0.0
        self.idf: Dict[str, float] = {}
        self.inverted_index: Dict[str, List[Tuple[int, float]]] = defaultdict(list)
        self.num_docs: int = 0

    def fit(self, field_tokens: List[List[str]]) -> "SingleFieldBM25":
        self.num_docs = len(field_tokens)
        self.inverted_index.clear()
        self.idf.clear()

        if self.num_docs == 0:
            self.avg_doc_len = 0.0
            self.doc_len = np.array([], dtype=np.float32)
            self.doc_norm = np.array([], dtype=np.float32)
            return self

        lengths = [len(toks) for toks in field_tokens]
        self.doc_len = np.array(lengths, dtype=np.float32)
        self.avg_doc_len = float(np.mean(self.doc_len)) if self.num_docs > 0 else 0.0

        if self.avg_doc_len > 0:
            self.doc_norm = self.k1 * (1.0 - self.b + self.b * (self.doc_len / self.avg_doc_len))
        else:
            self.doc_norm = np.zeros(self.num_docs, dtype=np.float32)

        doc_frequencies: Dict[str, int] = defaultdict(int)
        for doc_idx, toks in enumerate(field_tokens):
            term_counts: Dict[str, int] = defaultdict(int)
            for t in toks:
                term_counts[t] += 1
            for t, count in term_counts.items():
                doc_frequencies[t] += 1
                self.inverted_index[t].append((doc_idx, float(count)))

        for t, df in doc_frequencies.items():
            self.idf[t] = math.log(1.0 + (self.num_docs - df + 0.5) / (df + 0.5))

        return self

    def score(self, query_tokens: List[str]) -> np.ndarray:
        scores = np.zeros(self.num_docs, dtype=np.float32)
        if self.num_docs == 0 or self.avg_doc_len == 0.0:
            return scores

        from collections import Counter
        counts = Counter(query_tokens)
        k1_plus_1 = self.k1 + 1.0
        doc_norm = self.doc_norm

        for t, qtf in counts.items():
            if t not in self.inverted_index:
                continue
            weight = self.idf[t] * qtf * k1_plus_1
            for doc_idx, tf in self.inverted_index[t]:
                scores[doc_idx] += (weight * tf) / (tf + doc_norm[doc_idx])

        return scores


class FieldAwareBM25:
    """
    Multi-field BM25 index indexing 8 separate code fields:
    - filepath
    - filename
    - symbol_names
    - qualified_names
    - signatures
    - docstrings
    - comments
    - body
    """

    def __init__(self):
        self.tokenizer = CodeTokenizer()
        self.fields = [
            "filepath",
            "filename",
            "symbol_names",
            "qualified_names",
            "signatures",
            "docstrings",
            "comments",
            "body",
        ]
        self.indices: Dict[str, SingleFieldBM25] = {f: SingleFieldBM25() for f in self.fields}
        self.num_docs: int = 0
        self.doc_paths: List[str] = []

    def fit_from_fields(self, doc_paths: List[str], field_tokens: Dict[str, List[List[str]]]) -> "FieldAwareBM25":
        self.num_docs = len(doc_paths)
        self.doc_paths = doc_paths
        for f in self.fields:
            self.indices[f].fit(field_tokens.get(f, [[] for _ in range(self.num_docs)]))
        return self

    def score_isolated_field(self, field_name: str, query: str) -> np.ndarray:
        if field_name not in self.indices:
            raise ValueError(f"Unknown field: {field_name}")
        query_tokens = self.tokenizer.tokenize_text(query)
        return self.indices[field_name].score(query_tokens)

    def score_all_fields(self, query: str, weights: Optional[Dict[str, float]] = None) -> np.ndarray:
        w = weights or {
            "filepath": 2.5,
            "filename": 3.0,
            "symbol_names": 2.5,
            "qualified_names": 2.0,
            "signatures": 1.0,
            "docstrings": 1.0,
            "comments": 0.5,
            "body": 1.0,
        }
        total_score = np.zeros(self.num_docs, dtype=np.float32)
        for f, weight in w.items():
            if f in self.indices and weight > 0:
                s = self.score_isolated_field(f, query)
                total_score += weight * s
        return total_score


# ==============================================================================
# CHANNEL C: SUBWORD RETRIEVAL CHANNEL
# ==============================================================================

class SubwordChannel:
    """
    Fast subword character n-gram index targeting identifiers, qualified names, and file paths.
    Bridges morphological gaps, abbreviations, and composite identifier naming variations.
    """

    def __init__(self, min_n: int = 3, max_n: int = 5):
        self.min_n = min_n
        self.max_n = max_n
        self.num_docs: int = 0
        self.doc_paths: List[str] = []
        self.inverted_index: Dict[str, List[Tuple[int, float]]] = defaultdict(list)
        self.idf: Dict[str, float] = {}

    def _extract_ngrams(self, tokens: List[str]) -> List[str]:
        ngrams: List[str] = []
        for t in tokens:
            t_clean = t.lower()
            if len(t_clean) < self.min_n:
                continue
            bound = f"<{t_clean}>"
            for n in range(self.min_n, min(len(bound) + 1, self.max_n + 1)):
                for i in range(len(bound) - n + 1):
                    ngrams.append(bound[i : i + n])
        return ngrams

    def fit_from_tokens(self, doc_paths: List[str], doc_identifier_tokens: List[List[str]]) -> "SubwordChannel":
        self.num_docs = len(doc_paths)
        self.doc_paths = doc_paths
        self.inverted_index.clear()
        self.idf.clear()

        df_counts: Dict[str, int] = defaultdict(int)
        for doc_idx, toks in enumerate(doc_identifier_tokens):
            ngs = self._extract_ngrams(toks)
            tf: Dict[str, int] = defaultdict(int)
            for ng in ngs:
                tf[ng] += 1
            for ng, count in tf.items():
                df_counts[ng] += 1
                self.inverted_index[ng].append((doc_idx, float(count)))

        for ng, df in df_counts.items():
            self.idf[ng] = math.log(1.0 + (self.num_docs - df + 0.5) / (df + 0.5))

        return self

    def score(self, query: str) -> np.ndarray:
        scores = np.zeros(self.num_docs, dtype=np.float32)
        if self.num_docs == 0:
            return scores

        # Extract tokens from query
        words = IDENTIFIER_CHAR_REGEX.findall(query)
        tokens: List[str] = []
        for w in words:
            for st in split_identifier(w):
                if len(st) >= self.min_n:
                    tokens.append(st.lower())

        q_ngrams = self._extract_ngrams(tokens)
        if not q_ngrams:
            return scores

        q_tf: Dict[str, int] = defaultdict(int)
        for ng in q_ngrams:
            q_tf[ng] += 1

        for ng, q_count in q_tf.items():
            if ng in self.inverted_index:
                idf_val = self.idf[ng]
                for doc_idx, d_count in self.inverted_index[ng]:
                    scores[doc_idx] += idf_val * math.sqrt(d_count * q_count)

        return scores


# ==============================================================================
# CHANNEL D: BOUNDED STRUCTURAL EXPANSION
# ==============================================================================

class BoundedStructuralExpansion:
    """
    1-hop verified relationship expansion for top candidates.
    Expands:
    - Target to known test files (inverted test mapping via stem index and import graph)
    - File to direct imports / importers
    - Seeds can be provided from prior channels or direct query file mentions
    """

    def __init__(self):
        self.doc_paths: List[str] = []
        self.path_to_idx: Dict[str, int] = {}
        self.import_graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_import_graph: Dict[str, Set[str]] = defaultdict(set)
        self.stem_to_targets: Dict[str, Set[str]] = defaultdict(set)
        self.test_to_target: Dict[str, Set[str]] = defaultdict(set)
        self.target_to_test: Dict[str, Set[str]] = defaultdict(set)

    def fit_from_graph(
        self,
        doc_paths: List[str],
        doc_imports: List[List[str]],
    ) -> "BoundedStructuralExpansion":
        self.doc_paths = doc_paths
        self.path_to_idx = {p: i for i, p in enumerate(doc_paths)}
        self.import_graph.clear()
        self.reverse_import_graph.clear()
        self.stem_to_targets.clear()
        self.test_to_target.clear()
        self.target_to_test.clear()

        # Build module to path map
        module_to_path: Dict[str, str] = {}
        for p in self.doc_paths:
            p_clean = p.replace("\\", "/")
            fname = p_clean.split("/")[-1]
            stem = fname.rsplit(".", 1)[0].lower()
            if "test" not in fname.lower() and len(stem) > 2:
                self.stem_to_targets[stem].add(p_clean)

            # Python module stems
            if p_clean.endswith(".py"):
                mod = p_clean[:-3].replace("/", ".")
                module_to_path[mod] = p_clean
                parts = mod.split(".")
                if len(parts) > 1:
                    module_to_path[parts[-1]] = p_clean

        # Link imports
        for idx, p in enumerate(self.doc_paths):
            p_clean = p.replace("\\", "/")
            for imp in doc_imports[idx]:
                if imp in module_to_path:
                    target = module_to_path[imp]
                    if target != p_clean:
                        self.import_graph[p_clean].add(target)
                        self.reverse_import_graph[target].add(p_clean)

        # Link test files using stem dictionary ($O(N)$ lookup)
        for p in self.doc_paths:
            p_clean = p.replace("\\", "/")
            fname_lower = p_clean.split("/")[-1].lower()
            if "test" in fname_lower:
                for part in re.split(r"[_\-\.]", fname_lower):
                    if len(part) > 3 and part in self.stem_to_targets:
                        for target in self.stem_to_targets[part]:
                            if target != p_clean:
                                self.test_to_target[p_clean].add(target)
                                self.target_to_test[target].add(p_clean)

        return self

    def expand_candidates(
        self,
        seed_scores: Dict[int, float],
        decay: float = 0.5,
        max_seeds: int = 15,
        max_expansion_per_seed: int = 8,
    ) -> Dict[int, Tuple[float, Dict[str, Any]]]:
        """
        Expands top seed candidates by 1 verified hop.
        Returns: {expanded_doc_idx: (boost_score, evidence_metadata)}
        """
        sorted_seeds = sorted(seed_scores.items(), key=lambda x: -x[1])[:max_seeds]
        expansion_scores: Dict[int, Tuple[float, Dict[str, Any]]] = {}

        for seed_idx, seed_val in sorted_seeds:
            if seed_val <= 0:
                continue
            seed_path = self.doc_paths[seed_idx]

            # 1. Target -> Tests
            tests = self.target_to_test.get(seed_path, set())
            for t_path in list(tests)[:max_expansion_per_seed]:
                if t_path in self.path_to_idx:
                    t_idx = self.path_to_idx[t_path]
                    boost = seed_val * decay
                    evidence = {"seed_path": seed_path, "relation": "tested_by", "seed_score": seed_val}
                    if t_idx not in expansion_scores or expansion_scores[t_idx][0] < boost:
                        expansion_scores[t_idx] = (boost, evidence)

            # 2. Test -> Target
            targets = self.test_to_target.get(seed_path, set())
            for tgt_path in list(targets)[:max_expansion_per_seed]:
                if tgt_path in self.path_to_idx:
                    tgt_idx = self.path_to_idx[tgt_path]
                    boost = seed_val * decay
                    evidence = {"seed_path": seed_path, "relation": "tests_target", "seed_score": seed_val}
                    if tgt_idx not in expansion_scores or expansion_scores[tgt_idx][0] < boost:
                        expansion_scores[tgt_idx] = (boost, evidence)

            # 3. Direct importers
            importers = self.reverse_import_graph.get(seed_path, set())
            for imp_path in list(importers)[:max_expansion_per_seed]:
                if imp_path in self.path_to_idx:
                    imp_idx = self.path_to_idx[imp_path]
                    boost = seed_val * decay * 0.7
                    evidence = {"seed_path": seed_path, "relation": "imported_by", "seed_score": seed_val}
                    if imp_idx not in expansion_scores or expansion_scores[imp_idx][0] < boost:
                        expansion_scores[imp_idx] = (boost, evidence)

            # 4. Direct imports
            imports = self.import_graph.get(seed_path, set())
            for imp_path in list(imports)[:max_expansion_per_seed]:
                if imp_path in self.path_to_idx:
                    imp_idx = self.path_to_idx[imp_path]
                    boost = seed_val * decay * 0.7
                    evidence = {"seed_path": seed_path, "relation": "imports", "seed_score": seed_val}
                    if imp_idx not in expansion_scores or expansion_scores[imp_idx][0] < boost:
                        expansion_scores[imp_idx] = (boost, evidence)

        return expansion_scores


# ==============================================================================
# MULTI-CHANNEL UNION & CANDIDATE MANAGER
# ==============================================================================

@dataclass
class CandidateItem:
    doc_idx: int
    filepath: str
    channel_provenance: Set[str] = field(default_factory=set)
    channel_scores: Dict[str, float] = field(default_factory=dict)
    structural_evidence: List[Dict[str, Any]] = field(default_factory=list)
    combined_score: float = 0.0


class MultiChannelCandidateEngine:
    """
    Unified multi-channel candidate generation engine for RepoNeedle V1.0.0.
    Executes:
    - Channel A: ExactSymbolIndex
    - Channel B: FieldAwareBM25
    - Channel C: SubwordChannel
    - Channel D: BoundedStructuralExpansion
    Performs single-pass AST and polyglot document extraction for fast, memory-bounded indexing.
    """

    def __init__(self):
        self.channel_a = ExactSymbolIndex()
        self.channel_b = FieldAwareBM25()
        self.channel_c = SubwordChannel()
        self.channel_d = BoundedStructuralExpansion()
        self.doc_paths: List[str] = []
        self.num_docs: int = 0
        self.tokenizer = CodeTokenizer()

    def fit(self, docs: List[FileDoc]) -> "MultiChannelCandidateEngine":
        """
        Fits all 4 channels using a fast, single-pass feature extraction loop.
        """
        self.num_docs = len(docs)
        self.doc_paths = [d.path.replace("\\", "/") for d in docs]

        doc_symbols: List[List[str]] = []
        doc_qualified: List[List[str]] = []
        doc_signatures: List[List[str]] = []
        doc_docstrings: List[List[str]] = []
        doc_comments: List[List[str]] = []
        doc_body_toks: List[List[str]] = []
        doc_imports: List[List[str]] = []
        doc_ident_tokens: List[List[str]] = []

        field_tokens_by_field: Dict[str, List[List[str]]] = {
            f: [] for f in self.channel_b.fields
        }

        for doc in docs:
            p_clean = doc.path.replace("\\", "/")
            fname = p_clean.split("/")[-1]

            path_toks = self.tokenizer.tokenize_path(p_clean)
            fname_toks = self.tokenizer.tokenize_path(fname)

            syms: List[str] = list(doc.symbols) if doc.symbols else []
            qualified: List[str] = []
            sigs: List[str] = []
            docs_list: List[str] = []
            comments: List[str] = []
            imps: List[str] = list(doc.imports) if doc.imports else []
            body_toks: List[str] = []

            content = doc.content or ""
            if content:
                # Comments scan
                for line in content.splitlines():
                    line_s = line.strip()
                    if line_s.startswith(("#", "//", "/*", "*")):
                        comments.extend(self.tokenizer.tokenize_text(line_s))

                # Python AST parsing
                if p_clean.endswith(".py"):
                    try:
                        tree = ast.parse(content[:25000])
                        mod_doc = ast.get_docstring(tree)
                        if mod_doc:
                            docs_list.extend(self.tokenizer.tokenize_text(mod_doc))
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                syms.append(node.name)
                                c_doc = ast.get_docstring(node)
                                if c_doc:
                                    docs_list.extend(self.tokenizer.tokenize_text(c_doc))
                                for item in node.body:
                                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                        syms.append(item.name)
                                        qualified.append(f"{node.name}.{item.name}")
                                        m_doc = ast.get_docstring(item)
                                        if m_doc:
                                            docs_list.extend(self.tokenizer.tokenize_text(m_doc))
                                        for a in item.args.args:
                                            if a.arg != "self":
                                                sigs.append(a.arg)
                            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                syms.append(node.name)
                                f_doc = ast.get_docstring(node)
                                if f_doc:
                                    docs_list.extend(self.tokenizer.tokenize_text(f_doc))
                                for a in node.args.args:
                                    if a.arg != "self":
                                        sigs.append(a.arg)
                            elif isinstance(node, ast.Import):
                                for alias in node.names:
                                    imps.append(alias.name)
                            elif isinstance(node, ast.ImportFrom):
                                if node.module:
                                    imps.append(node.module)
                    except Exception:
                        # Regex fallback for truncated or syntax error files
                        for m in re.finditer(r"^(?:def|class)\s+([a-zA-Z0-9_]+)", content, re.MULTILINE):
                            syms.append(m.group(1))

                # Polyglot fallback (Rust, Go, JS, TS)
                else:
                    for m in re.finditer(r"\bfn\s+([a-zA-Z0-9_]+)", content):
                        syms.append(m.group(1))
                    for m in re.finditer(r"\b(?:struct|trait|enum|class|type)\s+([a-zA-Z0-9_]+)", content):
                        syms.append(m.group(1))
                    for m in re.finditer(r"\bfunc\s+(?:\([^\)]+\)\s+)?([a-zA-Z0-9_]+)", content):
                        syms.append(m.group(1))

                body_toks = self.tokenizer.tokenize_text(content[:3000])

            # Deduplicate symbols while preserving order
            seen_s: Set[str] = set()
            clean_syms: List[str] = []
            for s in syms:
                if s not in seen_s and len(s) > 1:
                    seen_s.add(s)
                    clean_syms.append(s)

            doc_symbols.append(clean_syms)
            doc_qualified.append(qualified)
            doc_signatures.append(sigs)
            doc_docstrings.append(docs_list)
            doc_comments.append(comments)
            doc_body_toks.append(body_toks)
            doc_imports.append(imps)

            # Subword identifier tokens: path + symbols + signatures
            subword_toks = list(path_toks) + list(clean_syms) + list(sigs)
            doc_ident_tokens.append(subword_toks)

            # Fields for BM25
            field_tokens_by_field["filepath"].append(path_toks)
            field_tokens_by_field["filename"].append(fname_toks)
            field_tokens_by_field["symbol_names"].append([tok for s in clean_syms for tok in split_identifier(s)])
            field_tokens_by_field["qualified_names"].append([tok for q in qualified for tok in split_identifier(q)])
            field_tokens_by_field["signatures"].append([tok for s in sigs for tok in split_identifier(s)])
            field_tokens_by_field["docstrings"].append(docs_list)
            field_tokens_by_field["comments"].append(comments)
            field_tokens_by_field["body"].append(body_toks)

        # Fit Channel A
        self.channel_a.fit_from_doc_info(self.doc_paths, doc_symbols, doc_qualified, doc_signatures)

        # Fit Channel B
        self.channel_b.fit_from_fields(self.doc_paths, field_tokens_by_field)

        # Fit Channel C
        self.channel_c.fit_from_tokens(self.doc_paths, doc_ident_tokens)

        # Fit Channel D
        self.channel_d.fit_from_graph(self.doc_paths, doc_imports)

        return self

    def generate_candidates(
        self,
        query: str,
        enable_exact_symbols: bool = True,
        enable_field_bm25: bool = True,
        enable_subwords: bool = True,
        enable_structural_expansion: bool = True,
        bm25_field_weights: Optional[Dict[str, float]] = None,
    ) -> List[CandidateItem]:
        """
        Executes all active candidate channels, collects non-zero score items,
        normalizes active channel scores, and returns deduplicated candidates.
        """
        candidates: Dict[int, CandidateItem] = {}

        def get_cand(idx: int) -> CandidateItem:
            if idx not in candidates:
                candidates[idx] = CandidateItem(doc_idx=idx, filepath=self.doc_paths[idx])
            return candidates[idx]

        # Channel A: Exact Symbol Index
        if enable_exact_symbols:
            sym_scores = self.channel_a.retrieve_candidates(query)
            for idx, s in sym_scores.items():
                if s > 0:
                    c = get_cand(idx)
                    c.channel_provenance.add("exact_symbol")
                    c.channel_scores["exact_symbol"] = float(s)

        # Channel B: Field-Aware BM25
        if enable_field_bm25:
            bm25_scores = self.channel_b.score_all_fields(query, weights=bm25_field_weights)
            for idx, s in enumerate(bm25_scores):
                if s > 0:
                    c = get_cand(idx)
                    c.channel_provenance.add("field_bm25")
                    c.channel_scores["field_bm25"] = float(s)

        # Channel C: Subword Retrieval
        if enable_subwords:
            sub_scores = self.channel_c.score(query)
            for idx, s in enumerate(sub_scores):
                if s > 0:
                    c = get_cand(idx)
                    c.channel_provenance.add("subwords")
                    c.channel_scores["subwords"] = float(s)

        # Channel D: Bounded Structural Expansion
        if enable_structural_expansion:
            seed_scores: Dict[int, float] = {}
            if candidates:
                seed_scores = {
                    idx: max(c.channel_scores.values()) if c.channel_scores else 0.0
                    for idx, c in candidates.items()
                }
            else:
                # Standalone Channel D ablation: seed from query file path mentions
                info = extract_normalized_identifiers(query)
                for fp in info["file_paths"]:
                    fp_clean = fp.lower()
                    for doc_idx, p in enumerate(self.doc_paths):
                        p_lower = p.lower()
                        if fp_clean == p_lower or p_lower.endswith(fp_clean) or fp_clean.endswith(p_lower):
                            seed_scores[doc_idx] = 10.0
                        elif fp_clean.split("/")[-1] == p_lower.split("/")[-1]:
                            seed_scores[doc_idx] = 6.0

            if seed_scores:
                exp_scores = self.channel_d.expand_candidates(seed_scores)
                for idx, (boost, ev) in exp_scores.items():
                    c = get_cand(idx)
                    c.channel_provenance.add("structural_expansion")
                    c.channel_scores["structural_expansion"] = float(boost)
                    c.structural_evidence.append(ev)

        if not candidates:
            return []

        # Max-normalize active channel scores for balanced candidate ranking
        channel_maxima: Dict[str, float] = defaultdict(float)
        for c in candidates.values():
            for ch, score in c.channel_scores.items():
                if score > channel_maxima[ch]:
                    channel_maxima[ch] = score

        # Weights per channel
        weights = {
            "exact_symbol": 0.40,
            "field_bm25": 0.35,
            "subwords": 0.15,
            "structural_expansion": 0.10,
        }

        for c in candidates.values():
            comb = 0.0
            for ch, s in c.channel_scores.items():
                m = channel_maxima[ch]
                norm_s = (s / m) if m > 0 else 0.0
                comb += weights.get(ch, 0.25) * norm_s
            c.combined_score = comb

        return sorted(candidates.values(), key=lambda c: -c.combined_score)
