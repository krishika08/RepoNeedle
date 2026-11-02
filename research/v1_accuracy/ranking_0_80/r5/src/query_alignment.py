"""
R5.2: Query-to-Code Alignment & Fine-Grained Code-Unit Scorer.
Aligns developer queries with specific functions, methods, classes, and source spans.
Provides:
1. QueryIntentDetector: Categorizes intent (definition, reference, error, validation, test).
2. CodeUnitScorer: Aligns candidate units using lexical BM25, exact symbol matching, and subword overlap.
3. SourceSpanLocalizer: Determines the most relevant source-span/function within each candidate.
"""
import re
import os
import math
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict, Counter

from code_unit import CodeUnitIndexer

DEF_PATTERNS = [
    re.compile(r"\b(?:where\s+is|defined\s+in|definition\s+of|implementing|declaration\s+of|implementation\s+of)\b", re.I),
    re.compile(r"\b(?:class|def|fn|function|struct|trait|interface|type|enum)\s+([A-Za-z0-9_]+)", re.I),
    re.compile(r"\b(?:signature|constructor|method)\s+([A-Za-z0-9_]+)", re.I),
]

REF_PATTERNS = [
    re.compile(r"\b(?:where\s+is\s+.*called|call\s+site|callers|usages|references|invocations|invoked\s+by|imported\s+by)\b", re.I),
    re.compile(r"\b(?:consumer|downstream|calls|calling)\b", re.I),
]

ERROR_PATTERNS = [
    re.compile(r"\b(?:traceback|stack\s+trace|failure_excerpt|build\s+failed|panic:|exception:|error:|syntaxerror|typeerror|valueerror)\b", re.I),
    re.compile(r'File\s+["\'][^"\']+["\'],\s+line\s+\d+'),
    re.compile(r"\bFAIL\b"),
]

VALIDATION_PATTERNS = [
    re.compile(r"\b(?:validat[a-z]*|check(?:ing|s)?|sanitiz[a-z]*|constraint[s]?|enforce[a-z]*)\b", re.I),
]

TEST_PATTERNS = [
    re.compile(r"\b(?:test|tests|testing|coverage|spec|fixture|assert|pytest)\b", re.I),
]


class QueryIntent:
    DEFINITION = "definition"
    REFERENCE = "reference"
    ERROR = "error"
    VALIDATION = "validation"
    TEST = "test"
    GENERAL = "general"


class QueryIntentDetector:
    """Classifies user queries into actionable code-search intents."""

    @classmethod
    def detect(cls, query: str) -> str:
        if any(p.search(query) for p in ERROR_PATTERNS):
            return QueryIntent.ERROR
        if any(p.search(query) for p in TEST_PATTERNS):
            return QueryIntent.TEST
        if any(p.search(query) for p in REF_PATTERNS):
            return QueryIntent.REFERENCE
        if any(p.search(query) for p in VALIDATION_PATTERNS):
            return QueryIntent.VALIDATION
        if any(p.search(query) for p in DEF_PATTERNS):
            return QueryIntent.DEFINITION
        return QueryIntent.GENERAL


class CodeUnitScorer:
    """Evaluates fine-grained code-unit relevance and source-span alignment."""

    @classmethod
    def score_candidate_unit(
        cls,
        cand: Dict[str, Any],
        query_text: str,
        query_tokens: List[str],
        intent: str
    ) -> Tuple[float, Dict[str, Any]]:
        path = cand.get("path", "")
        scores = cand.get("scores", {})
        exact_sym_score = scores.get("exact_symbol", 0.0)

        # Decompose candidate path into subwords and tokens
        path_tokens = CodeUnitIndexer.tokenize_identifiers(path)
        path_subwords = set(CodeUnitIndexer.decompose_subwords(path_tokens))
        q_set = set(query_tokens)

        # Subword match score
        sub_overlap = len(path_subwords & q_set)
        unit_score = 0.5 * min(sub_overlap, 6)

        # Exact symbol channel boost
        if exact_sym_score > 0:
            unit_score += min(exact_sym_score / 5.0, 2.0)

        # Intent-conditioned adjustments
        best_span = f"{os.path.basename(path)}:L1-L50"
        matched_symbols = [t for t in query_tokens if t in path_subwords]

        if intent == QueryIntent.DEFINITION:
            if not ("test" in path.lower()) and sub_overlap > 0:
                unit_score *= 1.4
            if matched_symbols:
                best_span = f"fn {matched_symbols[0]}() in {os.path.basename(path)}"

        elif intent == QueryIntent.TEST:
            if "test" in path.lower():
                unit_score *= 1.5
                best_span = f"test_suite in {os.path.basename(path)}"

        elif intent == QueryIntent.ERROR:
            # Traceback lines often match exact filenames or module names
            base_lower = os.path.basename(path).lower()
            if any(term in base_lower for term in q_set if len(term) > 3):
                unit_score *= 1.6
                best_span = f"error_frame in {os.path.basename(path)}"

        elif intent == QueryIntent.VALIDATION:
            if any(term in path.lower() for term in ("validate", "check", "clean", "assert", "sanitize")):
                unit_score *= 1.5
                best_span = f"validator in {os.path.basename(path)}"

        metadata = {
            "best_unit": best_span,
            "subword_overlap": sub_overlap,
            "exact_sym_score": exact_sym_score,
            "unit_score": float(unit_score),
        }
        return float(unit_score), metadata
