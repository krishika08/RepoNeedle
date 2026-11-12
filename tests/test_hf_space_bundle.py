"""
The Hugging Face Space and the demo API (api.py) run a copy of the engine bundled in
hf_artifacts/space/reponeedle. These tests keep that copy identical to the root package (minus the
optional MCP package), smoke-test the Gradio app on the bundled engine, and check the Hugging Face
release script's validation and upload safeguards without any network access.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPACE_DIR = ROOT / "hf_artifacts" / "space"
SCRIPT = ROOT / "scripts" / "prepare_hf_release.py"
TOKEN_SENTINEL = "hf_SENTINEL_never_print_7f3a9c"


def _load_release_script():
    spec = importlib.util.spec_from_file_location("prepare_hf_release_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def release():
    return _load_release_script()


# ---------------------------------------------------------------------------
# Bundle synchronisation
# ---------------------------------------------------------------------------

def test_bundled_engine_is_identical_to_root_package(release):
    problems = release.compare_bundle(str(ROOT / "reponeedle"), str(SPACE_DIR / "reponeedle"))
    assert problems == [], (
        "hf_artifacts/space/reponeedle has diverged from reponeedle/. Re-copy the changed files "
        "(everything except reponeedle/mcp/):\n" + "\n".join(problems)
    )


def test_bundle_excludes_optional_mcp_package():
    assert (ROOT / "reponeedle" / "mcp").is_dir()
    assert not (SPACE_DIR / "reponeedle" / "mcp").exists()
    for path in (SPACE_DIR / "reponeedle").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "reponeedle.mcp" not in text and "import mcp" not in text, path


def test_bundled_version_matches_project_version(release):
    project = release.read_project_version(str(ROOT))
    assert release.read_declared_version(str(ROOT / "reponeedle" / "__init__.py")) == project
    assert release.read_declared_version(str(SPACE_DIR / "reponeedle" / "__init__.py")) == project


def test_divergence_is_detected(release, tmp_path):
    bundle = tmp_path / "reponeedle"
    shutil.copytree(SPACE_DIR / "reponeedle", bundle, ignore=shutil.ignore_patterns("__pycache__"))
    assert release.compare_bundle(str(ROOT / "reponeedle"), str(bundle)) == []

    with open(bundle / "engine.py", "a", encoding="utf-8") as f:
        f.write("\n# local edit\n")
    (bundle / "core" / "router.py").unlink()
    (bundle / "extra.py").write_text("x = 1\n", encoding="utf-8")
    (bundle / "mcp").mkdir()
    (bundle / "mcp" / "server.py").write_text("", encoding="utf-8")

    problems = release.compare_bundle(str(ROOT / "reponeedle"), str(bundle))
    assert "content differs: reponeedle/engine.py" in problems
    assert "missing from bundle: reponeedle/core/router.py" in problems
    assert "not in root package (or excluded from the bundle): reponeedle/extra.py" in problems
    assert "not in root package (or excluded from the bundle): reponeedle/mcp/server.py" in problems


def test_line_ending_differences_are_not_divergence(release, tmp_path):
    root_pkg, bundle = tmp_path / "root", tmp_path / "bundle"
    root_pkg.mkdir()
    bundle.mkdir()
    (root_pkg / "a.py").write_bytes(b"x = 1\ny = 2\n")
    (bundle / "a.py").write_bytes(b"x = 1\r\ny = 2\r\n")
    assert release.compare_bundle(str(root_pkg), str(bundle)) == []


# ---------------------------------------------------------------------------
# Gradio Space smoke test (fresh process, bundled engine, no Gradio required)
# ---------------------------------------------------------------------------

_SPACE_SMOKE = r"""
import json, sys
sys.path.insert(0, "hf_artifacts/space")
import app, reponeedle
out = {"engine_file": reponeedle.__file__, "engine_version": reponeedle.__version__, "examples": []}
for example in app.EXAMPLES:
    status, rows, baseline, preview = app.run_reponeedle_demo(*example)
    out["examples"].append({"repo": example[0], "opt_in": example[6], "status": status,
                            "files": [r[1] for r in rows], "baseline_rows": len(baseline)})
default = app.run_reponeedle_demo(*app.EXAMPLES[-1][:6])
out["selective_default"] = {"status": default[0], "files": [r[1] for r in default[1]]}
out["gradio_installed"] = app.gr is not None
print("JSON:" + json.dumps(out))
"""


@pytest.fixture(scope="module")
def space_smoke():
    proc = subprocess.run(
        [sys.executable, "-c", _SPACE_SMOKE], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    line = next(l for l in proc.stdout.splitlines() if l.startswith("JSON:"))
    return json.loads(line[5:])


def test_space_runs_the_bundled_engine(space_smoke, release):
    assert Path(space_smoke["engine_file"]).resolve() == (SPACE_DIR / "reponeedle" / "__init__.py").resolve()
    assert space_smoke["engine_version"] == release.read_project_version(str(ROOT))


def test_space_examples_cover_both_repositories_and_retrieve(space_smoke):
    examples = space_smoke["examples"]
    assert {e["repo"] for e in examples} == {"pallets/flask", "psf/requests"}
    for e in examples:
        if not e["opt_in"]:
            assert "RETRIEVED CONTEXT" in e["status"], e["status"][:200]
            assert "Experimental Abstention**: disabled" in e["status"]
            assert e["files"] and e["baseline_rows"] > 0


def test_space_abstention_is_opt_in(space_smoke):
    opted_in = [e for e in space_smoke["examples"] if e["opt_in"]]
    assert len(opted_in) == 1, "exactly one example (the selective one) opts in explicitly"
    assert "ABSTAINED (experimental abstention, opt-in)" in opted_in[0]["status"]
    assert "uncalibrated" in opted_in[0]["status"]
    # The same query without the opt-in returns ranked context (the 1.2.0 default).
    default = space_smoke["selective_default"]
    assert "RETRIEVED CONTEXT" in default["status"]
    assert "Experimental Abstention**: disabled" in default["status"]
    assert default["files"]


def test_space_checkbox_defaults_to_unchecked():
    source = (SPACE_DIR / "app.py").read_text(encoding="utf-8")
    assert "gr.Checkbox(" in source
    checkbox = source[source.index("gr.Checkbox("):]
    checkbox = checkbox[: checkbox.index(")\n")]
    assert "value=False" in checkbox
    assert "experimental" in checkbox.lower() and "uncalibrated" in checkbox.lower()


# ---------------------------------------------------------------------------
# prepare_hf_release.py: validation and upload safeguards (fake Hub client, no network)
# ---------------------------------------------------------------------------

class _FakeHub:
    def __init__(self, space_sdk="gradio", space_exists=True, head_matches=True):
        self.calls = []
        self.space_sdk = space_sdk
        self.space_exists = space_exists
        self.head_matches = head_matches
        self.tokens_seen = []
        hub = self

        class RepositoryNotFoundError(Exception):
            pass

        class HfApi:
            def __init__(self, token=None):
                hub.tokens_seen.append(token)

            def whoami(self):
                return {"name": "RepoNeedle", "type": "user", "orgs": []}

            def repo_info(self, repo_id, repo_type):
                hub.calls.append(("repo_info", repo_type, repo_id))
                if repo_type == "space" and not hub.space_exists:
                    raise RepositoryNotFoundError(repo_id)
                sha = "uploaded-sha" if hub.head_matches else "someone-elses-sha"
                return types.SimpleNamespace(sha=sha, sdk=hub.space_sdk if repo_type == "space" else None)

            def create_repo(self, repo_id, repo_type, exist_ok, space_sdk=None):
                hub.calls.append(("create_repo", repo_type, repo_id))
                if repo_type == "space":
                    hub.space_exists = True
                    hub.space_sdk = space_sdk

            def upload_folder(self, folder_path, repo_id, repo_type, commit_message):
                hub.calls.append(("upload_folder", repo_type, repo_id))
                return types.SimpleNamespace(oid="uploaded-sha")

        self.module = types.ModuleType("huggingface_hub")
        self.module.HfApi = HfApi
        self.module.get_token = lambda: None

    def uploads(self):
        return [c for c in self.calls if c[0] in ("create_repo", "upload_folder")]


@pytest.fixture
def fake_hub(monkeypatch):
    def make(**kwargs):
        hub = _FakeHub(**kwargs)
        monkeypatch.setitem(sys.modules, "huggingface_hub", hub.module)
        return hub
    return make


@pytest.fixture
def no_token(monkeypatch, release):
    monkeypatch.setattr(release, "resolve_hf_token", lambda cli_token=None: None)


def test_check_only_without_token_validates_and_uploads_nothing(release, no_token, capsys):
    assert release.run_release(dry_run=True) == 0
    out = capsys.readouterr().out
    assert "Bundled reponeedle package is identical to the root package" in out
    assert "No repositories were created" not in out  # stopped before any Hub client was created
    assert "Dry-run completed local file validation" in out


def test_check_only_with_token_does_not_upload_or_print_token(release, fake_hub, capsys):
    hub = fake_hub()
    assert release.run_release(token=TOKEN_SENTINEL, dry_run=True) == 0
    out = capsys.readouterr().out
    assert hub.uploads() == []
    assert hub.tokens_seen == [TOKEN_SENTINEL]
    assert TOKEN_SENTINEL not in out
    assert "No repositories were created and no files were uploaded." in out


def test_space_only_does_not_touch_the_dataset(release, fake_hub, capsys):
    hub = fake_hub()
    assert release.run_release(token=TOKEN_SENTINEL, space_only=True) == 0
    out = capsys.readouterr().out
    assert hub.uploads() == [
        ("create_repo", "space", "RepoNeedle/RepoNeedle-Playground"),
        ("upload_folder", "space", "RepoNeedle/RepoNeedle-Playground"),
    ]
    assert not any(c[1] == "dataset" for c in hub.calls)
    assert TOKEN_SENTINEL not in out
    assert "--- [Validation] Dataset Artifacts ---" not in out


def test_dataset_and_space_flags_are_mutually_exclusive(release, fake_hub):
    hub = fake_hub()
    assert release.run_release(token=TOKEN_SENTINEL, space_only=True, dataset_only=True) == 1
    assert hub.calls == []


def test_refuses_to_upload_gradio_app_over_a_static_space(release, fake_hub, capsys):
    hub = fake_hub(space_sdk="static")
    assert release.run_release(repo_prefix="RepoNeedle", token=TOKEN_SENTINEL, space_only=True) == 1
    assert hub.uploads() == []
    assert "uses SDK 'static', not 'gradio'" in capsys.readouterr().out
    # The preflight reports the same problem.
    assert release.run_release(token=TOKEN_SENTINEL, space_only=True, dry_run=True) == 1


def test_missing_space_is_created_with_gradio_sdk(release, fake_hub):
    hub = fake_hub(space_exists=False)
    assert release.run_release(token=TOKEN_SENTINEL, space_only=True) == 0
    assert ("upload_folder", "space", "RepoNeedle/RepoNeedle-Playground") in hub.calls


def test_upload_is_verified_against_repository_head(release, fake_hub, capsys):
    hub = fake_hub(head_matches=False)
    assert release.run_release(token=TOKEN_SENTINEL, dataset_only=True) == 1
    assert "is not the uploaded commit" in capsys.readouterr().out


def _copy_release_tree(dst: Path) -> Path:
    ignore = shutil.ignore_patterns("__pycache__")
    shutil.copy2(ROOT / "pyproject.toml", dst / "pyproject.toml")
    shutil.copytree(ROOT / "reponeedle", dst / "reponeedle", ignore=ignore)
    shutil.copytree(ROOT / "hf_artifacts" / "space", dst / "hf_artifacts" / "space", ignore=ignore)
    shutil.copytree(ROOT / "hf_artifacts" / "dataset", dst / "hf_artifacts" / "dataset", ignore=ignore)
    return dst


def test_diverged_bundle_stops_publishing(release, fake_hub, tmp_path, capsys):
    root = _copy_release_tree(tmp_path)
    with open(root / "hf_artifacts" / "space" / "reponeedle" / "engine.py", "a", encoding="utf-8") as f:
        f.write("\n# drift\n")
    hub = fake_hub()
    assert release.run_release(token=TOKEN_SENTINEL, space_only=True, root_dir=str(root)) == 1
    out = capsys.readouterr().out
    assert "content differs: reponeedle/engine.py" in out
    assert "Release aborted" in out
    assert hub.calls == [] and hub.tokens_seen == []


def test_version_mismatch_stops_publishing(release, fake_hub, tmp_path, capsys):
    root = _copy_release_tree(tmp_path)
    init = root / "hf_artifacts" / "space" / "reponeedle" / "__init__.py"
    text = init.read_text(encoding="utf-8")
    project = release.read_project_version(str(ROOT))
    init.write_text(text.replace(f'__version__ = "{project}"', '__version__ = "1.1.0"'), encoding="utf-8")
    hub = fake_hub()
    assert release.run_release(token=TOKEN_SENTINEL, space_only=True, root_dir=str(root)) == 1
    assert "Version mismatch" in capsys.readouterr().out
    assert hub.calls == []
