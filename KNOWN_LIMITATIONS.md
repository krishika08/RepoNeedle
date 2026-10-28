# KNOWN LIMITATIONS AND ARCHITECTURAL BOUNDARIES: REPONEEDLE

**Version**: 0.1.0 Research Preview  
**Status**: Active Research Pipeline  
**Target Release**: Limited Research Release  
**Primary Benchmark**: Agent Retrieval Bench v2 ($N=427$ samples, 25 repositories, 271 unique snapshots)

---

## 1. Executive Summary of Limitations

While RepoNeedle demonstrates substantial, statistically significant improvements over classical BM25 and Lexical search on large-scale repository retrieval (+50.5% MRR, $p < 0.001$), it exhibits concrete failure modes and architectural boundaries that preclude an unqualified general-purpose release.

This document provides transparent, unhedged documentation of every known limitation, failure mode, and architectural trade-off.

---

## 2. Failure of Heuristic Selective Abstention in Production

### The Observed Defect
On the official Agent Retrieval Bench Selective Retrieval split ($N=82$ total abstention queries across 71 frozen repository snapshots), RepoNeedle achieved **0.0% abstention accuracy (0 / 82)**:
- Natural No-Gold GitHub Issues ($N=50$): **0 / 50 correctly abstained (100% false return rate)**
- Counterfactual Wrong-Repo Tasks ($N=32$): **0 / 32 correctly abstained (100% false return rate)**

### Root Cause Analysis
The `SelectiveAbstainer` module uses a dual-signal heuristic:
1. **Z-Score Peakiness**: Measures whether top BM25 scores stand out significantly from the background distribution of document scores ($Z = \frac{s_1 - \mu}{\sigma}$).
2. **Repository Symbol Overlap**: Measures the proportion of query tokens matching extracted AST symbols or file paths.

In production benchmark conditions on complete repositories (often containing 500 to 5,000 files), this heuristic fundamentally breaks down:
1. **Natural Issues Contain Repository Vocabulary**: Natural issue descriptions filed against an open-source project inherently use terms relevant to that project (e.g. class names, module references, feature names). Even when the issue describes an external dependency bug, the text contains valid repo vocabulary, driving the overlap score above `0.70`.
2. **Counterfactual Queries Share Ubiquitous Software Primitives**: Counterfactual tasks taken from other repositories still use universal software engineering terms (`client`, `server`, `parse`, `config`, `handler`, `error`, `connect`). In any substantial repository, these terms match numerous valid functions, causing $Z$-scores to register between `2.5` and `4.0`.
3. **Threshold Mismatch**: The calibrated threshold of $\tau = 0.38$ was calibrated on small synthetic toy corpora. On full-scale repositories, heuristic confidence scores consistently fell in the range `[0.64, 0.86]`, never falling below $\tau$.

### Required Resolution
Heuristic confidence scoring based on surface lexical overlap is scientifically inadequate for repository abstention. Future versions will require a dedicated, fine-tuned cross-encoder or neural classifier trained specifically to discriminate internal bugs from out-of-scope issues. Until then, RepoNeedle's selective abstention feature must be treated as purely experimental.

---

## 3. Deep Recall Deficit Compared to RepoMap

### The Observed Defect
While RepoNeedle matches or slightly exceeds RepoMap on top-rank precision (MRR: `0.2287` vs `0.2140`, a non-significant +6.9% difference, $p=0.4089$), **RepoMap substantially outperforms RepoNeedle at high recall depth**:
- **Recall@20**: RepoMap `0.6306` vs RepoNeedle `0.4279` (**+47.4% relative advantage for RepoMap**)
- **BCY@8k**: RepoMap `0.3788` vs RepoNeedle `0.3450` (**+9.8% relative advantage for RepoMap**)
- **BCY@16k**: RepoMap `0.5235` vs RepoNeedle `0.4192` (**+24.9% relative advantage for RepoMap**)
- **BCY@32k**: RepoMap `0.6166` vs RepoNeedle `0.4279` (**+44.1% relative advantage for RepoMap**)

### Architectural Mechanism
1. **PageRank Component Connectivity**: RepoMap computes PageRank over the full identifier reference graph. When a query references a high-centrality hub, PageRank probability naturally diffuses across the entire connected subgraph, successfully capturing secondary and tertiary relevant files in positions 10 through 20.
2. **RepoNeedle Precision Focus**: RepoNeedle's multi-signal scoring and knapsack density optimization aggressively prioritize top-rank relevance density ($U_i / C_i^\gamma$). Files outside the immediate lexical or direct AST neighborhood receive low scores, causing tail recall to plateau around 0.43.
3. **Recommendation**: For applications requiring broad recall across entire sub-systems (e.g. large architectural refactorings), standalone RepoMap or hybridizing RepoNeedle with deeper graph diffusion walks is recommended.

---

## 4. Performance Deficit on High-Level Issue Comments (`comment2context`)

### The Observed Defect
On the `comment2context` task track ($N=80$ samples), classical BM25 outperforms RepoNeedle:
- **MRR**: Official BM25 `0.1974` vs RepoNeedle `0.1708` (**-13.5% deficit for RepoNeedle**)
- **Recall@5**: Official BM25 `0.2146` vs RepoNeedle `0.1646` (**-23.3% deficit**)
- **Recall@20**: Official BM25 `0.5292` vs RepoNeedle `0.2083` (**-60.6% deficit**)
- **BCY@8k**: Official BM25 `0.2604` vs RepoNeedle `0.1896` (**-27.2% deficit**)

### Root Cause
1. **Colloquial Text vs AST Symbols**: Issue comments are written in conversational prose (e.g. "could we make timeouts configurable in the client?"). They often lack exact class or function names.
2. **Weight Dilution**: `WorkflowRouter` classifies `comment2context` queries and distributes score weights across BM25 (0.50), Semantic (0.35), and Graph (0.15). In the absence of dense neural embeddings, the subword character $n$-gram semantic index can introduce noise, diluting the sharp term-frequency signal that pure BM25 provides.
3. **Mitigation**: In applications where queries are predominantly high-level human discussion, BM25 weight should be manually set to $\ge 0.85$.

---

## 5. Monolithic File Saturation and Context Truncation

### The Observed Defect
In repositories containing large monolithic source files (>2,000 lines of code, e.g. `etcdserver/server.go` or `models/modeling_bert.py`):
1. **Budget Exhaustion**: If a monolithic file is packed in full (`Tier: FULL`), it can consume 3,000 to 6,000 tokens, exhausting an entire 4k or 8k budget on a single file and crowding out supporting secondary files.
2. **Skeleton Truncation Risk**: In `Tier: SKELETON` mode, RepoNeedle preserves class and function signatures while eliding implementation bodies. While this preserves architectural context, if the task requires fine-grained reasoning about an inner private helper or nested closure, the relevant code logic is omitted.
3. **Absence of Span Slicing**: RepoNeedle currently operates at the file and structural skeleton level. It does not perform fine-grained AST block slicing (e.g. extracting only lines 450–520 of a 3,000-line file).

---

## 6. Local Compute Boundaries & Neural Baseline Scope

### Execution Boundaries
1. **CPU Native Execution**: The evaluation and benchmarks were executed strictly in a standard CPU environment (Python 3.12 AMD64 on Windows 11).
2. **Lack of Local GPU Neural Inference**: Heavy neural embedding models (such as `Qwen/Qwen3-Embedding-4B` and `8B`, `pplx-embed-v1-4b`) were evaluated by reference to official published ARB literature. They were not executed locally due to the absence of CUDA hardware and deep learning frameworks (`torch`, `transformers`) in the sandboxed execution environment.
3. **Scope Bounding**: RepoNeedle is designed as an ultra-fast, zero-dependency CPU retrieval system. It should not be mischaracterized as a competitor to fine-tuned 8-billion-parameter dense neural models running on H100 clusters.

---

## 7. Benchmark Repository Concentration

### Distribution Imbalance
While the evaluation spans 25 open-source repositories, query distribution in ARB v2 is naturally clustered:
- `gin-gonic/gin`: 88 queries (25.5% of positive samples)
- `tokio-rs/tokio`: 42 queries (12.2% of positive samples)
- `etcd-io/etcd`: 36 queries (10.4% of positive samples)

### Validation Safeguard
To ensure that headline gains over BM25 (+50.5%) were not simply driven by large gains on Gin, **repository-clustered bootstrap resampling** was conducted across all 25 repositories (10,000 resamples). The repository-clustered 95% Confidence Interval for $\Delta_{\text{MRR}}$ remained strictly positive (`[+0.0202, +0.1129]`), confirming statistical significance across clusters. However, broader evaluation across diverse languages (e.g. Java, C++, Ruby, PHP) remains an open objective.

---

## 8. Summary Table of Architectural Limitations

| Limitation | Impact | Severity | Planned Mitigation |
| :--- | :--- | :---: | :--- |
| **Heuristic Abstention Failure** | 0.0% accuracy on no-gold tasks | **HIGH** | Fine-tuned neural cross-encoder discriminator |
| **Deep Tail Recall Deficit** | Recall@20 lags RepoMap by -32.1% | **MEDIUM** | Multi-hop graph diffusion for tail ranks |
| **`comment2context` Deficit** | MRR lags pure BM25 by -13.5% | **MEDIUM** | Dynamic BM25 up-weighting on colloquial inputs |
| **Monolithic File Saturation** | 2k+ line files crowd budget | **MEDIUM** | AST block/span-level context slicing |
| **CPU Only / No Neural Weights** | Cannot perform deep semantic reasoning | **LOW (Design Choice)** | Optional pluggable neural embedding backend |
| **Benchmark Cluster Imbalance** | Top 3 repos represent 48% of queries | **LOW** | Expanded evaluation on Multi-Repo Benchmarks |

