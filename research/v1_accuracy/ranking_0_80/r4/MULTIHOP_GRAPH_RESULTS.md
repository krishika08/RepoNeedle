# RepoNeedle — Phase R4: Multi-Hop Structural Retrieval Results

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R4 — Dense Semantic + Multi-Hop Structural Retrieval  
**Date**: November 2, 2026  
**Status**: Experimental Findings & Empirical Evaluation  

---

## 1. Executive Summary

Phase R4 evaluated multi-hop structural retrieval across the 345 benchmark queries in two configurations:
1. **Treatment C (Multi-Hop Graph Alone)**: Ranking candidates exclusively by structural path proximity from seed files with hop attenuation and hub dampening.
2. **Treatment E (R2 + Multi-Hop Graph Retrieval)**: Multi-hop graph scores combined with the authoritative R2 baseline.

### Primary Conclusions
- **Standalone Structural Traversal is Insufficient**: In isolation, multi-hop graph retrieval collapses catastrophically (Validation MRR drops to **0.1172**, Hit@1 falls to **0.00%**, and Held-Out MRR drops to **0.0478**). Without lexical relevance anchoring, graph traversal wanders into structural neighborhoods that are architecturally connected but conceptually irrelevant.
- **R2 + Multi-Hop Graph (Treatment E)**: Yields a slight gain on Train (MRR 0.4632 vs 0.4544, $\Delta = +0.0088$), but shows slight regression on Validation (MRR 0.2956 vs 0.2971, $\Delta = -0.0015$) and Held-Out (MRR 0.2957 vs 0.2965, $\Delta = -0.0008$).
- **Role in Hybrid System**: Multi-hop structural retrieval cannot serve as an independent ranking channel or simple additive feature; its primary value is as a structural tie-breaker in multi-file edit propagation (`edit2ripple`).

---

## 2. Master Evaluation Metrics: Baseline vs Graph Treatments

| Split | Metric | Treatment A (R2 Baseline) | Treatment C (Graph Alone) | Treatment E (R2 + Graph) | Delta (E vs A) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Validation** | **MRR** | **0.2971** | **0.1172** | **0.2956** | **-0.0015** |
| ($N=60$) | **Hit@1** | 16.67% | 0.00% | 16.67% | 0.00% |
| | Recall@5 | 0.3208 | 0.1653 | 0.3042 | -0.0166 |
| | Recall@10 | 0.4236 | 0.2847 | 0.4236 | 0.0000 |
| | Recall@20 | 0.5875 | 0.3986 | 0.5792 | -0.0083 |
| **Train** | **MRR** | 0.4544 | 0.2661 | **0.4632** | **+0.0088** |
| ($N=210$) | **Hit@1** | 25.71% | 16.19% | **27.14%** | +1.43% |
| | Recall@5 | 0.5745 | 0.2647 | **0.5823** | +0.0078 |
| | Recall@10 | 0.7033 | 0.3821 | 0.6960 | -0.0073 |
| | Recall@20 | 0.8009 | 0.6583 | **0.8018** | +0.0009 |
| **Held-Out** | **MRR** | 0.2965 | 0.0478 | **0.2957** | **-0.0008** |
| ($N=75$) | **Hit@1** | 17.33% | 1.33% | 17.33% | 0.00% |
| | Recall@5 | 0.4489 | 0.0400 | 0.4356 | -0.0133 |
| | Recall@10 | 0.5222 | 0.0844 | 0.5222 | 0.0000 |
| | Recall@20 | 0.5800 | 0.1844 | **0.5933** | +0.0133 |
| **Overall** | **MRR** | 0.3927 | 0.1927 | **0.3976** | **+0.0049** |
| ($N=345$) | **Hit@1** | 22.32% | 10.14% | **23.19%** | +0.87% |
| | Recall@20 | 0.7157 | 0.5101 | **0.7178** | +0.0021 |

---

## 3. Failure Analysis: The Mechanics of Graph Distraction

Why does pure structural traversal fail so severely in isolation?

### 3.1 Proximity Does Not Imply Intent
Software repositories exhibit high static coupling: a database model file imports types, validators, serialization schemas, migration utilities, and logging frameworks.
- When an engineer submits a query asking: `"fix validator constraint on user email"`, the seed file is `models/user.py`.
- Treatment C traverses 1-hop dependencies and finds `db/engine.py`, `utils/logging.py`, `migrations/v2.py`, and `validators/user.py`.
- Because `db/engine.py` and `utils/logging.py` have higher static connectivity, they receive equal or higher graph scores than `validators/user.py`.
- **Result**: Top-1 accuracy is 0.0% on the validation set because structural distance cannot distinguish *what changed* from *what happened to be imported*.

### 3.2 Attenuation Sensitivity
Without lexical weighting, 2-hop traversal quickly expands the candidate space to include tens of irrelevant files. While $\gamma = 0.5$ dampens 2-hop paths, when multiple 2-hop paths converge on a module, path score accumulation offsets attenuation.

---

## 4. Key Takeaways for System Architecture

1. **Static graphs must be downstream filters or multipliers, never upstream generators or independent rankers.**
2. **Structural signal is highest for `edit2ripple` tasks**, where developers explicitly modify caller-callee chains. In `comment2context` and `trace2code`, lexical and semantic signals dominate.
3. Incorporating graph traversal requires multi-signal calibration, leading directly to the hybrid fusion designs of Treatments G and H.

