"""
Automation script to validate and publish RepoNeedle release artifacts to Hugging Face.

Publishes:
1. Dataset: <org>/RepoNeedle-Bench
2. Space:   <org>/RepoNeedle-Playground (Gradio SDK; the bundled engine in hf_artifacts/space)

The static Space (hf_artifacts/static_space/) is not published by this script; it is uploaded
manually (see docs/STATIC_PLAYGROUND_DEPLOYMENT.md).

The expected release version is read from pyproject.toml (the authoritative declaration). The
Space's bundled `reponeedle` package must be identical to the root package, except for the optional
`reponeedle/mcp/` package, which the demo does not need.

Supports:
- Environment variable HF_TOKEN or HUGGING_FACE_HUB_TOKEN
- Stored huggingface_hub token from `huggingface-cli login`
- CLI argument `--token` (never printed or logged)
- `--check-only` / `--dry-run` preflight validation mode (no repositories created, nothing uploaded)
"""

import os
import re
import sys
import json
import argparse
from typing import Optional, Dict, Any, List


EXPECTED_DATASET_FILES = [
    os.path.join("README.md"),
    os.path.join("schema.json"),
    os.path.join("data", "train.jsonl"),
    os.path.join("data", "test.jsonl"),
]

EXPECTED_SPACE_FILES = [
    os.path.join("README.md"),
    os.path.join("requirements.txt"),
    os.path.join("app.py"),
    os.path.join("reponeedle", "__init__.py"),
    os.path.join("reponeedle", "engine.py"),
    os.path.join("reponeedle", "models.py"),
    os.path.join("reponeedle", "cli.py"),
    os.path.join("reponeedle", "core", "__init__.py"),
    os.path.join("reponeedle", "core", "abstention.py"),
    os.path.join("reponeedle", "core", "arm101.py"),
    os.path.join("reponeedle", "core", "attenuation.py"),
    os.path.join("reponeedle", "core", "budget.py"),
    os.path.join("reponeedle", "core", "cascade.py"),
    os.path.join("reponeedle", "core", "change_impact.py"),
    os.path.join("reponeedle", "core", "function_graph.py"),
    os.path.join("reponeedle", "core", "graph.py"),
    os.path.join("reponeedle", "core", "lexical.py"),
    os.path.join("reponeedle", "core", "packer.py"),
    os.path.join("reponeedle", "core", "router.py"),
    os.path.join("reponeedle", "core", "semantic.py"),
    os.path.join("reponeedle", "core", "tokenizer.py"),
]

# Sub-packages of the root package that are deliberately NOT bundled into the Space.
BUNDLE_EXCLUDED_DIRS = ("mcp",)
_IGNORED_DIR_NAMES = {"__pycache__"}
_IGNORED_SUFFIXES = (".pyc", ".pyo")


def read_project_version(root_dir: str) -> str:
    """Returns [project].version from pyproject.toml, the authoritative version declaration."""
    path = os.path.join(root_dir, "pyproject.toml")
    try:
        import tomllib  # Python 3.11+
    except ImportError:  # pragma: no cover - Python 3.10
        tomllib = None
    if tomllib is not None:
        with open(path, "rb") as f:
            return tomllib.load(f)["project"]["version"]
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    section = re.search(r"^\[project\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    match = section and re.search(r'^version\s*=\s*"([^"]+)"', section.group(1), re.M)
    if not match:
        raise ValueError("Could not read [project].version from pyproject.toml")
    return match.group(1)


def read_declared_version(init_path: str) -> Optional[str]:
    """Returns the `__version__` string literal declared in a package __init__.py, if any."""
    with open(init_path, "r", encoding="utf-8") as f:
        match = re.search(r"""^__version__\s*=\s*["']([^"']+)["']""", f.read(), re.M)
    return match.group(1) if match else None


def _package_files(pkg_dir: str, excluded_dirs=()) -> Dict[str, str]:
    """Maps package-relative POSIX paths to absolute paths, skipping caches and excluded sub-packages."""
    files: Dict[str, str] = {}
    for current, dirs, names in os.walk(pkg_dir):
        rel_dir = os.path.relpath(current, pkg_dir)
        dirs[:] = sorted(
            d for d in dirs
            if d not in _IGNORED_DIR_NAMES and not (rel_dir == "." and d in excluded_dirs)
        )
        for name in sorted(names):
            if name.endswith(_IGNORED_SUFFIXES):
                continue
            rel = os.path.normpath(os.path.join(rel_dir, name)).replace(os.sep, "/")
            files[rel] = os.path.join(current, name)
    return files


def _read_normalized(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read().replace(b"\r\n", b"\n")


def compare_bundle(root_pkg_dir: str, bundle_pkg_dir: str) -> List[str]:
    """
    Lists every difference between the root `reponeedle` package and the Space's bundled copy.

    The bundle must contain exactly the root package's files (line endings normalised), minus
    BUNDLE_EXCLUDED_DIRS. An empty list means the two are synchronised.
    """
    problems: List[str] = []
    root_files = _package_files(root_pkg_dir, BUNDLE_EXCLUDED_DIRS)
    bundle_files = _package_files(bundle_pkg_dir)
    for rel in sorted(set(root_files) - set(bundle_files)):
        problems.append(f"missing from bundle: reponeedle/{rel}")
    for rel in sorted(set(bundle_files) - set(root_files)):
        problems.append(f"not in root package (or excluded from the bundle): reponeedle/{rel}")
    for rel in sorted(set(root_files) & set(bundle_files)):
        if _read_normalized(root_files[rel]) != _read_normalized(bundle_files[rel]):
            problems.append(f"content differs: reponeedle/{rel}")
    return problems


def resolve_hf_token(cli_token: Optional[str] = None) -> Optional[str]:
    """Resolves Hugging Face authentication token without echoing credentials."""
    if cli_token and cli_token.strip():
        return cli_token.strip()

    env_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if env_token and env_token.strip():
        return env_token.strip()

    try:
        from huggingface_hub import get_token
        stored = get_token()
        if stored and stored.strip():
            return stored.strip()
    except ImportError:
        pass

    # Fallback to standard token path
    cache_token_path = os.path.expanduser("~/.cache/huggingface/token")
    if os.path.isfile(cache_token_path):
        try:
            with open(cache_token_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception:
            pass

    return None


def _redact(message: Any, token: Optional[str]) -> str:
    """Removes the token from any message before it is printed."""
    text = str(message)
    if token:
        text = text.replace(token, "[REDACTED]")
    return text


def validate_local_dataset(dataset_dir: str) -> bool:
    """Validates dataset files, JSONL syntax, split counts, and schema."""
    print("\n--- [Validation] Dataset Artifacts ---")
    all_ok = True

    for rel_path in EXPECTED_DATASET_FILES:
        full_path = os.path.join(dataset_dir, rel_path)
        if not os.path.isfile(full_path):
            print(f"  [FAIL] Missing expected dataset file: {rel_path}")
            all_ok = False
        else:
            print(f"  [OK] Found dataset file: {rel_path}")

    if not all_ok:
        return False

    # Validate schema file
    schema_path = os.path.join(dataset_dir, "schema.json")
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
            required_keys = schema.get("required", [])
    except Exception as exc:
        print(f"  [FAIL] Could not parse schema.json: {exc}")
        return False

    # Validate JSONL samples
    expected_counts = {"train": 10, "test": 5}
    for split, count in expected_counts.items():
        jsonl_path = os.path.join(dataset_dir, "data", f"{split}.jsonl")
        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
            if len(lines) != count:
                print(f"  [FAIL] {split}.jsonl has {len(lines)} samples, expected {count}")
                all_ok = False
            else:
                print(f"  [OK] {split}.jsonl sample count: {len(lines)} (expected {count})")

            for idx, line in enumerate(lines):
                sample = json.loads(line)
                for req in required_keys:
                    if req not in sample:
                        print(f"  [FAIL] {split}.jsonl row {idx} missing required key: {req}")
                        all_ok = False
        except Exception as exc:
            print(f"  [FAIL] Error validating {split}.jsonl: {exc}")
            all_ok = False

    return all_ok


def validate_local_space(space_dir: str, root_dir: str, expected_version: str) -> bool:
    """Validates Space files, requirements, and that the bundled package matches the root package."""
    print("\n--- [Validation] Space Artifacts ---")
    all_ok = True

    for rel_path in EXPECTED_SPACE_FILES:
        full_path = os.path.join(space_dir, rel_path)
        if not os.path.isfile(full_path):
            print(f"  [FAIL] Missing expected space file: {rel_path}")
            all_ok = False
        else:
            print(f"  [OK] Found space file: {rel_path}")

    if not all_ok:
        return False

    # Version: bundled package == root package == pyproject.toml.
    try:
        bundled_version = read_declared_version(os.path.join(space_dir, "reponeedle", "__init__.py"))
        root_version = read_declared_version(os.path.join(root_dir, "reponeedle", "__init__.py"))
    except Exception as exc:
        print(f"  [FAIL] Error reading package versions: {exc}")
        return False
    if bundled_version == root_version == expected_version:
        print(f"  [OK] Bundled reponeedle declares version {bundled_version} (matches pyproject.toml and the root package)")
    else:
        print(
            f"  [FAIL] Version mismatch: pyproject.toml={expected_version}, "
            f"root reponeedle={root_version}, bundled reponeedle={bundled_version}"
        )
        all_ok = False

    # Content: bundled package must be identical to the root package (minus optional MCP).
    excluded = ", ".join(f"reponeedle/{d}/" for d in BUNDLE_EXCLUDED_DIRS)
    if os.path.isdir(os.path.join(space_dir, "reponeedle", "mcp")):
        print("  [FAIL] Bundled package must not include reponeedle/mcp/ (optional MCP SDK not installed in the Space)")
        all_ok = False
    problems = compare_bundle(os.path.join(root_dir, "reponeedle"), os.path.join(space_dir, "reponeedle"))
    if problems:
        print("  [FAIL] Bundled reponeedle package is not synchronised with the root package:")
        for problem in problems:
            print(f"         - {problem}")
        all_ok = False
    else:
        print(f"  [OK] Bundled reponeedle package is identical to the root package (excluding {excluded})")

    # Verify requirements.txt includes essential runtime libraries
    req_path = os.path.join(space_dir, "requirements.txt")
    try:
        with open(req_path, "r", encoding="utf-8") as f:
            reqs = f.read()
        reqs_ok = True
        for dep in ["gradio", "numpy", "scipy", "networkx", "pydantic", "pathspec"]:
            if dep not in reqs.lower():
                print(f"  [FAIL] Space requirements.txt missing dependency: {dep}")
                reqs_ok = False
        if reqs_ok:
            print("  [OK] Space requirements.txt covers all core runtime dependencies")
        all_ok = all_ok and reqs_ok
    except Exception as exc:
        print(f"  [FAIL] Error reading Space requirements.txt: {exc}")
        all_ok = False

    return all_ok


def verify_account_permissions(api, repo_prefix: str, token: Optional[str] = None) -> bool:
    """Verifies Hugging Face authentication, active identity, and target namespace access."""
    print("\n--- [Authentication & Namespace Check] ---")
    try:
        user_info = api.whoami()
    except Exception as exc:
        print(f"  [FAIL] Failed to authenticate with Hugging Face API: {_redact(exc, token)}")
        return False

    username = user_info.get("name")
    user_type = user_info.get("type", "user")
    orgs = [org.get("name") for org in user_info.get("orgs", []) if isinstance(org, dict)]

    print(f"  [OK] Authenticated Identity: {username} (Type: {user_type})")
    print(f"  [OK] Associated Organizations: {', '.join(orgs) if orgs else '(None)'}")

    # Verify namespace authority
    if username == repo_prefix:
        print(f"  [OK] Active user '{username}' matches target namespace '{repo_prefix}' (Direct Owner).")
        return True
    elif repo_prefix in orgs:
        print(f"  [OK] User '{username}' is a confirmed member of target organization '{repo_prefix}'.")
        return True
    else:
        print(
            f"  [WARNING] Target namespace '{repo_prefix}' does not match active username ('{username}') "
            f"nor is it listed in affiliated organizations ({orgs})."
        )
        print(
            f"  If '{repo_prefix}' is a new organization, ensure account '{username}' has administrative "
            f"privileges to create and manage repositories under '{repo_prefix}'."
        )
        return False


def check_space_target(api, space_repo_id: str, token: Optional[str] = None) -> bool:
    """
    Refuses to publish the Gradio app into an existing Space that uses a different SDK (for example
    the static Playground frontend), which would overwrite that Space's README/front matter.
    A Space that does not exist yet is allowed (it will be created with the Gradio SDK).
    """
    try:
        info = api.repo_info(repo_id=space_repo_id, repo_type="space")
    except Exception as exc:
        if type(exc).__name__ == "RepositoryNotFoundError":
            print(f"  [OK] Space {space_repo_id} does not exist yet; it will be created with the Gradio SDK.")
            return True
        print(f"  [FAIL] Could not inspect Space {space_repo_id}: {_redact(exc, token)}")
        return False
    sdk = getattr(info, "sdk", None)
    if sdk != "gradio":
        print(
            f"  [FAIL] Space {space_repo_id} uses SDK '{sdk}', not 'gradio'. Refusing to upload the Gradio "
            "app over it (the static frontend is deployed separately)."
        )
        return False
    print(f"  [OK] Space {space_repo_id} exists and uses the Gradio SDK.")
    return True


def _upload_and_verify(api, folder: str, repo_id: str, repo_type: str, commit_message: str) -> str:
    """Uploads a folder and verifies that the repository's head is the commit just created."""
    commit = api.upload_folder(
        folder_path=folder,
        repo_id=repo_id,
        repo_type=repo_type,
        commit_message=commit_message,
    )
    info = api.repo_info(repo_id=repo_id, repo_type=repo_type)
    expected = getattr(commit, "oid", None)
    if expected and getattr(info, "sha", None) != expected:
        raise RuntimeError(f"repository head {getattr(info, 'sha', None)} is not the uploaded commit {expected}")
    return getattr(info, "sha", None) or "(unknown)"


def run_release(
    repo_prefix: str = "RepoNeedle",
    token: Optional[str] = None,
    dry_run: bool = False,
    dataset_only: bool = False,
    space_only: bool = False,
    root_dir: Optional[str] = None,
) -> int:
    if dataset_only and space_only:
        print("[ERROR] --dataset-only and --space-only are mutually exclusive.")
        return 1

    root_dir = os.path.abspath(root_dir or os.path.join(os.path.dirname(__file__), ".."))
    dataset_dir = os.path.join(root_dir, "hf_artifacts", "dataset")
    space_dir = os.path.join(root_dir, "hf_artifacts", "space")

    try:
        version = read_project_version(root_dir)
    except Exception as exc:
        print(f"[ERROR] Could not determine the release version from pyproject.toml: {exc}")
        return 1

    targets = "Dataset only" if dataset_only else "Space only" if space_only else "Dataset and Space"
    print("=" * 72)
    print(f"RepoNeedle {version}: Hugging Face Release Preflight & Publisher")
    print("=" * 72)
    print(f"Workspace Root:    {root_dir}")
    print(f"Target Namespace:  {repo_prefix}")
    print(f"Targets:           {targets}")
    print(f"Mode:              {'DRY RUN / VALIDATION ONLY' if dry_run else 'LIVE PUBLISH'}")
    print("=" * 72)

    # 1. Local Validation (only the artifacts that would be published)
    dataset_valid = True if space_only else validate_local_dataset(dataset_dir)
    space_valid = True if dataset_only else validate_local_space(space_dir, root_dir, version)

    if not dataset_valid or not space_valid:
        print("\n[ERROR] Local artifact preflight checks failed. Release aborted.")
        return 1

    print("\n[OK] All local release artifacts verified successfully.")

    # 2. Authentication Check
    auth_token = resolve_hf_token(token)
    if not auth_token:
        print("\n" + "=" * 72)
        print("[NOTICE] Hugging Face Authentication Token Not Detected.")
        print("=" * 72)
        print("Local release artifacts have been built, verified, and packaged successfully.")
        print("To authenticate and perform preflight verification or publication, provide a token:")
        print("  1. CLI Flag:  python scripts/prepare_hf_release.py --token <HF_TOKEN>")
        print("  2. Env Var:   $env:HF_TOKEN = '<HF_TOKEN>' (PowerShell)")
        print("                export HF_TOKEN='<HF_TOKEN>' (Linux/macOS)")
        print("  3. CLI Login: huggingface-cli login")
        print("=" * 72)
        if dry_run:
            print("\nDry-run completed local file validation without API authentication.")
            return 0
        return 1

    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("\n[ERROR] 'huggingface_hub' package is required. Install via: pip install huggingface_hub")
        return 1

    api = HfApi(token=auth_token)
    has_namespace_access = verify_account_permissions(api, repo_prefix, auth_token)

    dataset_repo_id = f"{repo_prefix}/RepoNeedle-Bench"
    space_repo_id = f"{repo_prefix}/RepoNeedle-Playground"

    space_target_ok = True
    if not dataset_only:
        print("\n--- [Space Target Check] ---")
        space_target_ok = check_space_target(api, space_repo_id, auth_token)

    if dry_run:
        print("\n" + "=" * 72)
        if space_target_ok:
            print("[DRY RUN COMPLETE] Preflight validation succeeded.")
        else:
            print("[DRY RUN COMPLETE] Preflight found a blocking Space target problem (see above).")
        print("No repositories were created and no files were uploaded.")
        print("=" * 72)
        return 0 if space_target_ok else 1

    if not has_namespace_access:
        print(
            f"\n[ERROR] Account lacks confirmed authority for namespace '{repo_prefix}'. "
            "Halting to prevent unintended uploads."
        )
        return 1
    if not space_target_ok:
        print("\n[ERROR] Space target check failed. Halting to prevent unintended uploads.")
        return 1

    # 3. Publish
    upload_errors: List[str] = []

    if not space_only:
        print(f"\n[Dataset] Creating/Updating Dataset: {dataset_repo_id}...")
        try:
            api.create_repo(repo_id=dataset_repo_id, repo_type="dataset", exist_ok=True)
            sha = _upload_and_verify(
                api, dataset_dir, dataset_repo_id, "dataset",
                f"release: synchronize RepoNeedle-Bench dataset artifacts (RepoNeedle {version})",
            )
            print(f"  [OK] Successfully uploaded and verified Dataset: https://huggingface.co/datasets/{dataset_repo_id}")
            print(f"       Repository SHA: {sha}")
        except Exception as exc:
            err = f"Dataset upload failed for {dataset_repo_id}: {_redact(exc, auth_token)}"
            print(f"  [FAIL] {err}")
            upload_errors.append(err)

    if not dataset_only:
        print(f"\n[Space] Creating/Updating Space: {space_repo_id}...")
        try:
            api.create_repo(repo_id=space_repo_id, repo_type="space", space_sdk="gradio", exist_ok=True)
            sha = _upload_and_verify(
                api, space_dir, space_repo_id, "space",
                f"release: synchronize RepoNeedle-Playground Space application (RepoNeedle {version})",
            )
            print(f"  [OK] Successfully uploaded and verified Space: https://huggingface.co/spaces/{space_repo_id}")
            print(f"       Space SHA: {sha}")
        except Exception as exc:
            err = f"Space upload failed for {space_repo_id}: {_redact(exc, auth_token)}"
            print(f"  [FAIL] {err}")
            upload_errors.append(err)

    if upload_errors:
        print("\n" + "=" * 72)
        print("[ERROR] One or more uploads failed:")
        for e in upload_errors:
            print(f"  - {e}")
        print("=" * 72)
        return 1

    print("\n" + "=" * 72)
    print("[SUCCESS] Hugging Face artifacts uploaded and verified:")
    if not space_only:
        print(f"  Dataset: https://huggingface.co/datasets/{dataset_repo_id}")
    if not dataset_only:
        print(f"  Space:   https://huggingface.co/spaces/{space_repo_id}")
    print("=" * 72)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Prepare and publish RepoNeedle artifacts to Hugging Face.")
    parser.add_argument("--token", type=str, default=None, help="Hugging Face User Access Token (write permissions)")
    parser.add_argument("--org", type=str, default="RepoNeedle", help="Target Hugging Face namespace/org prefix")
    parser.add_argument("--check-only", "--dry-run", action="store_true", dest="dry_run", help="Run local validation and auth checks without uploading")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--dataset-only", action="store_true", help="Publish only the dataset")
    scope.add_argument("--space-only", action="store_true", help="Publish only the space")
    args = parser.parse_args()

    exit_code = run_release(
        repo_prefix=args.org,
        token=args.token,
        dry_run=args.dry_run,
        dataset_only=args.dataset_only,
        space_only=args.space_only,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
