# RepoNeedle Stage 3.13 — Unresolved Claims and Open Evidence Gaps

This register audits all claims and performance dimensions where conclusive evidence is currently blocked, unverified, or requiring external authorization.

---

## 1. Inventory of Active Claims & Resolution Status

| Claim / Objective ID | Claim Statement | Historical Stage | Current Disposition | Root Blocker & Evidence Required for Closure |
|---|---|:---:|:---:|---|
| **GAP-01** | **Independent Benchmark Generalization on ContextBench** | Stage 3.10 - 3.13 | **BLOCKED** | External network requests to `https://huggingface.co/datasets/Contextbench/ContextBench` return `HTTP Error 403: Forbidden` under sandbox security. Requires authorized unsandboxed network permission to download official dataset archive. ARB v2 cannot be substituted for independent validation. |
| **GAP-02** | **Dynamic Per-Query Stopwatch Latency of Official RepoMap** | Stage 3.5 - 3.12 | **UNRESOLVED / UNMEASURABLE IN SANDBOX** | Official RepoMap's `180.20 ms` is a literature scalar. A true head-to-head dynamic stopwatch comparison requires installing the complete tree-sitter C bindings and Aider runtime under identical Python harness to measure per-query milliseconds. |
| **GAP-03** | **End-to-End Downstream Agent Patch Success Rate** | Informal notes | **WITHDRAWN / OUT OF SCOPE** | Claims that higher BCY@8k directly translates to $+12\%$ SWE-bench resolve rate are unverified downstream agent hypotheses. RepoNeedle is evaluated strictly as a retrieval and context-packing engine; downstream LLM benchmark execution is not supported in the sandbox. |
| **GAP-04** | **Universal 2x Speedup for Cascaded Reranking (CONFIG-10)** | Stage 3.10 | **DISQUALIFIED / QUALIFIED** | Empirical profiling in Stage 3.12 and 3.13 proves that CONFIG-10 is **slower** than CONFIG-09 on small codebases (< 200 files) due to SciPy CSR non-contiguous row slicing overhead. The 2x-3x speedup applies strictly to large codebases ($\ge 600$ files). The universal claim is withdrawn and replaced by the workload-conditional operating policy. |

---

## 2. Protocols for Resolving Open Gaps

### Protocol for GAP-01 (ContextBench Independent Validation):
1. Obtain explicit user authorization to execute unsandboxed network download.
2. Ingest `Contextbench/ContextBench` using [`validate_contextbench.py`](file:///F:/RepoNeedle/research/stage3_13/validate_contextbench.py).
3. Validate SHA-256 archive checksum against published reference hash.
4. Execute frozen candidates (`BASE-BM25`, `CONFIG-09`, `CONFIG-10`) without hyperparameter tuning.
5. Compute paired bootstrap confidence intervals and Holm-adjusted Wilcoxon significance tests.

### Protocol for GAP-02 (RepoMap Dynamic Latency):
1. RepoMap runtime dependencies (`aider-chat`, `tree-sitter-languages`, `grep-ast`) must be compiled and pinned in a dedicated environment.
2. Run identical benchmark queries across the 5 representative repositories.
3. Record median, p90, p95 stopwatch milliseconds under identical CPU core affinity.
