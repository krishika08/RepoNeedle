# PyPI Trusted Publishing (OIDC) Setup Guide

This document describes how to configure **PyPI Trusted Publishing** for RepoNeedle using OpenID Connect (OIDC).

Trusted Publishing replaces long-lived, manually managed PyPI API tokens with cryptographically signed, short-lived OIDC identity tokens issued directly by GitHub Actions.

---

## 1. Authoritative Configuration Parameters

When registering the trusted publisher on PyPI, configure the exact values below:

| Parameter | Configuration Value | Description |
| :--- | :--- | :--- |
| **PyPI Project Name** | `reponeedle` | Name of the package on PyPI |
| **Owner** | `krishika08` | GitHub organization or username |
| **Repository Name** | `RepoNeedle` | GitHub repository name |
| **Workflow Name** | `release.yml` | Workflow file inside `.github/workflows/` |
| **Environment Name** | `pypi` | GitHub Actions deployment environment |

---

## 2. Step 1: Configure Trusted Publisher on PyPI

Because `reponeedle` is an initial public release (the package name is not yet registered on PyPI), configure a **Pending Publisher**:

1. Sign in to your account at [pypi.org](https://pypi.org/).
2. Navigate to **Account Settings** $\to$ **Publishing** (or directly visit `https://pypi.org/manage/account/publishing/`).
3. Under the **Add a publisher** section, select **GitHub**.
4. Fill in the required fields:
   - **PyPI Project Name**: `reponeedle`
   - **Owner**: `krishika08`
   - **Repository name**: `RepoNeedle`
   - **Workflow name**: `release.yml`
   - **Environment name**: `pypi`
5. Click **Add publisher**.

> [!NOTE]
> PyPI creates a "pending publisher" record. When the first release tag is pushed and GitHub Actions triggers `release.yml`, PyPI cryptographically verifies the GitHub OIDC token, creates the `reponeedle` project, associates ownership with `krishika08`, and converts the pending publisher into an active trusted publisher.

---

## 3. Step 2: Configure the GitHub Environment

In GitHub, protect the deployment target using the environment specified in `release.yml`:

1. Navigate to the repository on GitHub: `https://github.com/krishika08/RepoNeedle`.
2. Go to **Settings** $\to$ **Environments**.
3. Click **New environment**.
4. Set the name to exactly `pypi` and click **Configure environment**.
5. *(Recommended Security Rules)*:
   - **Deployment branches and tags**: Select **Selected tags** and specify rule `v*` (ensuring only release tags can deploy).
   - **Required reviewers**: Optionally add `krishika08` for explicit deployment confirmation.

---

## 4. Step 3: Automated Workflow Architecture (`.github/workflows/release.yml`)

The release pipeline consists of two decoupled jobs:

```
[ Git Tag: v* ]
       │
       ▼
┌──────────────────────────────────────────────┐
│ Job 1: build                                 │
│ - Checkout full git history                  │
│ - Set up Python 3.11                         │
│ - python -m build                            │
│ - python -m twine check --strict dist/*      │
│ - sha256sum * > SHA256SUMS                   │
│ - Upload artifacts (packages & checksums)    │
└──────────────────────┬───────────────────────┘
                       │ Validated Artifacts
                       ▼
┌──────────────────────────────────────────────┐
│ Job 2: publish                               │
│ - Environment: pypi                          │
│ - Permissions: id-token: write               │
│ - Download validated distributions           │
│ - pypa/gh-action-pypi-publish@release/v1     │
└──────────────────────────────────────────────┘
```

### Security & Integrity Controls:
- **Zero API Tokens**: No API tokens, passwords, or secrets are stored in GitHub repository secrets.
- **Strict Triggering**: Triggers exclusively on `push` of tags matching `v*`. Normal branch pushes and Pull Requests never invoke this workflow.
- **Least-Privilege Permissions**: Top-level permissions are read-only (`contents: read`). The `publish` job explicitly requests only `id-token: write` and `contents: read`.
- **Pre-Publication Twine Audit**: Distributions must pass `twine check --strict` before the publish job is scheduled.
- **Deterministic Checksums**: SHA-256 hashes are recorded in `checksums/SHA256SUMS` and emitted to the GitHub Step Summary.

---

## 5. Step 4: Executing a Release

Once the trusted publisher and GitHub environment are configured:

```bash
# 1. Ensure you are on the verified main commit
git checkout main
git pull origin main

# 2. Create the annotated release tag
git tag -a v1.1.0 -m "RepoNeedle V1.1.0: Change-Impact Ranking Engine Release"

# 3. Push the tag to trigger release.yml
git push origin v1.1.0
```

GitHub Actions will automatically run `.github/workflows/release.yml`, build the validated distributions, exchange OIDC claims with PyPI, and publish `reponeedle==1.1.0` to PyPI.
