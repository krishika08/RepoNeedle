"""
CUD-Pack: Capacity-Sensitive Utility-Density Context Packing Engine.
Engineered for Zero-Overflow, Multi-Tier Context Delivery in RepoNeedle V1.0.0.
"""

import ast
import re
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict


class ContextTier(str, Enum):
    FULL = "full"
    FOCUS_SPAN = "focus_span"
    SKELETON = "skeleton"
    INTERFACE = "interface"
    OMITTED = "omitted"


# Official ARB regex code tokenizer
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+|[^A-Za-z0-9_\s]", re.UNICODE)

COMMON_STOPWORDS = {
    "the", "a", "an", "in", "on", "of", "to", "for", "with", "at", "by", "from",
    "and", "or", "is", "it", "this", "that", "be", "as", "if", "else", "then",
    "return", "self", "none", "true", "false", "func", "function", "test", "testing",
    "error", "err", "context", "ctx", "code", "file", "data", "value", "type", "struct",
    "package", "import", "class", "def", "async", "public", "private", "string", "int",
    "pr_title", "pr_body", "changed_file", "summary", "fixes", "issue", "review_comment",
    "given_file", "diff_hunk_context",
}


def filter_query_terms(query_text: str) -> Set[str]:
    words = re.findall(r"[A-Za-z0-9_]+", query_text.lower())
    return {w for w in words if len(w) >= 3 and w not in COMMON_STOPWORDS}


class ExactTokenizer:
    """Exact code tokenizer with memoization and packaging accounting."""

    def __init__(self):
        self._cache: Dict[int, int] = {}

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        h = hash(text)
        if h in self._cache:
            return self._cache[h]
        c = len(TOKEN_RE.findall(text))
        if len(self._cache) < 250000:
            self._cache[h] = c
        return c

    def package_file(self, path: str, content: str) -> Tuple[str, int]:
        ext = path.split(".")[-1] if "." in path else "text"
        wrapped = f"# File: {path}\n```{ext}\n{content}\n```\n\n"
        tokens = self.count_tokens(wrapped)
        return wrapped, tokens

    def package_overhead(self, path: str) -> int:
        ext = path.split(".")[-1] if "." in path else "text"
        header = f"# File: {path}\n```{ext}\n\n```\n\n"
        return self.count_tokens(header)


class CodeSpanExtractor:
    """High-performance multi-tier representation extractor with memoization."""

    def __init__(self, tokenizer: ExactTokenizer):
        self.tok = tokenizer
        self._span_cache: Dict[Tuple[str, int], Tuple[str, int]] = {}
        self._skel_cache: Dict[Tuple[str, int], Tuple[str, int]] = {}

    def extract_focus_span(self, content: str, path: str, query_terms: Set[str], cap_lines: int = 65) -> Tuple[str, int]:
        cache_key = (path, hash(content[:200]))
        if cache_key in self._span_cache:
            return self._span_cache[cache_key]

        lines = content.splitlines()
        if len(lines) <= 45:
            res = (content, self.tok.count_tokens(content))
            self._span_cache[cache_key] = res
            return res

        # 1. Capture imports & package declaration
        import_lines = []
        for idx, l in enumerate(lines[:30], 1):
            s = l.strip()
            if s.startswith(("import ", "from ", "package ", "use ", "const ", "var ")):
                import_lines.append(l)

        # 2. Python AST extraction
        if path.endswith(".py"):
            try:
                tree = ast.parse(content)
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
                    res = (rendered, self.tok.count_tokens(rendered))
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
            res = self.extract_skeleton(content, path)
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
        res = (rendered, self.tok.count_tokens(rendered))
        self._span_cache[cache_key] = res
        return res

    def extract_skeleton(self, content: str, path: str) -> Tuple[str, int]:
        cache_key = (path, hash(content[:200]))
        if cache_key in self._skel_cache:
            return self._skel_cache[cache_key]

        lines = content.splitlines()
        outline = [l for l in lines if l.strip().startswith((
            "class ", "def ", "async def ", "func ", "pub fn ", "fn ", "impl ", "struct ",
            "interface ", "type ", "import ", "from ", "package ", "export ", "public ", "private "
        ))]
        rendered = "\n".join(outline[:60])
        res = (rendered, self.tok.count_tokens(rendered))
        self._skel_cache[cache_key] = res
        return res


class PackedItem:
    def __init__(
        self,
        path: str,
        tier: ContextTier,
        rendered_content: str,
        content_tokens: int,
        packaged_tokens: int,
        score: float,
        rank: int,
        reason: str,
    ):
        self.path = path
        self.tier = tier
        self.rendered_content = rendered_content
        self.content_tokens = content_tokens
        self.packaged_tokens = packaged_tokens
        self.score = score
        self.rank = rank
        self.reason = reason


class CUDPackOptimizer:
    """
    Capacity-Sensitive Utility-Density Context Packing Engine.
    Strict Invariant: actual_packaged_tokens <= budget_tokens (0 Downstream Overflows).
    """

    def __init__(self, tokenizer: Optional[ExactTokenizer] = None):
        self.tok = tokenizer or ExactTokenizer()
        self.extractor = CodeSpanExtractor(self.tok)

    def pack_context(
        self,
        candidate_pool: List[Dict[str, Any]],
        budget_tokens: int,
        query_text: str = "",
        query_terms: Optional[List[str]] = None,
        track: str = "",
        mode: str = "complete",  # "compact" (4k) or "complete" (8k, 16k, 32k)
    ) -> List[PackedItem]:
        if not candidate_pool or budget_tokens <= 0:
            return []

        q_terms_set = filter_query_terms(query_text) if query_text else set(t.lower() for t in (query_terms or []))

        def get_dir(p: str) -> str:
            parts = p.split("/")
            return "/".join(parts[:-1]) if len(parts) > 1 else ""

        selected: List[PackedItem] = []
        selected_paths: Set[str] = set()
        selected_dirs: Dict[str, int] = defaultdict(int)
        tokens_used = 0

        # Scan candidates in rank order with capacity-sensitive multi-tier sizing
        for rank, c in enumerate(candidate_pool[:85], 1):
            p = c["path"]
            if p in selected_paths:
                continue

            content = c.get("content", "")
            if not content:
                continue

            rem_budget = budget_tokens - tokens_used
            if rem_budget <= 35:
                break

            # Representation sizes
            full_w, full_tok = self.tok.package_file(p, content)
            span_c, _ = self.extractor.extract_focus_span(content, p, q_terms_set)
            span_w, span_tok = self.tok.package_file(p, span_c)
            skel_c, _ = self.extractor.extract_skeleton(content, p)
            skel_w, skel_tok = self.tok.package_file(p, skel_c)

            chosen = None

            if mode == "complete":
                # COMPLETE CONTEXT MODE (>= 8k): Prioritize complete source files
                if rank == 1:
                    if full_tok <= rem_budget and full_tok <= budget_tokens * 0.70:
                        chosen = (ContextTier.FULL, full_tok, content, "Rank-1 full file preservation")
                    elif span_tok <= rem_budget:
                        chosen = (ContextTier.FOCUS_SPAN, span_tok, span_c, "Rank-1 focus span (oversized full)")
                elif rank <= 12:
                    if full_tok <= rem_budget and full_tok <= budget_tokens * 0.55:
                        chosen = (ContextTier.FULL, full_tok, content, "Complete file preservation")
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
                # COMPACT MODE (4k): Maximize span coverage and prevent single distractor displacement
                if rank == 1 and full_tok <= 1200 and full_tok <= rem_budget * 0.45:
                    chosen = (ContextTier.FULL, full_tok, content, "Primary compact full file")
                elif span_tok <= rem_budget:
                    chosen = (ContextTier.FOCUS_SPAN, span_tok, span_c, "High-density implementation span")
                elif skel_tok <= rem_budget:
                    chosen = (ContextTier.SKELETON, skel_tok, skel_c, "Structural outline")

            if chosen:
                tier, pkg_tok, rendered, reason = chosen
                selected.append(PackedItem(
                    path=p,
                    tier=tier,
                    rendered_content=rendered,
                    content_tokens=self.tok.count_tokens(rendered),
                    packaged_tokens=pkg_tok,
                    score=c.get("m1_score", 0.0),
                    rank=rank,
                    reason=reason,
                ))
                selected_paths.add(p)
                selected_dirs[get_dir(p)] += 1
                tokens_used += pkg_tok

        # Residual Backfill
        rem_budget = budget_tokens - tokens_used
        if rem_budget >= 45:
            for rank, c in enumerate(candidate_pool[len(selected):85], len(selected) + 1):
                p = c["path"]
                if p in selected_paths:
                    continue
                content = c.get("content", "")
                if not content:
                    continue
                skel_c, _ = self.extractor.extract_skeleton(content, p)
                _, skel_tok = self.tok.package_file(p, skel_c)
                if skel_tok <= rem_budget:
                    selected.append(PackedItem(
                        path=p,
                        tier=ContextTier.SKELETON,
                        rendered_content=skel_c,
                        content_tokens=self.tok.count_tokens(skel_c),
                        packaged_tokens=skel_tok,
                        score=c.get("m1_score", 0.0),
                        rank=rank,
                        reason="Residual margin backfill outline",
                    ))
                    selected_paths.add(p)
                    tokens_used += skel_tok
                    rem_budget -= skel_tok
                    if rem_budget < 45:
                        break

        # Verification Invariant:
        assert tokens_used <= budget_tokens, f"CRITICAL: Budget overflow! {tokens_used} > {budget_tokens}"
        return selected
