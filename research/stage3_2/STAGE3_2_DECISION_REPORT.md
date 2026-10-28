# REPONEEDLE STAGE 3.2: FINAL DECISION REPORT AND EVIDENCE-DRIVEN SYNTHESIS

**Document ID**: `STAGE3.2-DECISION-001`  
**Date**: 2026-10-28  
**Branch**: `research-program`  
**Frozen Candidate Commit**: `cd7f3b0c8e37d5ff4b1ea27c0065b75ad4f71a9e`  
**Frozen Candidate Tag**: `stage3-candidate-freeze`  
**Historical Baseline Tag**: `v0.1.0-baseline` (`8e00425a1b32d2948bbda1810416b0df470a273e`)  
**Scope**: Definitive Synthesis of Stage 3.2 Held-Out Evaluation, Baseline Comparisons, Memory Constraints, and Downstream Status  

---

## 1. Executive Summary & Pre-Registered Decision Rule Audit

Stage 3.2 was initiated to resolve discrepancies identified during the Stage 3.1 forensic audit, evaluate frozen retrieval candidates under strictly isolated held-out conditions ($N=14$ independent repositories), and apply preregistered decision rules with absolute scientific fidelity.

### Audit of Pre-Registered Decision Rules on Held-Out Partition ($N=14$):

| Pre-Registered Rule | Required Threshold | Observed Empirical Value | Decision Status |
| :--- | :--- | :--- | :--- |
| **Rule 1: Statistically Significant Gain** | 95% Clustered Bootstrap CI strictly $> 0$ vs BM25 | 95% CI = **[0.0000, +0.1071]** ($p = 0.3356$) | **FAILED** (Lower bound touches 0.0000) |
| **Rule 2: Minimum Relative Gain** | Relative Context Recall Gain $\ge +5.0\%$ vs BM25 | Relative Gain = **+4.00%** (0.9286 vs 0.8929) | **FAILED** (Below 5.0% threshold) |
| **Rule 3: Memory Footprint Ceiling** | Process Memory Overhead $\le 100$ MB | Incremental Heap: 34.09 MB; Total RSS: **103.1–110.3 MB** | **PASSED (Heap) / FAILED (Literal RSS)** |
| **Rule 4: Latency Ceiling** | Median CPU Query Latency $\le 50$ ms | Median Warm Latency = **1.87–11.78 ms** | **PASSED** (Over $4\times$ faster than ceiling) |

### The Four Formal Claim Statuses:

1. **Independent Retrieval Generalization**:
   $$\mathbf{PRELIMINARY\ GENERALIZATION\ EVIDENCE\ ONLY}$$
   *Justification*: Because Rules 1 and 2 failed on the held-out partition ($N=14$) and statistical power is constrained by the micro-evaluation corpus scale, claims of definitive independent retrieval generalization cannot be made.
2. **Downstream Coding Agent Benefit**:
   $$\mathbf{DOWNSTREAM\ BENEFIT\ REMAINS\ UNVERIFIED}$$
   *Justification*: Physical inspection confirmed neither Docker, Podman, nor WSL are available on the host. In compliance with scientific honesty, context sufficiency cannot be equated with verified patch generation or unit-test success.
3. **Neural Quality Track**:
   $$\mathbf{NEURAL\ PERFORMANCE\ INCOMPLETE\ /\ UNVERIFIED}$$
   *Justification*: An exhaustive filesystem audit found zero `.onnx` model files. Previous claims were derived from a NumPy hash projection simulation; all claims of verified ONNX neural performance are revoked.
4. **Track A CPU-First In-Process Architecture**:
   $$\mathbf{VERIFIED\ PRACTICAL\ ARCHITECTURE}$$
   *Justification*: The deterministic, zero-dependency Static Hybrid architecture (Candidate C) is verified with 44/44 passing tests, robust sub-15ms query execution, and reliable in-process execution.

---

## 2. Comprehensive Candidate Evaluation Matrix

The 7 frozen systems were evaluated under strictly matched test conditions on the isolated partitions:

### 2.1 Held-Out Partition ($N=14$ Independent Repositories)

| System ID | Candidate Configuration | Context Recall@8k | Context Precision@8k | Context F1 | BCY@8k | Separate MRR | Recall@20 | Mean Latency |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BASE-BM25** | Pure BM25 Baseline | 0.8929 | 0.6881 | 0.7483 | 0.8939 | 0.9286 | 0.9286 | 14.65 ms |
| **BASE-REPOMAP**| Aider-Style RepoMap Reference | **1.0000** | **0.7119** | **0.8150** | **1.0000** | 0.6071 | **1.0000** | **0.58 ms** |
| **CAND-A** | Static Hybrid Full Files | 0.9286 | 0.6405 | 0.7435 | 0.9286 | 0.9286 | 0.9286 | 3.83 ms |
| **CAND-B** | Candidate A + Skeletons | 0.9286 | 0.6405 | 0.7435 | 0.9286 | 0.9286 | 0.9286 | 3.86 ms |
| **CAND-C** | Candidate B + Doc Filter 0.5x | 0.9286 | 0.6405 | 0.7435 | 0.9286 | 0.9286 | 0.9286 | 4.53 ms |
| **CAND-D** | Candidate C + Graph Diffusion | 0.9286 | 0.6405 | 0.7435 | 0.9286 | 0.9286 | 0.9286 | 4.45 ms |
| **CAND-E** | Candidate D + Polyglot Symbols | 0.9286 | 0.6405 | 0.7435 | 0.9286 | 0.9286 | 0.9286 | 5.06 ms |

### 2.2 Replication Partition ($N=5$ Development Repositories)

| System ID | Candidate Configuration | Context Recall@8k | Context Precision@8k | Context F1 | BCY@8k | Separate MRR | Recall@20 | Mean Latency |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BASE-BM25** | Pure BM25 Baseline | 0.9000 | 1.0000 | 0.9333 | 0.9220 | 1.0000 | 1.0000 | 2.99 ms |
| **BASE-REPOMAP**| Aider-Style RepoMap Reference | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.52 ms |
| **CAND-A..E** | Candidates A through E | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ~3.30 ms |

---

## 3. Comparative Baseline Analysis

### 3.1 RepoNeedle Candidate C vs Pure BM25
- **Paired Head-to-Head**: **1 Win, 13 Ties, 0 Losses**.
- **Win Analysis**: On `facebook/react`, Candidate C successfully leveraged subword n-gram matching on React hook internals (`useMemoCache`, `useTransition`) to retrieve both required implementation files, whereas BM25 retrieved only 1.
- **Statistical Significance**: $t = 1.000$, $p = 0.3356$. Due to the small sample size ($N=14$), the gain cannot be declared statistically significant at $\alpha = 0.05$.

### 3.2 RepoNeedle Candidate C vs Aider-Style RepoMap
- **Paired Head-to-Head**: **0 Wins, 13 Ties, 1 Loss**.
- **Context Metric Superiority**: RepoMap achieved **1.0000 Recall** and **0.8150 F1** vs Candidate C's **0.9286 Recall** and **0.7435 F1**.
- **Loss Analysis**: On `BurntSushi/ripgrep`, RepoMap used AST call graph centrality to locate the nested terminal printer crate (`termcolor.rs`) despite zero lexical query overlap, while RepoNeedle experienced a vocabulary mismatch failure.
- **Where RepoNeedle Outperforms RepoMap**:
  - **Ranking Precision (MRR)**: RepoNeedle achieved **0.9286 MRR** vs RepoMap's **0.6071 MRR**. RepoNeedle places the primary culprit file at Rank 1 in 92.9% of cases, whereas RepoMap produces a broad architectural summary without strict first-hit prioritization.
  - **Full Content vs Signatures**: RepoNeedle packs complete file contents and smart AST skeletons; RepoMap outputs only definition signatures, requiring follow-up tool calls to inspect implementation logic.

---

## 4. Multi-Scale Resource & Memory Profiling

Resource consumption was benchmarked across three repository scales:

| Scale | Repository | Files | LOC | Incremental Heap (MB) | Process Working Set (RSS) (MB) | Warm p50 Latency (ms) | Throughput (QPS) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Micro Fixture** | `django/django` (micro) | 5 | 70 | 0.48 MB | 80.7 MB | 0.55 ms | 1819 QPS |
| **Medium Repo** | `pallets/click` | 133 | 14,670 | 34.09 MB | 103.1 MB | 11.78 ms | 85 QPS |
| **Large Repo** | `caddyserver/caddy` | 250 | 22,995 | 45.10 MB | 110.3 MB | 3.04 ms | 329 QPS |

### Reconciliation of Process Working Set (RSS) vs Heap:
- Under an **incremental heap interpretation**, RepoNeedle is exceptionally lean ($\le 45.1$ MB heap on 250 files).
- Under a strict **total process RSS interpretation**, the 100 MB ceiling is breached on medium and large repositories (103.1 MB and 110.3 MB) due to the base CPython interpreter footprint (~40 MB) and OS working set allocation.
- In accordance with pre-registered commitments, this literal breach is formally documented.

---

## 5. Summary of Deliverables Created in `research/stage3_2/`

1. `DATASET_PROVENANCE.md`: Full accounting of ContextBench distribution and sandbox network blocker diagnosis.
2. `HELDOUT_MANIFEST.json`: Cryptographically locked manifest of 14 held-out and 5 replication repositories.
3. `CANDIDATE_EVALUATION.csv`: 7-system evaluation across both partitions.
4. `PER_REPOSITORY_RESULTS.csv`: Granular per-repository metrics for all systems.
5. `PER_SAMPLE_RESULTS.jsonl`: Raw per-sample outputs with ranked paths and token breakdowns.
6. `STATISTICAL_ANALYSIS.md`: Rigorous bootstrap confidence intervals and paired significance tests.
7. `SWE_BENCH_EXECUTION_REPORT.md`: Infrastructure smoke test documenting missing container runtimes.
8. `MODEL_ARTIFACT_VERIFICATION.md`: Forensic audit confirming 0 `.onnx` files and revoking simulated neural claims.
9. `RUNTIME_AND_MEMORY.csv`: Multi-scale resource profiling table across micro, medium, and large codebases.
10. `FAILURE_ANALYSIS.md`: Detailed diagnostics of micro-saturation, `ripgrep` failure, and memory ceiling breach.
11. `REPRODUCE.md`: Deterministic reproduction instructions for all Stage 3.2 experiments.

---

## 6. Strategic Recommendations and Long-Term Program Directive

1. **Preserve Baseline and Candidate Freeze**: Keep `v0.1.0-baseline` (`8e00425`) and `stage3-candidate-freeze` (`cd7f3b0`) intact. Do not modify frozen candidates.
2. **Withhold Public Benchmark and Release Claims**: Do not publish to Hugging Face or PyPI until independent evaluation can be performed on the complete 1,136-task benchmark and verified in a containerized evaluation environment.
3. **Consolidate Track A for Production**: RepoNeedle Candidate C provides a highly reliable, deterministic, CPU-first retrieval engine with 0 external weight dependencies, sub-15ms latency, and high MRR (0.9286), making it immediately suitable as an in-process indexing library for local agent workflows.
