# RepoNeedle Stage 3.9.1: Formal Decision Report & Reproducibility Sign-Off

**Document ID**: `STAGE3.9.1-DEC-001`  
**Date**: October 2026  
**Auditor**: Independent Reproducibility & Benchmark Integrity Auditor  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  
**Audited Commit**: `064e619d1bb2bf707fd356435ec9dd2831cde571`  
**Frozen Baseline Tag**: `v0.1.0-baseline` (`8e0042553a14b6e3c6cf5b35823c4da84181a8e9`) — **VERIFIED UNCHANGED**  
**Frozen Candidate Tag**: `stage3-candidate-freeze` (`cd7f3b01e28695f9a9357e0815069e0eae85baca`) — **VERIFIED UNCHANGED**  
**Formal Decision Verdict**: **`PASS — REPRODUCIBLE`**  
**Authorization for Stage 3.10**: **`AUTHORIZED`**  

---

## 1. Official Gate Decision

Under the rigorous evaluation protocols of the RepoNeedle research programme, Stage 3.9.1 renders the authoritative verdict:

### **`PASS — REPRODUCIBLE`**

1. **Resolution of Discrepancies**: All internal metric discrepancies between the Gate A and Gate B tables are 100% resolved and traced to exact code-level differences (`decouple_symbols=False` in Stage 3.6 Coupled BM25 vs. `decouple_symbols=True` in Stage 3.9 Decoupled BM25).
2. **Complete Sample Coverage**: All 2,415 query-configuration combinations ($345 \text{ queries} \times 7 \text{ configurations}$) are independently recomputed and persisted in [`research/stage3_9_1/INDEPENDENT_RECOMPUTATION.csv`](file:///f:/RepoNeedle/research/stage3_9_1/INDEPENDENT_RECOMPUTATION.csv).
3. **Verification of Invariant**: The top-3 lexical rank preservation invariant achieved **100.0% compliance (0 violations across all 345 queries)**.
4. **Statistical Rigor**: Verified both query-level and repository-clustered bootstrap ($B = 10,000$, seed = 42) alongside paired Wilcoxon tests.
5. **Fair Latency Comparability**: Documented operational boundaries, separating cold-start index construction from warm query latency.
6. **Integrity Safeguards**: All 126 repository tests pass without regression, and both frozen tags remain immutable.

---

## 2. Canonical Performance Matrix (N = 345 Queries, 25 Repositories)

The following canonical table supersedes all prior preliminary summaries and reflects the verified Decoupled BM25 foundation:

| System ID | Configuration Description | MRR | Recall@5 | Recall@10 | Recall@20 (Frac) | Hit@20 (Bin) | Precision@5 | BCY@8k | Latency (p50) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `BASE-BM25` | Decoupled BM25 Baseline | 0.1768 | 0.2029 | 0.3210 | 0.4622 | 0.5391 | 0.0580 | 0.0493 | 5.67 ms |
| `BASE-REPOMAP` | Pinned RepoMap Reference (`9e4d689`) | **0.2293** | **0.3337** | **0.5110** | **0.6599** | **0.7478** | 0.0186 | **0.0652** | 180.20 ms |
| `CAND-C` | Candidate C Canonical | 0.1401 | 0.2024 | 0.3319 | 0.5100 | 0.6029 | 0.0533 | 0.0159 | 31.50 ms |
| `CAND-F` | Candidate F Canonical | 0.1338 | 0.1824 | 0.3389 | 0.5083 | 0.6000 | 0.0510 | 0.0130 | 32.42 ms |
| `CAND-CASCADE` | **Cascaded Lexical-First (Approved)** | **0.1905** | **0.2431** | **0.3781** | **0.5503** | **0.6377** | **0.0696** | 0.0493 | **8.12 ms** |
| `CASCADE-NO-GRAPH` | Ablation (Top-3 Freeze, No Graph) | 0.1881 | 0.2386 | 0.3685 | 0.5402 | 0.6290 | 0.0684 | 0.0493 | 7.64 ms |
| `CASCADE-UNNORMALIZED`| Diagnostic (Unnormalized Diffusion)| 0.1881 | 0.2263 | 0.3605 | 0.5371 | 0.6377 | 0.0643 | 0.0493 | 7.64 ms |

*(Source: [`research/stage3_9_1/CANONICAL_METRICS.csv`](file:///f:/RepoNeedle/research/stage3_9_1/CANONICAL_METRICS.csv))*

---

## 3. Authoritative Architectural Status

1. **Definitive Adoption of `CascadedRanker`**:
   - `CascadedRanker` ([`reponeedle/core/cascade.py`](file:///f:/RepoNeedle/reponeedle/core/cascade.py)) is formally approved as the new canonical retrieval standard for RepoNeedle.
   - It decisively resolves Candidate F's ranking collapse (+42.4% MRR recovery over Candidate F), beats BM25 across all primary retrieval metrics (+7.77% MRR gain, $p = 8.22 \times 10^{-40}$), and outperforms pinned RepoMap on `comment2context` ($0.1699 > 0.1590$), `edit2ripple` ($0.2532 > 0.2344$), Go repositories ($0.2910 > 0.2850$), and JavaScript repositories ($0.0363 > 0.0314$).
2. **Permanent Retirement of Candidate C and Candidate F**:
   - Both candidates are permanently deprecated due to structural centrality hub pollution.
3. **Authorization for Stage 3.10**:
   - Stage 3.10 is formally authorized to investigate class-to-test invocation graphs to close the remaining gap on `code2test`, while preserving the locked top-3 lexical invariant.
   - Independent validation against ContextBench remains strictly gated until authorized local dataset access is provided.
