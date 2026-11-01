# RepoNeedle Stage 3.7.1: Failure Analysis & Root-Cause Deconstruction

**Document ID**: `STAGE3-7-1-FAIL-001`  
**Stage**: Stage 3.7.1 — Statistical Validation, Component Attribution & Research Integrity  
**Date**: November 1, 2026  
**Workspace**: `F:\RepoNeedle`  

---

## 1. Executive Summary

This report provides the comprehensive engineering failure analysis for Stage 3.7.1, deconstructing:
1. The exact mechanisms behind Candidate F's historical failure.
2. The localized failure cases of EXP-378 on CLI repositories (`pallets/click` and `clap-rs/clap`).
3. The 98.78% false-acceptance rate in selective abstention.
4. The discrepancy between file recall and context-packing yield (BCY@8k).

---

## 2. Forensic Analysis of Candidate F Failure Modes

Under the unconstrained full-corpus protocol, Candidate F collapsed to **0.1351 MRR**, lagging behind pure BM25 (**0.1735 MRR**). Our controlled ablations isolated three compounding failure mechanisms:

### 2.1 BM25 Document-Length Inflation
- In Okapi BM25, the normalization denominator is:
  $$\text{denom} = tf + k_1 \cdot \left(1 - b + b \cdot \frac{dl}{avgdl}\right)$$
- In Candidate F, polyglot symbols were coupled directly into the effective document length ($dl = 2.5 \cdot \text{len}(path) + 2.0 \cdot \text{len}(sym) + 1.0 \cdot \text{len}(body)$).
- In symbol-dense implementation files (e.g. `tests/models/auto/test_tokenization_auto.py` in `transformers`), $dl$ was inflated by 1.2x to 2.5x.
- Across 514 gold file instances, length inflation had a **Spearman $r = 0.6029$ ($p = 3.53 \times 10^{-52}$)** correlation with target rank dropouts.

### 2.2 Unbounded Bidirectional Diffusion & Hub Dilution
- Repository graphs exhibit power-law scale-free connectivity, with hub nodes (like `__init__.py` or `mod.rs`) connecting to up to **3,890 edges**.
- In Candidate F, unnormalized bidirectional diffusion ($\alpha_{\text{fwd}} = 0.25, \alpha_{\text{bwd}} = 0.20$) pumped score mass into these supernodes.
- Forward propagation along import edges was statistically proven to harm retrieval (**$p = 0.0112$, $\Delta \text{MRR} = -0.0037$**), flooding top ranks with generic utility modules and knocking gold targets out of top-20 ranks in **44.4%** of evaluated cases.

### 2.3 Unconditioned Static PageRank Dilution
- Blending static PageRank with 1/3 weight penalizes leaf implementation logic and specific function definitions.
- Restoring PageRank into the architecture (`EXP-379`) caused MRR to plummet from **0.2052 down to 0.1429 (-0.0623)**, confirming PageRank as the single largest drag on retrieval performance.

---

## 3. Localized Outlier Analysis: Why Did `click` and `clap` Regress?

In the repository-level breakdown, while 22 of 25 repositories improved under EXP-378, two CLI repositories exhibited notable regressions:
- `pallets/click` ($N=26$ queries): Mean MRR delta of **-0.1653**.
- `clap-rs/clap` ($N=10$ queries): Mean MRR delta of **-0.0849**.

### Root Cause
In CLI framework repositories, the core architecture is organized around central command decorator registries (e.g. `click/core.py`, `click/decorators.py`, `clap/src/parser.rs`).
- In Candidate C and Candidate F, static PageRank assigned astronomical scores to these central dispatchers.
- Because benchmark queries for CLI frameworks frequently include generic terms like "click command argument parser" or "command line options", Candidate C's static PageRank accidentally promoted `core.py` to rank #1.
- In EXP-378, removing static PageRank forced the system to rely strictly on query-conditioned lexical and subword matching. For queries that lacked specific parameter names, lexical matches on leaf files displaced the central command module.
- **Remedy for Stage 3.8**: Introduce query-conditioned centrality attenuation rather than uniform static PageRank.

---

## 4. Selective Abstention Failure (98.78% False Accept Rate)

Under the default static threshold ($\text{max\_score} < 0.38$), only 1 of 82 zero-gold queries was rejected.
- **Root Cause**: The retrieval engine max-normalizes all scores ($\text{score} / \max(\text{scores})$). Consequently, if a single query term matches any token anywhere in the repository, the top-ranked document automatically receives a score of `1.0`.
- Because the top document score is always `1.0`, it never falls below the static 0.38 threshold, rendering abstention completely blind.
- **Remedy for Stage 3.8**: Confidence cannot be measured by absolute top score. It must be computed via repository-relative margin (e.g. difference between rank 1 and rank 5 score), query token coverage entropy, or IDF density.

---

## 5. Context Packing & BCY@8k Gap

While EXP-378 achieves **55.08% Recall@20** and **64.06% Hit@20**, its unconditional BCY@8k is **0.0527 (5.27%)**.
- **Root Cause**:
  1. Full file packing: Under the unconstrained protocol, when large files (e.g. 15,000–25,000 tokens) are retrieved in top ranks, they exhaust the 8,000 token budget immediately, preventing subsequent gold files from entering the prompt context.
  2. Multi-gold target dilution: For queries with multiple gold files, even if the primary target is packed, secondary targets are truncated by the budget limit.
- **Remedy for Stage 3.8**: Tighter AST skeleton extraction cap (e.g. 350-token skeleton outlines) to ensure all top-ranked target files fit within the 8,000 token prompt window.

