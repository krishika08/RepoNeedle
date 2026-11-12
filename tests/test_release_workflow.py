"""
Structural checks for .github/workflows/release.yml.

Guards the release security model (read-only test and build jobs, OIDC only in the publish job,
publish gated on validate and build, protected `pypi` environment) and the release-ref handling:
full-history checkouts of the exact release tag for both tag pushes and manual dispatches.

Not part of the strict no-skip Linux job: PyYAML is installed with the `api` extra
(`uvicorn[standard]`), which the strict job does not install.
"""

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOW_PATH = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "release.yml"
TAG_EXPR = "github.event_name == 'workflow_dispatch' && inputs.tag || github.ref_name"


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _triggers(wf):
    # PyYAML (YAML 1.1) parses the bare key `on` as boolean True.
    return wf.get("on", wf.get(True))


def _step(job, name_prefix):
    matches = [s for s in job["steps"] if s.get("name", "").startswith(name_prefix)]
    assert len(matches) == 1, f"expected one step starting with {name_prefix!r}, found {len(matches)}"
    return matches[0]


def _checkout_steps(job):
    return [s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout@")]


def test_tag_push_trigger_is_preserved(workflow):
    triggers = _triggers(workflow)
    assert triggers["push"] == {"tags": ["v*"]}
    assert set(triggers) == {"push", "workflow_dispatch"}


def test_manual_dispatch_requires_a_tag_input(workflow):
    inputs = _triggers(workflow)["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"tag"}
    assert inputs["tag"]["required"] is True
    assert inputs["tag"]["type"] == "string"


def test_release_tag_is_derived_from_the_event(workflow):
    assert workflow["env"]["RELEASE_TAG"] == "${{ " + TAG_EXPR + " }}"
    assert workflow["concurrency"]["group"] == "release-${{ " + TAG_EXPR + " }}"
    assert workflow["concurrency"]["cancel-in-progress"] is False


@pytest.mark.parametrize("job_name", ["validate", "build"])
def test_validate_and_build_check_out_the_release_tag_with_full_history(workflow, job_name):
    checkouts = _checkout_steps(workflow["jobs"][job_name])
    assert len(checkouts) == 1
    opts = checkouts[0]["with"]
    assert opts["ref"] == "refs/tags/${{ env.RELEASE_TAG }}"
    assert opts["fetch-depth"] == 0
    assert opts["persist-credentials"] is False


def test_validate_guards_trigger_tag_format_and_commit(workflow):
    steps = workflow["jobs"]["validate"]["steps"]
    names = [s.get("name", "") for s in steps]
    guard = names.index("Check release trigger and tag name")
    checkout = names.index("Checkout the release tag (full history and tags)")
    verify = names.index("Verify the checked-out commit is the release tag")
    assert guard < checkout < verify, "trigger guard must run before checkout, commit check right after"

    guard_script = steps[guard]["run"]
    assert 'refs/heads/main' in guard_script
    assert '"refs/tags/${RELEASE_TAG}"' in guard_script
    pattern = re.search(r"tag_pattern='([^']+)'", guard_script).group(1)
    for good in ["v1.2.0", "v10.0.1", "v1.3.0rc1", "v1.2.0.post1"]:
        assert re.fullmatch(pattern, good), good
    for bad in ["main", "1.2.0", "v1.2", "v0.1.0-baseline", "v1.2.0; rm -rf /", "v1.2.0\nx", ""]:
        assert not re.fullmatch(pattern.rstrip("$") + r"\Z", bad), bad

    verify_script = steps[verify]["run"]
    assert 'refs/tags/${RELEASE_TAG}^{commit}' in verify_script
    assert "git rev-parse HEAD" in verify_script
    assert "${GITHUB_SHA}^{commit}" in verify_script
    assert "git merge-base --is-ancestor" in verify_script and "refs/remotes/origin/main" in verify_script
    assert workflow["jobs"]["validate"]["outputs"]["commit"] == "${{ steps.release-commit.outputs.commit }}"


def test_build_verifies_it_builds_the_validated_commit(workflow):
    step = _step(workflow["jobs"]["build"], "Verify the checked-out commit is the validated release commit")
    assert step["env"]["VALIDATED_COMMIT"] == "${{ needs.validate.outputs.commit }}"
    assert 'refs/tags/${RELEASE_TAG}^{commit}' in step["run"]
    assert "${VALIDATED_COMMIT}" in step["run"]


def test_version_checks_use_the_release_tag(workflow):
    validate_step = _step(workflow["jobs"]["validate"], "Verify tag, pyproject version")
    assert 'os.environ["RELEASE_TAG"]' in validate_step["run"]
    assert "reponeedle.__version__" in validate_step["run"] and "pyproject.toml" in validate_step["run"]
    build_step = _step(workflow["jobs"]["build"], "Verify built artifacts carry the tagged version")
    assert 'VERSION="${RELEASE_TAG#v}"' in build_step["run"]


def test_no_expression_interpolation_inside_shell_scripts(workflow):
    # Untrusted or user-supplied values reach scripts through environment variables only.
    for job_name, job in workflow["jobs"].items():
        for step in job["steps"]:
            assert "${{" not in step.get("run", ""), f"{job_name}: {step.get('name')}"


def test_permissions_and_job_dependencies(workflow):
    assert workflow["permissions"] == {"contents": "read"}
    jobs = workflow["jobs"]
    assert set(jobs) == {"validate", "build", "publish"}
    assert jobs["validate"]["permissions"] == {"contents": "read"}
    assert jobs["build"]["permissions"] == {"contents": "read"}
    assert jobs["build"]["needs"] == "validate"
    assert jobs["publish"]["needs"] == ["validate", "build"]
    assert jobs["publish"]["permissions"] == {"id-token": "write", "contents": "read"}
    assert jobs["publish"]["environment"]["name"] == "pypi"
    for name in ("validate", "build"):
        assert "id-token" not in jobs[name]["permissions"]
        assert "environment" not in jobs[name]


def test_release_safeguards_are_kept(workflow):
    validate = workflow["jobs"]["validate"]
    strict = _step(validate, "Run MCP and security suites")
    assert strict["env"]["REPONEEDLE_FAIL_ON_SKIP"] == "1"
    assert "tests/test_indexing_security.py" in strict["run"]
    assert _step(validate, "Run full test suite")["run"].strip() == "pytest -q -rs"

    build = workflow["jobs"]["build"]
    assert "twine check --strict dist/*" in _step(build, "Validate distribution metadata")["run"]
    assert "sha256sum" in _step(build, "Generate and record SHA-256 checksums")["run"]

    publish = workflow["jobs"]["publish"]
    assert not _checkout_steps(publish), "publish must only use the artifacts built and verified by build"
    assert [s["uses"] for s in publish["steps"]] == [
        "actions/download-artifact@v4",
        "pypa/gh-action-pypi-publish@release/v1",
    ]
