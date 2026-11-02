"""
R5.4: Multi-Target Retrieval & Diversity Selector.
Solves the multi-file task retrieval problem by discovering:
1. Primary Implementation Targets
2. Supporting Implementation Targets
3. Companion Test Targets
4. Configuration and Build Targets
5. Documentation References

Uses Maximum Marginal Relevance (MMR) and role-aware diversity selection
to eliminate context redundancy while maximizing complete target recall.
"""
import os
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict


class TargetRole(str, Enum):
    PRIMARY_IMPL = "primary_impl"
    SUPPORT_IMPL = "support_impl"
    TEST = "test"
    CONFIG_BUILD = "config_build"
    DOCS = "docs"


BUILD_FILES = {"setup.py", "setup.cfg", "pyproject.toml", "cargo.toml", "package.json", "cmakelists.txt", "makefile", "pom.xml"}
DOC_EXTS = {".md", ".rst", ".txt", ".adoc"}


class MultiTargetSelector:
    """Selects a diverse, complementary set of code targets for multi-file tasks."""

    def __init__(self, diversity_lambda: float = 0.75, max_same_dir: int = 2):
        self.diversity_lambda = diversity_lambda
        self.max_same_dir = max_same_dir

    @classmethod
    def classify_role(cls, file_path: str, is_top_impl: bool = False) -> TargetRole:
        p_lower = file_path.lower()
        base = os.path.basename(p_lower)
        ext = os.path.splitext(p_lower)[1]

        if "test" in p_lower or base.startswith("test_") or base.endswith("_test.py"):
            return TargetRole.TEST
        if base in BUILD_FILES or ext in (".toml", ".cfg", ".ini", ".yaml", ".yml"):
            return TargetRole.CONFIG_BUILD
        if ext in DOC_EXTS or "doc" in p_lower:
            return TargetRole.DOCS
        if is_top_impl:
            return TargetRole.PRIMARY_IMPL
        return TargetRole.SUPPORT_IMPL

    def compute_lexical_similarity(self, path1: str, path2: str) -> float:
        """Computes directory and token overlap between two candidate file paths."""
        dir1 = os.path.dirname(path1).replace("\\", "/").split("/")
        dir2 = os.path.dirname(path2).replace("\\", "/").split("/")

        # Directory prefix match
        common_dirs = 0
        for d1, d2 in zip(dir1, dir2):
            if d1 == d2:
                common_dirs += 1
            else:
                break
        max_d = max(len(dir1), len(dir2), 1)
        dir_sim = common_dirs / max_d

        # File basename token similarity
        base1 = set(os.path.splitext(os.path.basename(path1))[0].split("_"))
        base2 = set(os.path.splitext(os.path.basename(path2))[0].split("_"))
        tok_sim = len(base1 & base2) / max(len(base1 | base2), 1)

        return 0.7 * dir_sim + 0.3 * tok_sim

    def select_diverse_targets(
        self,
        ranked_candidates: List[Dict[str, Any]],
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Applies role-aware MMR selection to return a diverse, high-coverage candidate set.
        Guarantees that secondary targets (tests, supporting modules) are not starved by
        clusters of redundant files from a single subdirectory.
        """
        if not ranked_candidates:
            return []

        selected: List[Dict[str, Any]] = []
        remaining = list(ranked_candidates)
        dir_counts: Dict[str, int] = defaultdict(int)
        seen_roles: Set[TargetRole] = set()

        # Step 1: Select top-ranked candidate unconditionally as Anchor
        top_cand = dict(remaining.pop(0))
        top_role = self.classify_role(top_cand.get("path", ""), is_top_impl=True)
        top_cand["target_role"] = top_role.value
        selected.append(top_cand)
        seen_roles.add(top_role)

        top_dir = os.path.dirname(top_cand.get("path", "")).replace("\\", "/")
        dir_counts[top_dir] += 1

        # Step 2: Iteratively select remaining targets using role-aware MMR (diversifying top_k)
        while remaining and len(selected) < top_k:
            best_idx = -1
            best_mmr_score = -float("inf")

            # Only consider top 50 remaining candidates for MMR candidate selection to keep latency sub-millisecond
            scan_limit = min(len(remaining), 50)
            for idx in range(scan_limit):
                cand = remaining[idx]
                c_path = cand.get("path", "")
                c_dir = os.path.dirname(c_path).replace("\\", "/")
                raw_rel = cand.get("score", 0.0)

                # Compute maximum redundancy with already selected candidates
                max_redundancy = max(
                    self.compute_lexical_similarity(c_path, s.get("path", ""))
                    for s in selected
                )

                # MMR formulation: lambda * Relevance - (1 - lambda) * Redundancy
                mmr = self.diversity_lambda * raw_rel - (1.0 - self.diversity_lambda) * (max_redundancy * raw_rel)

                # Role diversity bonus: encourage multi-target discovery
                cand_role = self.classify_role(c_path, is_top_impl=False)
                if cand_role not in seen_roles and cand_role in (TargetRole.TEST, TargetRole.SUPPORT_IMPL):
                    mmr *= 1.25

                # Directory saturation penalty
                if dir_counts[c_dir] >= self.max_same_dir:
                    mmr *= 0.65

                if mmr > best_mmr_score:
                    best_mmr_score = mmr
                    best_idx = idx

            if best_idx >= 0:
                chosen = dict(remaining.pop(best_idx))
                chosen_path = chosen.get("path", "")
                chosen_dir = os.path.dirname(chosen_path).replace("\\", "/")
                chosen_role = self.classify_role(chosen_path, is_top_impl=(TargetRole.PRIMARY_IMPL not in seen_roles))
                chosen["target_role"] = chosen_role.value
                chosen["mmr_score"] = float(best_mmr_score)

                selected.append(chosen)
                seen_roles.add(chosen_role)
                dir_counts[chosen_dir] += 1
            else:
                break

        # Append remaining candidates in original order to preserve 100% candidate recall
        selected.extend(remaining)

        # Re-assign ordinal ranks
        for idx, c in enumerate(selected, 1):
            c["rank"] = idx

        return selected

