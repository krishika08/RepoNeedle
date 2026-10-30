"""
Strict Information Leakage Prevention Guard for External Benchmark Evaluation.

Enforces fail-closed isolation between benchmark evaluation data and the retrieval pipeline.
Ensures evaluation-only target fields (gold_context, patch, test_patch, f2p, p2p)
can never reach the retrieval ranker.
"""

from typing import Dict, Any, Set

FORBIDDEN_EVALUATION_FIELDS: Set[str] = {
    "gold_context",
    "patch",
    "test_patch",
    "f2p",
    "p2p",
    "failing_tests",
    "passing_tests",
    "gold_files",
}

PERMITTED_RETRIEVAL_FIELDS: Set[str] = {
    "instance_id",
    "repo",
    "base_commit",
    "problem_statement",
    "language",
}


class DataLeakageSecurityException(Exception):
    """Raised when an evaluation-only target field is passed to the retrieval system."""
    pass


class LeakageGuard:
    """
    Enforces that retrieval input contains only permitted query and repo fields,
    completely scrubbing and guarding against target leakage.
    """

    @staticmethod
    def inspect_and_sanitize(task_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates that forbidden fields are absent or scrubs them, returning a
        sanitized retrieval packet containing only permitted fields.
        """
        # If forbidden fields exist in the raw record, verify they are stripped
        sanitized = {}
        for key in PERMITTED_RETRIEVAL_FIELDS:
            if key in task_record:
                sanitized[key] = task_record[key]

        # Audit that no forbidden key leaked into the sanitized dictionary
        leaked_keys = set(sanitized.keys()).intersection(FORBIDDEN_EVALUATION_FIELDS)
        if leaked_keys:
            raise DataLeakageSecurityException(
                f"FATAL: Evaluation targets detected in retrieval input packet: {leaked_keys}"
            )

        return sanitized

    @staticmethod
    def assert_no_leakage_in_engine_call(query_metadata: Dict[str, Any]):
        """
        Runtime assertion inside the adapter before calling RepoNeedle.
        """
        for field in FORBIDDEN_EVALUATION_FIELDS:
            if field in query_metadata:
                raise DataLeakageSecurityException(
                    f"DATA LEAKAGE DETECTED: Retrieval called with forbidden evaluation target: '{field}'."
                )
