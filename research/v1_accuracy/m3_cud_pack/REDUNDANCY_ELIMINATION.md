# REPONEEDLE V1.0.0 — REDUNDANCY ELIMINATION
## Distractor Suppression, Diversity Discounting, and High-Yield Context Optimization

**Document ID**: `REPONEEDLE-M3-REDUNDANCY-ELIMINATION`  
**Milestone**: M3.3 Context Packing Engine  
**Status**: APPROVED & AUDITED  
**Scope**: 345 Benchmark Queries across 25 Repositories  

---

### 1. The Redundancy and Distractor Crisis

In Milestone 3.2, the forensic audit of the baseline context packer revealed an alarming inefficiency in token allocation:
- **Distractor Saturation**: Between **89.2% and 95.8% of all packaged tokens were non-gold distractor code**.
- **Context Monopolization**: Multiple files from a single auxiliary directory (e.g., test mocks or generated serialization code) frequently filled the entire context window, crowding out the actual bug location or feature implementation.
- **Boilerplate Inflation**: Repetitive file headers, duplicate imports, and large auto-generated comment blocks consumed hundreds of tokens without providing actionable semantic information.

When an AI coding agent is subjected to 95% distractor context, two failure modes emerge:
1. **Lost in the Middle / Attention Dilution**: LLM reasoning performance degrades rapidly when gold implementation code is buried beneath thousands of tokens of irrelevant helper code.
2. **Context Window Starvation**: Truly critical files are entirely excluded from the prompt.

CUD-Pack solves this crisis through a four-layer redundancy elimination architecture.

---

### 2. Layer 1: Query-Term Frequency Filtering

A major cause of inflated focus spans in naive code extraction is matching on ubiquitous programming keywords. Queries frequently contain words like:
`func`, `function`, `def`, `class`, `return`, `test`, `context`, `error`, `err`, `type`, `struct`, `interface`, `nil`, `true`, `false`, `string`, `int`, `import`, `package`.

If an extractor treats these keywords as search anchors, every single function in every file matches, creating massive focus spans that consume 1,500–2,500 tokens of generic boilerplate.

#### CUD-Pack Keyword Pruning
The `filter_query_terms` engine maintains a curated polyglot stop-word dictionary:
```python
COMMON_STOPWORDS = {
    "func", "function", "def", "class", "return", "if", "else", "for", "while",
    "import", "package", "from", "as", "in", "to", "the", "and", "or", "is",
    "var", "let", "const", "type", "struct", "interface", "error", "err",
    "nil", "null", "none", "true", "false", "test", "tests", "testing",
    "string", "int", "bool", "float", "self", "this", "ctx", "context",
}
```
Query terms matching this set are purged prior to span windowing. Span extraction anchors exclusively on **high-specificity domain identifiers** (e.g., `suggest_subcommand_subset`, `TestPeriodicHourly`, `mapURI`, `longestCommonPrefix`). This single mechanism reduced average focus span size from 1,240 tokens down to 348 tokens—a $3.5\times$ efficiency gain.

---

### 3. Layer 2: Geometric Directory Diversity Discounting

When retrieval models return the top 85 candidates, candidates frequently cluster within a single subsystem. For example, in an HTTP router repository, 15 of the top 20 files may reside in `binding/`.

While the primary file in `binding/` contains crucial logic, subsequent files from the same directory often contain repetitive serialization tests or minor variant parsers. Packing all 15 files consumes the entire 4,096 budget on `binding/`, leaving 0 tokens for `context.go`, `gin.go`, or routing trees.

#### The Diversity Discounting Rule
CUD-Pack introduces a geometric decay on candidate utility based on directory co-occurrence:

$$\Delta_{\text{diversity}}(c) = \beta^{k_{\text{dir}(c)}}$$

Where:
- $\beta = 0.85$ is the decay multiplier.
- $k_{\text{dir}(c)}$ is the count of candidates already selected from candidate $c$'s directory.

#### Algorithmic Impact on Context Variety:
| Directory Representation Count ($k_{\text{dir}}$) | Effective Utility Multiplier | Optimizer Selection Behavior |
| :---: | :---: | :---: |
| 0 (First file from directory) | $1.000$ | Selected with full confidence. |
| 1 (Second file from directory) | $0.850$ | Selected if utility remains higher than competing modules. |
| 2 (Third file from directory) | $0.723$ | Heavily penalized; competing directories gain priority. |
| 3 (Fourth file from directory) | $0.614$ | Only exceptionally high-ranking files admitted. |
| $\ge 4$ (Fifth+ file from directory) | $< 0.522$ | Effectively suppressed in favor of module diversity. |

This diversity discounting ensures that multi-file tasks (e.g., a query involving both an interface definition in `pkg/api` and an implementation in `pkg/server`) successfully pack representatives from both packages into the limited token window.

---

### 4. Layer 3: Representation Tier Mutex and Duplicate Repression

In naive multi-tier packings, systems often accidentally pack both a full file and a separate outline of the same file, wasting tokens.

CUD-Pack enforces strict mutually exclusive representation selection:
$$\sum_{r \in \mathcal{R}(c_i)} x_{i, r} \le 1 \quad \forall \text{ candidate files } c_i$$

- If $c_i$ is selected as `FOCUS_SPAN`, all other tiers for $c_i$ (`FULL_FILE`, `SKELETON`, `INTERFACE`) are immediately masked.
- If additional token budget remains during the residual backfilling phase, existing selections may be **upgraded in-place** (e.g., transitioning `FOCUS_SPAN` to `FULL_FILE` by paying the marginal token difference $\Delta T = T(\text{FULL}) - T(\text{SPAN})$), ensuring that no candidate's content is duplicated.

---

### 5. Layer 4: Empirical Yield and Distractor Suppression Metrics

The impact of CUD-Pack's redundancy elimination was measured across all 345 benchmark queries:

| Metric | Baseline at 4k | CUD-Pack at 4k | Delta / Impact | Baseline at 8k | CUD-Pack at 8k | Delta / Impact |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Complete Any Coverage** | 32.46% | **46.67%** | **+14.21%** | 40.58% | **41.45%** | **+0.87%** |
| **Complete Impl Coverage** | 18.55% | **44.06%** | **+25.51%** | 35.94% | **38.26%** | **+2.32%** |
| **Micro Target Recall** | 34.05% | **51.95%** | **+17.90%** | 42.02% | **45.53%** | **+3.51%** |
| **Relevant Token Yield** | 4.2% | **7.1%** | **+69.0%** | 7.8% | **10.9%** | **+39.7%** |
| **Mean Utilization** | 98.2% | **99.6%** | **+1.4%** | 98.7% | **99.8%** | **+1.1%** |
| **Downstream Overflows** | 86.67% | **0.00%** | **-86.67%** | 79.42% | **0.00%** | **-79.42%** |

#### Key Takeaway:
At 4,096 tokens, CUD-Pack increases complete implementation coverage from **18.55% to 44.06%**—more than doubling the baseline—while eliminating 100% of downstream overflows and boosting relevant token yield by 69%.

