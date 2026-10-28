# REPONEEDLE STAGE 3 PRE-REGISTERED DECISION RULES & EVALUATION PROTOCOL

**Document ID**: `STAGE3-PREREG-001`  
**Registration Date**: 2026-10-28 (Pre-Test Registration)  
**Status**: LOCKED PRIOR TO INDEPENDENT EVALUATION  

---

## 1. Primary Metrics and Targets

### 1.1 Primary Retrieval Metric (Independent Held-Out Set)
- **Primary Metric**: **Context Recall@8k** (Percentage of gold-annotated context files/lines captured within the 8,000-token budget window).
- **Secondary Retrieval Metrics**:
  - **MRR (Mean Reciprocal Rank)** across candidate files.
  - **Context Precision@8k** (Proportion of retrieved tokens belonging to gold contexts).
  - **Budgeted Context Yield (BCY@8k)**: $\frac{\text{Gold Tokens Retrieved}}{\min(\text{Gold Tokens Total}, 8000)}$.
  - **F1 Score**: Harmonic mean of Context Recall@8k and Context Precision@8k.

### 1.2 Primary Downstream Metric (SWE-bench Lite Coding Agent)
- **Primary Downstream Metric**: **Patch Resolution Rate** (Percentage of instances where the coding agent produces a patch that passes the test harness).
- **Secondary Downstream Metrics**:
  - Context Quality Score (Token efficiency: gold tokens / total context tokens).
  - Agent Exploratory Tool Call Count (Fewer tool calls indicates more effective initial retrieval context).
  - Agent Failure Rate (Syntax error, timeout, or patch reject).

---

## 2. Pre-Registered Decision Criteria for Architectural Selection

To pass the Stage 3 Independent Generalization Gate, a candidate must satisfy all four pre-registered rules on the **held-out test partition**:

| Rule ID | Name | Formal Threshold Criterion | Statistical Test |
| :--- | :--- | :--- | :--- |
| **Rule 1** | **Statistical Superiority over BM25** | $\Delta_{\text{Recall@8k}} > 0$ with 95% repository-clustered bootstrap CI lower bound $> 0$. | 10,000 repository-clustered bootstrap iterations; paired $t$-test $p < 0.05$. |
| **Rule 2** | **Minimum Meaningful Retrieval Gain** | Relative gain $\ge +5.0\%$ on Context Recall@8k over matched BM25 baseline. | $\frac{\bar{Y}_{\text{Cand}} - \bar{Y}_{\text{BM25}}}{\bar{Y}_{\text{BM25}}} \ge 0.05$. |
| **Rule 3** | **Anti-Regression Boundary** | No individual repository in the held-out set may suffer a statistically significant regression exceeding $-10.0\%$ relative recall. | Per-repository paired difference check. |
| **Rule 4** | **Latency & Efficiency Envelope** | Median retrieval latency ($p_{50}$) must remain $\le 50.0$ ms per query on standard CPU. Memory footprint must remain $\le 100$ MB. | In-process timer and memory profiler on CPU. |

---

## 3. Multiple Comparisons & Model Selection Correction

- **Family-Wise Error Rate Control**: When comparing 5 candidates ($M=5$) against the baseline, apply the Holm-Bonferroni step-down procedure at $\alpha = 0.05$.
- **Pre-Registered Primary Candidate**: Based on Stage 2 results, **Candidate C** (Static Hybrid + Skeleton Compression + Doc Distractor Filtering) is pre-registered as the primary Track A production candidate.
- **Hypothesis Testing Hierarchy**:
  1. Test Candidate C vs BM25 (Primary Gate).
  2. If Candidate C passes, test Candidate D (Graph Diffusion) vs Candidate C.
  3. Test Candidate E (Polyglot Symbols) specifically on non-Python repositories.

---

## 4. Downstream Coding Agent Testing Protocol

- **Fixed Agent Scaffolding**: Agent prompt, reasoning model, file read/write tools, and system prompt remain strictly constant across runs.
- **Retriever as Controlled Variable**: The ONLY variable modified is the retrieval injection:
  - Agent without custom retrieval (Empty initial context / direct tool search).
  - Agent with BM25 initial context.
  - Agent with RepoMap initial context (where supported).
  - Agent with RepoNeedle Candidate initial context.
- **Audit Integrity Boundary**: If external infrastructure (Docker daemon permissions, sandboxed network isolation, or API keys) blocks executing full containerized unit tests on SWE-bench, the blocker must be formally logged as an infrastructure impediment, and retrieval-in-the-loop simulation must be reported without fabricating unit test execution.
