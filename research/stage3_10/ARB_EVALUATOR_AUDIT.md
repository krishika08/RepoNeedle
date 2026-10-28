# REPONEEDLE STAGE 3.10: ARB EVALUATOR AUDIT & SPECIFICATION CONTRACT

**Audit Date**: October 2026  
**Document ID**: `STAGE3.10-ARB-AUDIT-001`  
**Git Workspace**: `F:\RepoNeedle`  
**ARB Directory**: `F:\RepoNeedle\external\agent-retrieval-bench`  
**Status**: Authoritative Upstream Evaluator Reconciliation  

---

## 1. OFFICIAL REPOSITORY & PINNED EVALUATOR REVISION

* **Official Repository URL**: `https://github.com/eyuansu62/agent-retrieval-bench`
* **Pinned Evaluator Commit SHA**: `9e4d68937f29d5967afd62f4f6a24c1478298133` (October 27, 2026, `origin/main`)
* **Critical RepoMap Determinism Update**:
  - **Commit SHA**: `f0cc9bead468f85729a67a3ef3471bd99f7bd66e` (PR #3, merged October 22, 2026)
  - **Source Commit**: `dda9cc25b665581270423d7e5f3b337db6c1cf55` by Xucheng Zhou (`Make RepoMap symbol graph construction deterministic`)
  - **Upstream PR Directive**:
    > *"RepoMap previously allowed Python set iteration to affect capped symbol references and normalized symbol names. Stabilize those choices while preserving existing weights and caps so repeated evaluations can be compared reliably. Directive: Regenerate version-pinned RepoMap baseline artifacts before updating published scores."*
  - **Root Cause of Prior Variance**: In earlier revisions of `src/agent_retrieval_bench/repomap_eval.py`, symbol references were stored in standard unordered Python `set` collections. Because Python randomizes dictionary/set hash seeds across interpreter runs (`PYTHONHASHSEED`), iterating over sets produced non-deterministic symbol caps when a file defined $>80$ symbols. PR #3 enforced deterministic sorted ordering on all identifier references and import specs.

---

## 2. OFFICIAL SCORING & EVALUATION CONTRACT

The official Agent Retrieval Bench v2 evaluation contract comprises the following components:

### 2.1 Lexical BM25Okapi Model
* Implemented in `src/agent_retrieval_bench/baseline.py`:
  $$S(D, Q) = \sum_{q \in Q} \text{IDF}(q) \cdot \frac{f(q, D) \cdot (k_1 + 1)}{f(q, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$
* **Parameters**: $k_1 = 1.5$, $b = 0.75$.
* **IDF Formula**: Smooth Robertson-Sparck Jones IDF:
  $$\text{IDF}(q) = \ln\left(\frac{N - n(q) + 0.5}{n(q) + 0.5} + 1.0\right)$$

### 2.2 Tokenization Contract
* Function `agent_retrieval_bench.baseline.tokenize(text)`:
  - Regex splitting: `[A-Za-z0-9]+`
  - Subword splitting on camelCase transitions (`([a-z])([A-Z])`) and snake_case underscores.
  - Lowercases all extracted tokens. Minimum length $\ge 1$.

### 2.3 Multi-Target Fractional Recall Contract
* Function `agent_retrieval_bench.baseline.sample_metrics(gold_files, ranked_chunks, context_budget=8000, ...)`:
  $$\text{Recall@}k = \frac{|\text{GoldFiles} \cap \text{RankedFiles}_{1..k}|}{|\text{GoldFiles}|}$$
* **Critical Distinction**: This is **fractional recall**. Binary Hit@k (which counts 1 if *any* gold target is retrieved) is completely distinct. In Stage 3.5, binary Hit@20 was mistakenly published as Recall@20. Stage 3.6/3.9/3.10 strictly compute fractional recall.

### 2.4 Context Packing & Token BCY@8k Contract
* Implemented in `src/agent_retrieval_bench/bcy_curve.py`:
  - Function `pack_files(repo, base_commit, ranked_files, gold_files, corpus_cache, budget=8000)`:
  - Iterates through `ranked_files` in ranked order, charging header tokens ($20$ tokens per file) and content tokens.
  - Files fitting within the $8,000$ token budget are fully packed; the marginal file is partially included if remaining budget allows.
  - Computes:
    $$\text{Token BCY@8k} = \frac{|\text{GoldFiles} \cap \text{PackedFiles}|}{|\text{GoldFiles}|}$$

### 2.5 Official RepoMap Implementation
* Implemented in `src/agent_retrieval_bench/repomap_eval.py`:
  - Builds bipartite symbol reference graph from import statements and regex-extracted definitions.
  - Fuses query token match ($65\%$), PageRank centrality ($25\%$), and affinity propagation ($10\%$).
  - Evaluated via `evaluate_repomap_baseline()` with `all_files` candidate filter.

---

## 3. AUDIT OF EXECUTION ENVIRONMENT & HISTORICAL DISCREPANCIES

| Issue Identified | Historical Manifestation | Root Cause in Code | Resolution & Verification |
| :--- | :--- | :--- | :--- |
| **Manifest Relative Path Failure** | Earlier scripts reported `missing_corpus` when calling official ARB CLI | In `load_corpus_manifest(corpus_dir)`, `chunks_path` is parsed as relative `data/corpus/...`. If `cwd` is `F:\RepoNeedle`, `chunks_path.exists()` returned `False`. | Change working directory to `external/agent-retrieval-bench` or anchor paths to `ARB_DIR`. |
| **RepoMap Hash-Seed Variance** | RepoMap MRR varied between $0.2140$ and $0.2293$ | Python unordered set iteration over $>80$ symbol definitions per file prior to Oct 22, 2026. | Version pinned to commit `9e4d689` containing PR #3 (`f0cc9be`) deterministic sorting. |
| **BM25 Metric Mislabeled** | Stage 3.5 reported BM25 Recall@20 $= 0.4928$ | Stage 3.5 calculated binary Hit@20 ($170/345 = 0.4928$) and labeled it fractional recall. | Official contract verified: multi-target fractional Recall@20 is **0.4622** (file-level) / **0.4549** (chunk-level). |

---

## 4. VERIFICATION CONCLUSION

The official evaluation path in `external/agent-retrieval-bench` (commit `9e4d689`) is fully functional, deterministic, and verified. All evaluations in Stage 3.10 will use this version-pinned contract.
