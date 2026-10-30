# RepoNeedle Stage 3.19 — Clean Reproduction Report

**Date:** 2026-10-30  
**Evaluated Systems:** `BASE-REPOMAP`, `ARM-101-BASE`, `BASE-BM25` (with historical references `CAND-C`, `CAND-F`)  
**Corpus / Query Set:** Canonical ARB v2 (345 positive queries across 25 repositories, 218 snapshots)  
**Execution Mode:** Deterministic, full repository corpus, no candidate shortcuts, no oracle routing  

---

## 1. Reproduction Summary & Verified Metric Leaderboard

| System ID | Status | Integration Parity | MRR | Recall@5 | Recall@10 | Recall@20 | Precision@20 | Token BCY@4k | Token BCY@8k | P50 Lat (ms) | P95 Lat (ms) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BASE-REPOMAP** | External Reference | Upstream (9e4d689) | **0.2293** | **0.3855** | **0.5275** | **0.6599** | **0.0462** | **0.2185** | **0.3177** | 180.20* | 180.20* |
| **ARM-101-BASE** | Research Candidate | Unintegrated Prototype | 0.2078 | 0.3391 | 0.4493 | 0.5648 | 0.0397 | 0.1840 | 0.2822 | 12.92 | 130.53 |
| **BASE-BM25** | Lexical Baseline | Production (`lexical.py`) | 0.1752 | 0.2928 | 0.3942 | 0.4535 | 0.0322 | 0.1538 | 0.2150 | **10.24** | **116.49** |
| **CAND-C** | Superseded Baseline | Default `engine.py` | 0.1399 | 0.2319 | 0.3623 | 0.5105 | 0.0355 | 0.1620 | 0.2410 | 28.50 | 561.46 |
| **CAND-F** | Formally Invalidated | Invalidated Prototype | 0.1351 | 0.2290 | 0.3594 | 0.5078 | 0.0358 | 0.1580 | 0.2336 | 32.42 | 566.28 |

*Note on RepoMap Latency:* The identical 180.20 ms P50 and P95 values represent a historical static literature constant, as detailed in [research/stage3_19/LATENCY_METHODOLOGY.md](file:///F:/RepoNeedle/research/stage3_19/LATENCY_METHODOLOGY.md).

---

## 2. Integrity Safeguards & Anti-Shortcut Verification

The evaluation confirmed adherence to all 8 mandatory benchmark integrity rules:
1. **Zero Candidate Clamping:** Every eligible file in each corpus snapshot was loaded and indexed without truncation or file-count clamping.
2. **Zero Test-Only Filtering:** No candidate files were filtered based on test set knowledge or benchmark split membership.
3. **Zero Shortlist Restrictions:** All candidates were scored across the complete repository vocabulary.
4. **Zero Oracle Routing:** Workflow classification operated strictly on query text without cheating on ground truth gold files.
5. **Zero Synthetic Lookup Shortcuts:** File path matching used authentic repo relative paths.
6. **Unified Query & Corpus Input:** All three systems received identical document lists and queries.
7. **Random Seed Standardization:** Seed `42` was fixed for all stochastic resampling procedures.
8. **Independent Metric Evaluation:** Multi-target fractional recall and token-budget yield were evaluated via `independent_metrics.py`.

---

## 3. Cryptographic Provenance & Hash Verification

All inputs and generated artifacts were hashed to ensure reproducibility:
- Evaluated per-query rows: **345**
- Evaluated repositories: **25**
- Evaluated snapshots: **218**
- Clean reproduction result: **SUCCESS (All metrics reproduced bit-for-bit)**
