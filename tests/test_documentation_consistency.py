"""
Milestone 1D: guards against documentation drifting away from the implementation.

These checks validate real configuration and invocation behaviour (CLI parsers, pyproject
metadata, benchmark abstention policy, MCP tool schemas) and look only for a small set of
specific, known-bad claim patterns. They deliberately avoid asserting exact prose.
"""

import asyncio
import pathlib
import re
import shlex
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python 3.10 uses the declared tomli dependency
    import tomli as tomllib

PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
BENCH_CONFIG = ROOT / "docs" / "BENCHMARK_CONFIGURATION.md"

# Living documents that describe the *current* state (historical reports are excluded on purpose).
CURRENT_DOCS = [
    ROOT / "README.md",
    ROOT / "KNOWN_LIMITATIONS.md",
    ROOT / "CLAIMS_AND_EVIDENCE.md",
    ROOT / "docs" / "MCP_INTEGRATION.md",
    ROOT / "docs" / "ROADMAP.md",
    ROOT / "docs" / "BENCHMARK_CONFIGURATION.md",
    ROOT / "docs" / "ANNOUNCEMENT.md",  # historical, but corrected in place and publicly linked
]
USER_FACING_DOCS = [ROOT / "README.md", ROOT / "docs" / "MCP_INTEGRATION.md"]


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _table_paths(doc: str, block: str) -> list:
    m = re.search(rf"<!-- {block}:start -->(.*?)<!-- {block}:end -->", doc, re.S)
    assert m, f"marker block '{block}' missing from docs/BENCHMARK_CONFIGURATION.md"
    return re.findall(r"^\|\s*`([^`]+\.py)`", m.group(1), re.M)


def _code_blocks(text: str, langs=("bash", "sh", "")) -> list:
    return [body for lang, body in re.findall(r"```(\w*)\n(.*?)```", text, re.S) if lang in langs]


# ---------------------------------------------------------------------------
# Benchmark abstention policy
# ---------------------------------------------------------------------------

class TestBenchmarkAbstentionPolicy:

    def test_documented_opt_in_scripts_really_opt_in(self):
        paths = _table_paths(_read(BENCH_CONFIG), "abstention-opt-in-scripts")
        assert paths, "opt-in table is empty"
        for rel in paths:
            src = (ROOT / rel)
            assert src.is_file(), f"{rel} listed in BENCHMARK_CONFIGURATION.md does not exist"
            text = _read(src)
            assert re.search(r"enable_experimental_abstention\s*=\s*(True|is_selective)\b", text), (
                f"{rel} is documented as enabling experimental abstention but never does"
            )

    def test_every_script_reading_engine_abstention_is_classified(self):
        """A new script that reads `.abstained` from RepoNeedleEngine results must declare a policy."""
        doc = _read(BENCH_CONFIG)
        classified = set(_table_paths(doc, "abstention-opt-in-scripts")) | set(
            _table_paths(doc, "abstention-default-exempt")
        )
        unclassified = []
        for d in ("benchmarks", "research", "scripts"):
            for p in (ROOT / d).rglob("*.py"):
                text = p.read_text(encoding="utf-8", errors="ignore")
                if "RepoNeedleEngine" in text and re.search(r"\b\w+\.abstained\b", text):
                    rel = p.relative_to(ROOT).as_posix()
                    if rel not in classified:
                        unclassified.append(rel)
        assert not unclassified, (
            "These scripts read RepoNeedleEngine abstention results but are not listed in "
            f"docs/BENCHMARK_CONFIGURATION.md (opt-in or exempt table): {unclassified}"
        )

    def test_synthetic_runner_enables_heuristic_only_for_selective_samples(self, monkeypatch):
        """Invokes the real benchmark harness and records how it calls the engine."""
        sys.path.insert(0, str(ROOT))
        import benchmarks.runner as runner_mod
        from reponeedle.engine import RepoNeedleEngine
        from reponeedle.models import TaskType

        calls = []
        original = RepoNeedleEngine.retrieve

        def spy(self, query, *args, **kwargs):
            task = getattr(query, "task_type", None)
            calls.append((task, kwargs.get("enable_experimental_abstention")))
            return original(self, query, *args, **kwargs)

        monkeypatch.setattr(RepoNeedleEngine, "retrieve", spy)
        bench = runner_mod.BenchmarkRunner()
        selective = [s for s in bench.samples if s.task_type == TaskType.SELECTIVE][:1]
        positive = [s for s in bench.samples if s.task_type != TaskType.SELECTIVE][:1]
        assert selective and positive
        bench.samples = selective + positive
        result = bench.run_all()

        sel_calls = [flag for task, flag in calls if task == TaskType.SELECTIVE]
        pos_calls = [flag for task, flag in calls if task != TaskType.SELECTIVE]
        assert sel_calls and all(flag is True for flag in sel_calls)
        assert pos_calls and all(not flag for flag in pos_calls)
        assert "SelectiveAccuracy" in result["RepoNeedle"]

    def test_reproducibility_script_reports_missing_data(self, monkeypatch, tmp_path):
        sys.path.insert(0, str(ROOT / "scripts"))
        import verify_abstention_reproducibility as v

        monkeypatch.setattr(v, "ARB_DIR", tmp_path / "missing_arb")
        monkeypatch.setattr(v, "REPORT_DIR", tmp_path / "missing_reports")
        assert v.main([]) == 2
        with pytest.raises(SystemExit) as exc:
            v.main(["--help"])
        assert exc.value.code == 0


# ---------------------------------------------------------------------------
# Abstention default and stale claims
# ---------------------------------------------------------------------------

class TestAbstentionClaims:

    def test_default_is_disabled_and_documented_as_such(self):
        from reponeedle.models import BudgetConfig
        assert BudgetConfig().enable_experimental_abstention is False
        for doc in (ROOT / "README.md", ROOT / "KNOWN_LIMITATIONS.md", ROOT / "docs" / "MCP_INTEGRATION.md"):
            assert "disabled by default" in _read(doc).lower(), f"{doc.name} does not state the default"

    def test_documented_engine_threshold_matches_code(self):
        from reponeedle.models import BudgetConfig
        threshold = BudgetConfig().abstention_threshold
        for doc in (ROOT / "KNOWN_LIMITATIONS.md", ROOT / "CLAIMS_AND_EVIDENCE.md"):
            text = _read(doc)
            assert f"{threshold}" in text, f"{doc.name} does not mention the engine threshold {threshold}"
            for line in text.splitlines():
                if re.search(r"default abstention threshold[^.]*0\.38", line, re.I):
                    assert re.search(r"correct|not used|unused", line, re.I), f"stale threshold claim: {line}"

    @pytest.mark.parametrize("pattern", [
        r"calibrated selective abstention",
        r"100\s*%\s*selective abstention",
        r"100\s*%\s*test coverage",
        r"production[- ]ready in (reponeedle )?1\.2",
    ])
    def test_known_false_claims_only_appear_as_corrections(self, pattern):
        correction = re.compile(r"retract|refut|incorrect|correct(ed|ion)|not (supported|calibrated)", re.I)
        offenders = []
        for doc in CURRENT_DOCS:
            for no, line in enumerate(_read(doc).splitlines(), start=1):
                if re.search(pattern, line, re.I) and not correction.search(line):
                    offenders.append(f"{doc.relative_to(ROOT)}:{no}: {line.strip()[:120]}")
        assert not offenders, "Uncorrected false claim(s):\n" + "\n".join(offenders)


# ---------------------------------------------------------------------------
# Release status, test counts, installation examples
# ---------------------------------------------------------------------------

class TestReleaseAndInstallDocs:

    def test_package_version_is_consistent(self):
        import reponeedle
        assert PYPROJECT["project"]["version"] == reponeedle.__version__

    def test_unreleased_version_is_never_described_as_released(self):
        version = tuple(int(x) for x in PYPROJECT["project"]["version"].split(".")[:2])
        if version >= (1, 2):
            pytest.skip("1.2 is the packaged version; release wording is no longer forward-looking")
        qualifier = re.compile(
            r"planned|unreleased|not yet|development branch|until|once|upcoming|pending|candidate", re.I
        )
        offenders = []
        for doc in CURRENT_DOCS:
            for no, line in enumerate(_read(doc).splitlines(), start=1):
                if re.search(r"\b1\.2(\.0)?\b", line) and not qualifier.search(line):
                    if re.search(r"releas|availab|ship|production|since|in 1\.2", line, re.I):
                        offenders.append(f"{doc.relative_to(ROOT)}:{no}: {line.strip()[:120]}")
        assert not offenders, "Lines presenting unreleased 1.2 as released:\n" + "\n".join(offenders)

    def test_no_hard_coded_test_counts_in_user_docs(self):
        for doc in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]:
            m = re.search(r"\b\d{2,4}\s+(?:tests?\s+)?passed\b", _read(doc))
            assert not m, f"{doc.relative_to(ROOT)} hard-codes a test count ('{m.group(0)}'); it will go stale"

    def test_python_requirement_matches_docs(self):
        assert PYPROJECT["project"]["requires-python"] == ">=3.10"
        assert "3.10" in _read(ROOT / "README.md")
        assert "3.10" in _read(ROOT / "docs" / "MCP_INTEGRATION.md")

    def test_documented_extras_exist(self):
        extras = set(PYPROJECT["project"].get("optional-dependencies", {}))
        for doc in USER_FACING_DOCS:
            for extra in re.findall(r"(?:reponeedle|\.)\[([a-z0-9_-]+)\]", _read(doc)):
                assert extra in extras, f"{doc.name} references unknown extra '[{extra}]'"

    def test_documented_console_scripts_exist(self):
        scripts = set(PYPROJECT["project"]["scripts"])
        for doc in USER_FACING_DOCS:
            for block in _code_blocks(_read(doc)):
                for line in block.splitlines():
                    tok = line.strip().split(" ", 1)[0]
                    if tok.startswith("reponeedle"):
                        assert tok in scripts, f"{doc.name} uses unknown command '{tok}'"

    def test_documented_cli_flags_exist(self):
        from reponeedle.cli import build_parser as cli_parser
        from reponeedle.mcp.server import build_parser as mcp_parser_fn
        parsers = {
            "reponeedle": cli_parser(),
            "reponeedle-mcp": mcp_parser_fn(),
            "python -m reponeedle.mcp": mcp_parser_fn(),
        }
        known = {name: {o for a in p._actions for o in a.option_strings} for name, p in parsers.items()}
        checked = 0
        for doc in USER_FACING_DOCS:
            for block in _code_blocks(_read(doc)):
                for line in block.splitlines():
                    line = line.split("#", 1)[0].strip()
                    for prefix, opts in sorted(known.items(), key=lambda kv: -len(kv[0])):
                        if line.startswith(prefix + " ") or line == prefix:
                            for tok in shlex.split(line, posix=True):
                                flag = tok.split("=", 1)[0]
                                if flag.startswith("--"):
                                    checked += 1
                                    assert flag in opts, f"{doc.name}: '{flag}' is not a '{prefix}' option"
                            break
        assert checked > 5, "expected to validate CLI flags from documentation examples"


# ---------------------------------------------------------------------------
# MCP documentation vs registered tools
# ---------------------------------------------------------------------------

class TestMCPDocs:

    def test_documented_tools_and_arguments_exist(self, tmp_path):
        pytest.importorskip("mcp")
        from reponeedle.mcp.server import create_mcp_server

        (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        app = create_mcp_server(repo_dir=str(tmp_path))
        tools = {t.name: t for t in asyncio.run(app.list_tools())}
        doc = _read(ROOT / "docs" / "MCP_INTEGRATION.md")

        documented = set(re.findall(r"`(reponeedle_[a-z_]+)`", doc))
        assert documented == set(tools), f"documented {sorted(documented)} vs registered {sorted(tools)}"

        retrieve_props = set(tools["reponeedle_retrieve"].inputSchema["properties"])
        section = doc.split("### 5.1 `reponeedle_retrieve`", 1)[1].split("### 5.2", 1)[0]
        doc_args = set(re.findall(r"^- `([a-z_]+)` \(\*", section, re.M))
        assert doc_args == retrieve_props, f"documented {sorted(doc_args)} vs schema {sorted(retrieve_props)}"
