"""
RepoNeedle CUD-Pack: Capacity-Sensitive Utility-Density Context Packing Engine.
Provides deterministic, zero-downstream-overflow context assembly for AI coding agents.
Supports dual operational modes:
  - COMPACT MODE (Budget <= 4096 tokens, Elasticity α = 0.65)
  - COMPLETE CONTEXT MODE (Budget >= 8192 tokens, Elasticity α = 0.25)
"""

import ast
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from reponeedle.models import BudgetConfig, ContextTier, FileDoc, ScoredFile

# Official Benchmark Code Tokenizer Regex Pattern: regex_code_tokenizer_v1
BENCHMARK_TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+|[^A-Za-z0-9_\s]", re.UNICODE)
TOKEN_RE = BENCHMARK_TOKEN_PATTERN

COMMON_STOPWORDS: Set[str] = {
    "the", "a", "an", "in", "on", "of", "to", "for", "with", "at", "by", "from",
    "and", "or", "is", "it", "this", "that", "be", "as", "if", "else", "then",
    "return", "self", "none", "true", "false", "func", "function", "test", "testing",
    "error", "err", "context", "ctx", "code", "file", "data", "value", "type", "struct",
    "package", "import", "class", "def", "async", "public", "private", "string", "int",
    "pr_title", "pr_body", "changed_file", "summary", "fixes", "issue", "review_comment",
    "given_file", "diff_hunk_context", "implementation", "files", "total", "count",
}


def filter_query_terms(query_text: str) -> Set[str]:
    """Extracts distinctive alphanumeric terms from query text, filtering domain/benchmark stop words."""
    words = re.findall(r"[A-Za-z0-9_]+", query_text.lower())
    return {w for w in words if len(w) >= 3 and w not in COMMON_STOPWORDS}


class ExactTokenizer:
    """
    Exact code tokenizer implementing regex_code_tokenizer_v1 with hash-memoized caching
    and markdown packaging overhead accounting.
    """

    def __init__(self):
        self._cache: Dict[int, int] = {}

    def count_tokens(self, text: str, path: str = "") -> int:
        if not text:
            return 0
        h = hash(text)
        cached = self._cache.get(h)
        if cached is not None:
            return cached
        tokens = len(BENCHMARK_TOKEN_PATTERN.findall(text))
        if len(self._cache) < 250000:
            self._cache[h] = tokens
        return tokens

    def package_file(self, path: str, content: str) -> Tuple[str, int]:
        clean_path = path.replace("\\", "/")
        ext = clean_path.split(".")[-1] if "." in clean_path else "text"
        wrapped = f"# File: {clean_path}\n```{ext}\n{content}\n```\n\n"
        tokens = self.count_tokens(wrapped)
        return wrapped, tokens

    def packaging_overhead(self, path: str, ext: str = "") -> int:
        clean_path = path.replace("\\", "/")
        effective_ext = ext or (clean_path.split(".")[-1] if "." in clean_path else "text")
        sample_fmt = f"# File: {clean_path}\n```{effective_ext}\n\n```\n\n"
        return self.count_tokens(sample_fmt)

    def render_packaged_block(self, path: str, content: str) -> str:
        clean_path = path.replace("\\", "/")
        ext = clean_path.split(".")[-1] if "." in clean_path else "text"
        return f"# File: {clean_path}\n```{ext}\n{content}\n```\n\n"

    def render_prompt(self, selected_files: List[ScoredFile]) -> str:
        blocks = []
        for sf in selected_files:
            clean_path = sf.path.replace("\\", "/")
            ext = clean_path.split(".")[-1] if "." in clean_path else "text"
            rendered = sf.rendered_content if sf.rendered_content is not None else ""
            blocks.append(f"# File: {clean_path}\n```{ext}\n{rendered}\n```\n\n")
        return "".join(blocks)


class CodeSpanExtractor:
    """
    High-performance multi-tier representation extractor with memoization.
    Extracts syntactically bounded focal spans and structural skeletons across polyglot languages.
    """

    def __init__(self, tokenizer: Optional[ExactTokenizer] = None):
        self.tokenizer = tokenizer or ExactTokenizer()
        self._span_cache: Dict[Tuple[str, int], Tuple[str, int]] = {}
        self._skel_cache: Dict[Tuple[str, int], Tuple[str, int]] = {}

    def extract_focus_span(
        self,
        content: str,
        path: str,
        query_terms: Set[str],
        cap_lines: int = 65,
    ) -> Tuple[str, int]:
        if not content or not content.strip():
            return "", 0

        clean_path = path.replace("\\", "/")
        q_key = frozenset(query_terms) if query_terms else frozenset()
        cache_key = (clean_path, hash(content), q_key)
        if cache_key in self._span_cache:
            return self._span_cache[cache_key]

        lines = content.splitlines()
        if len(lines) <= 45:
            res = (content, self.tokenizer.count_tokens(content, clean_path))
            self._span_cache[cache_key] = res
            return res

        # 1. Capture imports & package declaration
        import_lines = []
        for idx, l in enumerate(lines[:30], 1):
            s = l.strip()
            if s.startswith(("import ", "from ", "package ", "use ", "const ", "var ")):
                import_lines.append(l)

        # 2. Python AST extraction
        if clean_path.endswith(".py"):
            try:
                tree = ast.parse(content, filename=clean_path)
                matched_nodes = []
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        name = node.name.lower()
                        if any(t in name for t in query_terms):
                            matched_nodes.append(node)

                if matched_nodes:
                    selected_l = set()
                    for mn in matched_nodes[:5]:
                        end_l = getattr(mn, "end_lineno", mn.lineno + 30)
                        for l in range(max(1, mn.lineno - 1), min(len(lines) + 1, end_l + 2)):
                            selected_l.add(l)
                            if len(selected_l) >= cap_lines:
                                break
                        if len(selected_l) >= cap_lines:
                            break

                    res_lines = list(import_lines) + ["# ... [context gap] ..."]
                    last_l = 0
                    for l_idx in sorted(selected_l):
                        if last_l > 0 and l_idx > last_l + 1:
                            res_lines.append("    # ... [elided implementation] ...")
                        res_lines.append(lines[l_idx - 1])
                        last_l = l_idx

                    rendered = "\n".join(res_lines)
                    res = (rendered, self.tokenizer.count_tokens(rendered, clean_path))
                    self._span_cache[cache_key] = res
                    return res
            except Exception:
                pass

        # 3. Polyglot keyword & identifier scan
        matched_l = []
        for idx, l in enumerate(lines, 1):
            s_lower = l.lower()
            if any(t in s_lower for t in query_terms):
                matched_l.append(idx)

        if not matched_l:
            res = self.extract_skeleton(content, clean_path)
            self._span_cache[cache_key] = res
            return res

        selected_l = set()
        for m in matched_l[:12]:
            for k in range(max(1, m - 2), min(len(lines) + 1, m + 4)):
                selected_l.add(k)
                if len(selected_l) >= cap_lines:
                    break
            if len(selected_l) >= cap_lines:
                break

        res_lines = list(import_lines) + ["// ... [context gap] ..."]
        last_l = 0
        for l_idx in sorted(selected_l):
            if last_l > 0 and l_idx > last_l + 1:
                res_lines.append("    // ... [elided lines] ...")
            res_lines.append(lines[l_idx - 1])
            last_l = l_idx

        rendered = "\n".join(res_lines)
        res = (rendered, self.tokenizer.count_tokens(rendered, clean_path))
        self._span_cache[cache_key] = res
        return res

    def extract_skeleton(
        self,
        content: str,
        path: str,
        query_terms: Optional[Set[str]] = None,
        max_skeleton_tokens: int = 350,
    ) -> Tuple[str, int]:
        if not content or not content.strip():
            return "", 0

        clean_path = path.replace("\\", "/")
        q_key = frozenset(query_terms) if query_terms else frozenset()
        cache_key = (clean_path, hash(content), q_key)
        if cache_key in self._skel_cache:
            return self._skel_cache[cache_key]

        lines = content.splitlines()
        skeleton_lines: List[str] = []
        query_set = query_terms or set()

        if clean_path.endswith(".py"):
            try:
                tree = ast.parse(content, filename=clean_path)
                imp_linenos = set()
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        imp_linenos.add(node.lineno)
                        doc = ast.get_docstring(node)
                        if doc and hasattr(node, "body") and node.body and isinstance(node.body[0], ast.Expr):
                            imp_linenos.add(node.body[0].lineno)
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        imp_linenos.add(node.lineno)

                for idx, line in enumerate(lines, start=1):
                    if idx in imp_linenos or line.strip().startswith(("class ", "def ", "async def ", "@", "import ", "from ")):
                        skeleton_lines.append(line)
                    elif query_set and any(q in line.lower() for q in query_set if len(q) > 2):
                        skeleton_lines.append(line)
                    elif skeleton_lines and skeleton_lines[-1] != "    # ... [elided implementation]":
                        skeleton_lines.append("    # ... [elided implementation]")
            except Exception:
                skeleton_lines = []

        if not skeleton_lines:
            for line in lines:
                s = line.strip()
                if s.startswith((
                    "class ", "def ", "async def ", "@", "import ", "from ",
                    "public ", "private ", "protected ", "export ", "interface ",
                    "type ", "func ", "package ", "pub ", "fn ", "impl ", "struct ", "use "
                )):
                    skeleton_lines.append(line)
                elif query_set and any(q in s.lower() for q in query_set if len(q) > 2):
                    skeleton_lines.append(line)
                elif skeleton_lines and skeleton_lines[-1] != "    # ... [elided implementation]":
                    skeleton_lines.append("    # ... [elided implementation]")

        rendered = "\n".join(skeleton_lines[:60])
        tokens = self.tokenizer.count_tokens(rendered, clean_path)
        effective_cap = min(max_skeleton_tokens, 280)
        if tokens > effective_cap:
            truncated_lines = list(skeleton_lines[:60])
            while len(truncated_lines) > 5 and tokens > effective_cap:
                truncated_lines = truncated_lines[:-5]
                rendered = "\n".join(truncated_lines) + "\n    # ... [truncated skeleton]"
                tokens = self.tokenizer.count_tokens(rendered, clean_path)

        res = (rendered, tokens)
        self._skel_cache[cache_key] = res
        return res


class CUDPackOptimizer:
    """
    Capacity-Sensitive Utility-Density Context Packing Engine.
    Strict Invariant: actual_packaged_tokens <= budget_tokens (0 Downstream Overflows).
    """

    def __init__(
        self,
        config_or_tokenizer: Optional[Union[BudgetConfig, ExactTokenizer]] = None,
        config: Optional[BudgetConfig] = None,
        tokenizer: Optional[ExactTokenizer] = None,
    ):
        if isinstance(config_or_tokenizer, BudgetConfig):
            self.config = config_or_tokenizer
            self.tokenizer = tokenizer or ExactTokenizer()
        elif isinstance(config_or_tokenizer, ExactTokenizer):
            self.tokenizer = config_or_tokenizer
            self.config = config or BudgetConfig()
        else:
            self.config = config or BudgetConfig()
            self.tokenizer = tokenizer or ExactTokenizer()

        self.extractor = CodeSpanExtractor(self.tokenizer)

    def generate_skeleton(
        self,
        content: str,
        filepath: str,
        query_terms: Optional[List[str]] = None,
    ) -> Tuple[str, int]:
        q_set = set(t.lower() for t in (query_terms or []))
        return self.extractor.extract_skeleton(content, filepath, q_set, self.config.skeleton_token_cap)

    def pack_context(
        self,
        candidate_files: Union[
            List[Tuple[FileDoc, float, Dict[str, float]]],
            List[Dict[str, Any]],
        ],
        budget_tokens: int,
        query_text: str = "",
        query_terms: Optional[Union[List[str], Set[str]]] = None,
        task_type: Optional[Any] = None,
        allow_skeletons: Optional[bool] = None,
        mode: Optional[str] = None,
    ) -> List[ScoredFile]:
        """
        Packs candidate files into the token budget using capacity-sensitive utility density.
        Strictly guarantees: sum(f.token_count for f in selected) <= budget_tokens.
        """
        if not candidate_files or budget_tokens <= 0:
            return []

        # 1. Operational Mode Resolution
        effective_mode = mode or self.config.mode
        if effective_mode == "auto":
            effective_mode = "compact" if budget_tokens <= 4096 else "complete"

        allow_skel = self.config.allow_skeletons if allow_skeletons is None else allow_skeletons

        # Normalize query terms
        if isinstance(query_terms, set):
            q_terms = query_terms
        elif isinstance(query_terms, list):
            q_terms = set(t.lower() for t in query_terms if len(t) >= 2 and t.lower() not in COMMON_STOPWORDS)
        elif query_text:
            q_terms = filter_query_terms(query_text)
        else:
            q_terms = set()

        # 2. Ingest Candidates
        cutoff = self.config.candidate_pool_cutoff or 85
        sliced_candidates = candidate_files[:cutoff]

        parsed_candidates = []
        for idx, item in enumerate(sliced_candidates, start=1):
            if isinstance(item, tuple):
                doc, score, c_scores = item
                path = doc.path
                content = doc.content
                base_score = float(score)
                rank = idx
            elif isinstance(item, dict):
                path = item.get("path", "")
                content = item.get("content", "")
                base_score = float(item.get("score", item.get("m1_score", 0.0)))
                rank = int(item.get("rank", idx))
                c_scores = item.get("component_scores", {})
            else:
                continue

            # Drop empty or invalid paths/content
            if not path or not path.strip() or content is None or not content.strip():
                continue

            parsed_candidates.append({
                "path": path,
                "content": content,
                "base_score": base_score,
                "rank": rank,
                "c_scores": c_scores,
            })

        if not parsed_candidates:
            return []

        def get_dir(p: str) -> str:
            parts = p.replace("\\", "/").split("/")
            return "/".join(parts[:-1]) if len(parts) > 1 else ""

        selected: List[ScoredFile] = []
        selected_paths: Set[str] = set()
        selected_dirs: Dict[str, int] = defaultdict(int)
        tokens_used = 0

        # Scan candidates in rank order with capacity-sensitive multi-tier sizing
        for rank, c in enumerate(parsed_candidates, 1):
            p = c["path"]
            if p in selected_paths:
                continue

            content = c["content"]
            rem_budget = budget_tokens - tokens_used
            if rem_budget <= 35:
                break

            # Representation sizes
            full_w, full_tok = self.tokenizer.package_file(p, content)

            chosen = None

            # If skeletons are disallowed (full files only)
            if not allow_skel:
                if full_tok <= rem_budget:
                    chosen = (ContextTier.FULL, full_tok, content, "Full file preservation (skeletons disallowed)")
            else:
                span_c, _ = self.extractor.extract_focus_span(content, p, q_terms)
                span_w, span_tok = self.tokenizer.package_file(p, span_c)
                skel_c, _ = self.extractor.extract_skeleton(content, p, q_terms)
                skel_w, skel_tok = self.tokenizer.package_file(p, skel_c)

                if effective_mode == "complete":
                    # COMPLETE CONTEXT MODE (>= 8k): Prioritize complete source files
                    if rank == 1:
                        if full_tok <= rem_budget and full_tok <= budget_tokens * 0.70:
                            chosen = (ContextTier.FULL, full_tok, content, "Rank-1 full file preservation")
                        elif full_tok > 500 and skel_tok <= rem_budget:
                            chosen = (ContextTier.SKELETON, skel_tok, skel_c, "Structural skeleton (oversized full)")
                        elif span_tok <= rem_budget:
                            chosen = (ContextTier.FOCUS_SPAN, span_tok, span_c, "Rank-1 focus span (oversized full)")
                    elif rank <= 12:
                        if full_tok <= rem_budget and full_tok <= budget_tokens * 0.55:
                            chosen = (ContextTier.FULL, full_tok, content, "Complete file preservation")
                        elif full_tok > 500 and skel_tok <= rem_budget:
                            chosen = (ContextTier.SKELETON, skel_tok, skel_c, "Capacity-adaptive structural outline")
                        elif span_tok <= rem_budget and span_tok < full_tok * 0.75:
                            chosen = (ContextTier.FOCUS_SPAN, span_tok, span_c, "Capacity-adaptive focus span")
                        elif skel_tok <= rem_budget and skel_tok < full_tok * 0.40:
                            chosen = (ContextTier.SKELETON, skel_tok, skel_c, "Capacity-adaptive structural outline")
                    else:
                        if span_tok <= rem_budget and span_tok < full_tok * 0.65:
                            chosen = (ContextTier.FOCUS_SPAN, span_tok, span_c, "Deep candidate focus span")
                        elif full_tok <= rem_budget and full_tok <= 850:
                            chosen = (ContextTier.FULL, full_tok, content, "Compact full file inclusion")
                        elif skel_tok <= rem_budget:
                            chosen = (ContextTier.SKELETON, skel_tok, skel_c, "Deep candidate outline")

                else:
                    # COMPACT MODE (<= 4k): Maximize span coverage and prevent single distractor displacement
                    if rank == 1 and full_tok <= 1200 and full_tok <= rem_budget * 0.45:
                        chosen = (ContextTier.FULL, full_tok, content, "Primary compact full file")
                    elif span_tok <= rem_budget:
                        chosen = (ContextTier.FOCUS_SPAN, span_tok, span_c, "High-density implementation span")
                    elif skel_tok <= rem_budget:
                        chosen = (ContextTier.SKELETON, skel_tok, skel_c, "Structural outline")

            if chosen:
                tier, pkg_tok, rendered, reason = chosen
                overhead = self.tokenizer.packaging_overhead(p)
                selected.append(
                    ScoredFile(
                        path=p,
                        score=c["base_score"],
                        lexical_score=c["c_scores"].get("lexical", 0.0),
                        semantic_score=c["c_scores"].get("semantic", 0.0),
                        structural_score=c["c_scores"].get("structural", 0.0),
                        workflow_boost=c["c_scores"].get("workflow_boost", 0.0),
                        token_count=pkg_tok,
                        tier=tier,
                        rendered_content=rendered,
                        explanation=f"{reason} ({pkg_tok} tokens, overhead: {overhead} tokens)",
                    )
                )
                selected_paths.add(p)
                selected_dirs[get_dir(p)] += 1
                tokens_used += pkg_tok

        # Residual Backfill Optimization
        rem_budget = budget_tokens - tokens_used
        if allow_skel and rem_budget >= 45:
            for c in parsed_candidates[len(selected):]:
                p = c["path"]
                if p in selected_paths:
                    continue
                content = c["content"]
                skel_c, _ = self.extractor.extract_skeleton(content, p, q_terms)
                _, skel_tok = self.tokenizer.package_file(p, skel_c)
                if skel_tok <= rem_budget:
                    overhead = self.tokenizer.packaging_overhead(p)
                    selected.append(
                        ScoredFile(
                            path=p,
                            score=c["base_score"],
                            lexical_score=c["c_scores"].get("lexical", 0.0),
                            semantic_score=c["c_scores"].get("semantic", 0.0),
                            structural_score=c["c_scores"].get("structural", 0.0),
                            workflow_boost=c["c_scores"].get("workflow_boost", 0.0),
                            token_count=skel_tok,
                            tier=ContextTier.SKELETON,
                            rendered_content=skel_c,
                            explanation=f"Residual margin backfill outline ({skel_tok} tokens, overhead: {overhead} tokens)",
                        )
                    )
                    selected_paths.add(p)
                    tokens_used += skel_tok
                    rem_budget -= skel_tok
                    if rem_budget < 45:
                        break

        # Verification Invariant:
        assert tokens_used <= budget_tokens, f"CRITICAL: Budget overflow! {tokens_used} > {budget_tokens}"
        return selected


# Backwards compatibility alias
BudgetOptimizer = CUDPackOptimizer
