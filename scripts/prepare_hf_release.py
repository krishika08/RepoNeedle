"""
Automation script to validate and publish RepoNeedle release artifacts to Hugging Face.
Publishes:
1. Dataset: RepoNeedle/RepoNeedle-Bench
2. Space: RepoNeedle/RepoNeedle-Playground
"""

import os
import sys
import argparse
from typing import Optional


def check_hf_auth(token: Optional[str] = None) -> Optional[str]:
    """Retrieves Hugging Face authentication token if available."""
    auth_token = token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not auth_token:
        # Check standard cache location
        cache_token_path = os.path.expanduser("~/.cache/huggingface/token")
        if os.path.isfile(cache_token_path):
            try:
                with open(cache_token_path, "r", encoding="utf-8") as f:
                    auth_token = f.read().strip()
            except Exception:
                pass
    return auth_token


def publish_artifacts(repo_prefix: str = "RepoNeedle", token: Optional[str] = None):
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    dataset_dir = os.path.join(root_dir, "hf_artifacts", "dataset")
    space_dir = os.path.join(root_dir, "hf_artifacts", "space")

    print(f"=== RepoNeedle Hugging Face Release Engineer ===")
    print(f"Root Directory: {root_dir}")
    print(f"Dataset Artifacts: {dataset_dir}")
    print(f"Space Artifacts: {space_dir}")

    # Verify files exist
    assert os.path.isfile(os.path.join(dataset_dir, "README.md")), "Dataset README.md missing"
    assert os.path.isfile(os.path.join(dataset_dir, "data", "train.jsonl")), "train.jsonl missing"
    assert os.path.isfile(os.path.join(dataset_dir, "data", "test.jsonl")), "test.jsonl missing"
    assert os.path.isfile(os.path.join(space_dir, "app.py")), "Space app.py missing"
    assert os.path.isfile(os.path.join(space_dir, "README.md")), "Space README.md missing"
    assert os.path.isfile(os.path.join(space_dir, "requirements.txt")), "Space requirements.txt missing"

    print("All release artifact files verified locally! [OK]")

    auth_token = check_hf_auth(token)
    if not auth_token:
        print("\n" + "=" * 70)
        print("ATTENTION: Hugging Face Authentication Token Not Detected.")
        print("=" * 70)
        print("All release artifacts have been built, verified, and packaged locally.")
        print("\nTo publish to Hugging Face, run the following command with your HF token:")
        print(f"  python scripts/prepare_hf_release.py --token <YOUR_HF_TOKEN>\n")
        print("Or set the environment variable:")
        print(f"  $env:HF_TOKEN = '<YOUR_HF_TOKEN>' (PowerShell)")
        print(f"  export HF_TOKEN='<YOUR_HF_TOKEN>' (Linux/macOS)\n")
        print("Target Repositories to be created:")
        print(f"  1. Dataset: https://huggingface.co/datasets/{repo_prefix}/RepoNeedle-Bench")
        print(f"  2. Space:   https://huggingface.co/spaces/{repo_prefix}/RepoNeedle-Playground")
        print("=" * 70)
        return

    try:
        from huggingface_hub import HfApi, create_repo
    except ImportError:
        print("huggingface_hub package not installed. Install via: pip install huggingface_hub")
        return

    api = HfApi(token=auth_token)

    # 1. Publish Dataset
    dataset_repo_id = f"{repo_prefix}/RepoNeedle-Bench"
    print(f"\n[1/2] Creating/Uploading Dataset to {dataset_repo_id}...")
    try:
        create_repo(dataset_repo_id, repo_type="dataset", exist_ok=True, token=auth_token)
        api.upload_folder(
            folder_path=dataset_dir,
            repo_id=dataset_repo_id,
            repo_type="dataset",
        )
        print(f"Successfully uploaded dataset to: https://huggingface.co/datasets/{dataset_repo_id}")
    except Exception as e:
        print(f"Dataset upload failed: {e}")

    # 2. Publish Space
    space_repo_id = f"{repo_prefix}/RepoNeedle-Playground"
    print(f"\n[2/2] Creating/Uploading Space to {space_repo_id}...")
    try:
        create_repo(space_repo_id, repo_type="space", space_sdk="gradio", exist_ok=True, token=auth_token)
        api.upload_folder(
            folder_path=space_dir,
            repo_id=space_repo_id,
            repo_type="space",
        )
        print(f"Successfully uploaded space to: https://huggingface.co/spaces/{space_repo_id}")
    except Exception as e:
        print(f"Space upload failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Prepare and publish RepoNeedle artifacts to Hugging Face.")
    parser.add_argument("--token", type=str, default=None, help="Hugging Face User Access Token (write permissions)")
    parser.add_argument("--org", type=str, default="RepoNeedle", help="Hugging Face organization or username prefix")
    args = parser.parse_args()

    publish_artifacts(repo_prefix=args.org, token=args.token)


if __name__ == "__main__":
    main()

