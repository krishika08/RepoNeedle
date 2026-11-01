# RepoNeedle Stage 3.9.5: Fragment-Aware Lexical Retrieval Experiment Plan

> **Document ID:** `research/stage3_9/FRAGMENT_RETRIEVAL_EXPERIMENT_PLAN.md`  
> **Target Evaluation:** Stage 3.9.6 / EXP-397, EXP-398, EXP-399  
> **Status:** Proposal for Research Governance Review (Pre-Implementation)  
> **Baseline Reference:** EXP-386 (Query-conditioned edge-type-aware file graph)

---

## 1. Experimental Objectives & Hypotheses

### 1.1 Core Research Question
Can direct function-level lexical matching using complete symbol fragments improve code retrieval quality without suffering from the structural disconnectivity, missing-import failures, and hub rank pollutions that invalidated Lean Function Call Graph (LFCG) diffusion?

### 1.2 Primary Hypotheses
- **$H_1$ (Coverage Recovery):** Ingesting complete symbol fragments will increase gold-target representation from $31.72\%$ to $> 90\%$, making fine-grained symbol evidence accessible to queries across all four benchmark tracks (including `trace2code` and `edit2ripple`).
- **$H_2$ (Density Gain without Dilution):** Multi-field function lexical scoring ($F_{\text{name}}$, $F_{\text{qual}}$, $F_{\text{sig}}$, $F_{\text{doc}}$, $F_{\text{body}}$) will surface small, highly relevant functions in large files without the term-frequency dilution inherent to whole-file BM25.
- **$H_3$ (Hub Immunity):** By strictly omitting graph diffusion hops and applying specificity attenuation, fragment lexical matching will eliminate the catastrophic rank regressions (such as the #1 $\to$ #3 drops in Diffusers and Pip) caused by utility super-hubs.

---

## 2. Experimental Arms

| Experiment ID | System Name | Core Retrieval Formulation | Purpose |
|---|---|---|---|
| **EXP-397** | **EXP-386-CANONICAL** | $S_{\text{EXP-397}}(d) = S_{\text{base}}(d) + 0.15 \cdot \text{boost}_{\text{386}}(d)$ | Active production reference baseline. File BM25 + Subword Semantic + Query-conditioned file graph. |
| **EXP-398** | **EXP-398-FRAG-MAX** | $S_{\text{EXP-398}}(d) = S_{\text{EXP-397}}(d) + 0.10 \cdot \Pi_{\text{max}}(q, d)$ | Isolated function lexical signal. Maximum complete function BM25 score per file. |
| **EXP-399** | **EXP-399-FRAG-CALIBRATED** | $S_{\text{EXP-399}}(d) = S_{\text{EXP-397}}(d) + 0.12 \cdot \Pi_{\text{calibrated}}(q, d)$ | Calibrated projection. Top-2 soft-max pooling + Specificity attenuation + Task modulation. |

---

## 3. Evaluation Population, Candidate Pools & Datasets

### 3.1 Benchmark Population
Evaluation will be conducted strictly across all **345 positive ARB v2 benchmark queries**:
- `code2test`: 119 queries (test file retrieval for source code)
- `comment2context`: 83 queries (implementation retrieval for issue/doc comments)
- `trace2code`: 91 queries (fault localization for stack traces)
- `edit2ripple`: 52 queries (dependent change retrieval for diffs)

### 3.2 Evaluation Populations Reported
1. **Overall Population (Primary):** All 345 queries across all 25 benchmark repositories (218 active corpus splits).
2. **Python-Eligible Subset:** Exactly 104 queries across the 13 Python repositories where function fragment extraction is active.
3. **Polyglot Identity Control:** 241 queries across the 12 non-Python repositories. Because fragment extraction is restricted to Python in this prototype, EXP-398 and EXP-399 must produce bit-for-bit identical rankings to EXP-397 on these 241 queries.

### 3.3 Candidate Pool & Gold Label Invariants
- **Frozen Candidate Files:** The document candidate pool $\mathcal{C}_{\text{file}}$ is strictly defined by the valid file documents in each corpus split. Fragments belong exclusively to parent files and cannot create or alter candidate file membership.
- **Frozen Gold Labels:** Gold targets are retrieved strictly via `agent_retrieval_bench.baseline.target_gold_files(sample)`. Gold labels will never be used to filter fragments or tune coefficients.

---

## 4. Inferential Methodology & Quantitative Acceptance Gates

### 4.1 Statistical Protocol
- **Method:** 10,000 paired repository-clustered bootstrap resamples (seed 42).
- **Clustering Unit:** Repository identity ($K = 25$ overall, $K = 13$ Python subset).
- **Interval Estimation:** Empirical percentile method ($2.5\%$ and $97.5\%$ for 95% two-sided CI).
- **p-Value:** Proportion of bootstrap means contradicting observed effect direction.

### 4.2 Formal Acceptance Gates for Promotion

| Gate ID | Criterion | Quantitative Threshold | Required Population |
|---|---|:---:|:---:|
| **Gate 1** | Mean MRR Improvement | $\Delta\text{MRR} \ge \mathbf{+0.0050}$ | Python Subset AND Overall |
| **Gate 2** | Statistical Significance | $95\% \text{ Clustered CI Lower Bound} > \mathbf{0.0}$ | Python Subset AND Overall |
| **Gate 3** | Directional Favorability | $\text{Wins} > \text{Losses}$ (at least $2:1$) | Python Subset |
| **Gate 4** | Budget Coverage Preservation | $\Delta\text{BCY@8k} \ge \mathbf{0.0000}$ (No regression) | Overall Benchmark |
| **Gate 5** | High-Rank Recall Monotonicity | $\Delta\text{Recall@20} \ge \mathbf{0.0000}$ | Overall Benchmark |
| **Gate 6** | Computational Overhead | Indexing overhead $< 15\%$, Median latency $< 10\text{ ms}$ | Production Feasibility |

---

## 5. Diagnostic Reporting Requirements

In addition to standard macro metrics, the evaluation report must provide:
1. **Per-Task-Type Breakdown:** Detailed MRR and Recall@10 across all 4 tracks (`code2test`, `comment2context`, `trace2code`, `edit2ripple`) to verify whether fragment indexing successfully reaches fault-localization and ripple-effect targets.
2. **Structural & Fragment Coverage Audit:**
   - Percentage of queries where $\ge 1$ gold file contains a complete function fragment.
   - Percentage of queries where the top-scoring function fragment belongs to a gold target.
   - Complete vs truncated fragment counts per repository.
3. **Exploratory Diagnostics:**
   - `pallets/click`: Detailed inspection of CLI command decorator fragments and argument parsing functions.
   - `clap-rs/clap`: Exploratory diagnostic on Rust procedural macro CLI structures (retained strictly diagnostic; not included in Python primary claims).
4. **Independent External Validation:** External generalization testing on non-ARB benchmarks will remain a deferred requirement pending successful passage of Gates 1–6 on ARB v2.

---

## 6. Pre-Implementation Risk Analysis & Mitigations

| Risk | Impact | Pre-Implementation Mitigation |
|---|---|---|
| **Generic Function Name Matches** (e.g. `parse`, `__init__`, `main`) | False-positive file promotion | Multi-field weighting ($F_{\text{qual}}$ and $F_{\text{sig}}$) plus Specificity Attenuation ($\Psi_{\text{spec}}$) downweights high-frequency generic terms. |
| **Docstring Length Disparity** | Verbose docstrings outscoring concise implementations | Field-level length normalization within BM25 multi-field representation prevents long docstrings from dominating code signals. |
| **Memory Footprint Expansion** | Indexing 350,000+ fragments exceeding RAM limits | Complete fragments are indexed in an inverted index with shared string interning; truncated/invalid fragments are immediately dropped from memory after classification. |
| **Zero Non-Python Benefit** | Polyglot benchmark MRR diluted by inactive repositories | Polyglot queries act as a built-in negative control. Macro gate evaluates both Overall and Python subset independently. |

---

## 7. Phased Execution Roadmap

```
Stage 3.9.5 (Current):
  ├── Final LFCG Audit & Baseline Reconciliation (Completed)
  ├── Architecture Design & Experiment Plan Formulation (Completed)
  └── Governance Recommendation: IMPLEMENT FRAGMENT LEXICAL PILOT

Stage 3.9.6 (Upon Approval):
  ├── Phase A: Build `research/stage3_9/prototypes/fragment_lexical_engine.py`
  ├── Phase B: Implement unit test suite for complete/truncated fragment classification
  ├── Phase C: Run diagnostic pre-flight on Click (N=26) and FastAPI (N=3)
  ├── Phase D: Execute full 345-query benchmark evaluation (EXP-397, EXP-398, EXP-399)
  └── Phase E: Perform 10,000 paired clustered bootstrap audit and deliver final report
```

---

## 8. Governance Recommendation on Design Proposal

### **RECOMMENDATION: IMPLEMENT FRAGMENT LEXICAL PILOT**

**Justification:**
1. Directly targets the root cause of the Stage 3.9.4 negative result: replaces structurally disconnected graph diffusion with direct lexical evidence, elevating gold file coverage from $31.72\%$ to $91.72\%$.
2. Solves the missing-import bottleneck: lexical matching requires zero cross-file caller-callee bindings.
3. Eliminates super-hub pollution: score propagation is strictly local ($\text{Function} \to \text{Enclosing File}$) with zero multi-hop diffusion.
4. Preserves all production boundaries: zero modifications to `reponeedle/` or `external/`.

