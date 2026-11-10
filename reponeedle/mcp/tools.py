"""
Tool definitions and handlers for RepoNeedle MCP Server.
"""

import time
from typing import List, Optional, Dict, Any, TYPE_CHECKING

# Type-only import: keeps `reponeedle.mcp` importable without the optional 'mcp' extra so the
# server entrypoint can print its friendly "install reponeedle[mcp]" error instead of crashing.
if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import TaskType, RankerType
from reponeedle.mcp.config import validate_and_normalize_path

VALID_RANKERS = {"legacy", "bm25", "arm101", "cascade", "change_impact"}
VALID_TASK_TYPES = {"auto", "code2test", "comment2context", "trace2code", "edit2ripple", "selective"}


def register_tools(
    app: "FastMCP",
    engine: RepoNeedleEngine,
    repo_dir: str,
    init_time_ms: float = 0.0,
) -> None:
    """
    Registers the three primary RepoNeedle retrieval and inspection tools
    on the provided FastMCP application instance.
    """

    @app.tool(
        name="reponeedle_retrieve",
        description=(
            "Retrieve the most relevant repository context for a natural-language coding task, "
            "issue description, or error traceback strictly within the requested token budget."
        ),
    )
    async def reponeedle_retrieve(
        query: str,
        budget_tokens: int = 4000,
        ranker: str = "legacy",
        task_type: str = "auto",
        anchor_files: Optional[List[str]] = None,
        enable_experimental_abstention: bool = False,
    ) -> Dict[str, Any]:
        """
        Retrieves context files and rendered markdown prompt within token limits.

        Args:
            query: Natural language coding task, issue description, or error traceback.
            budget_tokens: Maximum token budget for packed context (default: 4000).
            ranker: Ranking engine ('legacy', 'bm25', 'arm101', 'cascade', 'change_impact').
            task_type: Workflow task type ('auto', 'code2test', 'comment2context', 'trace2code', 'edit2ripple', 'selective').
                'selective' does not enable abstention by itself.
            anchor_files: Optional list of seed or modified file paths.
            enable_experimental_abstention: Opt in to the EXPERIMENTAL, uncalibrated out-of-scope
                abstention heuristic (default: false). When false, results are always returned
                (except for an empty repository) and out-of-scope queries are not detected.
        """
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty.")

        ranker_clean = ranker.lower().strip()
        if ranker_clean not in VALID_RANKERS:
            raise ValueError(
                f"Unknown ranker '{ranker}'. Supported rankers are: {sorted(list(VALID_RANKERS))}."
            )

        task_type_clean = task_type.lower().strip()
        if task_type_clean not in VALID_TASK_TYPES:
            raise ValueError(
                f"Unknown task_type '{task_type}'. Supported task types are: {sorted(list(VALID_TASK_TYPES))}."
            )

        validated_anchors = []
        if anchor_files:
            for a in anchor_files:
                validated_anchors.append(validate_and_normalize_path(repo_dir, a))

        effective_task = TaskType(task_type_clean) if task_type_clean != "auto" else None
        result = engine.retrieve(
            query=query.strip(),
            budget_tokens=budget_tokens,
            task_type=effective_task,
            ranker=ranker_clean,
            anchor_files=validated_anchors,
            enable_experimental_abstention=bool(enable_experimental_abstention),
        )

        selected_files_list = []
        for rank, sf in enumerate(result.selected_files, start=1):
            selected_files_list.append({
                "rank": rank,
                "path": sf.path,
                "tier": sf.tier.value if hasattr(sf.tier, "value") else str(sf.tier),
                "token_count": int(sf.token_count),
                "score": round(float(sf.score), 4),
                "explanation": sf.explanation or "",
            })

        return {
            "status": "abstained" if result.abstained else "success",
            "query": result.query,
            "ranker": result.ranker or ranker_clean,
            "task_type": result.task_type.value if hasattr(result.task_type, "value") else str(result.task_type),
            "abstained": bool(result.abstained),
            "explanation": result.explanation or "",
            "budget_tokens": int(result.budget_tokens),
            "total_tokens": int(result.total_tokens),
            "execution_time_ms": round(float(result.execution_time_ms), 2),
            "confidence_score": round(float(result.confidence_score), 4),
            "selected_files": selected_files_list,
            "rendered_context": result.rendered_context if not result.abstained else "",
            "abstention": result.abstention.model_dump() if result.abstention is not None else None,
        }

    @app.tool(
        name="reponeedle_change_impact",
        description=(
            "Identify files and regression tests potentially affected by modifications to specific "
            "anchor files using AST change propagation and Seed File Suppression (SFS)."
        ),
    )
    async def reponeedle_change_impact(
        anchor_files: List[str],
        query: str = "Assess change impact",
        budget_tokens: int = 4000,
    ) -> Dict[str, Any]:
        """
        Analyzes change impact and regression risk for one or more modified anchor files.

        Args:
            anchor_files: List of modified file paths to analyze (at least one required).
            query: Optional task or bug description (default: 'Assess change impact').
            budget_tokens: Maximum token budget for packed context (default: 4000).
        """
        if not anchor_files:
            raise ValueError("At least one anchor file is required for change-impact analysis.")

        validated_anchors = []
        for a in anchor_files:
            validated_anchors.append(validate_and_normalize_path(repo_dir, a))

        effective_query = query.strip() if query and query.strip() else "Assess change impact"
        result = engine.retrieve(
            query=effective_query,
            budget_tokens=budget_tokens,
            ranker="change_impact",
            anchor_files=validated_anchors,
            # Change-impact always reports "success"; never let the heuristic empty it silently.
            enable_experimental_abstention=False,
        )

        affected_files_list = []
        for rank, sf in enumerate(result.selected_files, start=1):
            affected_files_list.append({
                "rank": rank,
                "path": sf.path,
                "tier": sf.tier.value if hasattr(sf.tier, "value") else str(sf.tier),
                "token_count": int(sf.token_count),
                "score": round(float(sf.score), 4),
                "explanation": sf.explanation or "",
            })

        return {
            "status": "success",
            "query": result.query,
            "anchor_files": validated_anchors,
            "budget_tokens": int(result.budget_tokens),
            "total_tokens": int(result.total_tokens),
            "execution_time_ms": round(float(result.execution_time_ms), 2),
            "explanation": result.explanation or "",
            "affected_files": affected_files_list,
            "rendered_context": result.rendered_context,
        }

    @app.tool(
        name="reponeedle_inspect",
        description=(
            "Inspect the indexed repository state: returns file count, supported extensions, "
            "sample indexed paths, active rankers, engine configuration, indexing diagnostics "
            "(files skipped for exceeding the size limit or being unreadable), and the "
            "experimental abstention status."
        ),
    )
    async def reponeedle_inspect() -> Dict[str, Any]:
        """
        Returns diagnostic information about the indexed repository and active retrieval configuration.
        """
        indexed_paths = [doc.path for doc in engine.docs]
        sample_paths = indexed_paths[:25]

        return {
            "status": "ready",
            "repository_root": repo_dir,
            "indexed_file_count": len(engine.docs),
            "supported_file_types": [
                ".py", ".ts", ".js", ".tsx", ".jsx",
                ".go", ".rs", ".java", ".c", ".cpp",
                ".h", ".md", ".toml", ".yaml", ".yml", ".json"
            ],
            "indexed_path_examples": sample_paths,
            "sample_count": len(sample_paths),
            "active_rankers": sorted(list(VALID_RANKERS)),
            "default_ranker": "legacy",
            "budget_config": {
                "max_tokens": engine.budget_config.max_tokens,
                "allow_skeletons": engine.budget_config.allow_skeletons,
                "mode": engine.budget_config.mode,
            },
            "index_initialization": {
                "status": "initialized",
                "init_time_ms": round(init_time_ms, 2),
                "message": "Repository indexed in-memory at server startup. Restart server to refresh index.",
            },
            # Paths and counts only; file contents are never included.
            "indexing": engine.indexing_diagnostics.model_dump(),
            "abstention": {
                "default_enabled": bool(getattr(engine.budget_config, "enable_experimental_abstention", False)),
                "experimental": True,
                "calibrated": False,
                "threshold": float(engine.budget_config.abstention_threshold),
                "opt_in": "Pass enable_experimental_abstention=true to reponeedle_retrieve.",
            },
        }
