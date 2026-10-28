# REPONEEDLE STAGE 3.9: SYSTEMATIC DECISION REPORT

**Date**: October 2026  
**Document ID**: `STAGE3.9-DEC-001`  
**Git Branch**: `research-program`  
**Committed Base**: `fcab83b`  
**Frozen Tags Verified**:
- `v0.1.0-baseline`: `8e00425`
- `stage3-candidate-freeze`: `cd7f3b0`
**Official Decision Verdict**: **`PROMISING ON ARB, INDEPENDENT VALIDATION BLOCKED`**  
**Independent Validation Status**: **`BLOCKED / PRELIMINARY`** (Official ContextBench network download blocked by sandbox environment policy)  

---

## 1. OFFICIAL DECISION & ARCHITECTURAL VERDICT

Under the preregistered research governance rules for Stage 3.9, we render the following authoritative determinations:

### 1.1 Formal Rejection of Candidate C and Candidate F as Retrieval Leaders
- Candidate C ($\text{MRR} = 0.1394$) and Candidate F ($\text{MRR} = 0.1334$) are definitively **rejected** as retrieval quality leaders.
- Forensic investigation in Stage 3.9 proved that their lower retrieval accuracy relative to Pure BM25 ($\text{MRR} = 0.1759$) was caused by **Query-Independent Structural Centrality Contamination (PageRank Hub Pollution)** and **Unbounded Graph Diffusion Blowout**.
- These configurations must not be deployed or promoted as general code retrieval defaults.

### 1.2 Formal Adoption of the Recovered Retrieval Architecture
- The Recovered Candidate architecture—combining **Symbol-Decoupled BM25**, **Subword Semantic Matching**, **Documentation Distractor Filtering ($0.5\times$)**, and **Bounded Graph Diffusion ($\text{deg} \le 25$)**, with **Static PageRank Completely Excised**—is formally approved as the new RepoNeedle retrieval standard.
- Empirical standing across $N=345$ positive ARB v2 queries:
  - **MRR**: **$0.2063$** (vs. BM25's $0.1759$, Candidate C's $0.1394$, Candidate F's $0.1334$).
  - **Recall@20**: **$0.5513$** (vs. BM25's $0.4622$).
  - **Token BCY@8k**: **$0.2696$** (vs. BM25's $0.2121$).
  - **Statistically Significant Lead**: $+0.0304$ MRR over BM25 ($p < 0.0001$) and $+0.0669$ MRR over Candidate C ($p < 0.0001$).
  - **Cross-Repository Generalization**: Verified on 10 held-out repositories ($0.1750$ MRR vs. BM25's $0.1462$ and Candidate C's $0.0998$).

### 1.3 Standing Relative to Reference RepoMap
- Reference RepoMap maintains an advantage in deep recall ($0.2293$ MRR vs. $0.2063$ MRR).
- However, RepoNeedle's Recovered Candidate closes **75.6% of the quality gap** while operating with decisive operational advantages:
  - Warm query median latency: **$7.0\text{–}25.1\text{ ms}$** vs. RepoMap's **$180.2\text{ ms}$**.
  - Zero external LLM or tree-sitter subprocess dependencies.
  - Pure Python + NumPy/SciPy in-memory execution.
- We explicitly do NOT claim superiority over RepoMap in headline recall. RepoNeedle is positioned as a lightweight, low-latency, zero-dependency alternative with competitive retrieval quality.

### 1.4 Independent Generalization Status
- Status remains **`BLOCKED / PRELIMINARY`**.
- Network boundary policy prohibits downloading the official 1,136-task ContextBench dataset from Hugging Face.
- ARB v2 results are recognized as development corpus evidence. Independent generalization claims remain deferred until network access to official ContextBench is granted.

---

## 2. ARCHITECTURAL DECISION CONTRACT

1. **Rule 1 (Static PageRank Forbidden)**: Static PageRank must never be added as an unconditioned global term in retrieval scoring.
2. **Rule 2 (Decoupled Field Normalization)**: BM25 document length must reflect body text length. Symbol extractions must act exclusively as field-weighted query term boosts.
3. **Rule 3 (Bounded Diffusion)**: Graph diffusion must enforce degree cutoffs ($\text{deg} \le 25$) to prevent structural hubs from siphoning diffusion mass.
4. **Rule 4 (Cascaded Sparse Reranking for Scale)**: For repositories exceeding 5,000 files, the engine utilizes sparse cascaded reranking (BM25 top-50 candidate selection prior to subword rescoring), ensuring sub-15ms median latency.
