# RepoNeedle — Mission 0.80+ (Ranking Intelligence Research Programme)
# Phase R2 Deliverable 3: Test Intent Prior (TIP) Implementation Report

**Document ID:** `TIP_IMPLEMENTATION_REPORT.md`  
**Status:** Approved & Validated  
**Date:** November 2, 2026  
**Author:** Principal Search Relevance Engineer, Information Retrieval Researcher & ML Ranking Architect  
**Scope:** R2.2 Treatment Engineering, Asymmetric Prior Formulation, and Evaluation  

---

## 1. Problem Statement: Test versus Implementation Confusion

In code search systems, testing tasks have distinct asymmetric pragmatics:
- When a developer or agent submits a pull request with code changes and asks for corresponding tests, the prompt naturally describes the **implementation symbols** (e.g. `complete.rs`, `HelpTemplate`).
- Because implementation files contain the full struct, type, and function definitions, lexical matchers (BM25, subwords) score implementation files higher than test files.
- In ARB v2 Set A (`code2test`), **100.0% (148/148)** of gold files are test files. Yet under baseline M1, implementation files dominated positions 1 through 5, collapsing `code2test` MRR to **0.1589** (with only 4 Rank 1 hits across 106 queries).

---

## 2. Technical Architecture & Zero-Oracle Intent Classification

The TIP treatment was implemented in [`research/v1_accuracy/ranking_0_80/r2/src/test_intent.py`](file:///F:/RepoNeedle/research/v1_accuracy/ranking_0_80/r2/src/test_intent.py).

```mermaid
flowchart TD
    Q["Query Prompt & Metadata"] --> TIC["TestIntentClassifier<br/>Compute P(test_intent | Q) in [0.0, 1.0]"]
    TIC --> DECIDE{"P(test_intent) >= 0.5?"}
    DECIDE -->|No (Implementation Query)| NEUTRAL["Apply Neutral Prior<br/>Multiplier = 1.0 across all files"]
    DECIDE -->|Yes (Test-Seeking Query)| TRD["Candidate Role Detector<br/>is_test_candidate(path)"]
    TRD -->|Test File| BOOST["Asymmetric Boost<br/>S(c) = S(c) * (1.0 + beta * P) (beta = 1.5)"]
    TRD -->|Impl File| PRESERVE["Preserve Score<br/>S(c) = S(c) * 1.0 (No demotion)"]
```

### Component 1: Zero-Oracle Intent Classifier (`TestIntentClassifier`)
Never accesses ground-truth benchmark track labels. It infers test intent using runtime signals:
1. **Structural Metadata Triggers**:
   - `changed_file`, `implementation_files`, or `changed_file_summary` present in PR descriptions: $+0.55$ probability mass.
2. **Action Language Triggers**:
   - Verbs targeting test artifacts (`find|locate|write|add|verify` + `test|tests|spec|coverage`): $+0.35$.
3. **Execution Commands**:
   - `command` contains `go test`, `pytest`, `cargo test`, `npm test`: $+0.15$ (attenuated to $+0.05$ if `source_type` indicates application bug reproduction).
4. **Counter-Signals**:
   - Presence of `anchor_diff` (edit ripple seeking downstream code): $-0.20$.
   - Review comment on test file asking for business logic: $-0.10$.

### Component 2: Language-Agnostic Test Role Detector (`is_test_candidate`)
Universal test artifact detector covering Go, Rust, Python, TypeScript, JavaScript, Java, C/C++, and Ruby:
- **Directory Markers**: `/(tests?|__tests__|testsuite|spec|testing|src/test)/`
- **File Affixes**:
  - Python: `test_*.py`, `*_test.py`
  - Go: `*_test.go`
  - Rust: `tests/**/*.rs`, `*_test.rs`, `tests.rs`
  - TypeScript / JS: `*.test.ts`, `*.spec.ts`, `*.test.js`, `*.spec.js`
  - Java: `*Test.java`, `*Tests.java`, `*TestCase.java`

### Component 3: Asymmetric Prior Formulation (`TestIntentPrior`)
To avoid harmful unintended regressions on implementation queries, the prior is strictly **asymmetric**:
1. When test intent is active ($P \ge 0.5$):
   $$S_{\text{TIP}}(c) = \begin{cases} 
      S(c) \times (1.0 + \beta_{\text{test}} \cdot P(\text{test\_intent} \mid Q)) & \text{if } \text{is\_test\_candidate}(c) \\
      S(c) & \text{if implementation file (no global penalty)}
   \end{cases}$$
2. When test intent is negative ($P < 0.5$):
   $$S_{\text{TIP}}(c) = S(c) \quad \text{for all candidates}$$

---

## 3. Parameter Sweep on Training Set (210 Queries)

We evaluated the test boost weight $\beta_{\text{test}} \in [0.5, 3.0]$ on the Training set (15 repos):

| Boost Weight $\beta_{\text{test}}$ | Train MRR | Train Hit@1 | Train Recall@20 | Val MRR | Val Hit@1 | Val Recall@20 | Generalization Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline ($\beta = 0.0$)** | 0.3539 | 14.29% | 0.7499 | 0.1381 | 0.00% | 0.5125 | Unconditioned Baseline |
| **$\beta = 0.5$** | 0.3682 | 15.24% | 0.7681 | 0.1755 | 1.67% | 0.5361 | Moderate Lift |
| **$\beta = 1.0$** | 0.3836 | 17.14% | 0.7845 | 0.1897 | 1.67% | 0.5583 | Good Progression |
| **$\mathbf{\beta = 1.5}$ (Selected)** | **0.3978** | **19.05%** | **0.8009** | **0.2334** | **8.33%** | **0.5792** | **Optimal Generalization** |
| **$\beta = 2.0$** | 0.4002 | 19.05% | 0.8009 | 0.2494 | 10.00% | 0.5833 | Strong Performance |
| **$\beta = 2.5$** | 0.4018 | 19.05% | 0.8009 | 0.2585 | 11.67% | 0.5833 | Plateau |
| **$\beta = 3.0$** | 0.4027 | 19.05% | 0.8009 | 0.2591 | 11.67% | 0.5833 | Minor Diminishing Returns |

### Why $\beta = 1.5$ Was Selected
$\beta = 1.5$ produces a stable, robust $+0.0953$ MRR gain on Validation and $+0.0439$ on Train, while remaining conservatively balanced so that in cases of ambiguous intent, implementation candidates are not excessively suppressed.

---

## 4. Track-Level Impact (Treatment C vs Baseline A)

Evaluating Treatment C alone on the Validation set across task tracks confirms targeted effectiveness:

| Task Track | Queries ($n$) | Baseline A MRR | Treatment C MRR | $\Delta$ MRR | Hit@1 Lift |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`code2test`** | 21 | 0.1487 | **0.4208** | **+0.2721** | $0 \to 5$ hits |
| **`comment2context`** | 26 | 0.1178 | **0.1178** | **+0.0000** | Zero regression |
| **`edit2ripple`** | 7 | 0.1695 | **0.1695** | **+0.0000** | Zero regression |
| **`trace2code`** | 6 | 0.1521 | **0.1521** | **+0.0000** | Zero regression |
| **Validation Overall** | **60** | **0.1381** | **0.2334** | **+0.0953** | **$0 \to 5$ hits** |

**Conclusion:** TIP delivers a massive $+0.2721$ MRR surge on test-discovery queries while causing **zero regression ($0.0000\Delta$) on all three non-test task tracks**.

