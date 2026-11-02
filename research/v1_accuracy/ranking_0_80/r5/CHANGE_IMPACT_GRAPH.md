# RepoNeedle — Phase R5: Typed Change-Impact Intelligence Graph

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R5 — Function-Level, Change-Aware Code Retrieval  
**Date**: November 2, 2026  
**Status**: Architecture & Empirical Analysis  

---

## 1. Executive Summary & Architectural Breakthrough

In Phase R4, untyped call-graph expansion failed in isolation (MRR dropped to 0.1172) because treating all edges identically allowed utility sinks (`utils.py`, `errors.py`) to absorb structural activation across unrelated queries.

Phase R5 introduces the **Typed Change-Impact Intelligence Graph**:
- Decomposes static code relationships into **5 distinct typed relations**.
- Applies **intent-conditioned edge modulation**: dynamically activating edge types matching the user's task.
- Enforces non-linear hub dampening to prevent utility sinks.

### Primary Empirical Findings (Treatment F):
- **Validation MRR**: **0.3235** vs Baseline **0.2971** ($\mathbf{\Delta = +0.0264}$, $p = 0.0001$).
- **Held-Out MRR**: **0.3183** vs Baseline **0.2965** ($\mathbf{\Delta = +0.0218}$, **+7.35% relative gain on held-out codebases**).
- **Train MRR**: **0.4799** vs Baseline **0.4544** ($\Delta = +0.0255$).
- **Validation Recall@20**: **0.5958** (Highest Recall@20 observed across all R1–R5 treatments).
- **Overall Hit@1**: **25.51%** (88 queries at Rank 1 vs 77 in baseline).
- **Query Latency**: **0.541 ms mean** (P95: 0.659 ms) on standard CPU cores.

---

## 2. Multi-Relational Typed Edge Taxonomy

| Edge Type | Semantic Definition | Inferred Evidence | Default Weight | Conditioned Intent Multiplier |
| :--- | :--- | :--- | :---: | :---: |
| **`TESTS_BEHAVIOR`** | Test suite verifying an implementation | Test naming convention (`test_*.py`), assertion call sites, import of module | 1.00 | $1.6\times$ if `intent == TEST`<br>$0.8\times$ if `intent != TEST` |
| **`CHANGED_CALLER`** | Downstream caller affected by seed change | Static function invocation / call sites targeting seed | 0.85 | $1.5\times$ if `intent in (REF, ERROR)`<br>$0.9\times$ otherwise |
| **`IMPORTS_DEPENDENCY`**| Structural import dependency | `import x` or `from x import y` | 0.80 | $1.0\times$ (constant baseline) |
| **`MODULE_BUILD_CONFIG`**| Package/build manifest for module | Directory ancestor manifest (`setup.py`, `Cargo.toml`) | 0.50 | $1.4\times$ if `intent == VALIDATION`<br>$0.4\times$ otherwise |
| **`PUBLIC_SYMBOL_DOCS`** | Documentation mentioning module/symbol | Markdown / RST docs in `docs/` or `README.md` | 0.40 | $0.35\times$ (low baseline) |

---

## 3. Detailed Results Across Splits: Treatment F vs Baseline

| Split | Metric | Treatment A (R2 Baseline) | Treatment F (Change-Impact) | Delta ($\Delta$) | Relative Change |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Validation** | **MRR** | **0.2971** | **0.3235** | **+0.0264** | **+8.88%** |
| ($N=60$) | **Hit@1** | 16.67% | **20.00%** | +3.33% | +20.0% |
| | Recall@5 | 0.3208 | **0.3458** | +0.0250 | +7.79% |
| | Recall@10 | 0.4236 | 0.4236 | 0.0000 | 0.0% |
| | **Recall@20** | **0.5875** | **0.5958** | **+0.0083** | **+1.41%** |
| | Complete Coverage | 50.0% | **50.0%** | 0.0% | 0.0% |
| **Held-Out** | **MRR** | **0.2965** | **0.3183** | **+0.0218** | **+7.35%** |
| ($N=75$) | **Hit@1** | 17.33% | **18.67%** | +1.34% | +7.73% |
| | Recall@5 | 0.4489 | **0.4622** | +0.0133 | +2.96% |
| | Recall@10 | 0.5222 | **0.5289** | +0.0067 | +1.28% |
| | Recall@20 | 0.5800 | **0.6244** | **+0.0444** | **+7.66%** |
| | Complete Coverage | 52.0% | **56.0%** | +4.0% | +7.69% |
| **Train** | **MRR** | **0.4544** | **0.4799** | **+0.0255** | **+5.61%** |
| ($N=210$) | **Hit@1** | 25.71% | **29.52%** | +3.81% | +14.8% |
| | Recall@20 | 0.8009 | **0.8080** | +0.0071 | +0.89% |
| **Overall** | **MRR** | **0.3927** | **0.4176** | **+0.0249** | **+6.34%** |
| ($N=345$) | **Hit@1** | 22.32% | **25.51%** | +3.19% | +14.3% |
| | Recall@20 | 0.7157 | **0.7312** | +0.0155 | +2.17% |

---

## 4. Why Typed Change-Impact Succeeds on Held-Out Repositories

On held-out repositories (`django`, `scikit-learn`, `numpy`, `pandas`, `scipy`), Treatment F delivers a remarkable gain from **0.2965 to 0.3183 MRR** and boosts Recall@20 from **0.5800 to 0.6244**.

### Forensic Inspection:
1. **Test-Behavior Pairing**: In large repositories, developers often query about a specific feature (e.g. `dataframe rolling window quantile`). The seed file is `pandas/core/window/rolling.py`. The gold file to be modified is `pandas/tests/window/test_quantile.py`. Lexical BM25 places the test file at Rank 8 because the test file repeats fewer keywords. The `TESTS_BEHAVIOR` edge detects the token match between `window` and `rolling`, boosting the test file to **Rank 1**.
2. **Caller Disambiguation in Tracebacks**: In traceback queries (`trace2code`), the seed file is where the error crashed, but the actual bug fix belongs to the upstream caller that passed invalid arguments. The `CHANGED_CALLER` edge boosts the upstream caller into the top-3.

