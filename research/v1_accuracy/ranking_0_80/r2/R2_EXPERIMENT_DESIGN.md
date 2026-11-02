# RepoNeedle — Mission 0.80+ (Ranking Intelligence Research Programme)
# Phase R2 Deliverable 1: R2 Controlled Experiment Design

**Document ID:** `R2_EXPERIMENT_DESIGN.md`  
**Status:** Approved & Executed  
**Date:** November 2, 2026  
**Author:** Principal Search Relevance Engineer, Information Retrieval Researcher & ML Ranking Architect  
**Scope:** Phase R2 Controlled Ranking Experiments across 345 Queries in 25 Repositories  

---

## 1. Executive Charter & Mission Context

Mission 0.80+ establishes the disciplined research programme to elevate RepoNeedle's retrieval ranking to **$MRR \ge 0.80$**.
Following the Phase R1 forensic audit—which proved that candidate recall is already 100% (514/514 gold files present) and diagnosed that 82.5% of Rank 1 displacements stem from query seed self-retrieval and test/implementation confusion—Phase R2 executes the three highest-impact ranking treatments:

1. **R2.1: Seed File Suppression (SFS)**: Eliminates self-retrieval of input context files when developer intent is relational.
2. **R2.2: Test Intent Prior (TIP)**: Introduces runtime test-intent detection and asymmetric prior boosting for test discovery.
3. **R2.3: Stem & Directory Symmetry (SMS)**: Rewards structural filename stem correspondence and mirrored directory topologies.

---

## 2. Non-Negotiable Governance & Data Split

Phase R2 enforces strict experimental controls:
- **Preserve Frozen Baselines**: The production release `v0.1.0-release` (Top-20 MRR: 0.2287) and candidate reference M1 (Full-Pool MRR: 0.2675) remain immutable.
- **Identical Candidate Pool**: All treatments evaluate against identical candidate sets; candidate generation and CUD-Pack remain untouched.
- **Candidate Recall Invariant**: Candidate pool gold recall must remain $100.0\%$ (514/514) across all treatments. Seed files must be demoted, never deleted.
- **Zero-Oracle Inference**: No benchmark track labels, gold target paths, or oracle metadata may be used during inference.
- **Repository-Clustered Split**: Zero data leakage between partitions:
  - **Training Cluster (15 Repositories, 210 Queries)**: Feature extraction, ablation sweeps, and parameter tuning.
  - **Validation Cluster (5 Repositories, 60 Queries)**: Model selection, generalization verification, and hyperparameter validation.
  - **Held-Out Test Cluster (5 Repositories, 75 Queries)**: Strict blind evaluation executed exactly once after freezing the selected model.

| Split Name | Repositories Included | Query Count | Snapshot Count | Gold Target Files | Task Tracks Covered |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Train** | `gin`, `etcd`, `click`, `caddy`, `clap`, `spring-boot`, `vue`, `pip`, `fastapi`, `scrapy`, `ipython`, `tox`, `mockito`, `hypothesis`, `numpy` (15 repos) | 210 (60.9%) | 148 | 300 | `code2test`, `comment2context`, `edit2ripple`, `trace2code` |
| **Validation** | `tokio`, `diffusers`, `playwright`, `pydantic`, `eslint` (5 repos) | 60 (17.4%) | 33 | 92 | `code2test`, `comment2context`, `edit2ripple`, `trace2code` |
| **Held-Out** | `transformers`, `vite`, `pytest`, `ruff`, `mypy` (5 repos) | 75 (21.7%) | 37 | 122 | `code2test`, `comment2context`, `edit2ripple`, `trace2code` |
| **Total** | **25 Repositories** | **345 (100%)** | **218** | **514** | **Uniform Evaluation Scope** |

---

## 3. Controlled Experiment Matrix (Treatments A through H)

The experiment matrix systematically evaluates individual and combined treatments:

$$\text{Final Score } S(c) = S_{\text{M1}}(c) \times \Phi_{\text{SFS}}(c, Q) \times \Phi_{\text{TIP}}(c, Q) \times \Phi_{\text{SMS}}(c, Q)$$

| Treatment Code | Treatment Name | SFS Active ($\Phi_{\text{SFS}}$) | TIP Active ($\Phi_{\text{TIP}}$) | SMS Active ($\Phi_{\text{SMS}}$) | Theoretical Focus |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Treatment A** | Frozen Baseline | No ($1.0$) | No ($1.0$) | No ($1.0$) | Immutable reference M1 candidate ordering. |
| **Treatment B** | SFS Alone | Yes ($\gamma = 0.05$) | No ($1.0$) | No ($1.0$) | Isolates impact of seed self-retrieval elimination. |
| **Treatment C** | TIP Alone | No ($1.0$) | Yes ($\beta = 1.5$) | No ($1.0$) | Isolates impact of runtime test-intent boosting. |
| **Treatment D** | SMS Alone | No ($1.0$) | No ($1.0$) | Yes ($w = 0.1$) | Isolates impact of filename stem & mirrored symmetry. |
| **Treatment E** | SFS + TIP | Yes ($\gamma = 0.05$) | Yes ($\beta = 1.5$) | No ($1.0$) | Interaction of seed suppression and test prior. |
| **Treatment F** | SFS + SMS | Yes ($\gamma = 0.05$) | No ($1.0$) | Yes ($w = 0.1$) | Interaction of seed suppression and stem symmetry. |
| **Treatment G** | TIP + SMS | No ($1.0$) | Yes ($\beta = 1.5$) | Yes ($w = 0.1$) | Interaction of test prior and stem symmetry. |
| **Treatment H** | SFS + TIP + SMS | Yes ($\gamma = 0.05$) | Yes ($\beta = 1.5$) | Yes ($w = 0.1$) | Full composite multi-factor ranking treatment. |

---

## 4. Evaluation Protocol & Hypotheses

### Primary Hypotheses
1. **$H_1$ (Seed Trap)**: SFS (Treatment B) will reduce Rank 1 seed self-retrieval from $> 40\%$ to $0.0\%$, generating a statistically significant MRR gain ($\Delta \text{MRR} \ge +0.05$, $p < 0.01$).
2. **$H_2$ (Test Prior)**: TIP (Treatment C) will boost `code2test` MRR by $> +0.20$ without regressing non-test tasks (`trace2code`, `edit2ripple`).
3. **$H_3$ (Synergy)**: Combining SFS and TIP (Treatment E) will outperform either treatment individually, doubling Validation MRR ($> +100\%$ relative increase).
4. **$H_4$ (Generalization)**: The selected treatment will maintain its performance gain on the held-out test cluster without parameter tuning.

### Stop / Go Promotion Criteria
A treatment is eligible for promotion only if:
1. Candidate Pool Recall is **$100.0\%$** across all evaluated splits.
2. Validation MRR is strictly higher than Treatment A with **paired permutation $p < 0.05$**.
3. 95% bootstrap confidence interval of $\Delta \text{MRR}$ does not include zero.
4. Recall@20 on the validation set does not decrease relative to Treatment A.
5. P95 query re-ranking latency remains $< 50\text{ ms}$.

