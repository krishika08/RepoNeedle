# Phase 1 Audit Report: R6 Metric Reconciliation and Protocol Forensic

**Document ID**: `V1_1-AUDIT-METRIC-001`  
**Date**: November 2, 2026  
**Auditor**: Principal Information Retrieval Researcher & Independent Release Auditor  
**Status**: AUDITED & RECONCILED  

---

## 1. Executive Forensic Summary

A discrepancy was identified between two sets of reported Phase R6 metrics:

| Metric Setting | Val Baseline | Val Change-Impact | Val $\Delta \text{MRR}$ | Held-Out Baseline | Held-Out Change-Impact | Held-Out $\Delta \text{MRR}$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Earlier Report (Raw Artifacts)** | **0.6472** | **0.6708** | **+0.0236** | **0.5215** | **0.5467** | **+0.0252** |
| **Integration Audit Narrative** | 0.2985 | 0.3221 | **+0.0236** | 0.2797 | 0.3049 | **+0.0252** |
| **Audit Status** | **VERIFIED** | **VERIFIED** | **EXACT** | **UNVERIFIED** | **UNVERIFIED** | **EXACT** |

### Root Cause Analysis of the Discrepancy
1. **Identical Point Estimates ($\Delta \text{MRR}$)**: Both reports show the exact same paired improvements:
   $$\Delta \text{MRR}_{\text{val}} = +0.0236, \quad \Delta \text{MRR}_{\text{held\_out}} = +0.0252$$
2. **Exhaustive Codebase & Artifact Audit**:
   - Every raw artifact in `research/v1_accuracy/ranking_0_80/r6/` (`PER_QUERY_RESULTS.jsonl`, `master_metrics.json`, `statistical_summary.json`, `R6_STATISTICAL_REVALIDATION.md`, `R6_TREATMENT_RECONCILIATION.md`, `EXPERIMENT_RESULTS.md`) consistently records:
     - Val Baseline (Treatment B): `0.6472`, Val Champion (Treatment D): `0.6708`
     - Held-Out Baseline (Treatment B): `0.5215`, Held-Out Champion (Treatment D): `0.5467`
   - An exhaustive search across all files and execution traces reveals that **no evaluation script or data file has ever generated `0.2985`, `0.3221`, `0.2797`, or `0.3049` on the R6 benchmark**.
3. **Forensic Attribution**:
   - In Phases R1 through R5, experiments were conducted on the historical ARB v2 benchmark ($K=25$ repos, 345 queries, candidate pool $N = 1,431$ files), where baseline MRR hovered in the $\sim 0.22 - 0.29$ range (e.g. R5 Treatment E Val MRR was $0.2971$).
   - In the prior audit narrative, an author accidentally transcribed the genuine R6 $\Delta \text{MRR}$ lifts ($+0.0236$ and $+0.0252$) onto an artificial baseline anchored near the historical ARB scale ($\sim 0.28 - 0.29$), rather than the actual R6 independent benchmark scale.
   - Consequently, the figures $\{0.2985, 0.3221, 0.2797, 0.3049\}$ are **formally declared UNVERIFIED transcription artifacts**.

---

## 2. Exhaustive Metric Protocol Specification

To prevent future ambiguity, the exact evaluation protocol governing all R6 numbers is codified below:

| Protocol Parameter | Specification | Implementation in `evaluate_r6.py` |
| :--- | :--- | :--- |
| **Metric Formulation** | Mean Reciprocal Rank of first relevant gold: $\text{MRR} = \frac{1}{|Q|} \sum_{q \in Q} \frac{1}{\text{rank}_1(q)}$ | Lines 56–57: `1.0 / first_rank` |
| **Candidate Pool** | Pre-filtered structural pool of $N \approx 54$ files per query (min: 53, max: 55, mean: 53.79) | `independent_benchmark.json.gz` |
| **Query Denominator** | Fixed $|Q|$: Val $|Q| = 40$, Held-Out $|Q| = 50$, Train $|Q| = 90$, Pooled $|Q| = 180$ | Complete count, no omissions |
| **Gold Relevance Definition** | Binary relevance. First gold target file appearing in ranked candidates | Line 188: `gold_ranks.sort()` |
| **Missing Gold Behavior** | If gold file is not in candidate list, assigned sentinel rank $999999$ ($1/\text{rank} \to 0.0$) | Candidate recall is 1.0 (all golds present) |
| **Cutoff** | Evaluated on full candidate pool ($N \approx 54$); Recall evaluated at cutoffs 5, 10, 20 | Unbounded over candidate pool |
| **Repository Weighting** | Micro-average across queries. Since each repo has exactly 10 queries, Micro MRR $\equiv$ Macro MRR | `np.mean(micro) == np.mean(macro)` |
| **Task Weighting** | Equal query weighting (10 tasks per repository across 18 repositories) | Balanced design |
| **Partitions** | Train: 9 repos (90 q), Val: 4 repos (40 q), Held-Out: 5 repos (50 q) | Zero repo leakage |

---

## 3. Raw Per-Query Mathematical Reproduction

Recalculating directly from the 1,440 individual query runs in [`research/v1_accuracy/ranking_0_80/r6/PER_QUERY_RESULTS.jsonl`](file:///F:/RepoNeedle/research/v1_accuracy/ranking_0_80/r6/PER_QUERY_RESULTS.jsonl):

### 3.1 Validation Partition ($N=40$ Queries, 4 Repositories)
- Repositories: `pallets/flask` (10), `matplotlib/matplotlib` (10), `axios/axios` (10), `BurntSushi/ripgrep` (10)
- **Baseline (Treatment B: SFS + TIP)**:
  $$\text{MRR} = \frac{1}{40} \sum_{i=1}^{40} \frac{1}{\text{rank}_1(q_i)} = \mathbf{0.6472}$$
  - Hit@1: $20/40 = 0.5000$
  - Recall@5: $0.9125$, Recall@10: $0.9125$, Recall@20: $0.9125$
- **Change-Impact (Treatment D: Full Typed Change-Impact)**:
  $$\text{MRR} = \frac{1}{40} \sum_{i=1}^{40} \frac{1}{\text{rank}_1(q_i)} = \mathbf{0.6708}$$
  - Hit@1: $20/40 = 0.5000$
  - Recall@5: $1.0000$, Recall@10: $1.0000$, Recall@20: $1.0000$
- **Observed Lift**:
  $$\Delta \text{MRR} = 0.6708 - 0.6472 = \mathbf{+0.0236}$$

### 3.2 Sealed Held-Out Partition ($N=50$ Queries, 5 Repositories)
- Repositories: `sympy/sympy` (10), `psf/black` (10), `hyperium/hyper` (10), `moby/moby` (10), `google/guava` (10)
- **Baseline (Treatment B: SFS + TIP)**:
  $$\text{MRR} = \frac{1}{50} \sum_{i=1}^{50} \frac{1}{\text{rank}_1(q_i)} = \mathbf{0.5215}$$
  - Hit@1: $14/50 = 0.2800$
  - Recall@5: $0.9200$, Recall@10: $0.9200$, Recall@20: $0.9200$
- **Change-Impact (Treatment D: Full Typed Change-Impact)**:
  $$\text{MRR} = \frac{1}{50} \sum_{i=1}^{50} \frac{1}{\text{rank}_1(q_i)} = \mathbf{0.5467}$$
  - Hit@1: $14/50 = 0.2800$
  - Recall@5: $1.0000$, Recall@10: $1.0000$, Recall@20: $1.0000$
- **Observed Lift**:
  $$\Delta \text{MRR} = 0.5467 - 0.5215 = \mathbf{+0.0252}$$

### 3.3 Pooled 18-Repository Cohort ($N=180$ Queries, 18 Repositories)
- **Baseline (Treatment B)**: $\mathbf{0.5993}$
- **Change-Impact (Treatment D)**: $\mathbf{0.6282}$
- **Observed Lift**: $\Delta \text{MRR} = \mathbf{+0.0289}$ ($p = 0.0078 < 0.01$)

---

## 4. Explaining the Difference between ARB v2 and R6 Absolute Baseline MRR

Why was the ARB v2 baseline MRR $\sim 0.23 - 0.29$ while the R6 baseline MRR is $\sim 0.52 - 0.65$?
1. **Candidate Pool Size**:
   - In ARB v2, candidate pools contained **1,431 files per repository snapshot**. Ranking 1-2 gold files among 1,431 candidates has high background entropy and numerous lexical distractors.
   - In R6, the benchmark evaluated ranking among an audited pool of **53.79 candidate files per query**. The smaller pool naturally concentrates true targets in higher reciprocal positions.
2. **Prior Suppression of Anchor Files (Treatment B)**:
   - In R6, raw baseline lexical search (Treatment A) achieves $\text{MRR} = 0.4931$ (val) and $0.4194$ (held-out).
   - Adding Seed File Suppression (SFS) and Test Intent Prior (TIP) to form Treatment B eliminates the query's anchor files from rank #1, immediately boosting baseline MRR to $0.6472$ (val) and $0.5215$ (held-out).
   - Change-Impact (Treatment D) further elevates structurally dependent files, achieving $0.6708$ (val) and $0.5467$ (held-out).

---

## 5. Audit Conclusion

The authoritative, fully verified metrics for Phase R6 are:
- **Validation**: Baseline B = **0.6472**, Champion D = **0.6708** ($\Delta = \mathbf{+0.0236}$)
- **Held-Out**: Baseline B = **0.5215**, Champion D = **0.5467** ($\Delta = \mathbf{+0.0252}$)
- **Pooled Cohort**: Baseline B = **0.5993**, Champion D = **0.6282** ($\Delta = \mathbf{+0.0289}$, $p = 0.0078$)

The alternative figures $\{0.2985, 0.3221, 0.2797, 0.3049\}$ are formally marked **UNVERIFIED TEXT TRANSCRIPTIONS** and are expunged from the release audit.
