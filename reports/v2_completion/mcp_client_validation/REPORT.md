# V2 Milestone 1: Real MCP Client Integration Validation

**Date:** 2026-11-16 (UTC timestamps below)
**Branch:** `integration/v2-live-mcp-validation`, from `main` at `d4dfd0b`. The package code is identical to tag `v1.2.0`.
**Result:**

| Client | Status |
| :--- | :--- |
| Claude Code 2.1.81 (Windows, STDIO, print mode) | **VERIFIED** |
| Cursor 2.6.20 | **NOT TESTED** |
| Cline | **NOT TESTED** (not installed) |
| Windsurf | **NOT TESTED** (not installed) |

No RepoNeedle defect was found, so no code was changed.

Status terms: **VERIFIED** means observed working end to end in that client. **PARTIALLY VERIFIED** means only some steps were observed. **NOT TESTED** means no tool call was made in that client. **FAILED** means it was attempted and did not work.

## 1. Environment

| Item | Value |
| :--- | :--- |
| Operating system | Windows 11 Home Single Language, build 10.0.26200 (`Windows-11-10.0.26200-SP0`), x64 |
| Python | CPython 3.12.10, the system interpreter on `PATH` |
| RepoNeedle | 1.2.0 from PyPI. All 23 installed modules are byte-identical to the published `reponeedle-1.2.0-py3-none-any.whl`. |
| MCP SDK | `mcp` 1.30.0 |
| Claude Code | 2.1.81 (`claude --version`); session model reported as `claude-opus-4-6` (the CLI default) |
| Cursor | 2.6.20 (commit `b29eb4ee`, build date 2026-03-17) |
| Server commands tested | `python.exe -m reponeedle.mcp --repo <fixture>` and `reponeedle-mcp.exe --repo <fixture>` |
| Transport | STDIO only; RepoNeedle has no other transport |

## 2. Fixture repository

`make_fixture.py` (in this folder) creates a synthetic `shopcart` package outside the RepoNeedle repository. It contains 10 files and no real data:

| File | Role |
| :--- | :--- |
| `shopcart/pricing.py` | Utility: `apply_discount`, `add_tax`, `round_currency` |
| `shopcart/cart.py` | Application module; imports `pricing` |
| `shopcart/checkout.py` | Application module; imports `cart` and `pricing` |
| `shopcart/inventory.py` | Unrelated control module |
| `tests/test_pricing.py`, `tests/test_cart.py`, `tests/test_checkout.py` | Tests |

`pricing.py` deliberately contains a bug: `apply_discount` accepts percentages above 100. The fixture's own tests pass (8 passed).

## 3. Server checks (raw JSON-RPC over STDIO, no SDK client)

`stdio_protocol_check.py` drives the installed server with hand-written JSON-RPC, protocol `2025-06-18`. It passed **17/17** with each command form (`evidence/stdio_protocol_*.json`).

| Check | Result |
| :--- | :--- |
| `reponeedle-mcp --help`, `python -m reponeedle.mcp --help` | Exit 0 |
| `initialize` | `serverInfo` = `{"name": "reponeedle", "version": "1.2.0"}`; protocol `2025-06-18` negotiated; `tools` capability advertised |
| `tools/list` | Exactly `reponeedle_retrieve`, `reponeedle_change_impact`, `reponeedle_inspect` |
| `tools/call` for each tool | Success (results in §4) |
| Path arguments | Rejected as tool errors, with no file read:<br>• `../outside.py`, which doesn't exist;<br>• an existing file next to the fixture, by relative path (`../outside_marker.py`) and by absolute path. The message is `Security boundary violation`, and the file's content never appears. |
| Empty query, unknown tool | Rejected as tool errors |
| stdout | Only JSON-RPC 2.0 messages (10 lines, 0 invalid) |
| stderr | Contains the `[reponeedle-mcp] …` diagnostics |
| Shutdown | Exit 0 about 0.4 s after stdin closes |
| Read-only | The fixture's files and hashes are identical before and after |
| Missing `--repo` directory | Exit 1, message on stderr, nothing on stdout |

## 4. Claude Code 2.1.81: **VERIFIED**

### 4.1 Registration (project scope, inside the fixture only)

Run inside the fixture at 2026-11-16T16:45:14Z:

```text
$ claude mcp add --scope project reponeedle -- "<python.exe>" -m reponeedle.mcp --repo "<fixture>"
Added stdio MCP server reponeedle ... to project config
File modified: <fixture>\.mcp.json
```

The generated `.mcp.json`:

```json
{
  "mcpServers": {
    "reponeedle": {
      "type": "stdio",
      "command": "<python.exe>",
      "args": ["-m", "reponeedle.mcp", "--repo", "<fixture>"],
      "env": {}
    }
  }
}
```

- `claude mcp list` reported `reponeedle: … - ✓ Connected`.
- `claude mcp get reponeedle` reported `Scope: Project config (shared via .mcp.json)` and `Status: ✓ Connected`.
- Installed CLI syntax: `claude mcp add [options] <name> <commandOrUrl> [args...]`, where `-s/--scope` is `local` (default), `user` or `project`, and `--` separates the server command.

### 4.2 Sessions

All sessions ran with the parent session's `CLAUDE*` environment variables removed, so each behaved like a user-launched CLI.

| # | Time (UTC) | Configuration | Server command | Allowed tools |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 16:45:36–16:46:11 | `--mcp-config .mcp.json --strict-mcp-config` | `python -m reponeedle.mcp` | the 3 RepoNeedle tools |
| 2 | 16:46:41–16:47:23 | inline `--mcp-config '<json>' --strict-mcp-config` (no file) | `reponeedle-mcp.exe` | 3 RepoNeedle tools, `Read`, `Edit`, `Bash(python -m pytest:*)` |
| 3 | 16:47:49 | project `.mcp.json` from §4.1, picked up automatically (no `--mcp-config`) | `python -m reponeedle.mcp` | `reponeedle_inspect` |

Common flags: `-p --permission-mode dontAsk --output-format stream-json --verbose --no-session-persistence --max-budget-usd 3` (session 3 used a $1 cap). Every session ended `success`, with 0 tool errors and 0 permission denials.

**Tool discovery (Claude Code's own `init` event, every session):**
- `mcp_servers: [{"name": "reponeedle", "status": "connected"}]`
- `mcp__reponeedle__reponeedle_retrieve`, `mcp__reponeedle__reponeedle_change_impact`, `mcp__reponeedle__reponeedle_inspect`

Claude Code loads MCP tool schemas lazily: it fetched them with its `ToolSearch` tool before the first call.

**Tool calls made by Claude Code:**

| Session | Call | Result |
| :--- | :--- | :--- |
| 1 | `reponeedle_inspect {}` | `ready`; 11 files indexed (the 10 fixture files plus the project `.mcp.json`; see F1) |
| 1 | `reponeedle_retrieve {query: "Where is the discount applied to the cart total, and which tests cover it?", budget_tokens: 2000}` | `success`, 1262/2000 tokens. In rank order: `tests/test_cart.py`, `tests/test_checkout.py`, `shopcart/cart.py`, `shopcart/checkout.py`, `tests/test_pricing.py`, `README.md`, `shopcart/pricing.py`, … |
| 1 | `reponeedle_change_impact {anchor_files: ["shopcart/pricing.py"]}` | `success`. `cart.py`, `tests/test_pricing.py` and `checkout.py` flagged as "Confirmed AST import from seed 'pricing.py'"; the seed was suppressed (SFS). |
| 2 | `reponeedle_retrieve` with Claude's own bug query | `shopcart/pricing.py` rank 1, `tests/test_pricing.py` rank 2 |
| 2 | `reponeedle_change_impact {anchor_files: ["shopcart/pricing.py"], query: …}` | `tests/test_pricing.py` top-ranked; `cart.py` and `checkout.py` listed as dependants |
| 3 | `reponeedle_inspect {}` | `indexed_file_count` 11, `default_ranker` `legacy` |

**Coding workflow (session 2).** Prompt: fix discounts above 100%, consult RepoNeedle first, add a regression test, run the tests.
1. Claude called `reponeedle_retrieve`, then `reponeedle_change_impact`.
2. It read the two files RepoNeedle ranked first, `pricing.py` and `test_pricing.py`.
3. It added `if percent > 100: raise ValueError(...)` to `apply_discount` and `test_discount_above_100_rejected` to `tests/test_pricing.py`.
4. It ran `python -m pytest -q`: **9 passed**.

Its final answer cited the RepoNeedle rankings as the reason for which file it changed and which tests it ran. An independent diff against a fresh copy of the fixture shows exactly those two edits, and an independent `pytest` run also gives 9 passed.

Cost and duration:

| Session | Cost | Duration |
| :--- | :--- | :--- |
| 1 | $0.133 | 29.6 s |
| 2 | $0.201 | 38.9 s |
| 3 | $0.025 | 6.2 s |

### 4.3 Cleanup and configuration isolation

- `claude mcp remove reponeedle -s project` left `{"mcpServers": {}}`. The fixture's `.mcp.json` was then deleted.
- Before testing, the user had **no** MCP servers configured in `~/.claude.json` (top level or local scope), `~/.claude/settings*.json` or `~/.mcp.json`. After testing, those MCP sections were unchanged, and no project entries were created for the fixture paths.
- One side effect was found and reverted (F3).

### 4.4 Not covered for Claude Code

- **Interactive (TUI) sessions: NOT TESTED.** That includes the approval prompt shown for project `.mcp.json` servers.
- **`local` and `user` scopes: NOT TESTED.** They were avoided on purpose so the user's configuration was not modified.
- **macOS and Linux clients: NOT TESTED.**

## 5. Other clients

| Client | Installed? | Status | Notes |
| :--- | :--- | :--- | :--- |
| Cursor | Yes, 2.6.20 | **NOT TESTED** | No headless agent CLI is installed (no `cursor-agent`), and MCP tools are only callable from Cursor's interactive Agent chat, so no tool call was made. Read-only inspection of the installed 2.6.20 bundle shows it reads `.cursor/mcp.json` (an `mcpServers` map). There is no user-level `~/.cursor/mcp.json`, and no Cursor configuration was changed. |
| Cline | No: absent from VS Code 1.146.0 and Cursor extensions | **NOT TESTED** | — |
| Windsurf | No: no install directory, no `PATH` entry, no `~/.codeium/windsurf` | **NOT TESTED** | — |

## 6. Findings

None of these is a RepoNeedle MCP compatibility defect, so there were no code changes.

| ID | Finding | Impact and action |
| :--- | :--- | :--- |
| F1 | A project-scope `.mcp.json` at the repository root is indexed like any other JSON file. It was counted by `reponeedle_inspect`, ranked by `reponeedle_retrieve`, and returned in `rendered_context`. That text includes the server command and absolute paths. | Expected behaviour (the file is part of the repository, and the agent could already read it). It does use context tokens. Documented in `docs/MCP_INTEGRATION.md`. Avoid putting secrets in `.mcp.json` `env` entries. |
| F2 | Windows Smart App Control blocked the unsigned pip launcher `reponeedle.exe` (CodeIntegrity events 3033 and 3077, "An Application Control policy has blocked this file"). `reponeedle-mcp.exe` was blocked once, then ran consistently. | Host policy, not RepoNeedle. `python -m reponeedle.mcp` (with an absolute `python.exe`) is the reliable form on such hosts; documented. |
| F3 | Starting Claude Code 2.1.81 rewrote `~/.claude/settings.json` (at 16:45:40Z), reordering two keys without changing any value. | Client behaviour, outside RepoNeedle. The original was reconstructed from its pre-test SHA-256 and restored **byte-identically**. |
| F4 | On this tiny fixture every file fits in the budget, so retrieval returns all files and ranking quality **cannot** be judged. With the generic discount query, `pricing.py` ranked 7th; with Claude's bug-specific query it ranked 1st. | Validation scope only. No retrieval claim is made from this fixture. |
| F5 | `reponeedle_change_impact` scored the unrelated `shopcart/inventory.py` as a directory sibling (+0.75), close to the real importers. | Existing documented heuristic. Not changed (ranking is out of scope). |
| F6 | Tool error messages include the absolute repository path. | The client is local, so there is no exposure beyond that machine. Not changed. |

## 7. Tests

| Run | Result |
| :--- | :--- |
| MCP tests (`test_mcp_server.py`, `test_mcp_tools.py`, `test_mcp_optional_dependency.py`) on system Python 3.12.10 with `mcp` 1.30.0 | 24 passed, 1 skipped (symlink creation not permitted on this Windows host) |
| Full suite (Windows, Python 3.12, editable working tree) | 532 passed, 7 skipped (Windows symlink permission) |
| Strict CI list with `REPONEEDLE_FAIL_ON_SKIP=1`, run locally | 169 passed, but the run fails as designed because the 7 symlink skips cannot run on Windows. No Linux environment (WSL/Docker) is available locally. |
| Strict Linux job in CI on `main` `d4dfd0b` (identical package code): [run 43204511755](https://github.com/krishika08/RepoNeedle/actions/runs/43204511755) | 155 passed, 0 skipped; `serverInfo OK: {'name': 'reponeedle', 'version': '1.2.0'}`. This branch was not pushed, so it has no CI run of its own. |
| Package import and console scripts (installed package, neutral working directory) | `import reponeedle, reponeedle.mcp.server, reponeedle.cli` OK (1.2.0).<br>`reponeedle-mcp --help` exit 0; `python -m reponeedle.mcp --help` exit 0; `reponeedle.cli:main --help` exit 0; missing `--repo` exit 1.<br>`reponeedle.exe` was blocked by Smart App Control (F2). |
| Raw STDIO protocol check (§3) | 17/17 for each command form |
| Claude Code sessions (§4) | 3/3 successful; all three tools invoked; 0 tool errors |

## 8. Reproducing

```bash
pip install "reponeedle[mcp]==1.2.0"
python make_fixture.py <scratch>/shopcart_fixture
python stdio_protocol_check.py <scratch>/shopcart_fixture evidence.json                 # console script
python stdio_protocol_check.py <scratch>/shopcart_fixture evidence.json python -m reponeedle.mcp

cd <scratch>/shopcart_fixture
claude mcp add --scope project reponeedle -- <absolute python.exe> -m reponeedle.mcp --repo <absolute fixture path>
claude mcp list
claude -p "<prompt from evidence/claude_code_session1_tool_calls.json>" \
  --mcp-config .mcp.json --strict-mcp-config \
  --allowedTools "mcp__reponeedle__reponeedle_inspect,mcp__reponeedle__reponeedle_retrieve,mcp__reponeedle__reponeedle_change_impact" \
  --permission-mode dontAsk --output-format stream-json --verbose --no-session-persistence
claude mcp remove reponeedle -s project
```

If you run this from inside another Claude Code session, unset the inherited `CLAUDE*` variables first.

## 9. Evidence files

All paths are redacted to `<HOME>` / `<SCRATCH>`.

| File | Contents |
| :--- | :--- |
| `evidence/stdio_protocol_console_script.json`, `evidence/stdio_protocol_python_module.json` | Raw protocol checks |
| `evidence/claude_code_session1_tool_calls.json` | Discovery and all three tools |
| `evidence/claude_code_session2_coding_workflow.json` | Coding workflow |
| `evidence/claude_code_session3_project_scope.json` | Persisted project-scope registration |

Each Claude Code file records the exact command, the prompt, Claude Code's `init` event (version, model, MCP status, discovered tools), every tool call and result, and the final stats.

## 10. Limitations and open items

- Only one client (Claude Code) was exercised, on one OS (Windows) and in non-interactive mode. This does **not** establish compatibility with other clients, other operating systems, or interactive Claude Code sessions.
- Cursor needs a manual interactive test:
  1. Put a `.cursor/mcp.json` in a test project.
  2. Ask the Agent to call `reponeedle_inspect`.
  3. Record the version and the tool output.
- Cline and Windsurf need installation before they can be tested.
- The fixture is too small to evaluate retrieval quality (F4). Use the documented benchmark evaluations for that.
