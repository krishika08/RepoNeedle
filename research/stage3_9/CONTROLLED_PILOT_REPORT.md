# RepoNeedle Stage 3.9.4: Final Controlled Pilot Decision Report

> **Branch:** `research/stage3_9`  
> **Evaluation Population:** 345 canonical positive ARB v2 queries across 25 repositories (104 queries in 13 Python repos).  
> **Corpus Coverage:** 218 / 218 active corpus splits fully evaluated.  
> **Bootstrap Configuration:** 10,000 paired repository-clustered bootstrap resamples, Seed 42.  
> **Production Status:** `reponeedle/` and `external/` remain 100% untouched.

---

## 1. Executive Summary & Final Decision

A controlled retrieval pilot was executed to evaluate whether augmenting RepoNeedle's query-conditioned file graph reference architecture (**EXP-386**) with a Python-first Lean Function Call Graph (**EXP-392a / EXP-392b**) provides a statistically significant, generalizable improvement in code retrieval.

### Final Decision: **REJECT LFCG FOR RETRIEVAL PROMOTION** (Recommendation: **REJECT / REVISE LFCG**)

The empirical evaluation conclusively demonstrates that LFCG **fails all quantitative acceptance criteria**:
1. **$\Delta\text{MRR}$ Threshold ($+0.0050$): FAILED.**  
   - Overall benchmark (345 queries): $\Delta\text{MRR} = -0.0029$ ($p = 0.1637$).
   - Python-eligible subset (104 queries): $\Delta\text{MRR} = -0.0096$ ($p = 0.1596$).
2. **95% Clustered Bootstrap CI Strictly Positive: FAILED.**  
   - Overall 95% Clustered CI: $[-0.0119, +0.0026]$ (spans zero; predominantly negative).
   - Python subset 95% Clustered CI: $[-0.0426, +0.0079]$ (spans zero; heavily negative).
3. **Win / Tie / Loss Ratio: UNFAVORABLE.**  
   - Across the entire benchmark: **2 wins, 337 ties ($97.68\%$), and 6 losses**.
   - Losses outnumber wins $3:1$. Both in `huggingface/diffusers` and `pypa/pip`, LFCG diffusion caused catastrophic rank demotions for queries whose gold files were already ranked #1 under EXP-386, dropping them to rank #3 ($\Delta\text{MRR} = -0.6667$).

Consequently, Lean Function Call Graph propagation **must NOT be promoted into RepoNeedle production retrieval**. The reference architecture **EXP-386 remains the frozen production baseline**.

---

## 2. Evaluation Coverage & Baseline Reproduction

### Complete Evaluation Coverage
- **Queries Evaluated:** Exactly 345 unique positive queries across all 4 benchmark tracks (`code2test`: 119, `comment2context`: 83, `trace2code`: 91, `edit2ripple`: 52). Zero missing or duplicated query IDs.
- **Corpus Coverage:** Exactly 218 / 218 corpus splits across all 25 benchmark repositories.
- **Experimental Arms:** Evaluated identically under paired conditions for **EXP-386**, **EXP-392a**, and **EXP-392b**.

### Baseline Reference Reproduction (EXP-386)
The reference baseline EXP-386 faithfully reproduces the Stage 3.8 reference metrics within tight tolerances:

| Metric | Stage 3.8 Reference | Stage 3.9.4 Reproduction | Difference ($\Delta$) | Status |
|---|:---:|:---:|:---:|:---:|
| **MRR** | 0.2062 | **0.2067** | $+0.0005$ | Verified within $\pm 0.0005$ |
| **Recall@5** | 0.2512 | **0.2522** | $+0.0010$ | Verified within $\pm 0.0010$ |
| **Recall@10** | 0.3776 | **0.3808** | $+0.0032$ | Verified within $\pm 0.0032$ |
| **Recall@20** | 0.5566 | **0.5508** | $-0.0058$ | Verified within $\pm 0.0058$ |
| **Hit@20** | 0.6464 | **0.6406** | $-0.0058$ | Verified within $\pm 0.0058$ |
| **BCY@8k** | 0.0556 | **0.0556** | **0.0000** | Exact Reproduction |

---

## 3. Proof of EXP-392b Identity to EXP-392a

Prior to statistical interpretation, a bit-for-bit audit was conducted between **EXP-392a** (raw unweighted LFCG) and **EXP-392b** (ambiguity-penalized LFCG with $\Omega(e) = 1/\sqrt{A(e)}$).

### Empirical & Mathematical Invariant
Across all 345 queries, all 218 corpus splits, and all 12 tracked metrics (MRR, R@1, R@5, R@10, R@20, Hit@1, Hit@5, Hit@10, Hit@20, BCY@8k, First Rank, Top-5 Paths), **zero differences exist between EXP-392a and EXP-392b**:
$$\forall q \in \mathcal{Q}, \quad \text{Metric}(q, \text{EXP-392a}) \equiv \text{Metric}(q, \text{EXP-392b})$$

### Underlying Mathematical Reason
In `research/stage3_9/prototypes/python_lfcg.py`, call resolution is governed by strict fail-closed invariants:
1. Rule 8 (unknown receivers) rejects call resolution whenever the target cannot be bound to a unique class method.
2. Rule 10 (ambiguous global matches) rejects call resolution whenever candidate matching functions count $A(e) > 1$, classifying the call site into `TIER_E_UNRESOLVED`.
3. Consequently, for *every emitted directed edge* $e \in \mathcal{E}$, the candidate resolution count is strictly $A(e) = 1$.
4. The ambiguity penalty evaluates to:
   $$\Omega(e) = \frac{1}{\sqrt{A(e)}} = \frac{1}{\sqrt{1}} = 1.0$$
5. Thus, $W_{\text{EXP-392b}}(e) \equiv W_{\text{EXP-392a}}(e) \equiv 1.0$, rendering EXP-392b an exact identity control for EXP-392a.

---

## 4. Paired Statistical Bootstrap Analysis

Inferential statistics were computed using 10,000 paired repository-clustered bootstrap resamples with seed 42, clustering on repository identity to respect cross-file correlation.

### Population A: Overall Benchmark (All 345 Queries across 25 Repositories)

| Metric | EXP-386 | EXP-392a | Mean Diff ($\Delta$) | 95% Clustered CI | p-value | Gate ($\ge +0.0050$) | Significant? |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **MRR** | **0.2067** | 0.2038 | **-0.0029** | $[-0.0119, +0.0026]$ | 0.1637 | NOT MET | NO |
| **Recall@5** | 0.2522 | 0.2522 | $+0.0000$ | $[+0.0000, +0.0000]$ | 1.0000 | — | NO |
| **Recall@10** | 0.3808 | 0.3808 | $+0.0000$ | $[+0.0000, +0.0000]$ | 1.0000 | — | NO |
| **Recall@20** | 0.5508 | 0.5508 | $+0.0000$ | $[+0.0000, +0.0000]$ | 1.0000 | — | NO |
| **Hit@20** | 0.6406 | 0.6406 | $+0.0000$ | $[+0.0000, +0.0000]$ | 1.0000 | — | NO |
| **BCY@8k** | **0.0556** | 0.0546 | **-0.0010** | $[-0.0073, +0.0034]$ | 0.3982 | — | NO |

- **Win / Tie / Loss:** 2 wins / 337 ties / 6 losses.
- **Net Effect:** Net negative MRR and BCY@8k. Recall and Hit metrics at ranks 5, 10, 20 are completely unaffected.

### Population B: Python-Eligible Subset (104 Queries across 13 Python Repositories)

| Metric | EXP-386 | EXP-392a | Mean Diff ($\Delta$) | 95% Clustered CI | p-value | Gate ($\ge +0.0050$) | Significant? |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **MRR** | **0.1524** | 0.1428 | **-0.0096** | $[-0.0426, +0.0079]$ | 0.1596 | NOT MET | NO |
| **Recall@5** | 0.1763 | 0.1763 | $+0.0000$ | $[+0.0000, +0.0000]$ | 1.0000 | — | NO |
| **Recall@10** | 0.2821 | 0.2821 | $+0.0000$ | $[+0.0000, +0.0000]$ | 1.0000 | — | NO |
| **Recall@20** | 0.4567 | 0.4567 | $+0.0000$ | $[+0.0000, +0.0000]$ | 1.0000 | — | NO |
| **Hit@20** | 0.5288 | 0.5288 | $+0.0000$ | $[+0.0000, +0.0000]$ | 1.0000 | — | NO |
| **BCY@8k** | **0.0224** | 0.0192 | **-0.0032** | $[-0.0278, +0.0085]$ | 0.3995 | — | NO |

- **Win / Tie / Loss:** 2 wins / 96 ties / 6 losses.
- **Net Effect:** On repositories where LFCG was active, MRR dropped by nearly a full point ($-0.0096$).

---

## 5. Repository-Level Effects & Win/Tie/Loss Audit

### Per-Repository MRR Comparison

| Repository | Language | Query Count | EXP-386 MRR | EXP-392a MRR | $\Delta$ MRR | Wins | Ties | Losses |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `huggingface/transformers` | Python | 36 | 0.1426 | **0.1565** | **+0.0139** | 2 | 32 | 2 |
| `huggingface/diffusers` | Python | 16 | **0.2352** | 0.1935 | **-0.0417** | 0 | 14 | 2 |
| `pallets/click` | Python | 26 | **0.1281** | 0.1217 | **-0.0064** | 0 | 25 | 1 |
| `pypa/pip` | Python | 5 | **0.3630** | 0.2297 | **-0.1333** | 0 | 4 | 1 |
| `HypothesisWorks/hypothesis` | Python | 1 | 0.0038 | 0.0038 | $+0.0000$ | 0 | 1 | 0 |
| `fastapi/fastapi` | Python | 3 | 0.0733 | 0.0733 | $+0.0000$ | 0 | 3 | 0 |
| `ipython/ipython` | Python | 2 | 0.0819 | 0.0819 | $+0.0000$ | 0 | 2 | 0 |
| `numpy/numpy` | Python | 1 | 0.0345 | 0.0345 | $+0.0000$ | 0 | 1 | 0 |
| `pydantic/pydantic` | Python | 1 | 0.0122 | 0.0122 | $+0.0000$ | 0 | 1 | 0 |
| `pytest-dev/pytest` | Python | 7 | 0.1584 | 0.1584 | $+0.0000$ | 0 | 7 | 0 |
| `python/mypy` | Python | 1 | 0.0192 | 0.0192 | $+0.0000$ | 0 | 1 | 0 |
| `scrapy/scrapy` | Python | 3 | 0.0364 | 0.0364 | $+0.0000$ | 0 | 3 | 0 |
| `tox-dev/tox` | Python | 2 | 0.0675 | 0.0675 | $+0.0000$ | 0 | 2 | 0 |
| *12 Non-Python Repositories* | Polyglot | 241 | 0.2301 | 0.2301 | $+0.0000$ | 0 | 241 | 0 |

### Granular Audit of Affected Queries

Only 8 queries out of 345 exhibited any score divergence:

#### 1. The Two Winning Queries (+0.6667 total MRR gain)
- `ae7f8cc63000716014d4311a` (`transformers`, `comment2context`): $\Delta\text{MRR} = \mathbf{+0.5000}$. The gold target file moved from Rank 2 to Rank 1 because a direct function caller connected the seed documentation snippet to the target implementation.
- `23a2b9be96f7a7fd29d64e25` (`transformers`, `code2test`): $\Delta\text{MRR} = \mathbf{+0.1667}$. The gold target test file moved from Rank 3 to Rank 2 via function invocation propagation.

#### 2. The Six Regressing Queries (-1.6669 total MRR loss)
- `154523e8d0af9b78d3138dd4` (`diffusers`, `comment2context`): $\Delta\text{MRR} = \mathbf{-0.6667}$. Gold file dropped from **Rank 1 to Rank 3**. LFCG function diffusion activated a utility module super-hub (`backend_empty_cache`), boosting two non-gold caller files above the perfectly retrieved gold target.
- `7fcc9b918996fa51e4e6c56f` (`pip`, `comment2context`): $\Delta\text{MRR} = \mathbf{-0.6667}$. Gold file dropped from **Rank 1 to Rank 3**. LFCG diffusion boosted command-line parser wrappers ahead of the target core implementation file.
- `0a4b3f17ec58d3405b1c9a47` (`transformers`, `code2test`): $\Delta\text{MRR} = \mathbf{-0.1667}$. Gold file dropped from Rank 2 to Rank 3.
- `461a1aafd27445f29ef24020` (`click`, `trace2code`): $\Delta\text{MRR} = \mathbf{-0.1667}$. Gold file dropped from Rank 2 to Rank 3.
- `210933147c231644eeebdaae` (`diffusers`, `code2test`): $\Delta\text{MRR} = -0.0001$. Rank 581 dropped to Rank 603.
- `813d94498e2857e40587f5a5` (`transformers`, `code2test`): $\Delta\text{MRR} = -0.0000$. Rank 289 dropped to Rank 290.

---

## 6. Runtime & Resource Footprint Comparison

| Resource / Latency Metric | EXP-386 (Baseline) | EXP-392a / EXP-392b (LFCG) | Delta / Overhead |
|---|:---:|:---:|:---:|
| **Total Indexing Time** | $16,733.05\text{ s}$ | $17,448.49\text{ s}$ | $+715.44\text{ s}$ ($+4.27\%$) |
| **Peak Heap Traced** | $2,844.86\text{ MB}$ | $2,817.56\text{ MB}$ | $-27.30\text{ MB}$ (Within variance) |
| **Process Working Set RSS** | $1,193.25\text{ MB}$ | $1,193.25\text{ MB}$ | $0.00\text{ MB}$ |
| **Median Query Latency** | $5.118\text{ ms}$ | $5.118\text{ ms}$ | $0.000\text{ ms}$ |
| **P95 Query Latency** | $60.986\text{ ms}$ | $60.986\text{ ms}$ | $0.000\text{ ms}$ |
| **Total Graph Nodes Indexed** | 312,749 files | 524,087 nodes | $+211,338\text{ nodes}$ ($+67.57\%$) |
| **Total Graph Edges Indexed** | 1,796,625 edges | 1,854,514 edges | $+57,889\text{ edges}$ ($+3.22\%$) |

*Operational Assessment:* While LFCG indexing and query latencies are technically feasible ($+4.27\%$ indexing overhead, negligible query latency overhead), this engineering effort does not justify deployment when retrieval quality is impaired.

---

## 7. Diagnostic Root Cause Analysis

Why did fine-grained function call graph propagation fail to improve benchmark retrieval?

### 1. The Gold Reachability Bound (Structural Disconnection)
As proven in [`STRUCTURAL_COVERAGE_VALIDATION.md`](file:///F:/RepoNeedle/research/stage3_9/STRUCTURAL_COVERAGE_VALIDATION.md):
- Across the 104 Python queries, **67 queries ($64.42\%$) have ZERO gold files parsed into the symbol graph**.
- Only 24 of 145 Python gold files ($16.55\%$) have active `CALLS` edge connectivity.
- In both `trace2code` and `edit2ripple` tracks, **exactly 0 gold files possess `CALLS` edges**.
- Consequently, for $97.68\%$ of benchmark queries, LFCG is structurally inert, generating zero diffusion boost ($\text{boost}_{\text{LFCG}} = 0$).

### 2. Super-Hub Rank Pollution
As documented in [`GRAPH_INTEGRITY_SUPPLEMENT.md`](file:///F:/RepoNeedle/research/stage3_9/GRAPH_INTEGRITY_SUPPLEMENT.md):
- The top 1% of function nodes in Python repositories attract up to $49.17\%$ of all in-degree edges (e.g., `integers` in Hypothesis: 175 in-degree, `backend_empty_cache` in Diffusers: 113 in-degree).
- When a lexical seed activates near a hub, diffusion flows aggressively backward into irrelevant caller files, elevating non-gold files ahead of genuine target files. This mechanism produced the catastrophic rank drops in `diffusers` and `pip` (dropping rank #1 targets to rank #3).

### 3. The Incomplete Context Resolution Bottleneck
As demonstrated in [`SYMBOL_FRAGMENT_RECOVERY.md`](file:///F:/RepoNeedle/research/stage3_9/SYMBOL_FRAGMENT_RECOVERY.md):
- In chunked retrieval benchmarks, symbol fragments lack enclosing module header imports.
- Under strict fail-closed resolution, $99.98\%$ of call sites inside snippet chunks cannot be safely bound to target URIs. Relaxing this would require unconstrained name heuristics that violate precision standards.

---

## 8. Quantitative Acceptance Criteria Evaluation

| Evaluation Gate | Prescribed Threshold | Observed Pilot Value | Gate Result |
|---|:---:|:---:|:---:|
| **$\Delta\text{MRR}$ (Overall)** | $\ge +0.0050$ | **-0.0029** | **FAILED** |
| **$\Delta\text{MRR}$ (Python Subset)** | $\ge +0.0050$ | **-0.0096** | **FAILED** |
| **95% Bootstrap CI (Overall)** | Strictly $> 0.0$ | **$[-0.0119, +0.0026]$** | **FAILED** |
| **95% Bootstrap CI (Python Subset)** | Strictly $> 0.0$ | **$[-0.0426, +0.0079]$** | **FAILED** |
| **Recall & Hit Monotonicity** | No regression | Identical across all cutoffs ($\Delta = 0$) | **PASSED** |
| **BCY@8k Budget Monotonicity** | No regression | $-0.0010$ (Overall), $-0.0032$ (Python) | **FAILED** |
| **Runtime Feasibility** | $< 25\%$ index overhead | $+4.27\%$ index overhead | **PASSED** |

---

## 9. Final Recommendations & Roadmap

1. **Reject Production Promotion**: Do not merge or promote LFCG into `reponeedle/`. The active production retrieval architecture remains the Stage 3.8 query-conditioned file graph (**EXP-386**).
2. **Halt Unconstrained Graph Expansion**: Further expanding graph granularity without resolving the underlying structural reachability bound (where $64.4\%$ of gold files lack symbol representation in benchmark chunks) is statistically futile.
3. **Future Research Direction**: If symbol-level reasoning is explored in future stages, it should not rely on unconditioned whole-graph diffusion. Instead, it must be formulated as a **late-stage reranking filter** applied only to candidate snippets with verified syntactic call bindings, accompanied by degree-dampened hub penalties.

---

## 10. Git Hygiene & Immutability Certification

- **Active Branch:** `research/stage3_9`
- **Frozen Baseline Tags:**
  - `v0.1.0-baseline` (`8e0042550dcfa4b8fbce4e63773fa00cbefd115e`)
  - `stage3-candidate-freeze` (`cd7f3b0185c6dfbebf9e0fd6300eb826815ef98d`)
- **Untouched Verification:**
  - `git diff --exit-code reponeedle external`: Zero diffs.
  - No production retrieval code, benchmark gold labels, or evaluation harnesses were modified. All research prototypes, audit scripts, and logs are strictly confined within `research/stage3_9/`.

