# RepoNeedle Stage 3.8: Query-Conditioned Graph Retrieval Design
## Architectural Specification and Formal Mathematical Formulations

---

### 1. Architectural Motivation

Prior RepoNeedle stages identified two fundamental failure modes of repository graph propagation:
1. **Static Centrality Bias (Stage 3.7)**: Unconditional PageRank severely penalizes leaf modules, test utilities, and focused implementation files by multiplying rank scores by global connectivity.
2. **Indiscriminate Graph Diffusion (Stage 3.7.1)**: While hub-normalized backward diffusion improved aggregate MRR from 0.1409 to 0.2052, it caused localized regressions in repositories like `pallets/click` and `clap-rs/clap`. In Click, test callers of central classes (`src/click/core.py`) received diffusion energy, causing 15+ test files to leapfrog the true implementation target. In Clap, build manifests (`Cargo.toml`) and cross-crate utility modules absorbed diffusion energy.

**Core Design Hypothesis**:
> *A structural graph edge indicates syntactic dependency or naming coincidence, not guaranteed semantic relevance to the current developer intent. Graph propagation must be conditioned on the query context and edge semantics.*

---

### 2. Formal Mathematical Formulations

#### 2.1 Base Multi-Modal Retrieval Score
Let $D$ be the universe of candidate files in the repository. For query $q$ and document $d \in D$:
$$\text{Score}_{\text{lex}}(d) = \text{BM25}_{\text{decoupled}}(q, d)$$
$$\text{Score}_{\text{subword}}(d) = \text{SubwordSemantic}(q, d)$$
$$\text{Base}(d) = \frac{\text{Score}_{\text{lex}}(d) + \text{Score}_{\text{subword}}(d)}{2.0} \times \phi_{\text{doc}}(d)$$
where $\phi_{\text{doc}}(d) = 0.50$ if $d$ matches documentation/markup paths (`/doc/`, `/docs/`, `.md`, `.rst`, `.html`), and $1.00$ otherwise.

Seed candidate relevance is defined as:
$$\text{Hits}(d) = \text{Score}_{\text{lex}}(d) + \text{Score}_{\text{subword}}(d)$$
Top seeds $S \subset D$ are selected as the top 5 documents with $\text{Hits}(d) > 0$.

---

#### 2.2 Hub-Normalized Forward Diffusion
Forward diffusion propagates score from seed $s \in S$ to its successors $t \in \text{succ}(s)$ (files that $s$ calls/imports):
$$\text{Boost}_{\text{fwd}}(t) = \max_{s \in \text{pred}(t) \cap S} \left( \text{Hits}(s) \cdot \frac{0.25}{\sqrt{\max(1, \text{in\_degree}(t))}} \right)$$

---

#### 2.3 Query-Conditioned Backward Propagation Variants

##### Variant A: Query-Affinity Scaling (`EXP-385`)
Backward propagation transfers energy from seed $s$ to predecessor $p \in \text{pred}(s)$ (callers/importers of $s$). In `EXP-385`, the energy transfer is scaled by the predecessor's own query relevance:
$$\text{Affinity}(p) = \frac{\text{Hits}(p)}{\max_{d \in D} \text{Hits}(d)}$$
$$\text{Scale}_{\text{aff}}(p) = 0.20 + 0.80 \cdot \text{Affinity}(p)$$
$$\text{Boost}_{\text{bwd}}^{(385)}(p) = \max_{s \in \text{succ}(p) \cap S} \left( \text{Hits}(s) \cdot \frac{0.20}{\sqrt{\max(1, \text{out\_degree}(p))}} \cdot \text{Scale}_{\text{aff}}(p) \right)$$
*Property*: If predecessor $p$ has zero lexical/subword relevance to query $q$, its backward boost is attenuated by 80% ($\text{Scale} = 0.20$). If $p$ strongly matches the query, it receives full transmission ($\text{Scale} = 1.00$).

##### Variant B: Edge-Type-Aware Directional Gating (`EXP-386`)
In `EXP-386`, structural edges are classified by node role and query intent:
1. **Manifest File Attenuation**: If $p$ is a configuration/build manifest (`Cargo.toml`, `pyproject.toml`, `package.json`, `go.mod`), it receives strong attenuation:
   $$\gamma(p, s, q) = 0.05 \quad \text{if } p \in \text{Manifests}$$
2. **Test-Predecessor Attenuation (Implementation Queries)**: If query $q$ is an implementation/bug-fixing query (not seeking tests) and $p$ is a test file while $s$ is an implementation file:
   $$\gamma(p, s, q) = 0.15 \quad \text{if } p \in \text{Tests} \land s \notin \text{Tests} \land \neg \text{IsTestQuery}(q)$$
3. **Test-Predecessor Enhancement (Test-Seeking Queries)**: If query $q$ explicitly seeks test cases (`code2test` or mentions `test`, `assert`, `spec`):
   $$\gamma(p, s, q) = 1.25 \quad \text{if } p \in \text{Tests} \land \text{IsTestQuery}(q)$$
4. **Default Code-to-Code Edges**: $\gamma(p, s, q) = 1.00$.

Backward boost under `EXP-386`:
$$\text{Boost}_{\text{bwd}}^{(386)}(p) = \max_{s \in \text{succ}(p) \cap S} \left( \text{Hits}(s) \cdot \frac{0.20}{\sqrt{\max(1, \text{out\_degree}(p))}} \cdot \gamma(p, s, q) \right)$$

##### Variant C: Degree-Aware Leapfrog Margin Dampening (`EXP-387`)
To prevent any predecessor from leapfrogging the seed purely through structural boost:
$$\text{Margin}(s, p) = \max(0.0, \text{Base}(s) - \text{Base}(p))$$
$$\text{Boost}_{\text{raw}}(s, p) = \text{Hits}(s) \cdot \frac{0.20}{\sqrt{\max(1, \text{out\_degree}(p))}}$$
$$\text{Boost}_{\text{bwd}}^{(387)}(p) = \max_{s \in \text{succ}(p) \cap S} \min\left( \text{Boost}_{\text{raw}}(s, p), \text{Margin}(s, p) \right)$$
*Invariant*: $\text{Base}(p) + \text{Boost}_{\text{bwd}}(p) \le \text{Base}(s)$. A structural caller cannot jump ahead of its seed file unless it independently possessed higher base relevance.

##### Variant D: Combined Query-Conditioned Architecture (`EXP-388`)
Combines edge-type gating, affinity scaling, and margin dampening:
$$\text{Boost}_{\text{bwd}}^{(388)}(p) = \max_{s \in \text{succ}(p) \cap S} \min\left( \text{Boost}_{\text{raw}}(s, p) \cdot \text{Scale}_{\text{aff}}(p) \cdot \gamma(p, s, q), \text{Margin}(s, p) \right)$$

---

### 3. Final Combined Score Integration
For all candidates:
$$\text{FinalScore}(d) = \text{Base}(d) + 0.15 \cdot \max(\text{Boost}_{\text{fwd}}(d), \text{Boost}_{\text{bwd}}(d))$$

Ranking is produced by descending sort: $\text{Rank}(d) = \text{argsort}(-\text{FinalScore}(d))$.
Context packing maps ranked file paths to underlying chunk tokens up to the 8,000-token budget.

