# RepoNeedle Stage 3.9.5: Formal Decision on Lean Function Call Graph (LFCG)

> **Evaluation Authority:** RepoNeedle Architecture Governance  
> **Evaluation Reference:** EXP-386 (Query-conditioned edge-type-aware file graph)  
> **Candidate Systems:** EXP-392a (Unweighted LFCG), EXP-392b (Ambiguity-Penalized LFCG)  
> **Dataset:** 345 canonical positive ARB v2 queries across 25 repositories (104 queries in 13 Python repos)  
> **Evaluation Date:** November 1, 2026

---

## 1. Formal Decision & Verdict

### **VERDICT: REJECT CURRENT LFCG DIFFUSION FOR RETRIEVAL PROMOTION**

1. **EXP-392a and EXP-392b are REJECTED for promotion into RepoNeedle production retrieval.**
2. **EXP-386 remains the frozen, validated reference retrieval architecture.**
3. **No further heuristic graph-weight tuning or ad-hoc parameter adjustments on the current LFCG graph structure are authorized.**

---

## 2. Statistical Record of Final Controlled Pilot Results

The inferential statistics obtained from 10,000 paired repository-clustered bootstrap resamples (seed 42) are formally recorded as follows:

| Metric | Overall Benchmark (345 Queries) | Python-Eligible Subset (104 Queries) | Acceptance Gate | Gate Status |
|---|:---:|:---:|:---:|:---:|
| **Mean MRR Difference ($\Delta$)** | **-0.0029** | **-0.0096** | $\ge +0.0050$ | **FAILED** |
| **95% Clustered Bootstrap CI** | **[-0.0119, +0.0026]** | **[-0.0426, +0.0079]** | Strictly $> 0.0$ | **FAILED** |
| **p-value** | 0.1637 | 0.1596 | $< 0.05$ | **FAILED** |
| **Recall@5 Difference ($\Delta$)** | $+0.0000$ | $+0.0000$ | $\ge 0.0$ | Neutral |
| **Recall@10 Difference ($\Delta$)** | $+0.0000$ | $+0.0000$ | $\ge 0.0$ | Neutral |
| **Recall@20 Difference ($\Delta$)** | $+0.0000$ | $+0.0000$ | $\ge 0.0$ | Neutral |
| **Hit@20 Difference ($\Delta$)** | $+0.0000$ | $+0.0000$ | $\ge 0.0$ | Neutral |
| **BCY@8k Difference ($\Delta$)** | **-0.0010** | **-0.0032** | $\ge 0.0$ | **FAILED** |
| **Wins / Ties / Losses** | **2 / 337 / 6** | **2 / 96 / 6** | $\text{Wins} > \text{Losses}$ | **FAILED ($1:3$)** |

---

## 3. Core Evidence Warranting Rejection

The rejection of current LFCG diffusion is compelled by four insurmountable empirical findings:

### 3.1 The Gold-Target Reachability Bound (Structural Disconnection)
- Out of 104 Python queries, **67 queries ($64.42\%$) have zero gold target files parsed into the symbol graph**.
- Out of 145 Python gold files, **only 24 files ($16.55\%$) possess active `CALLS` edge connectivity**.
- In the `trace2code` and `edit2ripple` tracks, **exactly zero gold files have incoming or outgoing `CALLS` edges**.
- As a consequence, for **$97.68\%$ of queries (337 of 345)**, LFCG diffusion generates an activation boost of exactly zero ($\text{boost}_{\text{LFCG}} = 0$). Graph propagation is structurally incapable of reaching the gold set.

### 3.2 Super-Hub Distortion and Rank Pollution
- In the small minority of queries where diffusion did propagate, it produced **three times more losses than wins (6 losses vs 2 wins)**.
- High-degree utility function hubs (e.g. `backend_empty_cache` with in-degree 113 in Diffusers, `path_to_url` in Pip) diffuse activation indiscriminately into non-gold caller files.
- In both `huggingface/diffusers` and `pypa/pip`, this hub diffusion caused catastrophic rank demotions for queries whose gold files were already ranked #1 under EXP-386, dropping them to rank #3 ($\Delta\text{MRR} = -0.6667$).

### 3.3 The Structural Orphan Dominance
- Across all 13 Python repositories, out of 29,324 function nodes extracted, **20,401 nodes ($69.57\%$) are structural orphans** with in-degree = 0 and out-degree = 0.
- Attempting graph diffusion over a graph where $70\%$ of nodes are disconnected islands wastes indexing resources without providing communicative paths.

### 3.4 The Missing-Context Resolution Bottleneck
- In benchmark environments where source code is delivered via chunked JSONL records, symbol fragments lack top-level module import statements.
- Under strict fail-closed resolution standards, **$99.98\%$ of call sites inside snippet fragments cannot be safely resolved**. Relaxing this constraint would require unverified global name matching that severely compromises graph precision.

---

## 4. Preservation of Scope and Boundaries

1. **Production Code Immutability:** No code within [`reponeedle/`](file:///F:/RepoNeedle/reponeedle/) or [`external/`](file:///F:/RepoNeedle/external/) has been altered.
2. **Non-Rejection of Function-Level Information:** This formal decision explicitly rejects **whole-graph diffusion across Lean Function Call Graph edges**. It does **not** reject function-level indexing, signature analysis, docstring matching, or local symbol-aware lexical retrieval.
3. **Architectural Redirection:** Research is formally authorized to pivot toward **Fragment-Aware Lexical Retrieval (Stage 3.9.5 Phase 3–5)**.

