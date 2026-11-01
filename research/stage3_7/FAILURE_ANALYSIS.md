# RepoNeedle Stage 3.7: Retrieval Failure Deconstruction & Component Isolation Analysis

## 1. Executive Summary

Stage 3.6 formally retracted Candidate F's winner status after revealing that its reported Stage 3.5 score (0.2152 MRR) was achieved under a flawed, test-category-filtered evaluation protocol (`tests_only = True`) with hardcoded graph bypass shortcuts. Under the unconstrained protocol, Candidate F collapsed to **0.1351 MRR**, falling behind Candidate C (0.1409 MRR), pure BM25 (0.1735 MRR), and RepoMap (0.2293 MRR).

Stage 3.7 conducted a forensic component-isolation experiment series across all 345 positive ARB v2 queries and 218 repository splits to isolate the precise mechanisms responsible for this retrieval failure.

---

## 2. Failure Mechanism 1: BM25 Document-Length Inflation

### 2.1 The Mathematical Mechanism
The standard Okapi BM25 scoring formula is:

$$\text{Score}(D, Q) = \sum_{t \in Q} \text{IDF}(t) \cdot \frac{\text{TF}(t, D) \cdot (k_1 + 1)}{\text{TF}(t, D) + k_1 \cdot \left(1 - b + b \cdot \frac{dl}{avgdl}\right)}$$

In Candidate F, polyglot symbol extraction (functions, classes, structs, traits) extracted symbol identifiers and appended them directly into the document token stream. Furthermore, in `reponeedle/core/lexical.py`, when `decouple_symbols = False`:

$$\text{effective\_len} = \sum \text{weighted\_counts.values()} = 2.5 \cdot \text{len}(\text{path\_tokens}) + 2.0 \cdot \text{len}(\text{sym\_tokens}) + 1.0 \cdot \text{len}(\text{body\_tokens})$$

For symbol-dense code files (e.g. core modules, test suites, class registries), this definition inflated the effective document length $dl$ by **1.2x to 2.5x**. Because $dl$ sits directly in the normalization denominator, files with many symbol definitions suffered severe length normalization penalties, suppressing their BM25 score even when the query matched their identifiers.

### 2.2 Empirical Evidence (`BM25_LENGTH_DIAGNOSTICS.csv`)
Across 514 gold file instances in the benchmark:
- **Correlation with Rank Degradation**:
  - Pearson correlation: $r = 0.4989$ ($p = 1.05 \times 10^{-33}$)
  - Spearman rank correlation: $r = 0.6029$ ($p = 3.53 \times 10^{-52}$)
- **Concrete Degradation Case Studies**:
  1. `huggingface/transformers` (`tests/models/auto/test_tokenization_auto.py`):
     - Lexical tokens: 1,479 | Symbol tokens: 219 | Coupled length: 1,928 (1.30x inflation).
     - Rank with decoupled length: **#422** $\to$ Rank with coupled length: **#516** (**+94 rank drop**).
  2. `huggingface/transformers` (`tests/models/mt5/test_modeling_mt5.py`):
     - Lexical tokens: 1,329 | Symbol tokens: 113 | Coupled length: 1,566 (1.18x inflation).
     - Rank with decoupled length: **#426** $\to$ Rank with coupled length: **#505** (**+79 rank drop**).
  3. `fastapi/fastapi` (`tests/test_jsonable_encoder.py`):
     - Lexical tokens: 1,663 | Symbol tokens: 221 | Coupled length: 2,114 (1.27x inflation).
     - Rank with decoupled length: **#296** $\to$ Rank with coupled length: **#340** (**+44 rank drop**).

---

## 3. Failure Mechanism 2: Graph Hub Dilution

### 3.1 Unbounded Bidirectional Diffusion
Candidate F propagated seed query relevance along repository dependency edges:
- Forward propagation (seed $\to$ successors / imports): weight $\alpha_{\text{fwd}} = 0.25$.
- Backward propagation (predecessors / callers $\to$ seed): weight $\alpha_{\text{bwd}} = 0.20$.
- Degree threshold: $\text{max\_diffusion\_degree} = 999,999$ (unbounded).

### 3.2 Topological Hub Concentration (`GRAPH_HUB_DIAGNOSTICS.csv`)
Repository dependency graphs exhibit extreme heavy-tailed power-law connectivity:
- Maximum total node degree observed: **3,890 edges** on a single node (e.g. root packages and re-export modules like `__init__.py` or `mod.rs`).
- Median maximum degree across repositories: **160.0**.
- Top 5% most connected nodes account for **up to 62%** of all directed edge endpoints.

When seed files import or are imported by these supernodes, unnormalized diffusion pumps large score mass into the hub. In turn, when a hub is boosted, it pushes irrelevant utility modules into top-20 ranks, knocking true target files out.

### 3.3 Directional Asymmetry (`GRAPH_DIFFUSION_RESULTS.csv`)
- **Bidirectional Diffusion**:
  - Degraded gold files: **228 (44.4%)**
  - Improved gold files: **112 (21.8%)**
  - Unchanged: **174 (33.9%)**
  - *Verdict*: Unbounded bidirectional diffusion is net-destructive by a factor of 2:1.
- **Forward-Only Diffusion (EXP-375)**:
  - MRR: **0.1314** (regression of -0.0037 vs Candidate F, clustered Wilcoxon $p = 0.0112$).
  - Recall@20: **0.4827** (regression of -0.0251).
  - *Mechanism*: Forward edges point from implementation files to low-level utility libraries, standard libraries, and helper modules, drowning out the actual target.
- **Backward-Only Diffusion (EXP-376)**:
  - MRR: **0.1427** (improvement of +0.0076 vs Candidate F).
  - Recall@20: **0.5216** (improvement of +0.0138).
  - *Mechanism*: Backward edges point from dependents/callers to seeds, surfacing contextual callers and test suites.
- **Hub Normalization (EXP-377)**:
  - Normalizing diffusion boost by $1 / \sqrt{\text{degree}}$ improves **215 (41.8%)** of gold files and raises MRR to **0.1427**.

---

## 4. Failure Mechanism 3: Static PageRank Dilution

In both Candidate C and Candidate F, the base retrieval score was constructed as:

$$\text{Base Score} = \frac{\text{Score}_{\text{lexical}} + \text{Score}_{\text{semantic}} + \text{Score}_{\text{PageRank}}}{3.0}$$

Static PageRank assigns high scores to structural hubs regardless of the query text.
- PageRank completely ignores the user's task prompt.
- For queries targeting specific leaf functions or newly modified test files, PageRank injects a constant 33% penalty against the leaf target in favor of top-level dispatchers.
- In `EXP-378`, removing static PageRank from the base score and relying exclusively on query-conditioned lexical, semantic, and hub-normalized diffusion enabled MRR to surge from **0.1409 to 0.2052 (+0.0643)**.

---

## 5. Failure Mechanism 4: Selective Abstention Failure

Stage 3.6 reported a **98.78% false accept rate** on zero-gold queries under the default static threshold ($\text{max\_score} < 0.38$).
- Root Cause: Max-normalization ($\text{score} / \max(\text{scores})$) ensures that for every query, the top document always receives a score of `1.0` if any query term matched any token in the repository.
- A fixed global score threshold of 0.38 cannot reliably discriminate between true positive queries and unanswerable queries.
- Feasibility: Abstention requires repository-normalized confidence calibration (e.g. score margin between rank 1 and rank 5, query vocabulary density, or IDF entropy), which must be investigated in a dedicated calibration stage rather than post-hoc threshold tuning.

