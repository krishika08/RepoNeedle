# RepoNeedle V1.1 — Pull Request Restructuring Plan

**Document Version**: 1.0.0  
**Author**: Senior Release Engineer & Principal Software Architect  
**Date**: November 2026  
**Repository**: `krishika08/RepoNeedle`  
**Status**: ACTIVE / READY FOR MAINTAINER REVIEW  

---

## 1. Executive Summary & Problem Formulation

### 1.1 The Reviewability Bottleneck in PR #1
On November 2, 2026, Pull Request #1 (`v1.1-change-impact` $\to$ `v1.0-zero-failure`) was opened to deliver RepoNeedle V1.1:
- **PR URL**: [GitHub PR #1](https://github.com/krishika08/RepoNeedle/pull/1)
- **Reported Scope**: **211 changed files**, $+39,503$ additions, $-57$ deletions, spanning $4.22\text{ MB}$ of data.

A release engineering audit of PR #1 revealed an acute architectural anti-pattern:
**Over 93% of the files in PR #1 are experimental research artifacts**, including exploratory ranker prototypes (R1 through R6), simulation scripts, ablation matrices, benchmark datasets (`PER_QUERY_RESULTS.jsonl`, `independent_benchmark.json.gz`), and research decision reports. 

Only **12 files** (~2.8% of lines) actually comprise production engine code, public API modifications, CLI enhancements, production integration tests, and user-facing documentation.

### 1.2 Impact on Release Governance
1. **Reviewer Fatigue**: Maintainers attempting to review PR #1 must manually separate production logic from 40,000 lines of exploratory research code and JSON datasets.
2. **Merge Risk**: Large experimental datasets and prototype scripts pollute the production branch history and increase package distribution payload risk.
3. **CI Brittleness**: Research tests in `tests/test_ranking_r*.py` import from non-production directory structures (`research/...`), coupling production CI to research scratch trees.

---

## 2. Restructuring Architecture

To restore reviewability without sacrificing scientific reproducibility, RepoNeedle adopts a **two-tier branch and PR separation model**:

```
                              [ origin/v1.0-zero-failure ] (Base: fc8efa1)
                                      |              \
                                      |               \
                                      |                \
    [ v1.1-production-release ] <-----+                 +-----> [ v1.1-change-impact ]
    (Commit: 6406e7e)                                           (Commit: d72ffcf)
    - 13 production files                                       - 211 files (All R1-R6 research)
    - 270 production tests                                      - 308 tests (incl. research tests)
    - Full GitHub Actions CI                                    - Research datasets & logs
    - Pull Request #2 (Clean Release)                           - Pull Request #1 / Permanent Archive
```

### 2.1 Branch Topology & Responsibilities

| Branch Name | Base Commit | Target Commit | Scope & Purpose | PR Status |
| :--- | :--- | :--- | :--- | :--- |
| **`v1.0-zero-failure`** | `fc8efa1` | `fc8efa1` | Frozen V1.0.0 production baseline | **Base Branch** |
| **`v1.1-production-release`** | `fc8efa1` | `6406e7e` | **Clean production V1.1.0 release**: strictly 13 files (engine, CLI, API, tests, docs, CI) | **[PR #2 (Open)](https://github.com/krishika08/RepoNeedle/pull/2)** |
| **`research/v1.1-change-impact-archive`**| `fc8efa1` | `1d179ae` | **Permanent research archive**: complete immutable record of all R1–R6 research | Archive Branch |
| **`v1.1-change-impact`** | `fc8efa1` | `d72ffcf` | Original experimental branch with CI workflow | **[PR #1 (Open)](https://github.com/krishika08/RepoNeedle/pull/1)** |
| **`main`** | `78f73b8` | `78f73b8` | Original orphan repository root (untouched) | Mainline Reference |

---

## 3. PR #1 vs. PR #2 Comparison Matrix

| Dimension | Monolithic PR #1 (`v1.1-change-impact`) | Clean Production PR #2 (`v1.1-production-release`) |
| :--- | :---: | :---: |
| **Total Files Changed** | **211 files** | **13 files** ($93.8\%\text{ reduction}$) |
| **Lines Changed** | $+39,563$ / $-57$ | $+894$ / $-57$ ($97.7\%\text{ reduction}$) |
| **Production Source Code** | 10 files (2,356 lines) | 10 files (2,356 lines) — *Identical* |
| **Production Tests** | 1 file (242 lines, 11 tests) | 1 file (242 lines, 11 tests) — *Identical* |
| **User Documentation** | 1 file (144 lines) | 1 file (144 lines) — *Identical* |
| **CI Automation** | `.github/workflows/ci.yml` (added) | `.github/workflows/ci.yml` (included) |
| **Research Reports** | 99 files (14,381 lines) | **0 files** (Moved to research archive) |
| **Benchmark Datasets** | 6 files (2,820 lines, 2.66 MB) | **0 files** (Preserved on archive branch) |
| **Research Scripts** | 85 files (10,924 lines) | **0 files** (Preserved on archive branch) |
| **Research Regression Tests** | 5 files (`test_ranking_r*.py`) | **0 files** (Preserved on archive branch) |
| **Pytest Pass Count** | 308 passed (17.37s) | 270 passed (17.21s) |
| **Review Complexity** | Very High (Days of effort) | **Optimal (< 30 minutes)** |

---

## 4. Git Safety & Provenance Invariants

Throughout this restructuring, strict Git safety protocols were maintained:

1. **No Force-Pushes**: Neither local nor remote branch histories have been rewritten. `git push --force` was never invoked.
2. **No Overwriting of `main`**: Branch `origin/main` (SHA: `78f73b8`) remains completely untouched.
3. **Historical Tag Preservation**: All historical release tags (`v0.1.0-baseline`, `v0.1.0-release`, `stage3-candidate-freeze`) remain bit-identical at their original commits.
4. **Zero Data Loss**: No research artifacts, datasets, or evaluation scripts were deleted. Remote branch `origin/research/v1.1-change-impact-archive` guarantees perpetual provenance.
5. **PR #1 Preservation**: PR #1 was **not** closed unilaterally. A formal release audit comment was posted on PR #1 documenting the relationship with PR #2 and awaiting maintainer direction.

---

## 5. Review & Merging Recommendations for Maintainers

### Step 1: Review and Merge PR #2
1. Open [PR #2](https://github.com/krishika08/RepoNeedle/pull/2).
2. Review the 13 production files (see [`PRODUCTION_FILE_MANIFEST.md`](file:///F:/RepoNeedle/PRODUCTION_FILE_MANIFEST.md)).
3. Verify that GitHub Actions CI passes across Python 3.10, 3.11, and 3.12.
4. Merge PR #2 into `v1.0-zero-failure` (via Squash-and-Merge or Rebase-and-Merge).

### Step 2: Handle PR #1
- **Option A (Recommended)**: Close PR #1 with a note: *"Superseded for production release by PR #2. Research history preserved on branch `research/v1.1-change-impact-archive`."*
- **Option B**: Convert PR #1 into a dedicated research draft PR targeting a separate `research/` branch.

### Step 3: Fast-Forward or Synchronize `main` (Optional)
When maintainers wish to make `v1.0-zero-failure` / `v1.1-production-release` the default `main` branch:
```bash
git checkout main
git merge v1.1-production-release --allow-unrelated-histories -m "chore: align main with V1.1.0 production release"
git push origin main
```
