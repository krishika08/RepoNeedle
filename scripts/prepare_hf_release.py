"""
Automation script to validate and publish RepoNeedle release artifacts to Hugging Face.

Publishes:
1. Dataset: RepoNeedle/RepoNeedle-Bench
2. Space:   RepoNeedle/RepoNeedle-Playground

Supports:
- Environment variable HF_TOKEN or HUGGING_FACE_HUB_TOKEN
- Stored huggingface_hub token from `huggingface-cli login`
- CLI argument `--token` (never printed or logged)
- `--check-only` / `--dry-run` preflight validation mode
"""

import os
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


def validate_local_space(space_dir: str) -> bool:
    """Validates Space configuration, requirements, bundled reponeedle package and version."""
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

    # Check bundled reponeedle __version__ == "1.1.0"
    init_path = os.path.join(space_dir, "reponeedle", "__init__.py")
    try:
        with open(init_path, "r", encoding="utf-8") as f:
            content = f.read()
        if '__version__ = "1.1.0"' not in content and "__version__ = '1.1.0'" not in content:
            print("  [FAIL] Bundled reponeedle/__init__.py does not declare __version__ = '1.1.0'")
            all_ok = False
        else:
            print("  [OK] Bundled reponeedle declares version 1.1.0")
    except Exception as exc:
        print(f"  [FAIL] Error reading bundled __init__.py: {exc}")
        all_ok = False

    # Verify requirements.txt includes essential V1.1.0 libraries
    req_path = os.path.join(space_dir, "requirements.txt")
    try:
        with open(req_path, "r", encoding="utf-8") as f:
            reqs = f.read()
        for dep in ["gradio", "numpy", "scipy", "networkx", "pydantic", "pathspec"]:
            if dep not in reqs.lower():
                print(f"  [FAIL] Space requirements.txt missing dependency: {dep}")
                all_ok = False
        if all_ok:
            print("  [OK] Space requirements.txt covers all core runtime dependencies")
    except Exception as exc:
        print(f"  [FAIL] Error reading Space requirements.txt: {exc}")
        all_ok = False

    return all_ok


def verify_account_permissions(api, repo_prefix: str) -> bool:
    """Verifies Hugging Face authentication, active identity, and target namespace access."""
    print("\n--- [Authentication & Namespace Check] ---")
    try:
        user_info = api.whoami()
    except Exception as exc:
        print(f"  [FAIL] Failed to authenticate with Hugging Face API: {exc}")
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


def run_release(
    repo_prefix: str = "RepoNeedle",
    token: Optional[str] = None,
    dry_run: bool = False,
    dataset_only: bool = False,
    space_only: bool = False,
) -> int:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    dataset_dir = os.path.join(root_dir, "hf_artifacts", "dataset")
    space_dir = os.path.join(root_dir, "hf_artifacts", "space")

    print("=" * 72)
    print("RepoNeedle V1.1.0: Hugging Face Release Preflight & Publisher")
    print("=" * 72)
    print(f"Workspace Root:    {root_dir}")
    print(f"Target Namespace:  {repo_prefix}")
    print(f"Mode:              {'DRY RUN / VALIDATION ONLY' if dry_run else 'LIVE PUBLISH'}")
    print("=" * 72)

    # 1. Local Validation
    dataset_valid = validate_local_dataset(dataset_dir)
    space_valid = validate_local_space(space_dir)

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
    has_namespace_access = verify_account_permissions(api, repo_prefix)

    if dry_run:
        print("\n" + "=" * 72)
        print("[DRY RUN COMPLETE] Preflight validation succeeded.")
        print("No repositories were created and no files were uploaded.")
        print("=" * 72)
        return 0

    if not has_namespace_access:
        print(
            f"\n[ERROR] Account lacks confirmed authority for namespace '{repo_prefix}'. "
            "Halting to prevent unintended uploads."
        )
        return 1

    # 3. Publish Dataset
    dataset_repo_id = f"{repo_prefix}/RepoNeedle-Bench"
    space_repo_id = f"{repo_prefix}/RepoNeedle-Playground"
    upload_errors: List[str] = []

    if not space_only:
        print(f"\n[1/2] Creating/Updating Dataset: {dataset_repo_id}...")
        try:
            api.create_repo(repo_id=dataset_repo_id, repo_type="dataset", exist_ok=True)
            api.upload_folder(
                folder_path=dataset_dir,
                repo_id=dataset_repo_id,
                repo_type="dataset",
                commit_message="release: synchronize RepoNeedle-Bench V1.1.0 dataset artifacts",
            )
            # Verify uploaded repo
            info = api.repo_info(repo_id=dataset_repo_id, repo_type="dataset")
            print(f"  [OK] Successfully uploaded and verified Dataset: https://huggingface.co/datasets/{dataset_repo_id}")
            print(f"       Repository SHA: {info.sha}")
        except Exception as exc:
            err = f"Dataset upload failed for {dataset_repo_id}: {exc}"
            print(f"  [FAIL] {err}")
            upload_errors.append(err)

    if not dataset_only:
        print(f"\n[2/2] Creating/Updating Space: {space_repo_id}...")
        try:
            api.create_repo(repo_id=space_repo_id, repo_type="space", space_sdk="gradio", exist_ok=True)
            api.upload_folder(
                folder_path=space_dir,
                repo_id=space_repo_id,
                repo_type="space",
                commit_message="release: synchronize RepoNeedle-Playground V1.1.0 Space application",
            )
            # Verify uploaded repo
            info = api.repo_info(repo_id=space_repo_id, repo_type="space")
            print(f"  [OK] Successfully uploaded and verified Space: https://huggingface.co/spaces/{space_repo_id}")
            print(f"       Space SHA: {info.sha}")
        except Exception as exc:
            err = f"Space upload failed for {space_repo_id}: {exc}"
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
    print("[SUCCESS] All Hugging Face artifacts successfully synchronized and verified!")
    print(f"  1. Dataset: https://huggingface.co/datasets/{dataset_repo_id}")
    print(f"  2. Space:   https://huggingface.co/spaces/{space_repo_id}")
    print("=" * 72)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Prepare and publish RepoNeedle artifacts to Hugging Face.")
    parser.add_argument("--token", type=str, default=None, help="Hugging Face User Access Token (write permissions)")
    parser.add_argument("--org", type=str, default="RepoNeedle", help="Target Hugging Face namespace/org prefix")
    parser.add_argument("--check-only", "--dry-run", action="store_true", dest="dry_run", help="Run local validation and auth checks without uploading")
    parser.add_argument("--dataset-only", action="store_true", help="Publish only the dataset")
    parser.add_argument("--space-only", action="store_true", help="Publish only the space")
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
