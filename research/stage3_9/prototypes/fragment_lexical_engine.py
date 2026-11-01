"""
RepoNeedle Stage 3.9.6: Fragment-Aware Lexical Retrieval Engine.
Implements:
1. Complete, syntactically valid function fragment extraction and classification.
2. Incomplete header and truncated body quarantine.
3. Strict snapshot isolation and within-commit deduplication.
4. Multi-field lexical representation (name, qualified name, signature, parameters, docstring, body).
5. Projection models:
   - EXP-397: Exact canonical Stage 3.8 EXP-386 reference baseline.
   - EXP-398: EXP-397 + complete-function lexical matching via max pooling (alpha = 0.10).
   - EXP-399a: EXP-397 + soft-max top-2 function pooling (alpha = 0.10).
   - EXP-399b: EXP-397 + symbol specificity attenuation (alpha = 0.10).
"""

from __future__ import annotations

import os
import re
import ast
import json
import math
import hashlib
import textwrap
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Any
from collections import defaultdict, Counter


# Tokenizer regex: matches alphanumerics, splits on camelCase and snake_case
TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")
CAMEL_RE = re.compile(r"([a-z0-9])([A-Z])")


def tokenize_code(text: str) -> List[str]:
    if not text:
        return []
    # Split camelCase: e.g. getItem -> get Item
    s = CAMEL_RE.sub(r"\1 \2", text)
    raw_tokens = TOKEN_RE.findall(s.lower())
    tokens = []
    for t in raw_tokens:
        if len(t) > 1 and "_" in t:
            parts = t.split("_")
            for p in parts:
                if len(p) > 1:
                    tokens.append(p)
        tokens.append(t)
    return tokens


@dataclass(frozen=True)
class CompleteSymbolFragment:
    repo: str
    base_commit: str
    filepath: str
    name: str
    parent_class: Optional[str]
    qualified_name: str
    signature: str
    params: Tuple[str, ...]
    docstring: str
    body_text: str
    start_line: int
    end_line: int
    content_hash: str
    is_test: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repo": self.repo,
            "base_commit": self.base_commit,
            "filepath": self.filepath,
            "name": self.name,
            "parent_class": self.parent_class,
            "qualified_name": self.qualified_name,
            "signature": self.signature,
            "params": list(self.params),
            "docstring": self.docstring,
            "body_text": self.body_text[:200],  # preview
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content_hash": self.content_hash,
            "is_test": self.is_test,
        }


class FragmentClassifier:
    """
    Parses and categorizes symbol chunks fail-closed into:
    - COMPLETE_FUNCTION
    - INCOMPLETE_HEADER_ONLY
    - INCOMPLETE_BODY_TRUNCATED
    - QUARANTINED_INVALID
    """

    def __init__(self, repo: str, base_commit: str):
        self.repo = repo
        self.base_commit = base_commit
        self.complete_fragments: List[CompleteSymbolFragment] = []
        self.incomplete_headers_count = 0
        self.incomplete_bodies_count = 0
        self.quarantined_invalid_count = 0
        self.seen_signatures: Set[Tuple[str, str, int, int, str]] = set()

    def ingest_chunk(self, chunk: Dict[str, Any], candidate_files: Set[str]):
        path = chunk.get("path", "")
        if not path or not path.endswith(".py"):
            self.quarantined_invalid_count += 1
            return

        # Candidate pool invariance: if file is not in candidate files of this corpus, ignore
        if path not in candidate_files:
            return

        text = chunk.get("text", "")
        if not text.strip():
            self.quarantined_invalid_count += 1
            return

        start_line = chunk.get("start_line", 0)
        end_line = chunk.get("end_line", 0)
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

        is_test_file = "test" in path.lower() or path.lower().startswith("tests/")

        # Attempt dedented AST parse
        dedented = textwrap.dedent(text)
        try:
            tree = ast.parse(dedented)
        except SyntaxError as e:
            # Check if failure is at header or body
            err_line = e.lineno or 0
            if err_line <= 2 and any(kw in dedented[:100] for kw in ("def ", "async def ")):
                self.incomplete_headers_count += 1
            else:
                self.incomplete_bodies_count += 1
            return
        except Exception:
            self.quarantined_invalid_count += 1
            return

        # Walk AST to find functions
        found_function = False

        class FunctionExtractor(ast.NodeVisitor):
            def __init__(self, parent_clf):
                self.clf = parent_clf
                self.class_stack = []

            def visit_ClassDef(self, node: ast.ClassDef):
                self.class_stack.append(node.name)
                self.generic_visit(node)
                self.class_stack.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef):
                self._handle_func(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                self._handle_func(node)

            def _handle_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
                nonlocal found_function
                found_function = True

                parent_cls = self.class_stack[-1] if self.class_stack else None
                qual_name = f"{parent_cls}.{node.name}" if parent_cls else node.name

                dedup_key = (path, qual_name, start_line, end_line, content_hash)
                if dedup_key in self.clf.seen_signatures:
                    return
                self.clf.seen_signatures.add(dedup_key)

                # Parameters
                params = tuple([a.arg for a in node.args.args if a.arg not in ("self", "cls")])

                # Signature preview
                sig_lines = []
                for a in node.args.args:
                    ann = f": {ast.unparse(a.annotation)}" if getattr(a, "annotation", None) and hasattr(ast, "unparse") else ""
                    sig_lines.append(f"{a.arg}{ann}")
                ret_ann = f" -> {ast.unparse(node.returns)}" if getattr(node, "returns", None) and hasattr(ast, "unparse") else ""
                sig_repr = f"def {node.name}({', '.join(sig_lines)}){ret_ann}:"

                # Docstring
                doc = ast.get_docstring(node) or ""

                # Body text (approx from source)
                body_lines = dedented.splitlines()[node.lineno-1 : getattr(node, "end_lineno", len(dedented.splitlines()))]
                body_text = "\n".join(body_lines)

                is_test = is_test_file or node.name.startswith("test_") or node.name.endswith("_test")

                frag = CompleteSymbolFragment(
                    repo=self.clf.repo,
                    base_commit=self.clf.base_commit,
                    filepath=path,
                    name=node.name,
                    parent_class=parent_cls,
                    qualified_name=qual_name,
                    signature=sig_repr,
                    params=params,
                    docstring=doc,
                    body_text=body_text,
                    start_line=start_line + (node.lineno - 1),
                    end_line=start_line + (getattr(node, "end_lineno", node.lineno) - 1),
                    content_hash=content_hash,
                    is_test=is_test,
                )
                self.clf.complete_fragments.append(frag)

        FunctionExtractor(self).visit(tree)

        if not found_function:
            self.quarantined_invalid_count += 1


class MultiFieldFragmentBM25:
    """
    Inverted index over complete symbol fragments with 6 distinct fields:
    - name (w = 2.5)
    - qual (w = 2.0)
    - sig (w = 1.5)
    - params (w = 1.5)
    - doc (w = 1.8)
    - body (w = 1.0)
    """

    FIELDS = ["name", "qual", "sig", "params", "doc", "body"]
    DEFAULT_WEIGHTS = {
        "name": 2.5,
        "qual": 2.0,
        "sig": 1.5,
        "params": 1.5,
        "doc": 1.8,
        "body": 1.0,
    }

    def __init__(self, fragments: List[CompleteSymbolFragment], weights: Optional[Dict[str, float]] = None):
        self.fragments = fragments
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.N = len(fragments)
        self.k1 = 1.2
        self.b = 0.75

        # Field index storage: field -> token -> {frag_idx: tf}
        self.postings: Dict[str, Dict[str, Dict[int, int]]] = {fld: defaultdict(dict) for fld in self.FIELDS}
        self.doc_lengths: Dict[str, List[int]] = {fld: [0] * self.N for fld in self.FIELDS}
        self.avg_lengths: Dict[str, float] = {fld: 1.0 for fld in self.FIELDS}
        self.idf: Dict[str, Dict[str, float]] = {fld: {} for fld in self.FIELDS}

        # Symbol specificity: counts how many fragments share the function name
        self.symbol_corpus_counts: Dict[str, int] = Counter([f.name for f in fragments])

        if self.N > 0:
            self._build_index()

    def _build_index(self):
        for i, frag in enumerate(self.fragments):
            tokens_name = tokenize_code(frag.name)
            tokens_qual = tokenize_code(frag.qualified_name)
            tokens_sig = tokenize_code(frag.signature)
            tokens_params = tokenize_code(" ".join(frag.params))
            tokens_doc = tokenize_code(frag.docstring)
            tokens_body = tokenize_code(frag.body_text[:1000])  # bound body tokens to 1000 for efficiency

            field_tokens = {
                "name": tokens_name,
                "qual": tokens_qual,
                "sig": tokens_sig,
                "params": tokens_params,
                "doc": tokens_doc,
                "body": tokens_body,
            }

            for fld, tokens in field_tokens.items():
                self.doc_lengths[fld][i] = len(tokens)
                for t, count in Counter(tokens).items():
                    self.postings[fld][t][i] = count

        for fld in self.FIELDS:
            total_len = sum(self.doc_lengths[fld])
            self.avg_lengths[fld] = max(1.0, float(total_len) / float(self.N))

            # Compute Robertson-Sparck Jones IDF
            for t, posting in self.postings[fld].items():
                df = len(posting)
                # BM25 standard smoothed IDF: ln(1 + (N - df + 0.5) / (df + 0.5))
                self.idf[fld][t] = math.log(1.0 + (self.N - df + 0.5) / (df + 0.5))

    def score_query_per_field(self, query: str) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """
        Returns:
          total_scores: (N,) array of weighted multi-field BM25 scores
          per_field_scores: dict mapping field_name -> (N,) array of raw BM25 scores
        """
        import numpy as np

        if self.N == 0:
            return np.zeros(0, dtype=np.float32), {fld: np.zeros(0, dtype=np.float32) for fld in self.FIELDS}

        q_tokens = tokenize_code(query)
        if not q_tokens:
            return np.zeros(self.N, dtype=np.float32), {fld: np.zeros(self.N, dtype=np.float32) for fld in self.FIELDS}

        per_field = {fld: np.zeros(self.N, dtype=np.float32) for fld in self.FIELDS}

        for fld in self.FIELDS:
            w_fld = self.weights.get(fld, 1.0)
            avgdl = self.avg_lengths[fld]
            fld_postings = self.postings[fld]
            fld_idf = self.idf[fld]
            fld_lens = self.doc_lengths[fld]

            for t in q_tokens:
                if t in fld_postings:
                    idf_t = fld_idf[t]
                    for idx, tf in fld_postings[t].items():
                        L = fld_lens[idx]
                        denom = tf + self.k1 * (1.0 - self.b + self.b * (L / avgdl))
                        per_field[fld][idx] += float(idf_t * (tf * (self.k1 + 1.0)) / denom)

        total_scores = np.zeros(self.N, dtype=np.float32)
        for fld in self.FIELDS:
            total_scores += self.weights.get(fld, 1.0) * per_field[fld]

        return total_scores, per_field

