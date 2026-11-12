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
   - **Deployment branches and tags**: Select **Selected branches and tags** and add the tag rule `v*` and the branch rule `main`. Tag pushes deploy from `refs/tags/v*`; a [manual release of an existing tag](#6-manually-releasing-an-existing-tag) runs from `refs/heads/main`. A tags-only rule would block manual releases at the deployment gate.
   - **Required reviewers**: Optionally add `krishika08` for explicit deployment confirmation. Every publish, tag-push or manual, then waits for approval.

---

## 4. Step 3: Automated Workflow Architecture (`.github/workflows/release.yml`)

The release pipeline has three jobs. Each job starts only after the previous one succeeds.

```
[ Tag push v*  |  manual dispatch from main with tag input ]
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│ Job 1: validate                  (contents: read)        │
│ - Check trigger and tag format; dispatch only from main  │
│ - Checkout refs/tags/<tag> with full history and tags    │
│ - Verify HEAD == tag commit (== pushed commit for push;  │
│   tag commit on main for dispatch)                       │
│ - Verify tag == pyproject version == __version__         │
│ - Full test suite, strict MCP/security suites            │
└──────────────────────────┬───────────────────────────────┘
                           │ validated commit SHA
                           ▼
┌──────────────────────────────────────────────────────────┐
│ Job 2: build                     (contents: read)        │
│ - Checkout refs/tags/<tag> with full history and tags    │
│ - Verify HEAD == tag commit == validated commit          │
│ - python -m build; twine check --strict                  │
│ - Verify artifact file names carry the tag version       │
│ - sha256sum > SHA256SUMS; upload artifacts               │
└──────────────────────────┬───────────────────────────────┘
                           │ validated artifacts
                           ▼
┌──────────────────────────────────────────────────────────┐
│ Job 3: publish                                           │
│ - Environment: pypi                                      │
│ - Permissions: id-token: write, contents: read           │
│ - Download artifacts from build (no checkout)            │
│ - pypa/gh-action-pypi-publish@release/v1                 │
└──────────────────────────────────────────────────────────┘
```

### Security & Integrity Controls:
- **Zero API Tokens**: No API tokens, passwords, or secrets are stored in GitHub repository secrets.
- **Restricted Triggering**: The workflow runs only on a push of a tag matching `v*`, or on a manual `workflow_dispatch` from `main` naming an existing release tag. Normal branch pushes and pull requests never invoke it. A dispatch from any other branch, or with a tag that is malformed, does not exist or is not on `main`, fails in `validate`.
- **Exact Release Ref**: `validate` and `build` both check out `refs/tags/<tag>` (never the branch tree) with full history, verify that HEAD is the tag's commit, and `build` refuses to build anything other than the commit `validate` tested.
- **Least-Privilege Permissions**: Top-level permissions are read-only (`contents: read`). `validate` and `build` are read-only and do not persist checkout credentials. Only `publish` requests `id-token: write`.
- **Pre-Publication Twine Audit**: Distributions must pass `twine check --strict` before the publish job is scheduled.
- **Deterministic Checksums**: SHA-256 hashes are recorded in `checksums/SHA256SUMS` and emitted to the GitHub Step Summary.
- **No Concurrent Releases**: Runs for the same tag are serialised (`concurrency: release-<tag>`).

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

---

## 6. Manually Releasing an Existing Tag

Use this when a release tag already exists but its tag-push run failed for a reason unrelated to the tagged code. For example, `v1.2.0` was pushed while `release.yml` still used a shallow checkout, which broke the history tests. Re-running that old run would reuse the old workflow definition, so dispatch a new run instead. Do **not** delete, move or recreate the tag.

```bash
# Dispatch from main, so that the current release.yml is used. The jobs check out the tag, not main.
gh workflow run release.yml --ref main -f tag=v1.2.0
```

Or in the GitHub UI: **Actions** → **Release & Publish** → **Run workflow**, keep **Branch: main**, and enter the tag.

The run is rejected unless all of these hold:
- it was dispatched from `main`;
- the tag looks like `vX.Y.Z` (optionally `aN`/`bN`/`rcN` and `.postN`) and exists;
- the tag's commit is on `main`;
- the tag, `pyproject.toml` and `reponeedle.__version__` at that commit agree.

PyPI Trusted Publishing accepts the run unchanged: the OIDC token still comes from `krishika08/RepoNeedle`, workflow `release.yml`, environment `pypi`. PyPI does not restrict the triggering event or ref. If the `pypi` environment has deployment branch/tag rules, they must allow `main` (see [Step 2](#3-step-2-configure-the-github-environment)).
