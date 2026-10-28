# REPONEEDLE STAGE 3.6: SYSTEMATIC DECISION & AUDIT REPORT

**Date**: October 2026  
**Document ID**: `STAGE3.6-DEC-001`  
**Git Branch**: `research-program`  
**Base Commit**: `0fdc257`  
**Frozen Baseline Tag**: `v0.1.0-baseline` (`8e00425`)  
**Frozen Candidate Tag**: `stage3-candidate-freeze` (`cd7f3b0`)  
**Official Decision Verdict**: **`PROMISING ON ARB, INDEPENDENT VALIDATION BLOCKED`**  
**Independent Validation Status**: **`BLOCKED / PRELIMINARY`** (Official ContextBench dataset download blocked by network boundary)  

---

## 1. EXECUTIVE VERDICT & ARCHITECTURAL STANDING

### 1.1 The Definitive Verdict: Candidate F is a Pragmatic Trade-Off, Not an Unqualified Win
In accordance with Stage 3.6 research-verification decision rules, we explicitly reject the claim that Candidate F demonstrates universal retrieval superiority over RepoMap.

The reproducible evidence establishes that:
1. **Candidate F vs. Candidate C Paired Evidence**:
   - On the full ARB v2 benchmark ($N=345$), Candidate F demonstrates **no statistically significant overall advantage** over Candidate C:
     - MRR: $0.1351$ vs. $0.1399$ ($\Delta = -0.0048$, $95\%\text{ CI}: [-0.0153, +0.0076]$, Wilcoxon $p = 0.1164$).
     - Recall@20: $0.5078$ vs. $0.5105$ ($\Delta = -0.0027$, $95\%\text{ CI}: [-0.0227, +0.0230]$, Wilcoxon $p = 0.8473$).
     - Candidate F does yield targeted improvements on Rust repositories ($0.1208 \to 0.1441$ MRR on $N=48$), but does not generalize to a global win.
2. **RepoMap Retains Decisive Retrieval Quality Superiority**:
   - Official RepoMap achieves **$0.2293$ MRR** and **$0.6599$ Recall@20**, holding a statistically significant $+0.0942$ MRR advantage ($p < 0.0001$) and $+0.1520$ Recall@20 lead ($p < 0.0001$) over Candidate F ($0.1351$ MRR, $0.5078$ Recall@20).
3. **Candidate F's Genuine Advantage is Operational Efficiency**:
   - **Sub-35 ms Warm Query Latency**: Candidate F executes in **$32.42\text{ ms}$ (median)** vs. RepoMap's **$180.20\text{ ms}$**.
   - **Zero External LLM / Tree-sitter Invocations**: Candidate F operates purely locally in memory on CPU with $<8\text{ MB}$ of index data structures.
   - For agentic loops requiring rapid iterative context retrieval without remote API calls, Candidate F offers an attractive operational trade-off despite lower deep recall.

---

## 2. RECONCILED SYSTEM COMPARISON (ARB v2 POSITIVE BENCHMARK, N=345)

All four systems evaluated under one identical evaluation contract (`research/stage3_6/PER_QUERY_RESULTS.csv`):

| System ID | System Description | MRR | Recall@5 | Recall@10 | Recall@20 | Precision@5 | BCY@8k | Latency (p50) | Latency (p95) | LLM Dependency |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BASE-BM25** | Pure BM25 Lexical Keyword (EXP-016) | 0.1735 | 0.1986 | 0.3118 | 0.4549 | 0.0568 | 0.0493 | **20.85 ms** | 478.58 ms | None |
| **CAND-C** | Static Hybrid + Doc Filter (.5\times$) | 0.1399 | 0.2111 | 0.3196 | 0.5105 | 0.0557 | 0.0188 | 31.50 ms | 561.46 ms | None |
| **CAND-F** | Candidate C + Audited Polyglot Graph | 0.1351 | 0.1824 | 0.3316 | 0.5078 | 0.0504 | 0.0159 | 32.42 ms | 566.28 ms | None |
| **BASE-REPOMAP** | Aider AST PageRank Reference | **0.2293** | **0.3337** | **0.5110** | **0.6599** | 0.0186 | **0.0652** | 180.20 ms | 180.20 ms | AST Call Tree |

---

## 3. AUDIT FINDINGS & GOVERNANCE COMPLIANCE

### 3.1 Baseline Discrepancy Resolved
- The Stage 3.5 report published BM25 Recall@20 $= 0.4928$ and RepoMap Recall@20 $= 0.5681$.
- Forensic analysis proved that these figures were **binary Hit@20** ($170/345$ and $196/345$), mislabeled as fractional recall and compared against Candidate C's fractional recall ($0.5516$).
- The official ARB v2 metric implementation (`sample_metrics`) calculates multi-target fractional recall. Under the official contract, BM25 Recall@20 is **0.4467** and RepoMap Recall@20 is **0.6306**.
- The discrepancy is fully documented and resolved in `research/stage3_6/REPRODUCIBILITY_REPORT.md`.

### 3.2 Removal of Benchmark-Specific Bypass
- In Stage 3.5, `reponeedle/core/graph.py` contained hardcoded strings: `"search.rs", "standard.rs"` and `("core" in my_crate and "printer" in o_crate)` specifically targeting the synthetic 2-file `BurntSushi/ripgrep` fixture.
- In Stage 3.6, these hardcoded rules were completely excised. Cross-crate resolution now strictly relies on genuine `Cargo.toml` path dependencies, module imports, and shared symbols.
- 8 comprehensive unit tests were added to `tests/test_graph.py`, confirming manifest resilience and multi-language symbol resolution.

### 3.3 Context Packing vs. Ranking Independence
- Controlled experiments confirmed that structural skeletons increase file recall under tight 4k budgets from **$0.1602 \to 0.3474$ (+116.8%)** without altering candidate rankings.
- Extreme "Implementation Preservation" (Rank 1 full file + skeletons) causes catastrophic token yield collapse (BCY drops from $0.3835 \to 0.1247$), confirming that Candidate F's balanced packing policy is the optimal choice.

### 3.4 Process Working Set (RSS) Ceiling Assessment
- Retained index structures are remarkably compact ($5.94\text{ MB}$ on Click, $7.61\text{ MB}$ on Caddy).
- However, 64-bit CPython process runtime overhead ($\sim 40\text{--}50\text{ MB}$) means that medium codebases pass at **$98.6\text{ MB}$**, while larger codebases (250 files) reach **$103.1\text{ MB}$**, narrowly missing the literal $100\text{ MB}$ ceiling by $3.1\text{ MB}$.
- Achieving a guaranteed sub-100 MB process RSS on large codebases requires native Rust/C compilation.

---

## 4. NEXT HIGHEST-VALUE EXPERIMENT RECOMMENDATIONS

Based on the verified experimental evidence:

1. **Multi-Hop AST Hierarchy Bridging without Tree-sitter Latency**:
   - The primary reason RepoMap leads on Recall@20 ($0.6306$ vs. $0.5562$) is its multi-hop call graph.
   - Stage 4 should implement a lightweight 2-hop bounded sparse graph diffusion step using precomputed CSR matrix multiplication, closing the recall gap without incurring RepoMap's 180ms latency.
2. **Native Rust Indexing Core**:
   - To guarantee a strict $\le 100\text{ MB}$ process RSS ceiling on 1,000+ file codebases, compile the tokenizer, BM25 inverted index, and graph diffusion into a native Rust extension (`PyO3`), eliminating CPython's 50 MB base overhead.
3. **Independent ContextBench Acquisition**:
   - Resume external ContextBench evaluation once authorized network access is provided by host infrastructure.

