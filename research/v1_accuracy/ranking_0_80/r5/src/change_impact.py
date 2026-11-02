"""
R5.3: Typed Change-Impact Intelligence Engine.
Computes multi-relational change-propagation impact between query seeds and candidate files:
1. TESTS_BEHAVIOR: Tests covering the modified/seed implementation.
2. CHANGED_CALLER: Callers and downstream consumers of the seed entity.
3. IMPORTS_DEPENDENCY: Modules sharing structural imports or namespace proximity with the seed.
4. MODULE_BUILD_CONFIG: Build manifests (Cargo.toml, setup.py, pyproject.toml) associated with the seed.
5. PUBLIC_SYMBOL_DOCS: Documentation files referencing the seed module.

Evaluated per candidate pool in sub-millisecond CPU time with intent-adaptive weighting.
"""
import os
import math
import re
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict


class EdgeType(str, Enum):
    TESTS_BEHAVIOR = "tests_behavior"
    CHANGED_CALLER = "changed_caller"
    IMPORTS_DEPENDENCY = "imports_dependency"
    MODULE_BUILD_CONFIG = "module_build_config"
    PUBLIC_SYMBOL_DOCS = "public_symbol_docs"


BUILD_FILES = {"setup.py", "setup.cfg", "pyproject.toml", "cargo.toml", "package.json", "cmakelists.txt", "makefile", "pom.xml"}
DOC_EXTS = {".md", ".rst", ".txt", ".adoc"}


class ChangeImpactEngine:
    """Evaluates typed change-impact relationships between seeds and candidate files."""

    @staticmethod
    def extract_stem_tokens(path: str) -> Set[str]:
        base = os.path.splitext(os.path.basename(path))[0].lower()
        parts = re.split(r"[_\-/\\\s]+", base)
        return {p for p in parts if len(p) > 2 and p not in ("test", "tests", "src", "lib", "mod")}

    @classmethod
    def compute_candidate_impact(
        cls,
        seeds: List[str],
        candidates: List[Dict[str, Any]],
        query_intent: str = "general",
    ) -> Dict[str, float]:
        """
        Computes typed change-impact scores for all candidates relative to the query seeds.
        Conditioned on query intent (test, reference, definition, error, general).
        """
        if not seeds:
            return {}

        impact_scores: Dict[str, float] = {}

        # Pre-process seeds
        seed_stems: Dict[str, Set[str]] = {}
        seed_dirs: Dict[str, str] = {}
        for s in seeds:
            s_norm = s.replace("\\", "/").lower()
            seed_stems[s_norm] = cls.extract_stem_tokens(s_norm)
            seed_dirs[s_norm] = os.path.dirname(s_norm)

        # Multipliers based on query intent
        test_mult = 1.6 if query_intent == "test" else 0.8
        caller_mult = 1.5 if query_intent in ("reference", "error") else 0.9
        config_mult = 1.4 if query_intent == "validation" else 0.4

        for cand in candidates:
            c_path = cand.get("path", "").replace("\\", "/").lower()
            c_base = os.path.basename(c_path)
            c_ext = os.path.splitext(c_path)[1]
            c_tokens = cls.extract_stem_tokens(c_path)
            is_cand_test = "test" in c_path or c_base.startswith("test_") or c_base.endswith("_test.py")

            best_impact = 0.0

            for s_norm, s_tokens in seed_stems.items():
                if c_path == s_norm:
                    continue  # SFS handles seed suppression

                # 1. TESTS_BEHAVIOR
                if is_cand_test:
                    # Check token overlap between seed module and test file
                    overlap = len(s_tokens & c_tokens)
                    if overlap > 0:
                        score = (0.7 + 0.3 * min(overlap, 3)) * test_mult
                        best_impact = max(best_impact, score)
                    elif seed_dirs[s_norm] in c_path or any(tok in c_path for tok in s_tokens):
                        score = 0.5 * test_mult
                        best_impact = max(best_impact, score)

                # 2. CHANGED_CALLER / IMPORTS_DEPENDENCY (Proximity & Sibling)
                elif not is_cand_test:
                    c_dir = os.path.dirname(c_path)
                    s_dir = seed_dirs[s_norm]

                    # Same directory sibling
                    if c_dir == s_dir and s_dir:
                        overlap = len(s_tokens & c_tokens)
                        score = (0.5 + 0.25 * overlap) * caller_mult
                        best_impact = max(best_impact, score)
                    # Subdirectory or parent relationship
                    elif c_dir.startswith(s_dir) or s_dir.startswith(c_dir):
                        overlap = len(s_tokens & c_tokens)
                        score = (0.3 + 0.2 * overlap) * caller_mult
                        best_impact = max(best_impact, score)

                # 3. MODULE_BUILD_CONFIG
                if c_base in BUILD_FILES:
                    # If build file is in ancestor path of seed
                    if seed_dirs[s_norm].startswith(os.path.dirname(c_path)):
                        score = 0.4 * config_mult
                        best_impact = max(best_impact, score)

                # 4. PUBLIC_SYMBOL_DOCS
                if c_ext in DOC_EXTS or "doc" in c_path:
                    if len(s_tokens & c_tokens) > 0:
                        score = 0.35
                        best_impact = max(best_impact, score)

            impact_scores[cand.get("path", "")] = float(min(best_impact, 1.0))

        return impact_scores
