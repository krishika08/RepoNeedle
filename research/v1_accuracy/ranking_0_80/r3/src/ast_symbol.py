"""
AST Symbol Intelligence Engine for RepoNeedle Phase R3.
Provides:
1. IdentifierTokenizer: Polyglot CamelCase and snake_case normalization.
2. ASTIntentClassifier: Categorizes query intent into:
   - test_seeking
   - implementation_seeking (e.g. traceback/error logs)
   - definition_seeking
   - reference_seeking
   - general_search
3. ASTSymbolMatcher: Intent-conditioned definition and reference matching.
"""
import re
from typing import Dict, List, Optional, Set, Tuple

CAMEL_CASE_REGEX = re.compile(r"([a-z0-9])([A-Z])")
SNAKE_CASE_REGEX = re.compile(r"[_\-/\\\s]+")
BACKTICK_REGEX = re.compile(r"`([^`]+)`")
QUALIFIED_REGEX = re.compile(r"\b[A-Za-z0-9_]+(?:::[A-Za-z0-9_]+|\.[A-Za-z0-9_]+)+\b")

DEF_PATTERNS = [
    re.compile(r"\b(?:where\s+is|defined\s+in|definition\s+of|implementing|declaration\s+of)\b", re.I),
    re.compile(r"\b(?:class|def|fn|function|struct|trait|interface|type|enum)\s+([A-Za-z0-9_]+)", re.I),
    re.compile(r"\b(?:signature|constructor|method)\s+([A-Za-z0-9_]+)", re.I),
]

REF_PATTERNS = [
    re.compile(r"\b(?:call|caller|callers|call\s+site|usages|references|invocations|invoked\s+by|imported\s+by)\b", re.I),
    re.compile(r"\b(?:anchor_diff|ripple|downstream|consumer)\b", re.I),
]

TRACE_PATTERNS = [
    re.compile(r"\b(?:traceback|stack\s+trace|failure_excerpt|build\s+failed|panic:|exception:)\b", re.I),
    re.compile(r"\bFAIL\b"),
    re.compile(r'File\s+["\'][^"\']+["\'],\s+line\s+\d+'),
]

STOPWORDS = {
    "and", "for", "with", "the", "this", "that", "from", "import", "true", "false",
    "none", "null", "file", "line", "return", "self", "args", "kwargs", "pass"
}


class IdentifierTokenizer:
    """Polyglot identifier tokenizer supporting CamelCase, snake_case, and qualified identifiers."""

    @staticmethod
    def split_identifier(name: str) -> List[str]:
        s1 = CAMEL_CASE_REGEX.sub(r"\1 \2", name)
        parts = SNAKE_CASE_REGEX.split(s1)
        return [p.strip().lower() for p in parts if len(p.strip()) > 1]

    @classmethod
    def extract_symbols(cls, text: str) -> Dict[str, any]:
        backticked = [b.strip() for b in BACKTICK_REGEX.findall(text) if b.strip()]
        qualified = QUALIFIED_REGEX.findall(text)
        raw_words = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", text)

        subwords: Set[str] = set()
        for w in raw_words + qualified + backticked:
            for sw in cls.split_identifier(w):
                if sw not in STOPWORDS and len(sw) > 2:
                    subwords.add(sw)

        return {
            "backticked": backticked,
            "qualified": qualified,
            "subwords": list(subwords),
            "identifiers": [w for w in raw_words if w.lower() not in STOPWORDS][:20],
        }


class ASTIntentClassifier:
    """Classifies query into intent categories to guide downstream ranking features."""

    @staticmethod
    def classify(query_text: str, test_prob: float = 0.0) -> str:
        q_lower = query_text.lower()

        # 1. Test seeking (prioritized if test intent probability >= 0.5)
        if test_prob >= 0.5:
            return "test_seeking"

        # 2. Implementation seeking (crash, stacktrace, build failure)
        if any(p.search(query_text) for p in TRACE_PATTERNS) or ("command" in query_text and "fail" in q_lower):
            return "implementation_seeking"

        # 3. Reference seeking
        if any(p.search(query_text) for p in REF_PATTERNS) or "anchor_diff" in query_text:
            return "reference_seeking"

        # 4. Definition seeking
        if any(p.search(query_text) for p in DEF_PATTERNS):
            return "definition_seeking"

        return "general_search"


class ASTSymbolMatcher:
    """
    Computes intent-conditioned AST symbol matching and asymmetric definition boosts.
    """

    def __init__(
        self,
        def_boost: float = 1.0,
        impl_boost: float = 0.5,
        trace_test_penalty: float = 0.05,
    ):
        self.def_boost = def_boost
        self.impl_boost = impl_boost
        self.trace_test_penalty = trace_test_penalty

    def score_candidate(
        self,
        candidate_path: str,
        exact_symbol_score: float,
        is_test_path: bool,
        intent: str,
    ) -> float:
        """
        Returns a multiplicative boost factor for the candidate.
        Neutral = 1.0. Demotion < 1.0. Boost > 1.0.
        """
        multiplier = 1.0

        # Scenario 1: Implementation seeking (Traceback / Error log)
        if intent == "implementation_seeking":
            if is_test_path:
                # In trace2code, 100% of gold files are implementation files. Demote test files.
                multiplier *= self.trace_test_penalty
            elif exact_symbol_score > 0.0:
                # Boost implementation files defining or matching the failing symbol
                import math
                multiplier *= (1.0 + self.impl_boost * math.log1p(exact_symbol_score))

        # Scenario 2: Definition seeking
        elif intent == "definition_seeking":
            if not is_test_path and exact_symbol_score > 0.0:
                import math
                multiplier *= (1.0 + self.def_boost * math.log1p(exact_symbol_score))

        # Scenario 3: Test seeking (Handled by TIP in ranker, avoid boosting code definitions)
        elif intent == "test_seeking":
            pass

        # Scenario 4: Reference seeking or General search
        else:
            if exact_symbol_score > 0.0 and not is_test_path:
                import math
                # Mild symbol definition reinforcement
                multiplier *= (1.0 + 0.1 * math.log1p(exact_symbol_score))

        return multiplier
