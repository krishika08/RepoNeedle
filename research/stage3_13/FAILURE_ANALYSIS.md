# RepoNeedle Stage 3.13: Failure Analysis and Unresolved Limitations

**Document**: `research/stage3_13/FAILURE_ANALYSIS.md`  
**Stage**: Stage 3.13 — Canonical Reproducibility and Evidence Reconciliation  
**Date**: October 30, 2026  
**Status**: COMPLETE LIMITATIONS AUDIT  

---

## 1. Permanent Invalidation of Candidate F

### 1.1 The Mathematical Mechanism of Failure
Candidate F was originally claimed to achieve $0.2152$ MRR. Forensic inspection proved this claim was generated through:
1. Pruning code files in `code2test` via `candidate_filter="tests_only"`.
2. Hardcoding query bypasses for `BurntSushi/ripgrep` in `evaluate_graph_retrieval.py`.
3. Substituting binary Hit@20 ($0.5652$) for fractional Recall@20.

When evaluated on the 100% unconstrained candidate pool:
- Candidate F achieves only **$0.1338$ MRR** and **$0.5083$ Recall@20**.
- Pure Okapi BM25 achieves **$0.1752$ MRR** ($+30.9\%$ higher).
- Paired Wilcoxon testing confirms Candidate F is significantly inferior to BM25 ($p = 4.01 \times 10^{-14}$, 232 losses vs 99 wins).

### 1.2 Root Cause: Supernode Dilution
Without lexical rank protection, high-centrality files (e.g. base interfaces, abstract classes, utility sinks) absorb massive graph diffusion scores. When a query targets a specific leaf implementation file, unconstrained graph diffusion promotes connected supernodes into ranks 1–3, displacing the true gold target and collapsing reciprocal rank.

**Verdict**: Candidate F is permanently retired and invalidated.

---

## 2. Unresolved Limitations & Boundary Constraints

### 2.1 ContextBench External Validation Blocked
- **Status**: **`BLOCKED / PRELIMINARY`**
- **Reason**: The execution sandbox enforces strict network isolation. Official ContextBench benchmarks and evaluation harnesses require external network access to fetch evaluation splits and remote LLM judges.
- **Safeguard**: ARB v2 is designated as an internal development/regression benchmark. No claims of SWE-bench patch resolution or independent generalization are authorized until official ContextBench data is authenticated locally.

### 2.2 The In-Degree Hub Attenuation Trade-off
- In Stage 3.12, Factor B applied logarithmic fan-in attenuation:
  $$W_{\text{hub}} = \frac{1}{\log_2(2 + \text{deg}_{\text{in}})}$$
- While $W_{\text{hub}}$ successfully prevented 16 utility-sink regressions in Python (`huggingface/transformers`), it introduced 33 collateral regressions in Go (`gin-gonic/gin`, `etcd-io/etcd`).
- **Limitation**: Pure topological in-degree does not distinguish between low-information helper files (e.g. `string_utils.py`) and high-information core domain interfaces (e.g. `render/render.go`). Future work must incorporate module name heuristics or token density into hub penalties.

### 2.3 Flat Package Structure in Go
- 6 queries in Go repositories (`gin-gonic/gin` and `caddyserver/caddy`) regressed under Soft Lexical Damping (`ARM-100` and `ARM-101`).
- In Go, all files in the same directory share a single package namespace and flat export scope. Sibling modules with high lexical overlap can barely exceed the margin gate $\theta = \tau \cdot (\text{BM25}_1 - \text{BM25}_2)$ and displace the primary entrypoint.

### 2.4 Falsification of the Universal Sub-100 MB RSS Claim
- Native Win32 `GetProcessMemoryInfo` measurements confirm that process RSS scales with codebase size:
  - `pallets/click` (133 files): **$112.7\text{ MB}$ RSS**
  - `caddyserver/caddy` (555 files): **$198.0\text{ MB}$ RSS**
  - `etcd-io/etcd` (1,435 files): **$364.1\text{ MB}$ RSS**
- Any future claim that RepoNeedle operates globally under a 100 MB ceiling is scientifically false and prohibited by governance rules.

### 2.5 Retrieval Quality Ceiling vs. RepoMap
- Version-pinned official RepoMap (`9e4d689`) achieves **$0.2293$ MRR**, **$0.6599$ Recall@20**, and **$0.3177$ Token BCY@8k**.
- RepoNeedle's optimal configuration (`ARM-101`) achieves **$0.2078$ MRR**, **$0.5648$ Recall@20**, and **$0.2822$ Token BCY@8k**.
- RepoNeedle does not beat RepoMap on retrieval quality. Its value proposition is operational: **$8.44\text{ ms}$ P50 latency (over 21x faster than RepoMap's $180.20\text{ ms}$)**, CPU-first inference, and low memory overhead.
