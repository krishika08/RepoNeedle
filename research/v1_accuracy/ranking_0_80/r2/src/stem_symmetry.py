"""
R2.3 — Stem & Directory Symmetry (SMS) Module.
Language-aware, repository-independent path normalization and symmetry scoring.
"""
import os
import re
from functools import lru_cache
from typing import Dict, List, Optional, Set, Tuple

TEST_AFFIX_PATTERNS = [
    re.compile(r'^(test_|test-|spec_)', re.IGNORECASE),
    re.compile(r'(_test|-test|\.test|_spec|Test|Tests|TestCase)$', re.IGNORECASE),
]

@lru_cache(maxsize=32768)
def split_tokens(s: str) -> frozenset:
    """Split identifier/stem into constituent lowercase words (camelCase, snake_case, kebab-case)."""
    if not s:
        return frozenset()
    # Replace separators
    clean = re.sub(r'[-_./\\]', ' ', s)
    # Split camelCase
    clean = re.sub(r'([a-z])([A-Z])', r'\1 \2', clean)
    tokens = {t.lower() for t in clean.split() if t}
    return frozenset(tokens)

@lru_cache(maxsize=32768)
def extract_stem(path: str) -> Tuple[str, str, frozenset]:
    """
    Extracts raw stem, test-stripped stem, and token set from a file path.
    Returns: (raw_stem, stripped_stem, tokens)
    """
    if not path:
        return "", "", frozenset()
    base = os.path.basename(path)
    raw_stem, _ = os.path.splitext(base)
    
    stripped = raw_stem
    for pat in TEST_AFFIX_PATTERNS:
        stripped = pat.sub('', stripped)
        
    tokens = split_tokens(stripped)
    return raw_stem.lower(), stripped.lower(), tokens

class StemDirectorySymmetry:
    """Computes symmetry features between input seed files and candidate files."""

    @classmethod
    def compute_stem_similarity(cls, seed_path: str, cand_path: str) -> float:
        """
        Calculates stem similarity in [0.0, 1.0].
        Exact stripped match yields 1.0; token Jaccard overlap yields partial score.
        """
        _, stripped_seed, tokens_seed = extract_stem(seed_path)
        _, stripped_cand, tokens_cand = extract_stem(cand_path)

        if not stripped_seed or not stripped_cand:
            return 0.0

        if stripped_seed == stripped_cand:
            return 1.0

        if not tokens_seed or not tokens_cand:
            return 0.0

        intersection = tokens_seed & tokens_cand
        union = tokens_seed | tokens_cand
        return len(intersection) / len(union) if union else 0.0

    @classmethod
    def compute_mirrored_match(cls, seed_path: str, cand_path: str) -> float:
        """
        Detects standard source-to-test and sibling-test mirroring patterns across languages.
        """
        s_norm = seed_path.replace("\\", "/").strip().lower()
        c_norm = cand_path.replace("\\", "/").strip().lower()

        s_dir = os.path.dirname(s_norm)
        c_dir = os.path.dirname(c_norm)

        # Pattern 1: Co-located in same directory (Go, Rust modules, Python local tests)
        if s_dir == c_dir and s_dir:
            _, s_strip, _ = extract_stem(s_norm)
            _, c_strip, _ = extract_stem(c_norm)
            if s_strip == c_strip:
                return 1.0
            return 0.5

        # Pattern 2: src/ -> tests/ mirroring
        # e.g. src/foo/bar.py -> tests/foo/test_bar.py
        s_parts = [p for p in s_dir.split("/") if p not in ["src", "lib", "pkg", "internal"]]
        c_parts = [p for p in c_dir.split("/") if p not in ["tests", "test", "testsuite", "__tests__", "spec"]]

        if s_parts and c_parts and s_parts == c_parts:
            return 1.0

        # Pattern 3: Submodule matching
        # e.g. seed directory component matches candidate stem
        _, _, cand_tokens = extract_stem(c_norm)
        s_dir_tokens = set(s_dir.split("/"))
        if cand_tokens & s_dir_tokens:
            return 0.75

        return 0.0

    @classmethod
    @lru_cache(maxsize=65536)
    def compute_symmetry_score(cls, seed_path: str, cand_path: str) -> float:
        """
        Combines stem similarity and mirrored structure into an overall symmetry score in [0.0, 2.5].
        """
        stem_sim = cls.compute_stem_similarity(seed_path, cand_path)
        mirror_sim = cls.compute_mirrored_match(seed_path, cand_path)

        # If stems are identical, give strong weight
        score = (1.5 * stem_sim) + (1.0 * mirror_sim)
        return score

    @classmethod
    def score_candidate(cls, seeds: Set[str], cand_path: str) -> float:
        """Computes maximum symmetry score across all extracted seed files."""
        if not seeds:
            return 0.0
        scores = [cls.compute_symmetry_score(s, cand_path) for s in seeds]
        return max(scores) if scores else 0.0


class StemSymmetryReranker:
    """Applies symmetry boosting to candidate scores conditioned on query intent."""

    def __init__(
        self,
        weight: float = 0.5,
        enabled: bool = True
    ):
        """
        Args:
            weight: Scaling factor for symmetry boost.
            enabled: Toggle feature on/off.
        """
        self.weight = weight
        self.enabled = enabled

    def apply(
        self,
        candidates: List[dict],
        seeds: Set[str],
        is_relational: bool,
        weight: Optional[float] = None
    ) -> Tuple[List[dict], Dict[str, any]]:
        """
        Apply symmetry scoring.
        Returns:
            reordered_candidates: Candidate list with updated ranks and scores.
            telemetry: Diagnostic information.
        """
        w = weight if weight is not None else self.weight

        telemetry = {
            "applied": self.enabled and is_relational and bool(seeds),
            "weight": w,
            "boosted_count": 0,
        }

        if not self.enabled or not is_relational or not seeds:
            return list(candidates), telemetry

        modified_cands = []
        for c in candidates:
            cand_copy = dict(c)
            path = cand_copy.get("path", "")
            current_score = cand_copy.get("current_score", cand_copy.get("m1_score", 0.0))

            sym_score = StemDirectorySymmetry.score_candidate(seeds, path)
            cand_copy["sms_score"] = sym_score

            if sym_score > 0.1:
                # Additive or multiplicative boost
                boost = 1.0 + (w * sym_score)
                cand_copy["sms_boost"] = boost
                cand_copy["current_score"] = current_score * boost
                telemetry["boosted_count"] += 1
            else:
                cand_copy["sms_boost"] = 1.0
                cand_copy["current_score"] = current_score

            modified_cands.append(cand_copy)

        # Stable sort by current_score descending, breaking ties with original m1_rank
        reordered = sorted(
            modified_cands,
            key=lambda x: (x.get("current_score", 0.0), -x.get("m1_rank", 9999)),
            reverse=True
        )

        # Update ranks
        for idx, c in enumerate(reordered, 1):
            c["rank"] = idx

        return reordered, telemetry

if __name__ == "__main__":
    from split import load_data
    from seed_suppression import SeedExtractor
    train_data, _, _ = load_data()
    
    print("Testing StemDirectorySymmetry on Training samples...")
    for q in train_data[:8]:
        seeds = SeedExtractor.extract_seeds(q["query_text"])
        golds = q["gold_files"]
        if seeds:
            print(f"\nQuery {q['query_id'][:8]} | Seeds: {list(seeds)[:2]}")
            for g in golds[:2]:
                score = StemDirectorySymmetry.score_candidate(seeds, g)
                stem_sim = max(StemDirectorySymmetry.compute_stem_similarity(s, g) for s in seeds)
                mir_sim = max(StemDirectorySymmetry.compute_mirrored_match(s, g) for s in seeds)
                print(f"  Gold: {g} -> SMS Score: {score:.3f} (stem: {stem_sim:.2f}, mirror: {mir_sim:.2f})")
