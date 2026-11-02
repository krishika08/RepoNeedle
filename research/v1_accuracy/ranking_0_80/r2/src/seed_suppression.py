"""
R2.1 — Seed File Suppression (SFS) Module.
Parses query seed files, determines relational vs self-focused intent, and applies intent-guarded demotion.
"""
import json
import re
from typing import Dict, List, Optional, Set, Tuple

# Supported metadata keys containing seed file paths
SEED_METADATA_KEYS = [
    "changed_file",
    "anchor_file",
    "given_file",
    "file_path",
    "filename",
    "path",
]

# Patterns for extracting files from unified diffs
DIFF_PATTERNS = [
    re.compile(r'\+\+\+\s+b/([^\s\n\t]+)'),
    re.compile(r'---\s+a/([^\s\n\t]+)'),
    re.compile(r'diff\s+--git\s+a/([^\s\n\t]+)\s+b/([^\s\n\t]+)'),
]

# Explicit self-focus triggers (the user wants to inspect/explain the seed file itself)
SELF_FOCUS_PATTERNS = [
    re.compile(r'\b(explain|summarize|what\s+does|walk\s*through|how\s+does)\b.*?\b(this\s+file|this\s+function|this\s+class)\b', re.IGNORECASE),
    re.compile(r'\b(overview|description)\s+of\s+(this\s+file|the\s+file)\b', re.IGNORECASE),
    re.compile(r'\b(refactor|optimize|cleanup)\s+(only\s+)?(this\s+file)\b', re.IGNORECASE),
]

# Relational intent triggers (the user wants files related to, affected by, or testing the seed file)
RELATIONAL_INTENT_PATTERNS = [
    re.compile(r'\b(test|tests|testsuite|spec|testing|unit\s*test)\b', re.IGNORECASE),
    re.compile(r'\b(ripple|affected|downstream|impact|depend|callers?|usages?)\b', re.IGNORECASE),
    re.compile(r'\b(context|review\s*comment|diff\s*hunk|pr_body|pr_title)\b', re.IGNORECASE),
    re.compile(r'\b(find|locate|where\s+is|what\s+files?)\b', re.IGNORECASE),
]

def normalize_path(path: str) -> str:
    """Normalize file path for robust matching."""
    if not path:
        return ""
    p = path.replace("\\", "/").strip()
    if p.startswith("./"):
        p = p[2:]
    if p.startswith("/"):
        p = p[1:]
    return p

class SeedExtractor:
    """Extracts input seed files and determines query intent without oracle labels."""

    @staticmethod
    def extract_seeds(query_text: str) -> Set[str]:
        """Extract all candidate seed files mentioned in query metadata or diffs."""
        seeds = set()
        if not query_text:
            return seeds

        # Try parsing JSON
        try:
            d = json.loads(query_text)
            for k in SEED_METADATA_KEYS:
                val = d.get(k)
                if isinstance(val, str) and val.strip():
                    seeds.add(normalize_path(val))
                    
            impl_files = d.get("implementation_files")
            if isinstance(impl_files, list):
                for f in impl_files:
                    if isinstance(f, str) and f.strip():
                        seeds.add(normalize_path(f))

            anchor_diff = d.get("anchor_diff") or d.get("diff_hunk_context") or d.get("diff")
            if isinstance(anchor_diff, str):
                for pat in DIFF_PATTERNS:
                    for m in pat.finditer(anchor_diff):
                        for grp in m.groups():
                            if grp:
                                seeds.add(normalize_path(grp))
        except Exception:
            # Fallback to regex on raw text
            for k in SEED_METADATA_KEYS:
                pattern = rf'"{k}":\s*"([^"]+)"'
                for m in re.finditer(pattern, query_text):
                    seeds.add(normalize_path(m.group(1)))
            for pat in DIFF_PATTERNS:
                for m in pat.finditer(query_text):
                    for grp in m.groups():
                        if grp:
                            seeds.add(normalize_path(grp))

        return seeds

    @staticmethod
    def determine_intent(query_text: str, seeds: Set[str]) -> str:
        """
        Determine whether query intent is 'relational' or 'self_focused'.
        Returns:
            'relational': Developer is seeking related, dependent, or test files.
            'self_focused': Developer is asking to explain or edit the seed file itself.
        """
        if not seeds:
            return "neutral"

        # Check self-focused patterns
        for pat in SELF_FOCUS_PATTERNS:
            if pat.search(query_text):
                return "self_focused"

        # Check relational patterns or standard benchmark task formats
        try:
            d = json.loads(query_text)
            # If query has anchor_diff, diff_hunk_context, review_comment, or pr_body, it is relational
            if any(k in d for k in ["anchor_diff", "diff_hunk_context", "review_comment", "pr_body", "pr_title", "command"]):
                return "relational"
        except Exception:
            pass

        for pat in RELATIONAL_INTENT_PATTERNS:
            if pat.search(query_text):
                return "relational"

        # Default to relational if a seed is present in structured context
        return "relational"


class SeedSuppressor:
    """Applies intent-guarded ranking demotion to seed candidates."""

    def __init__(self, demotion_factor: float = 0.01, enabled: bool = True):
        """
        Args:
            demotion_factor: Multiplicative factor applied to seed file score (e.g. 0.01).
            enabled: Toggle suppression on/off.
        """
        self.demotion_factor = demotion_factor
        self.enabled = enabled

    def suppress(
        self,
        candidates: List[dict],
        query_text: str,
        demotion_factor: Optional[float] = None
    ) -> Tuple[List[dict], Dict[str, any]]:
        """
        Apply seed file suppression.
        Returns:
            reordered_candidates: Candidate list with updated ranks and scores.
            telemetry: Diagnostic information (extracted seeds, intent, suppressed count).
        """
        factor = demotion_factor if demotion_factor is not None else self.demotion_factor
        seeds = SeedExtractor.extract_seeds(query_text)
        intent = SeedExtractor.determine_intent(query_text, seeds)

        telemetry = {
            "seeds": list(seeds),
            "intent": intent,
            "suppressed_candidates": [],
            "enabled": self.enabled,
            "demotion_factor": factor,
        }

        if not self.enabled or not seeds or intent != "relational":
            # Return original candidates without alteration
            return list(candidates), telemetry

        modified_cands = []
        for c in candidates:
            cand_copy = dict(c)
            path_norm = normalize_path(cand_copy.get("path", ""))
            
            if path_norm in seeds:
                orig_score = cand_copy.get("m1_score", 0.0)
                demoted_score = orig_score * factor
                cand_copy["sfs_demoted"] = True
                cand_copy["sfs_orig_score"] = orig_score
                cand_copy["current_score"] = demoted_score
                telemetry["suppressed_candidates"].append(path_norm)
            else:
                cand_copy["sfs_demoted"] = False
                cand_copy["current_score"] = cand_copy.get("m1_score", 0.0)
                
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
    train_data, _, _ = load_data()
    suppressor = SeedSuppressor(demotion_factor=0.01)
    
    total_seeds = 0
    total_suppressed = 0
    for q in train_data[:10]:
        reordered, telem = suppressor.suppress(q["candidates"], q["query_text"])
        total_seeds += len(telem["seeds"])
        total_suppressed += len(telem["suppressed_candidates"])
        print(f"Query {q['query_id'][:8]} | Intent: {telem['intent']} | Seeds: {telem['seeds']} | Suppressed: {telem['suppressed_candidates']}")

