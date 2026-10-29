# RepoNeedle Stage 3.6: Forensic Repository Starting State & Lineage Verification

**Document ID**: `STAGE3-6-STATE-001`  
**Date**: October 2026  
**Auditor**: Forensic Research Integrity Team  
**Workspace**: `F:\RepoNeedle`  
**Current Git Branch**: `research-program`  
**Starting Commit**: `29bb3b90f301667ce6a10c2d7a2bcbaca924b182` (Stage 3.15)  
**Historical Target Commit**: `4f78cc3658dfb5e338a5458579d38d5d7ef416e8` (Stage 3.5)  
**Working Tree Status**: Clean (0 uncommitted changes)  

---

## 1. Lineage & Ancestry Verification

In accordance with Section 1 of the Stage 3.6 charter, the relationship between Stage 3.5 commit `4f78cc3` and Stage 3.15 commit `29bb3b9` was cryptographically verified:

```bash
git merge-base --is-ancestor 4f78cc3 29bb3b9
# Exit code: 0 (True - direct ancestor)
```

### Complete Linear Ancestry Path:
```
8e00425 (v0.1.0-baseline)
  │
  ▼
cd7f3b0 (stage3-candidate-freeze)
  │
  ▼
4f78cc3 [Stage 3.5: Architectural Decision & Candidate F introduction]
  │
  ▼
0fdc257 [Stage 3.5 normalization]
  │
  ▼
cbe6c49 [Stage 3.6: Authoritative ARB v2 evaluation & Candidate F audit]
  │
  ▼
60fb4c9 [Stage 3.7: Forensic evaluation reconciliation & research integrity audit]
  │
  ▼
fcab83b [Stage 3.8: Reproducibility lock, metric contract, and evidence audit]
  │
  ▼
91c6df8 [Stage 3.9: Ranking recovery, component isolation, and runtime optimization]
  │
  ▼
6ada204 [Stage 3.10: Canonical ranking recovery verification & statistical decisions]
  │
  ▼
59e77e6 [Stage 3.11: Cross-stage reconciliation, canonical recomputation, and statistical audit]
  │
  ▼
e350b14 [Stage 3.12: Performance hardening, fair benchmarking, and evidence closure]
  │
  ▼
bf7f4c8 [Stage 3.13: Canonical evidence reconciliation & independent validation gate]
  │
  ▼
3e889fc [Stage 3.14: Historical errata, runtime/memory reconciliation, and ContextBench gate]
  │
  ▼
29bb3b9 [Stage 3.15: ContextBench acquisition audit, fail-closed gate, and locked protocol] (HEAD)
```

Both Stage 3.5 commit `4f78cc3` and Stage 3.15 commit `29bb3b9` are present in the current repository history. All acquisition safeguards, evaluation adapters, and fail-closed gates developed in Stage 3.15 are fully incorporated into the working tree.

---

## 2. Frozen Tag Immutability Audit

| Tag Identifier | Expected Target Commit | Actual Target Commit | Tag Object Hash | Tag Type | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`v0.1.0-baseline`** | `8e00425` | `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` | `f9956f6273d4c23b...` | Annotated Tag | **VERIFIED UNCHANGED** |
| **`stage3-candidate-freeze`** | `cd7f3b0` | `cd7f3b01e28695f9a9357e0815069e0eae85baca` | `2354eaaf8b4fd5b7...` | Annotated Tag | **VERIFIED UNCHANGED** |

Both frozen tags remain strictly immutable and point to their original, frozen release commits.
