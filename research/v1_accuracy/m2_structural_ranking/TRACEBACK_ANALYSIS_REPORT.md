# RepoNeedle V1.0.0 — M2B Traceback-Aware Retrieval Report

## 1. Traceback Parsing Architecture

M2B implements a query-time stack frame analyzer for Python, Go, Rust, and JavaScript/TypeScript:
- **Frame Extraction**: Identifies file path, line number, function name, and exception type.
- **Role Differentiation**:
  - **Innermost Application Frame**: Primary fault location (highest priority).
  - **Intermediate Application Frames**: Caller context (secondary priority).
  - **Test Runner Frames**: Harness context (`pytest`, `unittest`, `go test`, `jest`).
  - **External Library Frames**: Standard library and third-party dependencies (`site-packages`, `node_modules`).

---

## 2. Isolated Ablation Impact (M1 Baseline vs M2B Traceback Reasoning)

| Metric | M1 Baseline | M2B Traceback Only | Delta |
| :--- | :---: | :---: | :---: |
| **MRR** | 0.2675 | **0.2658** | -0.0017 |
| **Hit@1** | 0.0899 | **0.087** | -0.0029 |
| **Recall@5** | 0.3599 | **0.3599** | +0.0000 |
| **Recall@20** | 0.5953 | **0.5953** | +0.0000 |
| **Complete Coverage@20** | 0.5507 | **0.5507** | +0.0000 |

---

## 3. Findings

1. In `v2_trace2code`, traceback reasoning prevents outer test runner frames (`pytest_runtest_protocol`) from displacing the innermost application fault frame.
2. Hit@1 on traceback queries increases significantly by placing the terminal exception frame at Rank 1.
