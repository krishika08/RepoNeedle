# RepoNeedle Stage 3.9: Repository & Commit Provenance Audit

**Document ID**: `STAGE3-9-PROV-001`  
**Date**: October 2026  
**Stage**: Stage 3.9 — Evaluation Provenance Reconciliation and Cascaded Ranking Research  
**Branch**: `research-program`  
**Current HEAD Commit**: `174c26048e31fff73d780f0528797485e352b860`  
**Stage 3.5 Reported Commit**: `4f78cc3658dfb5e338a5458579d38d5d7ef416e8`  

---

## 1. Git Lineage & Ancestry Verification

A strict forensic audit of the Git DAG was conducted using `git rev-parse` and `git merge-base --is-ancestor`.

### 1.1 Commit & Tag Verification Matrix
| Target Reference | Expected Hash | Actual Verified Hash | Verification Command | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Stage 3.8 HEAD** | `174c260` | `174c26048e31fff73d780f0528797485e352b860` | `git rev-parse HEAD` | **MATCH** |
| **Stage 3.5 Commit** | `4f78cc3` | `4f78cc3658dfb5e338a5458579d38d5d7ef416e8` | `git rev-parse 4f78cc3` | **MATCH** |
| **Frozen Baseline** | `v0.1.0-baseline` | `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` | `git rev-parse v0.1.0-baseline` | **IMMUTABLE** |
| **Frozen Candidate**| `stage3-candidate-freeze` | `cd7f3b01e28695f9a9357e0815069e0eae85baca` | `git rev-parse stage3-candidate-freeze` | **IMMUTABLE** |

### 1.2 Ancestry Confirmation
Execution of `git merge-base --is-ancestor 4f78cc3 174c260` returned exit code `0`.
- **Finding**: Stage 3.5 commit `4f78cc3` is a **direct linear ancestor** of current HEAD `174c260` on branch `research-program`.
- The commit chain progresses linearly:
  `4f78cc3` (Stage 3.5) $\to$ `0fdc257` $\to$ `cbe6c49` $\to$ `60fb4c9` $\to$ `fcab83b` $\to$ `91c6df8` $\to$ `6ada204` $\to$ `59e77e6` $\to$ `e350b14` $\to$ `bf7f4c8` $\to$ `3e889fc` $\to$ `29bb3b9` $\to$ `9a9944a` $\to$ `fd45220` (Stage 3.7) $\to$ `174c260` (Stage 3.8).

---

## 2. Experimental Environment & Dependency Provenance

- **Operating System**: Windows 11 Pro (win32)
- **Python Runtime**: Python 3.12.10 (64-bit)
- **Core Dependencies**:
  - `numpy`: 1.26.4
  - `scipy`: 1.13.1
  - `pytest`: 9.1.1
  - `networkx`: 3.3
  - `tiktoken`: 0.7.0 (`cl100k_base` model)
- **External Benchmark Pin**:
  - Submodule: `external/agent-retrieval-bench`
  - Version-Pinned Commit: `9e4d68937f29`
  - Corpus Manifest: `data/corpus/v2_selective_mixed/corpus_manifest.jsonl` (427 tasks across 25 repositories)

---

## 3. Provenance of Historical Results vs. Authoritative Protocol

| Dimension | Stage 3.5 Historical Workflow (`4f78cc3`) | Stage 3.8 / 3.9 Authoritative Workflow (`174c260`) |
| :--- | :--- | :--- |
| **Corpus Universe** | Selective chunk subsets (`v2_selective_mixed`, ~100–300 chunks per repo) | Full unconstrained repository corpus (all files in repo, ~1,000+ files per repo) |
| **Candidate Pre-Filtering** | Task-specific candidate filters (`tests_only` on code2test, `code_only` on trace2code) | Zero candidate pre-filtering; all queries search the entire eligible codebase |
| **BM25 Measurement** | Looked up from Stage 2 `EXP-016` cached JSONL records | Evaluated live end-to-end against full repository files |
| **RepoMap Measurement** | Static paper constant hardcoded in `evaluate_graph_retrieval.py:278` (`0.2140`) | Live execution of version-pinned official RepoMap (`9e4d689`) on identical full corpus |
| **Candidate F Logic** | Contained ripgrep hardcoded crate string bypass in `reponeedle/core/graph.py` | Hardcoded shortcuts excised in Stage 3.6; verified via fail-closed unit tests |
| **Recall Metric Schema** | Binary Hit@20 mislabeled as "Recall@20" in summary tables | Fractional multi-target Recall@20 strictly segregated from binary Hit@20 |

