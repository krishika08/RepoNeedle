# RepoNeedle Stage 3.9: Gate A Formal Decision & Reconciliation Report

**Document ID**: `STAGE3-9-GATE-A-001`  
**Date**: October 2026  
**Stage**: Stage 3.9 Gate A — Evaluation Provenance Reconciliation  
**Branch**: `research-program`  
**Current Commit**: `174c260`  
**Historical Commit**: `4f78cc3`  
**Audit Artifacts**:
- [`PROVENANCE_AUDIT.md`](file:///F:/RepoNeedle/research/stage3_9/PROVENANCE_AUDIT.md)
- [`METRIC_RECONCILIATION.csv`](file:///F:/RepoNeedle/research/stage3_9/METRIC_RECONCILIATION.csv)
- [`PER_QUERY_RANKING_DIFFERENCES.csv`](file:///F:/RepoNeedle/research/stage3_9/PER_QUERY_RANKING_DIFFERENCES.csv)
- [`INDEPENDENT_METRIC_VERIFICATION.md`](file:///F:/RepoNeedle/research/stage3_9/INDEPENDENT_METRIC_VERIFICATION.md)

---

## 1. Formal Gate A Decision

```
[GATE A DECISION] PASS — METRICS RECONCILED
```

The evaluation audit has traced every historical metric discrepancy between Stage 3.5 and Stage 3.8 to raw reproducible evidence, validated the clean-room metric calculations against hand-crafted fixtures, and established a single authoritative evaluation contract on the full unconstrained repository corpus ($N = 345$ positive instances).

Gate B (Cascaded Lexical-First Retrieval Experiment) is formally **AUTHORIZED**.

---

## 2. Summary Reconciliation Ledger

| System | Stage 3.5 Reported | Stage 3.8 Canonical | Discrepancy Status | Definitive Forensic Explanation |
| :--- | :---: | :---: | :---: | :--- |
| **`BASE-BM25`** | MRR: 0.1705<br>R@20: 0.4928 | MRR: 0.1735<br>R@20: 0.4549 | **RECONCILED** | Stage 3.5 reported binary Hit@20 ($170/345 = 0.4928$) mislabeled as recall, using Stage 2 chunk lookups. Canonical unconstrained full-corpus live run achieves $0.1735$ MRR and $0.4549$ fractional recall ($0.5304$ binary hit). |
| **`CAND-C`** | MRR: 0.2040<br>R@20: 0.5516 | MRR: 0.1399<br>R@20: 0.5105 | **RECONCILED** | Stage 3.5 evaluated on candidate-restricted pools (`tests_only` on code2test). Unconstrained full repository search introduces distractors, dropping MRR by $-0.0641$ to $0.1399$. |
| **`CAND-F`** | MRR: 0.2152<br>R@20: 0.5652 | MRR: 0.1351<br>R@20: 0.5078 | **RECONCILED / INVALIDATED** | Stage 3.5 relied on hardcoded string bypasses in `graph.py` and decoupled Stage 2 lookups. Full-corpus live execution collapses to $0.1351$ due to utility hub dilution. |
| **`BASE-REPOMAP`**| MRR: 0.2140<br>R@20: 0.5681 | MRR: 0.2293<br>R@20: 0.6599 | **RECONCILED / INVALIDATED** | Stage 3.5 hardcoded $0.2140$ from a static paper constant. Live evaluation of pinned RepoMap (`9e4d689`) achieves $0.2293$ MRR, $0.6599$ fractional recall, and $0.7478$ binary hit rate. |

---

## 3. Pre-Conditions for Gate B Execution

1. **Frozen Tag Immutability**:
   - `v0.1.0-baseline`: `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` (Verified).
   - `stage3-candidate-freeze`: `cd7f3b01e28695f9a9357e0815069e0eae85baca` (Verified).
2. **Evaluator Pin**: Agent Retrieval Bench v2 pinned at commit `9e4d68937f29`.
3. **Corpus Standard**: Unconstrained full repository corpus across all 25 repositories.
4. **Primary Retrieval Metric**: Multi-target fractional Recall@k and Mean Reciprocal Rank (MRR), with binary Hit@k reported strictly as a secondary diagnostic.
5. **No Production Ranking Override**: Experimental candidates remain decoupled and ablatable.

