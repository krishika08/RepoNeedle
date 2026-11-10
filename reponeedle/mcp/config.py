"""
Configuration and security path validation for RepoNeedle MCP Server.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from reponeedle.models import BudgetConfig
from reponeedle.engine import relpath_escapes_root


class MCPServerConfig(BaseModel):
    """Configuration schema for RepoNeedle MCP Server."""
    repo_dir: str = Field(default=".", description="Path to repository root.")
    budget: int = Field(default=4000, description="Default token budget for context packing.")
    allow_skeletons: bool = Field(default=True, description="Allow structural skeletons in packed context.")
    mode: str = Field(default="auto", description="CUD-Pack delivery mode ('auto', 'compact', 'complete').")
    max_files: int = Field(default=3000, description="Maximum files to index.")
    max_file_size_bytes: int = Field(
        default=500_000,
        gt=0,
        description="Files strictly larger than this many bytes are skipped (and reported) during indexing.",
    )


def validate_and_normalize_path(repo_dir: str, target_path: str) -> str:
    """
    Validates a file path against the configured repository root.
    Enforces path traversal protection and symlink escape checks.
    Returns normalized repository-relative path with forward slashes.

    Raises:
        ValueError: If path is empty, does not exist, is not a file, or violates security bounds.
    """
    if not target_path or not str(target_path).strip():
        raise ValueError("File path cannot be empty.")

    raw = str(target_path).strip()
    abs_repo = os.path.realpath(os.path.abspath(repo_dir))

    # Resolve candidate relative to repo_dir or current working directory
    cand1 = os.path.normpath(os.path.join(abs_repo, raw))
    cand2 = os.path.normpath(os.path.abspath(raw))

    chosen = None
    if os.path.exists(cand1) and os.path.isfile(cand1):
        chosen = cand1
    elif os.path.exists(cand2) and os.path.isfile(cand2):
        chosen = cand2

    if chosen is None:
        raise ValueError(f"Path '{raw}' does not exist or is not a regular file within repository '{repo_dir}'.")

    # Canonicalize symlinks
    real_chosen = os.path.realpath(chosen)

    # Verify target stays strictly within real_repo
    try:
        rel = os.path.relpath(real_chosen, abs_repo)
    except ValueError:
        raise ValueError(f"Path '{raw}' is located on a different drive than repository '{repo_dir}'.")

    # Component-aware: a legitimate name such as '..cache/x' is not a traversal.
    if relpath_escapes_root(rel) or os.path.isabs(rel):
        raise ValueError(f"Security boundary violation: Path '{raw}' resolves outside repository root '{repo_dir}'.")

    return rel.replace("\\", "/")
