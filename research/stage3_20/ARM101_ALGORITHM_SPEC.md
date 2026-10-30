# RepoNeedle Stage 3.20 — ARM-101 Algorithm Specification

**Component:** `ARM-101-BASE` Retrieval Architecture  
**Target Architecture:** CPU-Native, Workflow-Adaptive Repository Context Retrieval Engine  
**Authoritative Reference:** [research/stage3_14/pilot_attenuation.py](file:///F:/RepoNeedle/research/stage3_14/pilot_attenuation.py) and [research/stage3_11/function_graph_engine.py](file:///F:/RepoNeedle/research/stage3_11/function_graph_engine.py)  

---

## 1. Algorithm Overview

`ARM-101` (Adaptive Ranking Mechanism 101) is a two-stage retrieval architecture:
1. **Stage 1 (Lexical-First Candidate Generation):** Full-repository Okapi BM25 scoring with deterministic tie-breaking.
2. **Stage 2 (Bounded Function Graph Propagation):** Graph-assisted expansion using top-$3$ BM25 seeds across Level-1 verified function-call edges, class-to-test links, and convention-based test discovery.
3. **Stage 3 (Soft Lexical Damping Guard):** Rank #1 protection governed by parameter $\tau = 0.25$ against lexical confidence margin.

---

## 2. Mathematical Formulation & Step-by-Step Dataflow

### Step 1: Base Lexical & Semantic Scoring
Given query $q$ and repository documents $\mathcal{D} = \{d_1, d_2, \dots, d_N\}$:
- Compute Okapi BM25 score vector:
  $$S_{\text{lex}}(d) = \sum_{t \in q \cap d} \text{IDF}(t) \cdot \frac{f(t, d) \cdot (k_1 + 1)}{f(t, d) + k_1 \cdot \left(1 - b + b \cdot \frac{|d|}{\text{avgdl}}\right)}$$
  with $k_1 = 1.5, b = 0.75$.
- Compute subword semantic score vector: $S_{\text{sem}}(d) \in [0, 1]$.
- Deterministic BM25 sort order with path tie-breaking:
  $$\pi_{\text{BM25}} = \text{argsort}\Big(\big(-S_{\text{lex}}(d_i), \text{path}(d_i)\big)\Big)$$

### Step 2: Seed Selection
Select the top-$3$ lexical documents as diffusion seeds:
$$\mathcal{S} = \big\{\pi_{\text{BM25}}[0], \pi_{\text{BM25}}[1], \pi_{\text{BM25}}[2]\big\}$$
If $S_{\text{lex}}(s) \le 0$, seed $s$ is skipped.

### Step 3: Graph Construction & Edge Admissibility
The function call graph $\mathcal{G}_{\text{fn}} = (\mathcal{V}, \mathcal{E})$ admits directed edges $u \to v$ representing caller file $u$ and callee file $v$.
Edges are categorized and admitted based on confidence $c(e)$:
1. `intra_file_call` ($c = 1.0$): Call within the same file.
2. `verified_call` ($c = 0.90\text{--}1.0$): Explicit module import or unique class method match.
3. `unique_global_call` ($c = 0.90$): Function name defined in exactly one file in the entire repository.
4. `directory_local_call` ($c = 0.75$): Non-unique function defined in the same directory.
5. `structural_method_call` ($c = 0.70$): Unique non-generic method across classes.

**Allowed Edges for Propagation:**
$$\mathcal{E}_{\text{allowed}} = \{\text{'verified\_call'}, \text{'unique\_global\_call'}, \text{'intra\_file\_call'}\}$$
All edges must satisfy the **Package Compatibility Fence** ($\text{is\_pkg\_compat}(\text{dir}(u), \text{dir}(v))$) unless either file is a test file.

### Step 4: Degree-Normalized Graph Propagation
For each seed $s \in \mathcal{S}$ with seed score $S_{\text{lex}}(s)$:

1. **Forward Call Diffusion (Callees):**
   For each callee $v$ of $s$ with matching edge $e = (s, v) \in \mathcal{E}_{\text{allowed}}$:
   $$\text{norm}_{\text{fwd}} = \frac{1}{\sqrt{\text{deg}_{\text{out}}(s) \cdot \text{deg}_{\text{in}}(v)}}$$
   $$\text{boost}_{\text{fwd}}(v) = S_{\text{lex}}(s) \cdot w_{\text{fwd}} \cdot c(e) \cdot \text{norm}_{\text{fwd}} \cdot w_{\text{hub}}(v)$$
   where $w_{\text{fwd}} = 0.25$, and for ARM-101 unattenuated policy, $w_{\text{hub}}(v) = 1.0$.

2. **Reverse Call Diffusion (Callers):**
   For each caller $u$ of $s$ with matching edge $e = (u, s) \in \mathcal{E}_{\text{allowed}}$:
   $$\text{norm}_{\text{rev}} = \frac{1}{\sqrt{\text{deg}_{\text{in}}(s) \cdot \text{deg}_{\text{out}}(u)}}$$
   $$\text{boost}_{\text{rev}}(u) = S_{\text{lex}}(s) \cdot w_{\text{rev}} \cdot c(e) \cdot \text{norm}_{\text{rev}} \cdot w_{\text{hub}}(u)$$
   where $w_{\text{rev}} = 0.20$.

3. **Convention Test Discovery:**
   Companion test paths (e.g. `test_{stem}.py`, `{stem}_test.go`, `{stem}.test.ts`) receive:
   $$\text{boost}_{\text{test}}(d) = \max\Big(\text{boost}_{\text{test}}(d), S_{\text{lex}}(s) \cdot 0.35\Big)$$

Total graph boost:
$$B_{\text{graph}}(d) = \max\Big(\text{boost}_{\text{fwd}}(d), \text{boost}_{\text{rev}}(d), \text{boost}_{\text{test}}(d), \text{boost}_{\text{c2t}}(d)\Big)$$

### Step 5: Fused Scoring & Document Penalty
For each candidate $d \in \mathcal{D}$:
$$S_{\text{fused}}(d) = 0.60 \cdot S_{\text{lex}}(d) + 0.15 \cdot S_{\text{sem}}(d) + 0.25 \cdot B_{\text{graph}}(d)$$

If document $d$ matches documentation patterns (`/docs/`, `.md`, `.rst`, etc.):
$$S_{\text{fused}}(d) \leftarrow S_{\text{fused}}(d) \cdot 0.50$$

Sort candidates in descending order of fused score:
$$\pi_{\text{fused}} = \text{argsort}\Big(\big(-S_{\text{fused}}(d_i), \text{path}(d_i)\big)\Big)$$

### Step 6: Soft Lexical Damping ($\tau = 0.25$)

Let $s_1 = \pi_{\text{BM25}}[0]$ be the top lexical candidate, and $s_2 = \pi_{\text{BM25}}[1]$ be the second candidate.
Compute the **lexical confidence margin**:
$$\Delta_{\text{BM25}} = \max\Big(0.0, \, S_{\text{lex}}(s_1) - S_{\text{lex}}(s_2)\Big)$$

Compute the **Rank #1 Guard Threshold**:
$$\Theta_{\text{guard}} = \tau \cdot \Delta_{\text{BM25}} = 0.25 \cdot \Delta_{\text{BM25}}$$

Let $b^* = \pi_{\text{fused}}[0]$ be the top candidate under fused ranking:
$$\pi_{\text{final}} = \begin{cases}
\pi_{\text{fused}} & \text{if } b^* = s_1 \quad \text{or} \quad \big(S_{\text{fused}}(b^*) - S_{\text{fused}}(s_1) \ge \Theta_{\text{guard}}\big) \\
\big[s_1\big] \,\|\, \big(\pi_{\text{fused}} \setminus \{s_1\}\big) & \text{otherwise}
\end{cases}$$

> [!IMPORTANT]
> **Interpretation of $\tau = 0.25$:**
> $\tau$ is **not** an exponential decay or weight dampener. It is an **evidence margin hurdle**.
> A graph-promoted candidate can displace BM25's top candidate $s_1$ if and only if its fused score exceeds $s_1$ by at least $25\%$ of BM25's own confidence margin over the runner-up.
> When BM25 is highly confident ($\Delta_{\text{BM25}}$ is large), graph noise cannot dislodge $s_1$. When BM25 is uncertain ($\Delta_{\text{BM25}} \approx 0$), graph expansion freely promotes the best graph-connected file.

---

## 3. Interaction with Context Budget Packing

Ranking and context packing are strictly orthogonal:
1. `ARM-101` outputs the ordered sequence of ranked files: $\pi_{\text{final}} = [f_1, f_2, \dots, f_N]$.
2. The `BudgetOptimizer` greedily packs context chunks up to the token budget (e.g. 4,000 or 8,000 tokens) using the ordering defined by $\pi_{\text{final}}$.
3. Context yield metrics (e.g. Token BCY@8k) evaluate how much ground-truth code is packed within the token window.
