# KNOWN LIMITATIONS AND RELEASE RECOMMENDATIONS

**Document ID**: `KLR-2026-001`  
**Version**: 1.0.0  
**Date**: 2026-10-28  
**Author**: Principal Retrieval Researcher & Lead Systems Engineer  

---

## 1. Current Known Limitations

### Limitation 1: Heuristic Selective Abstention Complete Failure
- **Finding**: 0 out of 82 no-gold tasks were correctly identified in production benchmark conditions (100% false return rate).
- **Cause**: Lexical $Z$-score and symbol overlap fail on full repositories because real software bugs share terminology with the target codebase, and counterfactual tasks contain universal coding terms.
- **Remedy**: Selective abstention cannot be solved by heuristics; a learned neural discriminator or semantic entailment model is mandatory.

### Limitation 2: Deep Tail Recall Deficit vs. RepoMap
- **Finding**: RepoMap achieves Recall@20 of `0.6306` compared to RepoNeedle's `0.4279` (-32.1% deficit). On `trace2code`, RepoMap achieves Recall@20 of `0.8465` vs RepoNeedle `0.4092`.
- **Cause**: RepoNeedle's knapsack density optimizer focuses heavily on top-k precision ($k \le 5$). RepoMap's PageRank naturally diffuses probability across the entire connected component, capturing secondary callers.
- **Remedy**: Introduce fast personalized PageRank graph diffusion into RepoNeedle to expand tail recall without sacrificing top-1 precision.

### Limitation 3: Documentation Distractor Pollution in Issue Comments
- **Finding**: BM25 outperforms RepoNeedle on `comment2context` (MRR: `0.1974` vs `0.1708`).
- **Cause**: Markdown documentation files (`Documentation/`, `docs/`, `.rst`) share dense conversational vocabulary with issue comments, displacing actual code files in top ranks.
- **Remedy**: Apply content-type gating and path-penalty priors for non-code documentation files during code search tasks.

### Limitation 4: Monolithic File Context Exhaustion
- **Finding**: Single multi-thousand-line files (e.g. `server.go`, `modeling_bert.py`) consume 4k–6k tokens if included in `FULL` tier, crowding out supporting files.
- **Cause**: File-level knapsack packing lacks block/function-level slicing.
- **Remedy**: Implement fine-grained AST block-level slicing.

---

## 2. Release & Governance Recommendations

1. **Strict Prohibition on Premature Publication**:
   - No packages or models may be uploaded to Hugging Face or PyPI while the research program is active.
   - Any interim release must be labeled as a **Research Preview** with explicit disclaimers regarding selective retrieval.
2. **Prohibition on Unsubstantiated Claims**:
   - Never claim RepoNeedle beat RepoMap conclusively; empirical difference on MRR (+0.0148) is statistically insignificant ($p = 0.4089$), and RepoMap wins decisively on tail recall.
3. **Requirement for Independent Verification**:
   - No architectural change tuned on ARB v2 may be claimed as state-of-the-art until independently validated on the held-out benchmark suite ($N \ge 200$ across $\ge 50$ repositories).

