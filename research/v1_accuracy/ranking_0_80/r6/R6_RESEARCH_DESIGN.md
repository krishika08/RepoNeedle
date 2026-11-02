# RepoNeedle — Phase R6: Research Design & Experimental Protocol

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R6 — Independent Benchmark & Generalization Research  
**Author**: Principal Information Retrieval Researcher, Benchmark Architect & Software Intelligence Engineer  
**Date**: November 2, 2026  
**Status**: Formal Experimental Specification  

---

## 1. Executive Mandate & Scientific Objective

Phase R5 established **Treatment F (Change-Impact Retrieval with Typed Dependency Graphs)** as the authoritative research champion:
- Validation MRR: **0.3235** (+8.88% relative boost vs R2 Treatment E, $p = 0.0001$)
- Held-Out MRR: **0.3183** (+7.35% relative boost vs R2 Treatment E, $p = 0.0843$)
- Candidate Recall: **100.0%** (514/514 gold target files preserved)
- Latency: **0.541 ms** on CPU (well within the 10 ms SLA)

However, the R5 promotion audit established a fundamental governance limitation:
> **Provenance Disclosure**: The 25 repositories of Agent Retrieval Bench (ARB) v2 have been exposed continuously across Phases R1 through R5. The diagnostic "held-out" split in ARB v2 shares 100% repository, query, and commit overlap with prior exploration phases, and its 95% clustered confidence interval spanned zero ($p = 0.0843$).
>
> Therefore, Treatment F cannot be promoted to production without **independent empirical proof of generalizability on genuinely unseen, unexamined software repositories**.

### The Phase R6 Mission:
1. Construct an **independent, leak-free code retrieval benchmark** comprising 15–20 open-source repositories completely disjoint from the 25 ARB repositories.
2. Build authentic developer retrieval queries spanning bug fixes, PR changes, code navigation, implementation discovery, test discovery, and change ripple.
3. Conduct a rigorous, zero-oracle audit of the change-impact graph to disentangle **confirmed AST/import relationships** from **heuristic naming/directory proximity relationships**.
4. Evaluate 8 controlled model configurations (A through H) on repository-clustered Train, Validation, and sealed Held-Out partitions.
5. Statistically determine whether Treatment F generalizes out-of-distribution to justify production integration.

---

## 2. Experimental Hypotheses

| Hypothesis | Description | Verification Criterion |
| :--- | :--- | :--- |
| **$H_1$ (Generalization Hypothesis)** | Typed Change-Impact retrieval outperforms the baseline ranker on previously unseen repositories. | Clustered $\Delta \text{MRR} > 0$ on Independent Validation with $p < 0.05$. |
| **$H_2$ (Graph Semantics Hypothesis)** | Confirmed structural edges (AST calls, actual imports, verified symbols) provide higher precision than heuristic edges (stem overlap, directory proximity). | Ablation of heuristic edges preserves or improves precision/MRR. |
| **$H_3$ (Confidence Calibration Hypothesis)** | Weighting edges by empirical relationship confidence outperforms uncalibrated binary edge propagation. | Treatment G achieves higher MRR than Treatment D without recall degradation. |
| **$H_4$ (Held-Out Generalization Hypothesis)** | Performance improvements persist on a completely sealed, unseen final held-out cohort. | Clustered 95% CI strictly bounded above zero ($p < 0.05$) on Independent Held-Out. |

---

## 3. Strict Research Governance & Non-Negotiable Constraints

1. **Zero Exposure Rule**: None of the 25 original ARB repositories (`gin`, `etcd`, `click`, `caddy`, `clap`, `spring-boot`, `vue`, `pip`, `fastapi`, `scrapy`, `ipython`, `tox`, `mockito`, `hypothesis`, `numpy`, `tokio`, `diffusers`, `playwright`, `pydantic`, `eslint`, `transformers`, `vite`, `pytest`, `ruff`, `mypy`) may be included as unseen repositories.
2. **Three Repository-Disjoint Partitions**:
   - **New Train Partition**: Used strictly for feature exploration and edge confidence calibration.
   - **New Validation Partition**: Used strictly for hyperparameter selection and model comparison.
   - **New Final Held-Out Partition**: Completely sealed during all development; evaluated once for final gate decision.
3. **Zero-Oracle Compliance**: At inference time, no ranker may access gold file paths, expected target counts, ground truth track labels, or test answers. All features must be computed strictly from query text, observable file paths, and candidate source AST structures.
4. **Repository-Clustered Statistical Inference**: All bootstrap confidence intervals (10,000 iterations) and permutation tests must resample entire repository clusters, not individual queries, accounting for intra-repository variance.
5. **CPU-First Operational Envelope**: All rankers and graph traversal engines must execute within sub-millisecond to single-digit millisecond latency on standard CPU hardware.

---

## 4. Model Configurations Under Evaluation

To isolate the exact causal factors contributing to retrieval performance, Phase R6 evaluates 8 controlled treatments:

- **Treatment A (V1 Baseline)**: The frozen RepoNeedle V1.0.0 retrieval engine.
- **Treatment B (R2 Treatment E)**: Seed File Suppression (SFS) + Test Intent Prior (TIP).
- **Treatment C (R4 Treatment D)**: Dense Semantic Subword Alignment + Multi-Hop Structural Expansion.
- **Treatment D (R5 Treatment F)**: Full Typed Change-Impact Retrieval (all 5 original typed edge channels).
- **Treatment E (R5 Without Heuristic Edges)**: Typed Change-Impact with heuristic edges (directory proximity, stem overlap, doc extension) completely removed.
- **Treatment F (R5 With Verified Relationships Only)**: Typed Change-Impact relying strictly on AST-resolved calls, actual import references, verified symbol definitions, and verified build manifests.
- **Treatment G (Confidence-Calibrated Change Impact)**: Continuous Bayesian confidence-weighted edge propagation based on empirical precision audits.
- **Treatment H (Best Combined Model)**: Multi-channel integration of verified structural impact, calibrated heuristics, and test intent priors selected exclusively on Validation data.

---

## 5. Decision Framework

The final verdict on Phase R6 and promotion readiness for RepoNeedle V1.1 is governed by three formal paths:
- **Outcome A (Reject R5)**: If Treatment F fails to beat Treatment B on unseen repositories or suffers catastrophic regression.
- **Outcome B (Retain R5 as Research Champion)**: If Treatment F demonstrates internal utility but fails to achieve statistically significant generalization on the sealed held-out partition.
- **Outcome C (Approve R5 for Controlled Production Integration)**: If Treatment F or an improved variant demonstrates statistically significant superiority ($p < 0.05$) across independent validation and held-out partitions, preserves 100% candidate recall, and satisfies all CPU latency SLAs.

