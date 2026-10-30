# REPONEEDLE STAGE 3.6: GIT AND ENVIRONMENT MANIFEST

**Audit Date**: October 2026  
**Auditor**: Independent Research & Integrity Audit  
**Active Workspace**: `F:\RepoNeedle`  
**Active Branch**: `research-program`  
**Dedicated Audit Branch**: `research/stage3_6-audit`  

---

## 1. GIT ANCESTRY & COMMIT RECONCILIATION

### 1.1 Complete Historical Commit Lineage
| Stage Identifier | Short SHA | Full 40-Character Object SHA | Description | Ancestry Verification |
| :--- | :---: | :---: | :--- | :---: |
| **Stage 2** | `d826152` | `d826152e8e515f53e8ff356c3c7b9468e2140052` | Baseline evaluation and selective retrieval diagnostic | Direct Ancestor |
| **Stage 3.1** | `36879c6` | `36879c6ec7a3b37803f2780e2d142ca1dca5cb24` | Lexical candidate pool & subword index implementation | Direct Ancestor |
| **Stage 3.2** | `623c3bf` | `623c3bfcf2e65d21a97e416a2d989f6b92f7c00e` | Multi-tier context packing & skeleton token budgeting | Direct Ancestor |
| **Stage 3.3** | `50bcfd7` | `50bcfd7b7dbd76ce1e98d89e5fc82ea389ceca3d` | Documentation penalty filters and router ablation | Direct Ancestor |
| **Stage 3.4** | `878ff68` | `878ff68cfe8f3430ac3cc13278d277184f049df6` | Candidate C verification (reported BM25: 0.4467, RM: 0.6306) | Direct Ancestor |
| **Stage 3.5** | `4f78cc3` | `4f78cc3658dfb5e338a5458579d38d5d7ef416e8` | Candidate F claim commit (reported BM25: 0.4928, RM: 0.5681) | Direct Ancestor |
| **Stage 3.6 Audit Head** | `4f78cc3` | `4f78cc3658dfb5e338a5458579d38d5d7ef416e8` | Branch `research/stage3_6-audit` base point | Active Head |
| **Program Head** | `b4a6e58` | `b4a6e5827ca6b97d09d654d1d1f52096f26933e3` | Latest program commit on `research-program` | Working Tree |

### 1.2 Immutable Frozen Tags
| Tag Identifier | Tag Object SHA | Dereferenced Target Commit SHA | Verification Status |
| :--- | :---: | :---: | :---: |
| `v0.1.0-baseline` | `f9956f6273d4c23b29f261c80749a0d1292a9e4a` | `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` | **IMMUTABLE & VERIFIED** |
| `stage3-candidate-freeze` | `2354eaaf8b4fd5b7ea12288ba349f8b2414b7119` | `cd7f3b01e28695f9a9357e0815069e0eae85baca` | **IMMUTABLE & VERIFIED** |

*Tag Verification Assertion*: Neither tag has moved, been overwritten, or been amended. Verified via `git cat-file -p` and `pytest tests/test_stage3_6_forensic_reconciliation.py`.

---

## 2. SYSTEM ENVIRONMENT & HARDWARE ARCHITECTURE

- **Operating System**: Microsoft Windows 11 Home (Build 10.0.26200-SP0)
- **Architecture**: `AMD64` / `x86_64`
- **CPU**: Intel(R) Core(TM) Ultra 7 / Family 6 Model 170 Stepping 4, GenuineIntel (16 physical / 22 logical cores)
- **Total Physical RAM**: 32.0 GB
- **Primary Shell**: PowerShell 5.1 / PowerShell 7.5
- **File System**: NTFS (Drive `F:\`)

---

## 3. PYTHON RUNTIME & DEPENDENCY INVENTORY

- **Python Version**: Python 3.12.10 (tags/v3.12.10:9b7bc2d, Oct 10 2024, 15:45:15) [MSC v.1941 64 bit (AMD64)]
- **Pytest Version**: `pytest 9.1.1` (plugins: `anyio-4.15.1`, `asyncio-1.4.0`, `cov-7.1.0`)

### 3.1 Key Runtime & Scientific Packages
| Package | Version | Purpose |
| :--- | :---: | :--- |
| `numpy` | `2.5.2` | Matrix operations, score vectorization, and bootstrap resampling |
| `scipy` | `1.18.1` | Wilcoxon signed-rank tests and statistical distributions |
| `networkx` | `3.6.1` | Graph representation, PageRank, and directed edge traversal |
| `pydantic` | `2.13.5` | Data validation and structured immutable configuration schemas |
| `fastapi` | `0.110.0` | API routing interfaces |
| `pathspec` | `1.1.1` | Gitignore parsing and repository path filtering |
| `pytokens` | `0.4.1` | Token estimation and AST lexical analysis |

---

## 4. INTEGRITY PROTOCOL & SAFEGUARDS

1. **Tag Non-Mutation**: The research tags `v0.1.0-baseline` and `stage3-candidate-freeze` remain locked at their initial creation SHAs.
2. **Historical Preservations**: Stage 3.4 (`research/stage3_4/`) and Stage 3.5 (`research/stage3_5/`) artifacts and scripts are preserved strictly intact with no modifications or overwritten outputs.
3. **Audit Isolation**: All Stage 3.6 deliverables, scripts, and evaluation logs are contained within `research/stage3_6/` and executed on the audit branch `research/stage3_6-audit`.
