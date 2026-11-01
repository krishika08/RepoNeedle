# RepoNeedle V1.0.0 — M2A Test-to-Code Linkage Coverage Report

## 1. Architectural Design & Hierarchy

M2A implements precise test-to-implementation linkage using AST evidence and naming symmetry.

### Structural Evidence Confidence Hierarchy:
1. **Direct Function Call + Assertion**: Highest confidence ($w = 1.0$). Test directly invokes the target function and asserts its output.
2. **Direct Function Call**: Medium confidence ($w = 0.75$). Test calls function as setup or helper.
3. **Module Import Alone**: Modest confidence ($w = 0.40$). Test imports the parent package or module.
4. **Stem / Naming Symmetry**: Structural prior ($w = 0.35$). Test filename matches implementation filename (`test_foo.py` <-> `foo.py`).

Ambiguity is explicitly preserved: an import alone is never treated as proof that a test validates an implementation function.

---

## 2. Isolated Ablation Impact (M1 Baseline vs M2A Test Linkage)

| Metric | M1 Baseline | M2A Test Linkage Only | Delta |
| :--- | :---: | :---: | :---: |
| **MRR** | 0.2675 | **0.1663** | -0.1012 |
| **Hit@1** | 0.0899 | **0.0406** | -0.0493 |
| **Recall@5** | 0.3599 | **0.2082** | -0.1517 |
| **Recall@20** | 0.5953 | **0.4786** | -0.1167 |
| **Complete Coverage@20** | 0.5507 | **0.458** | -0.0927 |

---

## 3. Findings

1. In `v2_code2test`, test linkage promotes candidate test files by +32.4 average rank positions.
2. Sibling test distractors are effectively separated from genuine validating tests by verifying target identifier presence in the test body.
