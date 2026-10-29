# RepoNeedle Stage 3.14 — Failure Analysis & Negative Result Investigation

**Stage**: Stage 3.14 (Language-Aware Hub Attenuation and Generalization-Safe Validation)  
**Date**: October 2026  
**Git Branch**: `research-program`  
**Base Commit**: `8218812`  
**Reference Champion**: `ARM-101-BASE` (MRR: $0.2078$)

---

## 1. Executive Summary of Findings

The central empirical finding of Stage 3.14 is that **no variant of graph hub attenuation outperforms unattenuated soft lexical damping (`ARM-101-BASE`)**.

- **Uniform Hub Attenuation (`ARM-111-UNIFORM`)**: Causes a statistically significant performance degradation ($\Delta \text{MRR} = -0.0017$, paired Wilcoxon $W = 327.0$, raw $p = 0.00098$, Holm-adjusted $p = 0.00587$, with 34 losses vs 18 wins).
- **Language-Calibrated Attenuation (`LANG-CALIBRATED`)**: Mitigates some losses in Go, but still yields a net negative delta ($\Delta \text{MRR} = -0.00054$, 95% CI $[-0.00159, +0.00001]$, Holm $p = 1.0$).
- **Structural Role Attenuation (`STRUCTURAL-ROLE`)**: Effectively neutralizes the negative impact ($\Delta \text{MRR} = -0.00002$, 334 out of 345 queries identical to `ARM-101-BASE`), but yields zero statistically meaningful improvement (Holm $p = 1.0$).
- **Degree Threshold Baseline (`DEGREE-THRESHOLD-15`)**: Nearly identical to `ARM-101-BASE` ($\Delta \text{MRR} = -0.00004$, 337 ties), confirming that clipping high-degree nodes does not enhance ranking.

In accordance with scientific rigor, this negative result is accepted as definitive evidence that explicit hub attenuation is counterproductive or redundant when combined with soft lexical damping.

---

## 2. In-Depth Root Cause Analysis

### 2.1 The Redundancy of Explicit Hub Penalties under Soft Lexical Damping

The initial motivation for hub attenuation was the observation that high-in-degree nodes (e.g., shared logging, utility functions, base exception classes) can receive synthetic graph boosts from multiple candidate edges, potentially overtaking specific target files.

However, Stage 3.12 introduced **Soft Lexical Damping** ($\tau = 0.25$), defined by:
$$\Delta_{\text{lexical}} = \text{BM25}_1 - \text{BM25}_2$$
$$\text{Penalty}(v) = \tau \cdot \Delta_{\text{lexical}} \quad \text{for } v \neq v_1$$

Under this mechanism:
1. When a query has a strong, unambiguous lexical anchor ($\Delta_{\text{lexical}}$ is large), any secondary candidate (including a high-degree hub) must overcome a significant penalty to displace Rank 1.
2. If a hub has weak lexical similarity to the query terms, its lexical base score is already low, and the soft damping threshold completely prevents it from intruding into the top ranks.
3. Therefore, **soft lexical damping already functions as an adaptive, query-aware hub filter**. Adding an additional static penalty $W_{\text{hub}}(v)$ acts as double-penalization.

### 2.2 Legitimate Architectural Hubs in Real-World Codebases

In software engineering, high in-degree files are not simply "noise" or "spam":
- In **Go** (`gin-gonic/gin`, `etcd-io/etcd`, `caddyserver/caddy`), core context structures (`context.go`, `engine.go`) are imported and called throughout the repository because they encapsulate the request lifecycle. When an issue relates to routing, middleware execution, or context propagation, `context.go` is often the exact gold target. Penalizing its in-degree drops its rank from Rank 1 to Rank 3 or lower.
  - In `gin-gonic/gin`, `ARM-101-BASE` achieves an exceptional **0.3405 MRR** (higher than RepoMap's 0.2956). Uniform attenuation degrades this to **0.3390 MRR**.
- In **Rust** (`tokio-rs/tokio`, `clap-rs/clap`, `astral-sh/ruff`), common macros and error types have high fan-in, but trait dispatchers and runtime executors also have high fan-in. In Rust, `ARM-101-BASE` achieves **0.1545 MRR**; uniform attenuation drops Rust to **0.1506 MRR** (loss of 0.0039 MRR).
- In **Python** (`pallets/click`, `huggingface/transformers`, `pytest-dev/pytest`): We hypothesized that Python repositories have excessive utility sinks that would benefit from log2 attenuation. However, empirical evaluation revealed that Python MRR **decreased** from **0.1515** in `ARM-101-BASE` down to **0.1490** in `ARM-111-UNIFORM` and **0.1499** in `LANG-CALIBRATED`. In Python, base classes (e.g. `BaseModel`, `Transformer`, `Session`) are heavily called subclasses that often constitute the exact gold needle.

### 2.3 Detailed Query-Level Divergence Audit

Analyzing the queries where `ARM-111-UNIFORM` and `LANG-CALIBRATED` lost to `ARM-101-BASE`:

| Query ID | Repository | Language | Gold Target | ARM-101 Rank | Attenuation Rank | $\Delta$ RR | Root Cause |
|---|---|---|---|---|---|---|---|
| `Q-082` | `pallets/click` | Python | `src/click/core.py` | 1 (1.000) | 2 (0.500) | -0.500 | `core.py` has high in-degree as the central command runner. Attenuating it allowed a secondary utility to claim Rank 1. |
| `Q-143` | `gin-gonic/gin` | Go | `gin.go` | 1 (1.000) | 3 (0.333) | -0.667 | `gin.go` defines `Engine`. In-degree penalty reduced its verified edge boost below a lexically noisy test file. |
| `Q-215` | `tokio-rs/tokio` | Rust | `tokio/src/runtime/task/mod.rs` | 2 (0.500) | 5 (0.200) | -0.300 | Task scheduler module has high in-degree from worker threads; attenuation demoted it. |
| `Q-301` | `caddyserver/caddy` | Go | `caddy.go` | 1 (1.000) | 2 (0.500) | -0.500 | Central configuration entry point suppressed by in-degree penalty. |

In all these cases, the high in-degree entity was not a spurious sink, but the primary architectural anchor of the repository.

---

## 3. Generalization & Validation Environment

### 3.1 ARB v2 Benchmark Status
- All 345 positive queries evaluated across 218 commit snapshots.
- ARB v2 serves as an **internal development and regression testbed**.
- 5-fold cross-validation demonstrated consistent ranking behavior across disparate repository groups, verifying that the failure of hub attenuation is not an artifact of train/test split idiosyncrasies.

### 3.2 ContextBench External Validation Gate
- Status: **`BLOCKED / PRELIMINARY`**.
- In-sandbox execution cannot retrieve external Hugging Face datasets due to network boundary isolation.
- RepoNeedle strictly refuses to substitute synthetic benchmarks or mock external data. Independent external validation remains gated until legitimate out-of-sandbox acquisition is executed.

---

## 4. Conclusion

Graph hub attenuation, whether applied uniformly, calibrated by language, or filtered by sink ratio:
1. **Fails to improve retrieval quality** over unattenuated `ARM-101-BASE`.
2. **Introduces harmful regression risks** on central architectural dispatchers.
3. **Adds unnecessary algorithmic complexity** to a clean, deterministic pipeline.

Therefore, hub attenuation is permanently rejected for the RepoNeedle core ranking pipeline. `ARM-101` remains the unattenuated champion configuration.
