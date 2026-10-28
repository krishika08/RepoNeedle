# MULTI-DIMENSIONAL SCORECARD AND STATISTICAL DECISION RULES

**Document ID**: `SDR-2026-001`  
**Version**: 1.0.0  
**Date**: 2026-10-28  
**Author**: Principal Retrieval Researcher & Lead Systems Engineer  

---

## 1. The Five Dimensions of Evaluation

RepoNeedle rejects single-metric optimization. A retrieval system that increases MRR by 0.02 at the cost of 5-second latency or blowing through agent context limits is practically useless. We evaluate all systems across five rigorous dimensions:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        The Five Scorecard Dimensions                   │
├──────────────────────────────┬─────────────────────────────────────────┤
│ 1. Retrieval Quality         │ Top-k precision, rank depth, task yield │
│ 2. Context Packing Quality   │ Token budget efficiency, skeleton yield │
│ 3. Selective Abstention      │ Calibration, risk-coverage, safe failure│
│ 4. Downstream Agent Utility  │ End-to-end task resolution, tool calls  │
│ 5. Systems Efficiency        │ Latency distribution, memory, footprint │
└──────────────────────────────┴─────────────────────────────────────────┘
```

---

## 2. Formal Metric Definitions

### Dimension 1: Retrieval Quality
1. **Mean Reciprocal Rank (MRR)**:
   $$\text{MRR} = \frac{1}{|Q|} \sum_{q=1}^{|Q|} \frac{1}{\text{rank}_q}$$
   where $\text{rank}_q$ is the position of the first relevant file.
2. **Recall@k ($k \in \{5, 10, 20\}$)**:
   $$\text{Recall@}k = \frac{1}{|Q|} \sum_{q=1}^{|Q|} \frac{|\text{Retrieved}_k(q) \cap \text{Gold}(q)|}{|\text{Gold}(q)|}$$
3. **Relevant-File Candidate Coverage**: Percentage of queries where *all* gold files exist within top 50 candidates.

### Dimension 2: Context Packing Quality
1. **Budgeted Context Yield (BCY@$B$, $B \in \{2k, 4k, 8k, 16k\}$ tokens)**:
   $$\text{BCY@}B = \frac{1}{|Q|} \sum_{q=1}^{|Q|} \frac{|\text{PackedFiles}_B(q) \cap \text{Gold}(q)|}{|\text{Gold}(q)|}$$
   evaluated under strict canonical token counting (`regex_code_tokenizer_v1`).
2. **Context Noise Ratio (CNR@$B$)**:
   $$\text{CNR@}B = \frac{\text{Tokens of Irrelevant Files Packed in Budget } B}{B}$$
3. **Structural Integrity**: Binary verification that packed structural skeletons contain syntactically valid function signatures, classes, and types.

### Dimension 3: Selective Retrieval & Abstention
1. **Selective Abstention Accuracy**:
   $$\text{Acc}_{\text{abstain}} = \frac{\text{Correct Abstentions on No-Gold Tasks}}{\text{Total No-Gold Tasks}}$$
2. **False Return Rate (FRR)**: Percentage of no-gold queries where the retriever returns files (false positives).
3. **False Abstention Rate (FAR)**: Percentage of solvable positive queries where the retriever abstains (false negatives).
4. **Empirical Risk at Coverage $C$**: Error rate on the subset of queries where confidence score exceeds threshold $\tau(C)$.

### Dimension 4: Downstream Coding-Agent Utility (Practical Ground Truth)
1. **Pass@1 (Patch Resolution Rate)**:
   $$\text{Pass@1} = \frac{\text{Number of Tasks where Agent Patch Passes Test Suite}}{\text{Total Solvable Tasks}}$$
   evaluated using fixed agent scaffolding (e.g. SWE-agent / ContextBench harness) and fixed LLM (e.g. Claude 3.5 Sonnet).
2. **Exploration Step Reduction**: Percentage reduction in agent inspection tool calls (`view_file`, `grep`, `cd`) when pre-provided with retrieved context.
3. **Context Token Overhead**: Average prompt tokens billed across the entire multi-turn problem-solving trajectory.
4. **Failure Attribution**: Classification of agent failures into:
   - *Missing Context*: Gold file was not retrieved.
   - *Distractor Confusion*: Irrelevant file misled the agent.
   - *Synthesis Failure*: Context was present, but agent LLM failed to write the fix.

### Dimension 5: Systems Efficiency
1. **Cold & Warmed Latency Distribution**: $p_{50}, p_{95}, p_{99}$, and mean latency measured across 100+ warmed iterations.
2. **Index Construction Time**: Seconds required to parse and build all static graph, lexical, and semantic indices from scratch.
3. **Incremental Update Time**: Milliseconds required to re-index when a single file is modified.
4. **Memory Footprint**: Resident set size (RSS RAM) of the in-memory index.
5. **Dependency Burden**: Number and size of third-party runtime packages required.

---

## 3. Rigorous Statistical Decision Rules

To prevent false claims driven by random seed variance or repository clustering:

### Rule 1: Repository-Clustered Bootstrap Resampling
Queries from the same repository (e.g. Gin contributes 88 queries) exhibit correlated errors. Therefore:
- All paired difference evaluations must use **repository-clustered bootstrap resampling** ($B = 10,000$ iterations).
- Repositories, rather than individual queries, are resampled with replacement.
- A candidate $C$ is significantly better than baseline $B$ if and only if the **95% Confidence Interval for $\Delta_{\text{MRR}}(C - B)$ lies entirely above zero**.

### Rule 2: Minimum Practical Effect Size
- Statistical significance alone ($p < 0.05$) is insufficient if effect size is negligible.
- A candidate must demonstrate at least **$+5.0\%$ relative improvement** on the primary track metric (MRR for Track A; BCY@8k or Pass@1 for Track B).

### Rule 3: Anti-Regression Boundary
- A candidate that improves one task category at the expense of severe degradation elsewhere is rejected.
- **Maximum allowable secondary regression**: No single task category (`code2test`, `comment2context`, `trace2code`, `edit2ripple`) may regress by more than **$-10.0\%$ relative** compared to the baseline without an explicit pre-registered architectural exemption.

### Rule 4: Pareto Dominance Verification
A candidate $C$ dominates candidate $B$ ($C \succ B$) if:
$$\forall m \in \mathcal{M}, \quad m(C) \ge m(B) \quad \land \quad \exists m^* \in \mathcal{M}, \quad m^*(C) > m^*(B)$$
For Track A: $\mathcal{M} = \{\text{MRR}, \text{BCY@4k}, -\text{Latency}_{p95}, -\text{RAM}\}$.  
For Track B: $\mathcal{M} = \{\text{Pass@1}, \text{MRR}, \text{Recall@20}, -\text{Cost}\}$.

---

## 4. Experiment Sign-Off Protocol

Every experiment requires a three-step sign-off before being incorporated into mainline code:
1. **Preregistration**: Log hypothesis, target metrics, and configuration in `research/EXPERIMENT_REGISTRY.jsonl`.
2. **Automated Verification**: Run regression tests (`pytest -v`) and verify that all 34 existing robustness tests pass.
3. **Audit Trail**: Record raw predictions, bootstrap CIs, hardware timings, and failure taxonomy updates.
