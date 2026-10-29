# RepoNeedle Stage 3.9.2: Context-Budget Validity and Packing Policy Audit

**Document ID**: `STAGE3.9.2-BUDGET-001`  
**Date**: October 2026  
**Auditor**: Independent Reproducibility & Benchmark Integrity Auditor  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  
**Audited Implementations**:
- `agent_retrieval_bench.baseline.gold_coverage_at_budget` (`external/agent-retrieval-bench/src/agent_retrieval_bench/baseline.py:105`)
- `agent_retrieval_bench.bcy_curve.pack_files` (`external/agent-retrieval-bench/src/agent_retrieval_bench/bcy_curve.py:38`)
- `reponeedle.core.budget.BudgetOptimizer.pack_context` (`reponeedle/core/budget.py:95`)
- `reponeedle.core.tokenizer.estimate_tokens` (`reponeedle/core/tokenizer.py:47`)
**Primary Test Suite**: [`tests/test_stage3_9_2_budget_audit.py`](file:///F:/RepoNeedle/tests/test_stage3_9_2_budget_audit.py)  
**Primary Dataset**: [`research/stage3_9_2/PER_QUERY_BUDGET_COMPARISON.csv`](file:///F:/RepoNeedle/research/stage3_9_2/PER_QUERY_BUDGET_COMPARISON.csv)

---

## 1. Executive Summary

This forensic audit investigates the context-budget metrics used in the RepoNeedle research programme, resolving the dramatic discrepancy between the BCY@8k values reported in Stage 3.5 ($0.1964$ for BM25, $0.3060$ for Candidate F) and Stage 3.9.1 ($0.0493$ for BM25, $0.0130$ for Candidate F, $0.0493$ for Candidate Cascade).

### Core Findings
1. **Metric Unit Mismatch (Characters vs. Tokens)**:
   The metric `gold_coverage_at_budget` in ARB v2 (`baseline.py:105`) measures **characters** using Python `len(text)`. It does **not** count tokens.
   In contrast, Stage 3.5 reported BCY@8k from Stage 2's `pack_files` (`bcy_curve.py:38`), which measures **tokens** using the pinned regex tokenizer `regex_code_tokenizer_v1`.
2. **Greedy-Stop vs. Truncation/Skip Packing Policies**:
   `gold_coverage_at_budget` implements a **strict greedy-stop policy**: the moment a single chunk causes `used + len(text) > 8000`, the loop terminates immediately. It does not skip the oversized chunk to inspect smaller subsequent candidates, nor does it partially truncate the chunk.
3. **Budget Window Saturation**:
   Because chunks from ranks 1–2 typically consume 5,000 to 10,000 characters, rank 4+ candidates are **never evaluated** under greedy-stop. Because `CAND-CASCADE` locks ranks 1–3 to BM25, both systems pack identical chunks, resulting in identical $0.0493$ character coverage.
4. **Cascade Outperforms BM25 Under Token & Knapsack Budgets**:
   When evaluated under true token budgets or greedy-skip / skeleton packing policies, `CAND-CASCADE`'s rank 4+ graph promotions enter the budget window, achieving:
   - **Policy 3 (Token Truncation 8k)**: $0.2286$ vs. $0.1971$ ($+15.98\%$ relative gain).
   - **Policy 4 (Token Greedy-Skip 8k)**: $0.2129$ vs. $0.1877$ ($+13.43\%$ relative gain).
   - **Policy 5 (Token Skeletons 8k)**: $0.2431$ vs. $0.2029$ ($+19.81\%$ relative gain).

---

## 2. Forensic Code Audit of Budget Implementations

### 2.1 Implementation A: `agent_retrieval_bench.baseline.gold_coverage_at_budget`
```python
def gold_coverage_at_budget(gold: set[str], ranked_chunks: list[dict[str, Any]], context_budget: int) -> float:
    if not gold:
        return 0.0
    used = 0
    covered: set[str] = set()
    for chunk in ranked_chunks:
        text = str(chunk.get("text", ""))
        if used + len(text) > context_budget and used > 0:
            break
        used += len(text)
        path = str(chunk.get("path", ""))
        if path in gold:
            covered.add(path)
    return len(covered) / len(gold)
```
- **Unit of Measurement**: Characters (`len(text)`).
- **8,000 Characters in Code**: Equivalent to only $\sim 1,800$ to $2,500$ code tokens (since code punctuation and indentation yield $\sim 3.0$ to $4.5$ characters per token). Calling this metric `BCY@8k` creates false equivalence with 8,000-token LLM context windows.
- **Loop Termination**: Strict greedy-stop (`break`).
- **First-Chunk Boundary Quirk**: Notice `and used > 0`. On the first chunk ($used = 0$), the condition is `False`. Therefore, **chunk 0 is always included, even if its length exceeds 8,000 characters, and even if `context_budget == 0`**! This behavior was verified deterministically in `tests/test_stage3_9_2_budget_audit.py::test_exact_budget_boundary_and_zero_budget`.

### 2.2 Implementation B: `agent_retrieval_bench.bcy_curve.pack_files`
```python
def pack_files(repo, base_commit, ranked_files, gold_files, corpus_cache, budget):
    used = 0
    covered_gold = {threshold: set() for threshold in coverage_thresholds}
    for path in ranked_files:
        text = corpus_cache.file_text(repo, base_commit, path)
        header_tokens = count_tokens(f"### {path}\n")
        content_tokens = count_tokens(text)
        separator_tokens = 1 if text else 0
        total_tokens = header_tokens + content_tokens + separator_tokens
        remaining = budget - used
        if remaining <= 0:
            break
        if total_tokens <= remaining:
            used += total_tokens
            included_content_tokens = content_tokens
        else:
            partial_files += 1
            included_after_header = max(0, remaining - header_tokens)
            included_content_tokens = min(content_tokens, included_after_header)
            used = budget
        if path in gold_files and content_tokens > 0:
            if included_content_tokens >= 1:
                covered_gold[1].add(path)
        if used >= budget:
            break
    return {"bcy": len(covered_gold[1]) / len(gold_files), ...}
```
- **Unit of Measurement**: Tokens. Pinned regex tokenizer:
  $$\text{TOKEN\_RE} = \text{re.compile}(r"[A-Za-z\_][A-Za-z0-9\_]*|[0-9]+|[\wedge A-Za-z0-9\_\backslash s]", \text{re.UNICODE})$$
- **Boundary Policy**: Partial truncation. When a file exceeds remaining tokens, it packs as much of the file as fits. If $\ge 1$ content token is included, gold is marked as covered.
- **Granularity**: Full files (not chunks).

### 2.3 Implementation C: `reponeedle.core.budget.BudgetOptimizer.pack_context`
- **Unit of Measurement**: BPE token estimate via `estimate_tokens(text)`.
- **Boundary Policy**: Knapsack greedy-skip with multi-representation fallback. If a full file exceeds remaining budget, it extracts a structural skeleton (`generate_skeleton`, capturing signatures, imports, and docstrings at $15\text{--}40\%$ token cost). If the skeleton fits, it is packed; otherwise, it skips to subsequent candidates.

---

## 3. Systematic Policy Comparison across $N = 345$ Queries

We simulated five context-packing policies across all 345 positive benchmark queries in [`PER_QUERY_BUDGET_COMPARISON.csv`](file:///F:/RepoNeedle/research/stage3_9_2/PER_QUERY_BUDGET_COMPARISON.csv):

| Policy ID | Policy Description | Budget Unit | Packing & Truncation Mechanism | BASE-BM25 Coverage | CAND-CASCADE Coverage | Absolute Delta | Relative Gain |
| :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| **Policy 1** | ARB v2 Baseline Greedy-Stop | Characters | Chunks; halts at first chunk exceeding budget | 0.0493 | 0.0493 | 0.0000 | 0.00% |
| **Policy 2** | Character Knapsack Greedy-Skip | Characters | Chunks; skips oversized chunks, packs smaller subsequent chunks | 0.0374 | 0.0403 | +0.0029 | +7.75% |
| **Policy 3** | ARB Token Curve Boundary Truncation | Tokens (`regex_code_tokenizer_v1`) | Whole files; partially truncates boundary file | 0.1971 | **0.2286** | **+0.0315** | **+15.98%** |
| **Policy 4** | Whole-File Token Knapsack Greedy-Skip | Tokens (`regex_code_tokenizer_v1`) | Whole files; skips oversized files, packs smaller subsequent files | 0.1877 | **0.2129** | **+0.0252** | **+13.43%** |
| **Policy 5** | Structural Skeletons Knapsack | Tokens (`estimate_tokens`) | Full files + AST skeletons via `BudgetOptimizer` | 0.2029 | **0.2431** | **+0.0402** | **+19.81%** |

### Key Observations
1. **Policy 1 Saturation**:
   Under Policy 1, the top 2 BM25 files consume the entire 8,000-character budget. Because `CAND-CASCADE` strictly preserves the top 3 BM25 ranks, the packed context is identical between BM25 and Cascade.
2. **Policy 3 Exact Historical Match**:
   Under Policy 3 (Token Truncation 8k), BASE-BM25 achieves **$0.1971$**, matching Stage 3.5's recorded `0.1964` within $0.0007$. This proves that Stage 3.5's BCY@8k was a token-based metric from `pack_files`, not a character-based greedy-stop metric.
3. **Cascade's Superior Context Coverage**:
   Under realistic token budgets (Policies 3, 4, and 5), `CAND-CASCADE` significantly outperforms `BASE-BM25`:
   - Policy 3: $+0.0315$ ($0.2286$ vs. $0.1971$, $+15.98\%$).
   - Policy 5: $+0.0402$ ($0.2431$ vs. $0.2029$, $+19.81\%$).
   Graph-promoted files at ranks 4–10 are successfully packed when the context selection policy does not halt on the first file.

---

## 4. Deterministic Packing Regression Test Coverage

All budget dynamics and edge cases are enforced by automated regression tests in [`tests/test_stage3_9_2_budget_audit.py`](file:///F:/RepoNeedle/tests/test_stage3_9_2_budget_audit.py):

1. `test_greedy_stop_halts_on_oversized_top_file`: Proves that an oversized top file blocks smaller relevant candidates at ranks 2–3 under greedy-stop, whereas greedy-skip packs them ($0.0 \to 1.0$ coverage).
2. `test_character_vs_tokenizer_token_budget_units`: Proves character-to-token ratio in code is $\sim 2.0\text{--}4.5\times$, meaning 8,000 characters $\ne$ 8,000 tokens.
3. `test_structural_skeleton_vs_full_file_packing`: Verifies that `BudgetOptimizer` skeleton extraction compresses large code files by $> 50\%$, preserving essential symbols and methods.
4. `test_equal_ranked_files_deterministic_tie_breaking`: Verifies deterministic tie-breaking by lexicographical file path when scores are identical.
5. `test_exact_budget_boundary_and_zero_budget`: Verifies exact budget boundaries ($100, 199, 200$) and documents the ARB v2 `used==0` quirk where budget=0 still packs chunk 0.
6. `test_empty_files_and_boundary_truncation`: Verifies boundary truncation and handling of empty files under `pack_files`.
7. `test_ranking_metrics_vs_budgeted_metrics_separation`: Proves that a system can achieve perfect MRR ($1.0$) while reporting $0.0$ context coverage under greedy-stop, demonstrating that ranking and context-budget metrics measure orthogonal properties.

---

## 5. Canonical Recommendation & Contract Revision

1. **Retire Unqualified `BCY@8k` Label**:
   Never use `BCY@8k` without explicitly indicating the budget unit and packing policy.
2. **Canonical Metric Nomenclature**:
   - `Char_Coverage@8k_GreedyStop`: Historical ARB v2 character baseline metric ($0.0493$).
   - `Token_Coverage@8k_Truncation`: Pinned regex token metric via `pack_files` ($0.2286$).
   - `Token_Coverage@8k_Skeleton`: Structural skeleton knapsack metric via `BudgetOptimizer` ($0.2431$).
