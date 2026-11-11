# RepoNeedle Model Context Protocol (MCP) Integration Guide

**Status**: New in RepoNeedle 1.2.0 (**upcoming**; PyPI publication pending). The earlier PyPI release 1.1.0 does **not** include the MCP server.  
**Transport**: STDIO JSON-RPC 2.0 (HTTP/SSE transport is not implemented)  
**SDK Requirement**: `mcp>=1.28,<2` (Optional dependency group: `mcp`)  
**Validation**: Verified with the MCP Python SDK (in-process tool calls) and a raw JSON-RPC STDIO handshake (`initialize`, `tools/list`, `tools/call`) in the test suite. **Not yet validated in a live Claude Code, Cursor, Cline or Windsurf session**; the client configuration examples below follow each client's documented MCP configuration format.

---

## 1. Overview: What is MCP and Why RepoNeedle Supports It

The **Model Context Protocol (MCP)** is an open specification enabling AI coding agents (such as Claude Code, Cursor, Cline, and Windsurf) to securely access local tools, file systems, and specialized retrieval engines through a standardized JSON-RPC 2.0 protocol.

### Why RepoNeedle Fits MCP
1. **CPU-Only Execution**: Runs locally on commodity CPUs without GPUs, API keys or network calls. On the ARB v2 benchmark, per-query latency after indexing was ~142 ms median and ~318 ms mean (repository indexing is a separate one-time cost at server startup).
2. **Token Budget Invariant**: Returned context satisfies
   $$C_{\text{actual}} \le B_{\text{configured}}$$
   as counted by RepoNeedle's internal regex token model. Counts from a specific LLM tokenizer may differ, so leave headroom in tight context windows.
3. **Change-Impact Analysis**: Ranks downstream files, modules and regression tests related to files an agent has edited.
4. **Optional Dependency**: MCP support is packaged as an **optional extra** (`mcp`). Users who do not need MCP do not install the MCP SDK; the core engine keeps its standard dependencies (numpy, scipy, networkx, pydantic, pathspec, rich).

---

## 2. Installation

RepoNeedle core requires Python 3.10+. Install RepoNeedle 1.2.0 or later with the optional `mcp` extra:

```bash
pip install "reponeedle[mcp]>=1.2.0"
```

> [!NOTE]
> 1.2.0 is **upcoming**. Until it is published on PyPI, the command above cannot be resolved (1.1.0, the latest version on PyPI until then, contains neither the MCP server nor the `mcp` extra). In the meantime, install from a clone:
>
> ```bash
> git clone https://github.com/krishika08/RepoNeedle.git
> cd RepoNeedle
> pip install -e ".[mcp]"
> ```

To verify that the MCP server executable is available:

```bash
reponeedle-mcp --help
```

---

## 3. Server Launch Instructions

The RepoNeedle MCP server operates locally over the standard **STDIO** transport.

### Running via Console Script
```bash
reponeedle-mcp --repo /absolute/path/to/repository --budget 4000
```

### Running via Python Module
```bash
python -m reponeedle.mcp --repo /absolute/path/to/repository --budget 4000
```

### CLI Options

| Option | Flag | Default | Description |
| :--- | :---: | :---: | :--- |
| `--repo` | `-r` | `.` | Absolute or relative path to the target repository root. |
| `--budget` | `-b` | `4000` | Default token budget for retrieved context blocks. |
| `--transport` | | `stdio` | Transport protocol (`stdio`). |
| `--no-skeletons` | | `False` | Require full file bodies; disallow structural skeleton mode. |
| `--max-file-size-bytes` | | `500000` | Skip files strictly larger than this many bytes during the startup index. Must be a positive integer (zero/negative exits with code `1`). Skipped paths are reported by `reponeedle_inspect`. |

If files are excluded at startup, the server writes a one-line summary to `STDERR`, e.g. `[reponeedle-mcp] Indexing exclusions: 2 file(s) over 500000 bytes, 0 unreadable. Call reponeedle_inspect for the skipped paths.`

> [!IMPORTANT]
> **STDIO Cleanliness**: The MCP server sends all initialization logs and diagnostics exclusively to `STDERR`. `STDOUT` carries strictly formatted JSON-RPC messages, ensuring zero protocol framing corruption.

---

## 4. Client Configuration Examples

### 4.1 Claude Code CLI Integration

To add RepoNeedle as an MCP tool server in **Claude Code**, run (the `--` separates Claude Code's own options from the server command and its arguments):

```bash
claude mcp add reponeedle -- python -m reponeedle.mcp --repo /absolute/path/to/your/project
```

Or add an `mcpServers` entry to a Claude Code MCP configuration file (see the Claude Code documentation for the project- and user-scope file locations):

```json
{
  "mcpServers": {
    "reponeedle": {
      "command": "python",
      "args": [
        "-m",
        "reponeedle.mcp",
        "--repo",
        "/absolute/path/to/your/project",
        "--budget",
        "4000"
      ]
    }
  }
}
```

### 4.2 Cursor IDE Integration

In Cursor:
1. Open **Cursor Settings** $\to$ **Features** $\to$ **MCP**.
2. Click **+ Add New MCP Server**.
3. Configure the server:
   - **Name**: `reponeedle`
   - **Type**: `command`
   - **Command**: `python -m reponeedle.mcp --repo /absolute/path/to/your/project`

Or edit `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "reponeedle": {
      "command": "python",
      "args": [
        "-m",
        "reponeedle.mcp",
        "--repo",
        "/absolute/path/to/your/project"
      ]
    }
  }
}
```

---

## 5. Available MCP Tools

RepoNeedle exposes three tools to connected agents:

### 5.1 `reponeedle_retrieve`
Retrieves relevance-ranked source files, focus spans, and structural skeletons matching a natural language coding task, strictly packed within the requested token budget.

#### Input Schema
```json
{
  "query": "Fix authentication session expiration timeout",
  "budget_tokens": 4000,
  "ranker": "legacy",
  "task_type": "auto",
  "anchor_files": ["auth/session.py"],
  "enable_experimental_abstention": false
}
```

- `query` (*string*, required): Coding task, issue description, or traceback.
- `budget_tokens` (*integer*, default `4000`): Maximum context tokens.
- `ranker` (*string*, default `"legacy"`): Ranking algorithm (`legacy`, `bm25`, `arm101`, `cascade`, `change_impact`).
- `task_type` (*string*, default `"auto"`): Workflow intent (`auto`, `code2test`, `comment2context`, `trace2code`, `edit2ripple`, `selective`). `selective` does **not** enable abstention.
- `anchor_files` (*array of strings*, optional): Seed files used to condition retrieval.
- `enable_experimental_abstention` (*boolean*, default `false`): Opt in to the **experimental, uncalibrated** out-of-scope abstention heuristic. When `false`, the tool always returns ranked results (except for an empty repository) and does not detect out-of-scope queries. See [Section 5.4](#54-experimental-abstention).

#### Return Payload
```json
{
  "status": "success",
  "query": "Fix authentication session expiration timeout",
  "ranker": "legacy",
  "task_type": "comment2context",
  "abstained": false,
  "explanation": "Retrieved 3 files (1420/4000 tokens). Ranker: legacy. Task: comment2context. Experimental abstention disabled.",
  "budget_tokens": 4000,
  "total_tokens": 1420,
  "execution_time_ms": 12.4,
  "confidence_score": 0.84,
  "selected_files": [
    {
      "rank": 1,
      "path": "auth/session.py",
      "tier": "focus_span",
      "token_count": 450,
      "score": 0.8124,
      "explanation": "High-density implementation span"
    }
  ],
  "rendered_context": "# File: auth/session.py\n```python\n...\n```\n\n",
  "abstention": {
    "enabled": false,
    "status": "disabled",
    "experimental": true,
    "calibrated": false,
    "threshold": 0.12,
    "reason": "Experimental abstention disabled (default); out-of-scope queries are not detected and results are returned regardless of query scope."
  }
}
```

`confidence_score` is an uncalibrated heuristic signal, not a probability that the repository contains the answer.

---

### 5.2 `reponeedle_change_impact`
Identifies downstream files, dependent modules, and regression test suites affected by modifications to specific files. Implements verified R6 champion algorithms:
- **Seed File Suppression (SFS)**: Downweights seed files ($0.01\times$) so the agent is not re-fed files it already modified.
- **Test Intent Priors (TIP)**: Dynamically boosts associated regression test suites ($1.45\times$).
- **AST Dependency Traversal**: Confirmed imports, function calls, and directory proximity.

#### Input Schema
```json
{
  "anchor_files": [
    "auth/session.py",
    "auth/token.py"
  ],
  "query": "Assess authentication refactor impact",
  "budget_tokens": 4000
}
```

- `anchor_files` (*array of strings*, required): One or more modified or seed file paths.
- `query` (*string*, optional): Context description or task intent.
- `budget_tokens` (*integer*, default `4000`): Maximum context tokens.

---

### 5.3 `reponeedle_inspect`
Enables the coding agent to inspect the indexed repository state without dumping full source trees.

#### Input Schema
Takes no arguments (`{}`).

#### Return Payload
```json
{
  "status": "ready",
  "repository_root": "/absolute/path/to/project",
  "indexed_file_count": 148,
  "supported_file_types": [
    ".py", ".ts", ".js", ".tsx", ".jsx",
    ".go", ".rs", ".java", ".c", ".cpp",
    ".h", ".md", ".toml", ".yaml", ".yml", ".json"
  ],
  "indexed_path_examples": [
    "auth/session.py",
    "auth/token.py",
    "database/connection.py"
  ],
  "sample_count": 3,
  "active_rankers": ["arm101", "bm25", "cascade", "change_impact", "legacy"],
  "default_ranker": "legacy",
  "budget_config": {
    "max_tokens": 4000,
    "allow_skeletons": true,
    "mode": "auto"
  },
  "index_initialization": {
    "status": "initialized",
    "init_time_ms": 145.2,
    "message": "Repository indexed in-memory at server startup. Restart server to refresh index."
  },
  "indexing": {
    "source": "directory",
    "indexed_files": 148,
    "max_file_size_bytes": 500000,
    "skipped_large_files": 2,
    "skipped_paths": ["generated/large_module.py", "vendor/huge_source.cpp"],
    "skipped_unreadable_files": 0,
    "unreadable_paths": [],
    "skipped_symlink_outside_repository": 0,
    "symlink_outside_repository_paths": [],
    "skipped_directories": 0,
    "skipped_directory_paths": [],
    "skipped_directories_outside_repository": 0,
    "max_files": 3000,
    "max_files_reached": false
  },
  "abstention": {
    "default_enabled": false,
    "experimental": true,
    "calibrated": false,
    "threshold": 0.12,
    "opt_in": "Pass enable_experimental_abstention=true to reponeedle_retrieve."
  }
}
```

#### Indexing Diagnostics
The `indexing` object reports what the startup index excluded, so an agent can tell when a file it expects is missing:
- `skipped_paths` / `skipped_large_files`: supported-extension files strictly larger than `max_file_size_bytes` (set with `--max-file-size-bytes`). A file exactly at the limit is indexed.
- `unreadable_paths` / `skipped_unreadable_files`: files that could not be read (including broken links and link loops).
- `symlink_outside_repository_paths` / `skipped_symlink_outside_repository`: in-repository links whose target resolves outside the repository root. Their targets are never read; only the link path is listed.
- `skipped_directory_paths` / `skipped_directories`: directories that were not traversed. Directory symlinks and Windows junctions are never followed (files under a link target inside the repository are indexed once, under their real path), and a physical directory is never entered twice, so link cycles cannot cause repeated traversal. `skipped_directories_outside_repository` counts the links that resolve outside the repository root (or cannot be resolved); their contents are never listed or read.
- `max_files_reached`: `true` if indexing stopped at the `max_files` cap.

Paths are repository-relative with forward slashes and sorted. File contents are never included. Files excluded by `.gitignore`, built-in ignore patterns, or unsupported extensions are excluded by design and are not listed. Diagnostics describe the index built at server startup; restart the server to refresh them.

---

### 5.4 Experimental Abstention
RepoNeedle includes a heuristic that can abstain (return no files) when a query appears to be out of scope for the repository. It is **experimental and disabled by default**:

- **Why it is experimental**: on the official Agent Retrieval Bench v2 selective split it correctly abstained on **0 of 82** negative samples (100% false returns). Natural issues and wrong-repository queries share enough vocabulary with real code that the overlap, peakiness and margin signals do not separate them.
- **Why it is disabled by default**: leaving an uncalibrated filter on suggests that out-of-scope queries are being caught when they are not. With it disabled, agents should treat every result as candidate context, not as proof that the repository contains the answer.
- **How to enable it**: pass `"enable_experimental_abstention": true` to `reponeedle_retrieve`. The returned `abstention.status` is then `"evaluated"`, and an abstained response has `status: "abstained"`, empty `selected_files` and empty `rendered_context`.
- **`task_type: "selective"` does not enable it.** The task label only changes routing weights.
- `reponeedle_change_impact` never applies the heuristic.
- An empty repository always yields `abstained: true` with `abstention.status: "empty_repository"`, independent of the flag.

---

## 6. Security Boundaries

The RepoNeedle MCP server executes locally with read-only access to the configured repository. It enforces strict boundary controls:

1. **Explicit Root Configuration**: The repository root is fixed at server launch (`--repo`). Tool calls cannot specify or switch to arbitrary directories.
2. **Path Traversal Protection**: Tool path arguments (e.g. `anchor_files`) whose path climbs above the repository root (a leading `..` path component) or that point outside it are rejected with descriptive validation errors. Names that merely start with `..` (e.g. `..cache/x.py`) are legitimate and accepted.
3. **Symlink Escape Prevention**: Tool path arguments are resolved to their canonical location with `os.path.realpath()` and rejected if that lies outside the repository root. **Indexing applies the same rule**: every file is resolved before it is opened, files whose canonical location is outside the repository (symlinks; junctions on Windows) are skipped without reading the target, and only the in-repository link path is recorded (`symlink_outside_repository_paths`, reason `symlink_outside_repository`). Links that resolve inside the repository are indexed normally.
4. **Zero File Modification**: The server operates strictly read-only. It contains no file write, edit, or delete capabilities.
5. **Credential Safety**: Diagnostics, error messages, and inspection metadata never expose environment variables, API tokens, or secrets.

---

## 7. Operational Lifecycle & Index Refreshing

1. **Startup Ingestion**: The server parses repository ASTs and builds inverted postings indices **once** upon startup.
2. **In-Memory Query Re-use**: Subsequent tool calls execute against the pre-computed in-memory index, avoiding redundant disk scans. Query latency depends on repository size (small test repositories: a few milliseconds; ARB v2 real repositories: ~142 ms median).
4. **No Persistent Cache or File Watching**: The index is not persisted to disk and the server does not watch the filesystem; both are not implemented.
3. **Refreshing the Index**: When source files on disk change substantially, restart the MCP server process (or restart Claude Code / reload Cursor window) to rebuild the index.

---

## 8. Uninstalling Optional MCP Dependency

If MCP support is no longer needed:

```bash
pip uninstall mcp
```

RepoNeedle's core CLI (`reponeedle`) and Python API will continue functioning normally with zero missing dependency warnings.
