# RepoNeedle Stage 3.7: Authoritative Decision & Governance Report

**Document ID**: `STAGE3-7-DECISION-REPORT-001`  
**Date**: October 2026  
**Stage**: Stage 3.7 — Canonical Evaluation Reconciliation and Research Integrity Gate  
**Branch**: `research-program`  
**Base Commit**: `9a9944a`  
**Evaluated Systems**: `BASE-BM25`, `CAND-C`, `CAND-F`, `BASE-REPOMAP`  
**Evaluation Scope**: Full ARB v2 Positive Development Benchmark ($N = 345$ queries across $K = 25$ repositories)  

---

## 1. Executive Summary & Verdict

Stage 3.7 establishes the authoritative, canonical evidence foundation for RepoNeedle by reconciling metric discrepancies, auditing the statistical conclusions, resolving the Candidate C MRR drop, and locking a single unified evaluation protocol.

```
[STAGE 3.7 VERDICT] RECONCILED UNDER CANONICAL PROTOCOL — NO REPONEEDLE CANDIDATE BEATS REPOMAP
```

The audit conclusively establishes that:
1. Under an unconstrained full-corpus evaluation contract, neither Candidate C ($MRR = 0.1399$) nor Candidate F ($MRR = 0.1351$) outperforms pure BM25 ($MRR = 0.1735$).
2. Version-pinned official RepoMap (`9e4d689`) remains decisively ahead of all RepoNeedle candidates ($MRR = 0.2293$, $\text{Recall@20} = 0.6599$).
3. The historical Candidate F victory claim ($0.2152$ vs RepoMap $0.2140$) is formally invalidated.

---

## 2. Answers to Mandatory Decision Gate Questions

### Question 1: What are the canonical full-corpus MRR, fractional Recall@k, binary Hit@k, and BCY results for BM25, RepoMap, Candidate C, and Candidate F?

Evaluated across all $N = 345$ positive queries under the identical, unconstrained full-corpus contract ([`CANONICAL_RESULTS.csv`](file:///F:/RepoNeedle/research/stage3_7/CANONICAL_RESULTS.csv)):

| System Identifier | MRR | Recall@5 (Frac) | Recall@10 (Frac) | Recall@20 (Frac) | Hit@20 (Binary) | Precision@5 | Token BCY@8k | Latency p50 | Latency p95 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BASE-BM25`** | **0.1735** | 0.1986 | 0.3118 | 0.4549 | 0.5304 | **0.0568** | 0.1957 | **20.85 ms** | 478.58 ms |
| **`CAND-C`** | 0.1399 | **0.2111** | 0.3196 | 0.5105 | 0.6000 | 0.0557 | 0.2034 | 31.50 ms | 561.46 ms |
| **`CAND-F`** | 0.1351 | 0.1824 | **0.3316** | 0.5078 | 0.6029 | 0.0504 | 0.1775 | 32.42 ms | 566.28 ms |
| **`BASE-REPOMAP`** | **0.2293** | **0.3337** | **0.5110** | **0.6599** | **0.7478** | 0.0186 | **0.3177** | 180.20 ms | 180.20 ms |

*(Note: Multi-target fractional Recall@20 and Binary Hit@20 are strictly segregated. Binary hit rates are systematically higher because queries frequently possess $\ge 2$ gold files).*

---

### Question 2: Are all comparisons computed on the same query set, eligible corpus, and metric contract?
**YES.**
Every configuration evaluated in [`PER_QUERY_RESULTS.jsonl`](file:///F:/RepoNeedle/research/stage3_7/PER_QUERY_RESULTS.jsonl) received the exact same 345 positive queries, checked out at identical base commits, searching the complete eligible corpus of every repository, using identical POSIX path normalization and deterministic tie-breaking.

---

### Question 3: Which historical performance claims are invalidated or non-comparable?
Documented in [`METRIC_DISCREPANCY_LEDGER.md`](file:///F:/RepoNeedle/research/stage3_7/METRIC_DISCREPANCY_LEDGER.md):
1. **`CAND-F` MRR = 0.2152**: `INVALIDATED`. Relied on hardcoded string bypasses in `graph.py` and uncoupled Stage 2 lookups. End-to-end full corpus execution collapses to $0.1351$.
2. **`BASE-REPOMAP` MRR = 0.2140**: `INVALIDATED`. Unmeasured static paper constant hardcoded in `evaluate_graph_retrieval.py:278`. Pinned RepoMap actually achieves $0.2293$.
3. **`BASE-BM25` Recall@20 = 0.4928**: `NON_COMPARABLE`. Mislabeled Binary Hit@20 ($170/345 = 0.4928$) as fractional recall. True canonical fractional Recall@20 is $0.4549$.
4. **`BASE-REPOMAP` Recall@20 = 0.5681**: `NON_COMPARABLE`. Mislabeled Binary Hit@20 ($196/345 = 0.5681$). Pinned RepoMap achieves $0.6599$ fractional Recall@20 and $0.7478$ binary hit rate.
5. **`CAND-C` Recall@20 = 0.5516 & MRR = 0.2040**: `NON_COMPARABLE`. Calculated on candidate-restricted pools (`tests_only` on code2test). On unconstrained full corpus, true fractional recall is $0.5105$ and MRR is $0.1399$.

---

### Question 4: Does Candidate C or Candidate F demonstrate a statistically supported advantage over the canonical BM25 baseline?
**NO.**
1. **MRR**: Both Candidate C ($0.1399$) and Candidate F ($0.1351$) regress substantially below pure BM25 ($0.1735$).
2. **Statistical Significance**: The repository-clustered bootstrap 95% confidence interval for Candidate F vs BM25 is $[-0.0882, +0.0299]$, which broadly crosses zero. While Candidate F showed a modest gain on Recall@20 ($+0.0529$), the wins are concentrated in only 3 modular repositories (`click`, `tokio`, `ruff`), while large multi-package codebases (`etcd`, `caddy`, `eslint`) regressed. RepoNeedle currently has **no verified general statistical advantage over pure BM25**.

---

### Question 5: Does RepoNeedle outperform the pinned RepoMap baseline on any preregistered primary retrieval metric under this protocol?
**NO.**
Pinned official RepoMap (`9e4d689`) holds a statistically decisive lead over both Candidate C and Candidate F across all primary retrieval metrics:
- MRR: RepoMap $0.2293$ vs Candidate F $0.1351$ ($\Delta = +0.0942, p < 0.0001$).
- Recall@20: RepoMap $0.6599$ vs Candidate F $0.5078$ ($\Delta = +0.1520, p < 0.0001$).
- Token BCY@8k: RepoMap $0.3177$ vs Candidate F $0.1775$.

RepoNeedle's only advantage over RepoMap is execution latency: $32.42\text{ ms}$ (p50) vs $180.20\text{ ms}$.

---

### Question 6: Is independent ContextBench evaluation still blocked?
**YES.**
Independent validation remains formally **`BLOCKED — DATA ACCESS`**. Outbound network requests to Hugging Face returned HTTP 403 Forbidden under the sandbox boundary. In accordance with research integrity governance, no surrogate or mock datasets were substituted.

---

### Question 7: Which specific claims are now reproducible, which remain uncertain, and which are unsupported?
1. **Reproducible**:
   - Canonical ARB v2 full-corpus numbers for BM25, RepoMap, Candidate C, and Candidate F.
   - The root cause of Candidate C's MRR drop ($0.2040 \to 0.1399$) due to removing candidate pre-filtering.
   - The root cause of Candidate F's collapse ($0.1351$) due to supernode PageRank dilution and token length inflation.
2. **Uncertain / Requiring External Validation**:
   - Independent generalizability across unseen codebases (blocked pending ContextBench access).
   - Component isolation effects (mitigating PageRank dilution while preserving subword lexical matching).
3. **Unsupported / Formally Retracted**:
   - The claim that Candidate F beat RepoMap (MRR $0.2152$ vs $0.2140$).
   - The claim of a universal 100 MB process memory ceiling.
   - Any claim that ARB v2 scores represent independent generalization.
