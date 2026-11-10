"""
RepoNeedle Model Context Protocol (MCP) Server.
Provides local STDIO context retrieval tools for AI coding agents.
"""

__all__ = ["create_mcp_server", "main", "MCPServerConfig", "validate_and_normalize_path"]

from reponeedle.mcp.config import MCPServerConfig, validate_and_normalize_path
from reponeedle.mcp.server import create_mcp_server, main
