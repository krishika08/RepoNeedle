"""
RepoNeedle V1.1: Typed Change-Impact Ranking Engine.
Provides graph-guided change propagation ranking for coding agents.
Integrates confirmed static AST relationships (imports, symbols, calls, build manifests)
and calibrated heuristic associations with Seed File Suppression (SFS) and Test Intent Priors (TIP).
"""

import os
import re
import logging
from enum import Enum
from typing import Dict, List, Set, Tuple, Any, Optional
import numpy as np
from pydantic import BaseModel, Field

from reponeedle.models import FileDoc, Query

logger = logging.getLogger(__name__)

BUILD_FILES = {"setup.py", "setup.cfg", "pyproject.toml", "cargo.toml", "package.json", "go.mod", "pom.xml"}
DOC_EXTS = {".md", ".rst", ".txt", ".adoc"}

TEST_PATTERNS = re.compile(
    r"\b(?:test[a-z]*|spec[a-z]*|assert[a-z]*|verify[a-z]*|check[a-z]*|reproduc[a-z]*|regression)\b",
    re.I
)


class ChangeImpactConfig(BaseModel):
    """Configuration for Typed Change-Impact Ranking Engine."""
    enable_graph: bool = True
    fallback_on_error: bool = True
    
    # Impact Weights
    impact_multiplier: float = 3.0
    sfs_multiplier: float = 0.01
    tip_multiplier_test: float = 1.45
    tip_multiplier_non_test: float = 0.85

    # Relationship Weights (Confirmed)
    weight_confirmed_import: float = 0.75
    weight_confirmed_symbol: float = 0.80
    weight_confirmed_call: float = 0.80
    weight_confirmed_build: float = 0.40

    # Relationship Weights (Heuristics)
    weight_heuristic_test_stem: float = 0.85
    weight_heuristic_dir_proximity: float = 0.75
    weight_heuristic_doc: float = 0.35
    weight_heuristic_ancestor: float = 0.30


class ChangeImpactRanker:
    """
    Production-grade Change-Impact Ranker for RepoNeedle V1.1.
    Implements verified R6 champion logic with full error containment and explanations.
    """

    def __init__(self, config: Optional[ChangeImpactConfig] = None):
        self.config = config or ChangeImpactConfig()

    @staticmethod
    def extract_stem_tokens(path: str) -> Set[str]:
        base = os.path.splitext(os.path.basename(path))[0].lower()
        parts = re.split(r"[_\-\.]+", base)
        return {p for p in parts if len(p) > 1 and p not in {"test", "tests", "src", "lib", "mod"}}

    @classmethod
    def detect_test_intent(cls, query_text: str) -> bool:
        return bool(TEST_PATTERNS.search(query_text))

    def evaluate_candidate_impact(
        self,
        doc: FileDoc,
        seeds: List[str],
        query_text: str,
        is_test_query: bool,
    ) -> Tuple[float, List[str]]:
        """
        Computes maximum change-impact score for a document relative to query seeds.
        Returns (score, list_of_evidence_explanations).
        """
        if not seeds or not self.config.enable_graph:
            return 0.0, []

        c_path = doc.path.replace("\\", "/").lower()
        c_base = os.path.basename(c_path)
        c_ext = os.path.splitext(c_path)[1]
        c_tokens = self.extract_stem_tokens(c_path)
        c_symbols = set(s.lower() for s in (doc.symbols or []))
        c_imports = set(i.lower() for i in (doc.imports or []))

        is_cand_test = doc.is_test or "test" in c_path or c_base.startswith("test_") or c_base.endswith(("_test.py", "test.rs", "test.go"))

        best_score = 0.0
        explanations = []

        for s in seeds:
            s_norm = s.replace("\\", "/").lower()
            if c_path == s_norm:
                continue

            s_tokens = self.extract_stem_tokens(s_norm)
            s_dir = os.path.dirname(s_norm)
            c_dir = os.path.dirname(c_path)
            s_mod = os.path.splitext(s_norm)[0].replace("/", ".")

            # 1. Confirmed Import
            if s_mod in c_imports or any(s_tok in imp for s_tok in s_tokens for imp in c_imports if len(s_tok) > 3):
                score = self.config.weight_confirmed_import
                if score > best_score:
                    best_score = score
                    explanations.append(f"Confirmed AST import from seed '{os.path.basename(s_norm)}' (+{score:.2f})")

            # 2. Confirmed Public Symbol
            matching_syms = [sym for sym in c_symbols if sym in query_text.lower() and len(sym) > 3]
            if matching_syms:
                score = self.config.weight_confirmed_symbol
                if score > best_score:
                    best_score = score
                    explanations.append(f"Confirmed AST public symbol '{matching_syms[0]}' (+{score:.2f})")

            # 3. Confirmed Call
            if any(f"{tok}(" in query_text.lower() for tok in c_symbols if len(tok) > 3):
                score = self.config.weight_confirmed_call
                if score > best_score:
                    best_score = score
                    explanations.append(f"Confirmed function call invocation (+{score:.2f})")

            # 4. Confirmed Build Manifest
            if c_base in BUILD_FILES and (s_dir.startswith(c_dir) or c_dir == ""):
                score = self.config.weight_confirmed_build
                if score > best_score:
                    best_score = score
                    explanations.append(f"Governing build manifest '{c_base}' (+{score:.2f})")

            # 5. Heuristic Test Stem
            if is_cand_test:
                overlap = len(s_tokens & c_tokens)
                if overlap > 0:
                    score = self.config.weight_heuristic_test_stem if is_test_query else 0.55
                    if score > best_score:
                        best_score = score
                        explanations.append(f"Test naming stem overlap with seed '{os.path.basename(s_norm)}' (+{score:.2f})")

            # 6. Heuristic Directory Sibling
            if c_dir == s_dir and s_dir:
                score = self.config.weight_heuristic_dir_proximity
                if score > best_score:
                    best_score = score
                    explanations.append(f"Directory sibling in '{s_dir}' (+{score:.2f})")

            # 7. Heuristic Ancestor Containment
            elif (c_dir.startswith(s_dir) or s_dir.startswith(c_dir)) and s_dir:
                score = self.config.weight_heuristic_ancestor
                if score > best_score:
                    best_score = score
                    explanations.append(f"Directory hierarchy containment (+{score:.2f})")

            # 8. Heuristic Documentation
            if (c_ext in DOC_EXTS or "doc" in c_path) and len(s_tokens & c_tokens) > 0:
                score = self.config.weight_heuristic_doc
                if score > best_score:
                    best_score = score
                    explanations.append("Documentation stem match (+0.35)")

        return best_score, explanations

    def rank_with_scores(
        self,
        docs: List[FileDoc],
        lex_scores: np.ndarray,
        sem_scores: np.ndarray,
        query: Query,
        config_override: Optional[ChangeImpactConfig] = None,
    ) -> Tuple[List[int], np.ndarray, Dict[int, str]]:
        """
        Ranks candidate documents using Typed Change-Impact scoring.
        Returns:
            ranked_indices: document indices ordered descending by score
            fused_scores: np.ndarray of float32 scores
            explanations: mapping of doc_idx to descriptive explanation
        """
        active_config = config_override or self.config
        num_docs = len(docs)
        if num_docs == 0:
            return [], np.zeros(0, dtype=np.float32), {}

        try:
            seeds = [s.replace("\\", "/").lower() for s in (query.anchor_files or [])]
            is_test_query = self.detect_test_intent(query.text)

            fused_scores = np.zeros(num_docs, dtype=np.float32)
            explanations: Dict[int, str] = {}

            for idx, doc in enumerate(docs):
                c_path = doc.path.replace("\\", "/").lower()
                c_base = os.path.basename(c_path)
                is_cand_test = doc.is_test or "test" in c_path or c_base.startswith("test_") or c_base.endswith(("_test.py", "test.rs", "test.go"))

                # Base score from lexical + subwords
                base_score = float(lex_scores[idx]) + 0.15 * float(sem_scores[idx])

                # Seed File Suppression
                is_seed = bool(seeds and c_path in seeds)
                sfs_mult = active_config.sfs_multiplier if is_seed else 1.0

                # Test Intent Prior
                if is_test_query and is_cand_test:
                    tip_mult = active_config.tip_multiplier_test
                elif not is_test_query and is_cand_test:
                    tip_mult = active_config.tip_multiplier_non_test
                else:
                    tip_mult = 1.0

                score = base_score * sfs_mult * tip_mult
                exp_parts = []

                if is_seed:
                    exp_parts.append(f"Suppressed query seed ({active_config.sfs_multiplier}x)")
                if is_test_query and is_cand_test:
                    exp_parts.append(f"Test Intent Prior boost ({active_config.tip_multiplier_test}x)")

                # Change-Impact Graph Propagation
                if active_config.enable_graph and seeds:
                    impact, edge_exps = self.evaluate_candidate_impact(doc, seeds, query.text, is_test_query)
                    if impact > 0:
                        boost = active_config.impact_multiplier * impact
                        score += boost
                        exp_parts.extend(edge_exps)

                fused_scores[idx] = max(0.0, score)
                explanations[idx] = "; ".join(exp_parts) if exp_parts else "Lexical/semantic relevance"

            ranked_indices = sorted(range(num_docs), key=lambda i: (-float(fused_scores[i]), docs[i].path))
            return ranked_indices, fused_scores, explanations

        except Exception as exc:
            if active_config.fallback_on_error:
                logger.warning(f"ChangeImpactRanker encountered exception: {exc}. Falling back to baseline lexical fusion.")
                fallback_scores = np.maximum(0.0, lex_scores + 0.2 * sem_scores)
                ranked_indices = sorted(range(num_docs), key=lambda i: (-float(fallback_scores[i]), docs[i].path))
                explanations = {i: "Fallback to baseline lexical ranker due to exception" for i in range(num_docs)}
                return ranked_indices, fallback_scores, explanations
            raise

