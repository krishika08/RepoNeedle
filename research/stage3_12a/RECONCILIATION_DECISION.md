# RepoNeedle Stage 3.12A: Final Reconciliation Decision Report

**Stage**: Stage 3.12A — Canonical Evaluation Reconciliation and Graph Research Gate  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  
**HEAD Commit**: `3f4822d`  
**Anchor Commit**: `4f78cc3` (Stage 3.5)  
**Date**: October 29, 2026  
**Final Formal Decision**: **`RECONCILED — READY FOR STAGE 3.12 EXPERIMENTS`**  

---

## 1. Executive Statement of Reconciliation

All historical and cross-stage metric discrepancies between Stage 3.5 and Stage 3.11 have been forensically explained, mathematically reconciled, and independently recomputed from raw query-level predictions under one uniform evaluation protocol:

1. **Candidate F Claims Disproven and Retracted**:
   The Stage 3.5 claim that Candidate F achieved $0.2152$ MRR and beat RepoMap ($0.2140$) was an artifact of:
   - Restricting candidate files to test files only in `code2test`.
   - Evaluating synthetic 2-file ripgrep fixtures containing hardcoded bypasses.
   - Reporting binary Hit@20 ($195/345 = 0.5652$) mislabeled as "Recall@20".
   - Hardcoding an unmeasured, deflated reference dictionary constant for RepoMap.
   Under true unconstrained full-corpus execution, Candidate F collapses to **$0.1338$ MRR** and **$0.5083$ Recall@20**, falling significantly below baseline Okapi BM25 ($0.1752$ MRR, $p = 1.46 \times 10^{-13}$).
2. **Current State-of-the-Art in RepoNeedle**:
   Under the 100% unconstrained candidate pool:
   - `BASE-BM25`: **$0.1752$ MRR**, **$0.4535$ Recall@20**
   - `CONTROL-CASCADE`: **$0.1882$ MRR**, **$0.5503$ Recall@20**
   - `TEST-GRAPH` (Stage 3.10): **$0.1897$ MRR**, **$0.5605$ Recall@20**
   - `FUNCTION-GRAPH` (Stage 3.11 Frozen): **$0.1901$ MRR**, **$0.5605$ Recall@20**
   - `FUNCTION-GRAPH-NO-FREEZE` (Stage 3.11 Exploratory): **$0.2082$ MRR**, **$0.5648$ Recall@20**
   - `BASE-REPOMAP` (Pinned `9e4d689`): **$0.2293$ MRR**, **$0.6599$ Recall@20**
3. **Stage 3.12 Research Readiness**:
   With all historical confusion resolved and raw per-query baselines locked, Stage 3.12 is authorized to begin controlled factor testing of soft lexical damping and hub attenuation.

---

## 2. Answers to Mandated Reconciliation Checkpoints

### 2.1 What Caused the Metric Discrepancies?
1. **Candidate Universe**: Stage 3.5 used task-aware candidate filtering (pruning code files in `code2test`), whereas Stage 3.11 enforces a 100% unconstrained candidate pool.
2. **Metric Definitions**: Stage 3.5 presented binary Hit@20 labeled as "Recall@20", whereas Stage 3.11 computes exact multi-target fractional recall.
3. **RepoMap Reference**: Stage 3.5 hardcoded a static dictionary constant (`0.2140` MRR), whereas Stage 3.11 utilizes live predictions from official version-pinned RepoMap on commit `9e4d689` (`0.2293` MRR).
4. **Diagnostic Shortcuts**: Stage 3.5 evaluated a synthetic 2-file micro-fixture for `ripgrep`, whereas Stage 3.11 runs full-corpus parsing with zero bypasses.

### 2.2 Which Comparisons Are Now Genuinely Apples-to-Apples?
All metrics in [`CANONICAL_METRIC_SUMMARY.csv`](file:///F:/RepoNeedle/research/stage3_12a/CANONICAL_METRIC_SUMMARY.csv) are 100% apples-to-apples:
- Evaluated on the identical 345 positive ARB v2 queries across 218 snapshots.
- 100% unconstrained candidate universe for every query.
- Identical clean-room metric implementations (`independent_metrics.py`).
- Identical tie-breaking (alphabetical by normalized document path).

### 2.3 Which Historic Claims Remain Unsupported?
1. The claim that Candidate F beat RepoMap ($0.2152$ vs $0.2140$) is **formally retracted**.
2. Any claim that RepoNeedle operates under a universal 100 MB RSS ceiling across all codebases is **falsified** (memory scales with repository size).
3. Any claim of independent generalization or SWE-bench patch resolution is **unsupported**; ContextBench remains `BLOCKED / PRELIMINARY`.

### 2.4 Can Candidate F Be Reproduced?
- Candidate F's original score of $0.2152$ cannot be reproduced under canonical evaluation rules because it relied on candidate filtering and synthetic fixtures.
- Candidate F's true unconstrained score (**$0.1338$ MRR**) is 100% reproducible and verified in [`CANONICAL_METRIC_SUMMARY.csv`](file:///F:/RepoNeedle/research/stage3_12a/CANONICAL_METRIC_SUMMARY.csv).

### 2.5 Are Stage 3.12 Experiments Justified?
**YES**. Stage 3.12 experiments are fully justified to resolve the trade-off between the Rank 1–3 freeze ceiling effect ($0.1901$ MRR) and unconstrained utility-hub regressions ($0.2082$ MRR) through Soft Lexical Damping and In-Degree Hub Attenuation, as preregistered in [`STAGE3_12_DESIGN_SPEC.md`](file:///F:/RepoNeedle/research/stage3_12a/STAGE3_12_DESIGN_SPEC.md).

---

## 3. Governance and Provenance Ledger

- **Branch**: `research-program`
- **Starting/Ending Anchor**: `3f4822d`
- **Frozen Baseline Tag**: `v0.1.0-baseline` (`8e0042553a14b6e3c6cf5b35823c4da84181a8e9` — VERIFIED)
- **Frozen Candidate Tag**: `stage3-candidate-freeze` (`cd7f3b01e28695f9a9357e0815069e0eae85baca` — VERIFIED)
- **Test Suite**: 160 unit and integration tests passing (`pytest`).
- **Production Code Status**: Production defaults in `reponeedle/` remain **completely untouched**.
