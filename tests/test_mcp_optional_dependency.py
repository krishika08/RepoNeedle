"""
The MCP server entrypoint must fail gracefully (friendly stderr message, exit code 1) when the
optional 'mcp' extra is not installed, and the core package must remain importable.
"""

import subprocess
import sys

# Simulate a missing 'mcp' distribution in a fresh interpreter: a None entry in sys.modules
# makes any `import mcp...` raise ImportError.
_BLOCK_MCP = "import sys; sys.modules['mcp'] = None; "


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", _BLOCK_MCP + code],
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )


def test_core_package_imports_without_mcp():
    proc = _run("import reponeedle, reponeedle.cli; print('ok')")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"


def test_mcp_entrypoint_reports_missing_extra_without_traceback():
    proc = _run("from reponeedle.mcp.server import main; raise SystemExit(main(['--repo', '.']))")
    assert proc.returncode == 1
    assert "pip install 'reponeedle[mcp]'" in proc.stderr
    assert "Traceback" not in proc.stderr
    assert proc.stdout == ""
