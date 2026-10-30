# RepoNeedle Stage 3.15 — Canonical Executive Decision Report

**Document ID**: `STAGE3-15-DECISION-001`  
**Date**: October 2026  
**Git Branch**: `research-program`  
**Base Commit**: `12142e8`  
**Frozen Baseline Tag**: `v0.1.0-baseline` (`8e0042553a14b6e3c6cf5b35823c4da84181a8e9`)  
**Frozen Candidate Tag**: `stage3-candidate-freeze` (`cd7f3b01e28695f9a9357e0815069e0eae85baca`)  

---

## 1. Formal Evidence-Based Verdict

```
================================================================================
FINAL RESEARCH VERDICT: [REPRODUCED WITH CORRECTIONS]
================================================================================
```

### 1.1 Decision Choice Justification
Under the strict preregistered governance rules of Phase 6:
- **`REPRODUCED WITH CORRECTIONS`** is selected because:
  1. The code implementations for Candidate C, Candidate F, Okapi BM25, and ARM-101 are fully preserved, verified, and reproducible under the canonical unconstrained evaluation protocol across all 345 positive ARB v2 queries.
  2. However, the reported Stage 3.5 figures and their architectural interpretations **require extensive formal correction**:
     - Candidate F's claimed MRR of **0.2152** relied on candidate-restricted pools (`test_only` for `code2test`), synthetic lookup dictionaries, and hardcoded Ripgrep string bypasses. When evaluated under the mandatory unconstrained 100% full repository corpus, Candidate F collapses to **MRR 0.1351** (below pure BM25 $0.1752$, paired Wilcoxon $p = 0.0122$).
     - The Stage 3.5 RepoMap reference MRR of **0.2140** was an unmeasured, hardcoded static paper constant from an earlier draft (`evaluate_graph_retrieval.py:278`). Live empirical evaluation of version-pinned official RepoMap (`9e4d689`) establishes the true MRR as **0.2293**.
     - Stage 3.5's reported RepoMap "Recall@20" of **0.5681** was actually Binary Hit@20 ($196 / 345 = 0.5681$). Under the official multi-target fractional recall contract, pinned RepoMap achieves **0.6599**.
     - The universal $\le 100\text{ MB}$ process memory claim was an artifact of clamping Caddy to 250 files and truncating to 25k chars. True Caddy requires 198 MB RSS (272.8 MB peak).

---

## 2. Canonical Architecture Hierarchy & Scoreboard

Evaluated over all 345 positive ARB v2 queries (218 commit snapshots) across 25 polyglot repositories under identical unconstrained candidate universes:

| Rank | System ID | Source Commit | MRR | Recall@20 | Hit@20 | Token BCY@8k | P50 Latency (ms) | Isolated Caddy RSS (MB) | Paired $\Delta$ MRR vs ARM-101 | Wilcoxon $p$-value | Governance Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | `BASE-REPOMAP` | `9e4d689` | **0.2293** | **0.6599** | **0.7478** | **0.3177** | 180.20 | 198.0 | $+0.0215$ | $p = 0.0559$ (NS) | **External Benchmark Leader** |
| **2** | **`ARM-101-BASE`** | **`12142e8`** | **0.2078** | **0.5648** | **0.6493** | **0.2822** | **12.92** | **198.0** | **0.0000** | — | **CANONICAL RESEARCH CHAMPION** |
| 3 | `ARM-111-UNIFORM` | `12142e8` | 0.2061 | 0.5619 | 0.6464 | 0.2764 | 13.22 | 198.0 | $-0.0017$ | $p = 0.00098$ | Rejected (Statistically Significant Drag) |
| 4 | `CONTROL-CASCADE` | `064e619` | 0.1897 | 0.5605 | 0.6435 | 0.2585 | 13.11 | 198.0 | $-0.0181$ | $p = 2.89 \times 10^{-16}$ | Superseded Rigid Cascade |
| 5 | `BASE-BM25` | `12142e8` | 0.1752 | 0.4535 | 0.5275 | 0.2150 | 10.24 | 198.0 | $-0.0326$ | $p = 6.41 \times 10^{-31}$ | Decoupled Lexical Baseline |
| 6 | `CAND-C` | `cd7f3b0` | 0.1399 | 0.5105 | 0.5913 | 0.2410 | 28.50 | 198.0 | $-0.0679$ | $p = 1.11 \times 10^{-24}$ | Superseded Stage 3 Candidate |
| 7 | `CAND-F` | `4f78cc3` | 0.1351 | 0.5078 | 0.5884 | 0.2336 | 32.42 | 198.0 | $-0.0727$ | $p = 3.59 \times 10^{-18}$ | Formally Invalidated Candidate |

---

## 3. Core Research Conclusions

1. **`ARM-101-BASE` Overwhelmingly Surpasses Candidate F**:
   - Paired difference: $\Delta \text{MRR} = +0.0727$ ($95\%\text{ CI}: [+0.0499, +0.0955]$).
   - Paired Wilcoxon signed-rank test: $W = 12821.5, p = 3.59 \times 10^{-18}$ (242 wins vs 94 losses).
   - Candidate F is completely obsolete.
2. **Operational Trade-Off with RepoMap**:
   - RepoMap holds an MRR advantage on the overall ARB v2 benchmark ($0.2293$ vs $0.2078$, $\Delta = +0.0215, p = 0.0559$).
   - RepoNeedle `ARM-101-BASE` holds a massive operational latency advantage: **$12.92\text{ ms}$ P50 latency vs RepoMap's $180.20\text{ ms}$ ($>13.9\times$ faster)**.
   - On Go repositories (142 queries), RepoNeedle `ARM-101-BASE` outperforms RepoMap (**$0.3125$ vs $0.2866$ MRR**).
3. **Internal vs External Validation Boundaries**:
   - ARB v2 serves strictly as an **internal development and regression benchmark**.
   - True independent external validation on **ContextBench** remains designated as **`BLOCKED / PRELIMINARY`** due to environment network sandbox restrictions on Hugging Face dataset downloads.

---

## 4. Single Next Research Priority

The reconciliation audit confirms that internal ARB v2 retrieval quality is maximized under `ARM-101-BASE` ($0.2078$ MRR, $12.92\text{ ms}$ latency).

**The single justified next research priority is:**
Execute official out-of-sandbox acquisition of the official ContextBench dataset (`https://huggingface.co/datasets/Contextbench/ContextBench`, SHA-256 `62828b6d080c55490fd38c...`) to conduct genuine, unblocked independent external validation of `ARM-101-BASE`. No further tuning on internal ARB v2 queries should be conducted.
