# RepoNeedle Stage 3.9.1: Forensic Metric Discrepancy Audit

**Document ID**: `STAGE3.9.1-DISC-001`  
**Date**: October 2026  
**Auditor**: Independent Reproducibility & Benchmark Integrity Auditor  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  
**Audited Commit**: `064e619d1bb2bf707fd356435ec9dd2831cde571` (Stage 3.9 HEAD)  

---

## 1. Executive Summary

This audit investigates and resolves the internal metric discrepancies identified between the Gate A and Gate B tables in the Stage 3.9 research deliverables.

### The Investigated Discrepancy Table

| System | Metric | Gate A Reported Value | Gate B Reported Value | Absolute Difference | Relative Difference | Verified Provenance & Cause |
|---|---|---:|---:|---:|---:|---|
| **BASE-BM25** | MRR | 0.1735 | 0.1752 | +0.0017 | +0.98% | Symbol length decoupling in `reponeedle/core/lexical.py` |
| **BASE-BM25** | Recall@20 | 0.4549 | 0.4535 | -0.0014 | -0.31% | Rank shifts among zero/near-zero lexical matches |
| **CAND-C** | MRR | 0.1399 | 0.1412 | +0.0013 | +0.93% | Downstream score fusion of decoupled BM25 input |
| **CAND-F** | MRR | 0.1351 | 0.1358 | +0.0007 | +0.52% | Downstream seed selection of decoupled BM25 input |
| **BASE-REPOMAP**| MRR | 0.2293 | 0.2293 | 0.0000 | 0.00% | Exact match (External pinned baseline, commit `9e4d689`) |

---

## 2. Root Cause 1: Symbol Length Normalization Decoupling

### 2.1 Code-Level Provenance
In Git commit `cbe6c49` (Stage 3.6), the BM25 index document length normalization formula in `reponeedle/core/lexical.py` was implemented as:

```python
# Stage 3.6 Implementation (Coupled BM25)
effective_len = sum(weighted_counts.values())
```
Where `weighted_counts` included:
- `path_weight * len(path_tokens)`
- `symbol_weight * len(symbol_tokens)`
- `body_weight * len(body_tokens)`

Because `symbol_tokens` were extracted from all AST definitions and imports, files with rich class/function structures received very large `effective_len` values. In BM25Okapi, document length normalization penalizes terms in long documents:
$$\text{norm}(d) = 1 - b + b \cdot \frac{|d|}{\text{avgdl}}$$
As a result, source code files with dozens of methods were heavily penalized simply for declaring multiple symbols.

### 2.2 Introduction of `decouple_symbols` in Stage 3.9
In Stage 3.9, `reponeedle/core/lexical.py` introduced the `decouple_symbols` flag (defaulting to `True`):

```python
# Stage 3.9 Implementation (Decoupled BM25)
effective_len = (
    max(1.0, float(len(body_tokens) + len(path_tokens)))
    if self.decouple_symbols
    else sum(weighted_counts.values())
)
```
When `decouple_symbols = True`, symbol tokens continue to contribute to the document's term frequency ($TF$) and weighted query score, but they no longer inflate the document length normalization denominator.

### 2.3 Concrete Per-Query Demonstration
Consider query `597f32e9b482833bed151a23` (`clap-rs/clap`, task `code2test`, gold target `tests/builder/help.rs`):
- **Coupled BM25 (`decouple_symbols = False`)**:
  - Gold target document length normalization includes all symbol weights.
  - Gold target rank = **96**
  - $\text{MRR} = 1 / 96 = \mathbf{0.010417}$
  - Exactly matches `research/stage3_6/PER_QUERY_RESULTS.csv:597f32e9b482833bed151a23`.
- **Decoupled BM25 (`decouple_symbols = True`)**:
  - Symbol tokens are decoupled from the length normalization denominator.
  - Gold target rank = **95** (promoted by 1 position).
  - $\text{MRR} = 1 / 95 = \mathbf{0.010526}$
  - Exactly matches `research/stage3_9/PER_QUERY_CASCADE_RESULTS.csv:597f32e9b482833bed151a23`.

### 2.4 Corpus-Wide Aggregation
Across all 345 positive ARB v2 benchmark queries:
- **Coupled BM25 (Gate A table source)**: Mean $\text{MRR} = \mathbf{0.1735}$, Mean $\text{Recall@20} = \mathbf{0.4549}$.
- **Decoupled BM25 (Gate B table source)**: Mean $\text{MRR} = \mathbf{0.1752}$, Mean $\text{Recall@20} = \mathbf{0.4535}$.

Gate A used the historical canonical table from Stage 3.6/3.7/3.8 which recorded Coupled BM25. Gate B evaluated live against the updated `BM25Index` which defaulted to Decoupled BM25.

---

## 3. Root Cause 2: Downstream Propagation to Candidate C and Candidate F

In RepoNeedle's retrieval pipeline:
1. **Candidate C**:
   $$S_{\text{cand\_c}} = \frac{1}{3} \left( S_{\text{lex}} + S_{\text{sem}} + S_{\text{pr}} \right) \cdot \mathbb{I}_{\text{doc\_filter}}$$
2. **Candidate F**:
   $$S_{\text{cand\_f}} = S_{\text{cand\_c}} + 0.15 \cdot \text{Diffuse}\left( \text{Top5Seeds}\left( S_{\text{lex}} + S_{\text{sem}} \right) \right)$$

Because $S_{\text{lex}}$ directly enters both Candidate C score fusion and Candidate F seed selection:
- When $S_{\text{lex}}$ was computed with Coupled BM25, Candidate C achieved $\text{MRR} = \mathbf{0.1399}$ and Candidate F achieved $\text{MRR} = \mathbf{0.1351}$.
- When $S_{\text{lex}}$ was computed with Decoupled BM25, Candidate C achieved $\text{MRR} = \mathbf{0.1412}$ and Candidate F achieved $\text{MRR} = \mathbf{0.1358}$.

The difference is entirely deterministic and mathematically attributable to the lexical score input.

---

## 4. Root Cause 3: Pinned RepoMap Stability

`BASE-REPOMAP` achieved identical metrics across both Gate A and Gate B tables:
$$\text{MRR} = \mathbf{0.2293}, \quad \text{Recall@20} = \mathbf{0.6599}$$
RepoMap is an external reference system whose rankings were generated using tree-sitter tag extraction and PageRank at commit `9e4d689`. It does not import or execute `reponeedle/core/lexical.py`, and therefore its scores and ranks were completely unaffected by the `decouple_symbols` parameter.

---

## 5. Root Cause 4: Explanation of Identical BCY@8k = 0.0488

In `research/stage3_9/CASCADE_ABLATIONS.csv`, both `BASE-BM25` and `CAND-CASCADE` reported identical $\text{BCY@8k} = \mathbf{0.0488}$.

### Forensic Investigation:
In `research/stage3_9/evaluate_cascade_ablation.py`:
```python
top_chunks = []
seen = set()
for p in ranked_paths[:15]:
  if p in path_to_chunks and p not in seen:
    top_chunks.extend(path_to_chunks[p])
    seen.add(p)
bcy_8k = gold_coverage_at_budget(gold_set, top_chunks, 8000)
```
And in `agent_retrieval_bench.baseline.gold_coverage_at_budget`:
```python
used = 0
covered = set()
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

1. **Character Budget Cutoff**: `gold_coverage_at_budget` treats `context_budget = 8000` as character length (`len(text)`), not token count.
2. **Chunk Size Saturation**: ARB v2 file chunks average 2,500 to 5,000 characters each. Consequently, only the chunks from the top 1 or 2 files fit before `used + len(text) > 8000` triggers the `break` statement.
3. **Top-3 Lexical Freeze Invariant**: By definition of `CascadedRanker`, ranks 0, 1, and 2 of `CAND-CASCADE` are 100% identical to `BASE-BM25`.
4. **Conclusion**: Any graph-promoted candidates at rank 4+ never enter the 8,000-character budget window because the first two files exhaust the budget. Thus, under whole-chunk packing without skeletal compression, BM25 and the cascade yield identical coverage within 8,000 characters.

---

## 6. Root Cause 5: Coverage Format in `PER_QUERY_CASCADE_RESULTS.csv`

The Stage 3.9 per-query file `research/stage3_9/PER_QUERY_CASCADE_RESULTS.csv` recorded 345 rows in wide format (tracking `bm25`, `cand_c`, `cand_f`, `repomap`, and `cascade`), but omitted columns for `CASCADE-NO-GRAPH` and `CASCADE-UNNORMALIZED`.

Stage 3.9.1 resolves this by generating `research/stage3_9_1/INDEPENDENT_RECOMPUTATION.csv` in standard tall format:
$$\text{Total Rows} = 345 \text{ queries} \times 7 \text{ configurations} = \mathbf{2,415 \text{ rows}}$$
Every configuration is explicitly represented with all 14 evaluated retrieval metrics.

