# RepoNeedle Stage 3.13: Architectural & Reproducibility Decision Report

**Stage**: Stage 3.13 — Canonical Reproducibility and Evidence Reconciliation  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  
**Anchor Commits**: `4f78cc3` (Stage 3.5) $\to$ `275f0ae` (Stage 3.12 / HEAD)  
**Date**: October 30, 2026  
**Final Formal Decision**: **`RECONCILED`**  

---

## 1. Formal Decision & Justification

The formal decision for Stage 3.13 is **`RECONCILED`**.

### Justification
1. **100% Mathematical Reconciliation**:
   All 11 material discrepancies cataloged between Stage 3.5 and Stage 3.12 have been forensically explained, reproduced on raw query predictions, and reconciled under one uniform canonical evaluation protocol ([`research/stage3_13/METRIC_DISCREPANCIES.csv`](file:///F:/RepoNeedle/research/stage3_13/METRIC_DISCREPANCIES.csv)).
2. **Complete Query Alignment**:
   All 345 positive ARB v2 queries and 218 repository snapshots match with zero exclusions, zero additions, and zero synthetic bypasses ([`research/stage3_13/PER_QUERY_RESULTS.csv`](file:///F:/RepoNeedle/research/stage3_13/PER_QUERY_RESULTS.csv)).
3. **Candidate F Claims Formally Retracted**:
   Candidate F's reported score of $0.2152$ is proven to be an artifact of candidate pool pre-filtering (`tests_only` in `code2test`), synthetic `ripgrep` bypasses, and mislabeled binary hit rates. Under unconstrained canonical evaluation, Candidate F collapses to **$0.1338$ MRR**, significantly below baseline BM25 ($0.1752$, $p = 4.01 \times 10^{-14}$).
4. **RepoMap Reference Provenance Fixed**:
   The static dictionary constant ($0.2140$ MRR) in Stage 3.5 is replaced by empirical predictions from version-pinned official RepoMap (`9e4d689`), achieving **$0.2293$ MRR** and **$0.6599$ Recall@20**.
5. **Memory and Latency Grounded**:
   The universal sub-100 MB ceiling is falsified; memory scales with codebase size ($112.7\text{ MB}$ for Click, $198.0\text{ MB}$ for Caddy, $364.1\text{ MB}$ for Etcd). Latency is right-skewed; warm query median (P50) is **$8.44\text{ ms}$** (21x faster than RepoMap's $180.20\text{ ms}$).
6. **Test Suite Integrity Confirmed**:
   The full project test suite contains **171 tests, all passing synchronously in 7.31 seconds**.

---

## 2. Canonical Score Ledger

Under the 100% unconstrained candidate pool across all 345 positive ARB v2 queries:

| System Name | Canonical Mean MRR | Fractional Recall@20 | Binary Hit@20 | Token BCY@8k | Warm P50 Latency | Isolated Process RSS |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `BASE-BM25` | 0.1752 | 0.4535 | 0.5275 | 0.2150 | 6.82 ms | 112.7 MB |
| `CAND-C` | 0.1401 | 0.5100 | 0.5797 | 0.2516 | 31.50 ms | 124.6 MB |
| `CAND-F` | 0.1338 | 0.5083 | 0.5739 | 0.2412 | 32.42 ms | 124.6 MB |
| `CONTROL-CASCADE` | 0.1897 | 0.5605 | 0.6435 | 0.2586 | 8.50 ms | 112.7 MB |
| `ARM-111` (`PROPOSED`) | 0.2061 | 0.5619 | 0.6464 | 0.2764 | 8.44 ms | 112.7 MB |
| `ARM-101` (`OPTIMAL`) | **0.2078** | **0.5648** | **0.6493** | **0.2822** | **8.76 ms** | **112.7 MB** |
| `BASE-REPOMAP` | **0.2293** | **0.6599** | **0.7478** | **0.3177** | 180.20 ms | 185.0 MB |

---

## 3. Governance Confirmations

- **Production Source Code**: Completely untouched. All research code resides in `research/`.
- **Immutable Git Tags**: Verified unchanged:
  - `v0.1.0-baseline` $\to$ `8e0042553a14b6e3c6cf5b35823c4da84181a8e9`
  - `stage3-candidate-freeze` $\to$ `cd7f3b01e28695f9a9357e0815069e0eae85baca`
- **ContextBench**: Designated as **`BLOCKED / PRELIMINARY`**.
- **RepoMap Relationship**: RepoMap achieves higher retrieval quality ($0.2293$ vs $0.2078$). RepoNeedle delivers an operational throughput advantage ($8.44\text{ ms}$ vs $180.20\text{ ms}$).
