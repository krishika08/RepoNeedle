"""
Workflow-adaptive routing and task classification for repository retrieval.
"""

import re
from typing import Dict, List, Tuple
from reponeedle.models import TaskType, Query

# Regex patterns for detecting stack traces and errors
STACK_TRACE_REGEX = re.compile(
    r"(?:Traceback \(most recent call last\):|File [\"'][^\"']+[\"'], line \d+|[A-Za-z0-9_]+Error:|[A-Za-z0-9_]+Exception:)",
    re.IGNORECASE,
)
FILE_FRAME_REGEX = re.compile(
    r"File [\"']([^\"']+)[\"'], line (\d+)(?:, in ([a-zA-Z0-9_]+))?",
    re.IGNORECASE,
)
TEST_KEYWORD_REGEX = re.compile(
    r"\b(test|tests|test_[\w]+|[\w]+_test|pytest|unittest|regression|verify|fixture|assert|assert_)\b",
    re.IGNORECASE,
)
RIPPLE_KEYWORD_REGEX = re.compile(
    r"\b(ripple|impact|affected|dependents?|callers?|callees?|breaking change|refactor|references?)\b",
    re.IGNORECASE,
)


class WorkflowRouter:
    """
    Classifies task intent and dynamically computes retrieval fusion weights.
    """

    def __init__(self):
        pass

    def classify_intent(self, query: Query) -> Tuple[TaskType, Dict[str, any]]:
        """
        Infers the task type if set to AUTO, and extracts contextual metadata
        (e.g., extracted frames for trace2code, target modules for code2test).
        """
        if query.task_type != TaskType.AUTO:
            return query.task_type, {}

        text = query.text
        metadata = {}

        # 1. Trace / Error Check
        frames = FILE_FRAME_REGEX.findall(text)
        if STACK_TRACE_REGEX.search(text) or frames:
            metadata["trace_frames"] = frames
            return TaskType.TRACE2CODE, metadata

        # 2. Ripple / Impact Check
        if query.anchor_files or RIPPLE_KEYWORD_REGEX.search(text):
            return TaskType.EDIT2RIPPLE, metadata

        # 3. Test Retrieval Check
        test_matches = TEST_KEYWORD_REGEX.findall(text)
        if len(test_matches) >= 2 or any(w in text.lower() for w in ["find tests", "test suite", "regression test", "add test"]):
            return TaskType.CODE2TEST, metadata

        # 4. Default: Comment / Natural Language Issue
        return TaskType.COMMENT2CONTEXT, metadata

    def get_fusion_weights(self, task_type: TaskType) -> Dict[str, float]:
        """
        Returns the optimal fusion weights for:
        - lexical (BM25)
        - semantic (Subword/dense)
        - structural (PageRank/centrality)
        - workflow_boost (task-specific graph or frame boosts)
        """
        if task_type == TaskType.TRACE2CODE:
            return {
                "lexical": 0.45,
                "semantic": 0.15,
                "structural": 0.05,
                "workflow_boost": 0.35,
            }
        elif task_type == TaskType.CODE2TEST:
            return {
                "lexical": 0.25,
                "semantic": 0.20,
                "structural": 0.05,
                "workflow_boost": 0.50,
            }
        elif task_type == TaskType.EDIT2RIPPLE:
            return {
                "lexical": 0.15,
                "semantic": 0.15,
                "structural": 0.20,
                "workflow_boost": 0.50,
            }
        elif task_type == TaskType.SELECTIVE:
            return {
                "lexical": 0.40,
                "semantic": 0.40,
                "structural": 0.20,
                "workflow_boost": 0.0,
            }
        else:  # COMMENT2CONTEXT
            return {
                "lexical": 0.40,
                "semantic": 0.40,
                "structural": 0.20,
                "workflow_boost": 0.0,
            }
