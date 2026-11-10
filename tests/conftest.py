"""
Shared pytest configuration.

Strict no-skip mode: when REPONEEDLE_FAIL_ON_SKIP=1 is set (used by the Linux MCP/security CI job),
any skipped test or skipped module fails the run. This guarantees that MCP tests and symlink
security tests actually execute in that job instead of silently skipping.
"""

import os


def pytest_sessionfinish(session, exitstatus):
    if os.environ.get("REPONEEDLE_FAIL_ON_SKIP") != "1":
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    skipped = reporter.stats.get("skipped", []) if reporter else []
    if skipped:
        if reporter:
            reporter.write_line(
                f"REPONEEDLE_FAIL_ON_SKIP=1: {len(skipped)} test(s) or module(s) were skipped; failing the run.",
                red=True,
            )
        session.exitstatus = 1
