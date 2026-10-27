"""
Token-budget-aware context selection and knapsack packing engine.
Optimizes relevant context coverage under hard token constraints.
"""

import ast
import re
from typing import List, Tuple, Dict, Optional
import numpy as np

from reponeedle.models import FileDoc, ScoredFile, ContextTier, BudgetConfig
from reponeedle.core.tokenizer import estimate_tokens


class BudgetOptimizer:
    """
    Optimizes context selection to maximize relevant context coverage within a strict token budget.
    Supports tiered multi-representation (Full File, Structural Skeleton, Focused Snippet).
    """

    def __init__(self, config: Optional[BudgetConfig] = None):
        self.config = config or BudgetConfig()

    def generate_skeleton(self, content: str, filepath: str, query_terms: List[str] = None) -> Tuple[str, int]:
        """
        Extracts structural skeleton (classes, functions, method signatures, docstrings,
        and query-matching lines) to retain architectural context at 10-15% of the token cost.
        """
        lines = content.splitlines()
        if len(lines) <= 40:
            tokens = estimate_tokens(content)
            return content, tokens

        skeleton_lines: List[str] = []
        in_docstring = False

        query_set = set(t.lower() for t in (query_terms or []))

        try:
            tree = ast.parse(content, filename=filepath)
            important_linenos = set()

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    important_linenos.add(node.lineno)
                    # Include docstring if present
                    doc = ast.get_docstring(node)
                    if doc and hasattr(node, "body") and node.body and isinstance(node.body[0], ast.Expr):
                        important_linenos.add(node.body[0].lineno)
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    important_linenos.add(node.lineno)

            # Also include lines with strong query matches
            if query_set:
                for idx, line in enumerate(lines, start=1):
                    line_lower = line.lower()
                    if any(q in line_lower for q in query_set if len(q) > 2):
                        # Add match and 1 line surrounding context
                        important_linenos.add(max(1, idx - 1))
                        important_linenos.add(idx)
                        important_linenos.add(min(len(lines), idx + 1))

            for idx, line in enumerate(lines, start=1):
                if idx in important_linenos:
                    skeleton_lines.append(line)
                elif line.strip().startswith(("class ", "def ", "async def ", "@", "import ", "from ")):
                    skeleton_lines.append(line)
                elif skeleton_lines and skeleton_lines[-1] != "    # ... [elided implementation]":
                    skeleton_lines.append("    # ... [elided implementation]")

        except Exception:
            # Fallback regex-based skeleton
            for line in lines:
                stripped = line.strip()
                if stripped.startswith((
                    "class ", "def ", "async def ", "@", "import ", "from ",
                    "public ", "private ", "protected ", "export ", "interface ",
                    "type ", "func ", "package ", "pub ", "fn ", "impl ", "struct ", "use "
                )):
                    skeleton_lines.append(line)
                elif query_set and any(q in stripped.lower() for q in query_set if len(q) > 2):
                    skeleton_lines.append(line)
                elif skeleton_lines and skeleton_lines[-1] != "    # ... [elided implementation]":
                    skeleton_lines.append("    # ... [elided implementation]")

        rendered = "\n".join(skeleton_lines)
        tokens = estimate_tokens(rendered)
        # Cap skeleton tokens if needed
        if tokens > self.config.skeleton_token_cap and len(rendered) > 1000:
            rendered = rendered[: int(self.config.skeleton_token_cap * 3.5)] + "\n# ... [truncated skeleton]"
            tokens = estimate_tokens(rendered)

        return rendered, tokens

    def pack_context(
        self,
        candidate_files: List[Tuple[FileDoc, float, Dict[str, float]]],
        budget_tokens: int,
        query_terms: List[str] = None,
    ) -> List[ScoredFile]:
        """
        Packs files into the token budget using marginal utility density knapsack selection.
        Each candidate is evaluated for full inclusion vs skeleton inclusion.
        """
        if not candidate_files or budget_tokens <= 0:
            return []

        # Sort candidate files by base score descending
        sorted_candidates = sorted(candidate_files, key=lambda x: x[1], reverse=True)

        selected: List[ScoredFile] = []
        tokens_used = 0

        for doc, score, component_scores in sorted_candidates:
            if score <= 0.0:
                continue

            doc_tokens = doc.token_count if doc.token_count > 0 else estimate_tokens(doc.content)
            tokens_remaining = budget_tokens - tokens_used

            if tokens_remaining <= 50:
                break

            # Decision logic for Tier:
            # 1. If full file fits comfortably (e.g. <= 40% of total budget or fits in remaining tokens and score is top tier)
            if doc_tokens <= tokens_remaining and (doc_tokens <= budget_tokens * 0.45 or len(selected) == 0):
                selected.append(
                    ScoredFile(
                        path=doc.path,
                        score=float(score),
                        lexical_score=component_scores.get("lexical", 0.0),
                        semantic_score=component_scores.get("semantic", 0.0),
                        structural_score=component_scores.get("structural", 0.0),
                        workflow_boost=component_scores.get("workflow_boost", 0.0),
                        token_count=doc_tokens,
                        tier=ContextTier.FULL,
                        rendered_content=doc.content,
                        explanation=f"Full file included (tokens: {doc_tokens}, score: {score:.3f}).",
                    )
                )
                tokens_used += doc_tokens

            # 2. If full file is too large but skeletons are permitted
            elif self.config.allow_skeletons:
                skeleton_content, skeleton_tokens = self.generate_skeleton(
                    doc.content, doc.path, query_terms
                )
                if skeleton_tokens <= tokens_remaining:
                    selected.append(
                        ScoredFile(
                            path=doc.path,
                            score=float(score * 0.85),  # slight discount for skeleton representation
                            lexical_score=component_scores.get("lexical", 0.0),
                            semantic_score=component_scores.get("semantic", 0.0),
                            structural_score=component_scores.get("structural", 0.0),
                            workflow_boost=component_scores.get("workflow_boost", 0.0),
                            token_count=skeleton_tokens,
                            tier=ContextTier.SKELETON,
                            rendered_content=skeleton_content,
                            explanation=f"Structural skeleton included ({skeleton_tokens} tokens vs full {doc_tokens} tokens, saving {doc_tokens - skeleton_tokens} tokens).",
                        )
                    )
                    tokens_used += skeleton_tokens

        return selected

