# RepoNeedle Stage 3.13 — Independent Validation Gate Readiness (ContextBench)

## 1. Independent Validation Gate Status: BLOCKED

- **Target Dataset**: `Contextbench/ContextBench`
- **Official Host**: `https://huggingface.co/datasets/Contextbench/ContextBench`
- **Sandbox Probe Result**: `HTTP Error 403: Forbidden (Sandbox Isolation Boundary)`
- **Gate Verdict**: **BLOCKED**
- **Integrity Rule**: Per RepoNeedle research integrity guidelines:
  1. No synthetic proxy benchmark is fabricated to substitute for the official dataset.
  2. No external network restriction or credential boundary is bypassed.
  3. ARB v2 is strictly development/regression evidence and is NEVER cited as independent generalization.

---

## 2. Official Specification & Verification Contract

When authorized unsandboxed network permission is granted by the user, the dataset will be ingested and verified according to the following deterministic contract:

### Expected Artifact Schema:
```json
{
  "id": "cb_sample_001",
  "repository": "facebook/react",
  "base_commit": "b8cf82f1d9e2a860cb6200fc60114f6b64f3316f",
  "query": "Fix memory leak in useEffect cleanup when unmounting async component",
  "gold_files": [
    "packages/react-reconciler/src/ReactFiberWorkLoop.js",
    "packages/react-reconciler/src/ReactFiberCommitWork.js"
  ],
  "budget_tokens": 8192
}
```

### Ingestion & Integrity Verification:
1. **SHA-256 Digest Verification**: Prior to unpacking or evaluation, the dataset archive must match the published upstream cryptographic hash.
2. **Zero-Overlap Audit**: Verify that repositories and queries in ContextBench do not leak into the ARB v2 development set.
3. **Execution Harness**: Run frozen configurations (`BASE-BM25`, `CONFIG-09`, `CONFIG-10`) with zero hyperparameter tuning.

---

## 3. Deterministic Validation Runner

The standalone verification entry point is implemented at:
[`research/stage3_13/validate_contextbench.py`](file:///F:/RepoNeedle/research/stage3_13/validate_contextbench.py)

Usage (when run outside sandbox):
```powershell
python research/stage3_13/validate_contextbench.py --verify-and-run
```
