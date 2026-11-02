# RepoNeedle — Phase R4: Multi-Hop Structural Retrieval Architecture

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R4 — Dense Semantic + Multi-Hop Structural Retrieval  
**Date**: November 2, 2026  
**Status**: Architecture & Design Specification  

---

## 1. System Motivation & Architectural Foundations

In large-scale codebases, software entities rarely exist in isolation; they are deeply interconnected through static imports, interface implementations, and call graphs. While lexical matching identifies files that share surface vocabulary, multi-hop structural retrieval aims to uncover:
1. **Transitive Ripple Effects**: Files modified in response to an interface change that do not repeat the query keywords.
2. **Hidden Test-to-Implementation Linkages**: Test harnesses that test an implementation class without explicitly mentioning the class name in docstrings.
3. **Architectural Proximity**: Code components that reside within the immediate execution graph of the primary seed files.

RepoNeedle R4 leverages the existing lightweight `FunctionGraphEngine` to build an in-memory directed dependency graph over repository files.

---

## 2. Multi-Hop Graph Traversal Formulation

Let $G = (V, E, W)$ represent the directed repository dependency graph where:
- $V$: Set of repository files ($|V| \le 10,000$).
- $E \subseteq V \times V$: Directed dependency edges, where $(u, v) \in E$ denotes that module $u$ references, imports, or invokes an entity in module $v$.
- $W: E \to (0, 1]$: Edge confidence weight assigned by static analysis:
  - Direct function/method invocation: $w(e) = 1.0$
  - Explicit module import: $w(e) = 0.8$
  - Type annotation / class inheritance: $w(e) = 0.6$

### 2.1 Multi-Hop Path Activation with Distance Attenuation
Given a set of initial seed files $\mathcal{S} \subset V$ identified by the lexical front-end, structural activation propagates outwards via breadth-first search (BFS) up to max hop distance $H = 2$.

The raw structural proximity score for node $v \in V$ from seed $s \in \mathcal{S}$ along path $p = (s = v_0, v_1, \dots, v_k = v)$ of length $k \le H$ is:
$$\text{PathScore}(p) = \prod_{i=1}^k w(v_{i-1}, v_i) \cdot \gamma^k$$
where $\gamma = 0.5$ is the geometric hop attenuation factor.

For any target file $v$, its aggregated raw graph score across all simple paths from all active seeds is:
$$S_{\text{raw\_graph}}(v) = \sum_{s \in \mathcal{S}} \max_{p: s \rightsquigarrow v, \, |p| \le H} \text{PathScore}(p)$$

### 2.2 Cycle and Infinite Loop Prevention
To guarantee termination and prevent infinite loops in cyclic import topologies (common in Python package hierarchies), the BFS traversal maintains a strict `visited_nodes` set per path trajectory. Paths revisiting an already explored node are pruned immediately.

---

## 3. The Central Hub Problem & Hub Dampening

### 3.1 The Utility Sink Vulnerability
In any production software repository, utility modules (`utils.py`, `helpers.js`, `constants.py`, `errors.py`, `base.py`) exhibit disproportionately high in-degrees. Naive graph propagation causes utility files to accumulate activation from every single seed node. As a result, utility files consistently rise to Rank 1 across diverse queries, acting as catastrophic false-positive distractors.

### 3.2 Non-Linear Hub Dampening Formulation
To neutralize this pathology, RepoNeedle R4 applies a degree-penalized hub dampening multiplier to every node $v$:
$$\text{HubDamp}(v) = \begin{cases} 
1.0 & \text{if } \text{deg}(v) \le 10 \\
\frac{1.0}{\sqrt{\text{deg}(v)}} & \text{if } 10 < \text{deg}(v) \le 50 \\
\frac{1.0}{\text{deg}(v)} & \text{if } \text{deg}(v) > 50 
\end{cases}$$
where $\text{deg}(v) = \text{in\_deg}(v) + \text{out\_deg}(v)$.

The hub-calibrated structural score is:
$$S_{\text{graph}}(v) = S_{\text{raw\_graph}}(v) \cdot \text{HubDamp}(v)$$

---

## 4. Intent-Conditioned Traversal Routing

Static code graphs are directed, but query relevance demands direction-aware traversal depending on intent:

1. **Test Intent (`is_test_query == True`)**:
   - Primary traversal traverses **in-edges** ($u \to v$ where $u$ is a test file importing implementation $v$, or $v$ is a test file importing seed $s$).
   - Test files directly importing the candidate receive an additional $+0.25$ edge bonus.
2. **Implementation Intent (`is_test_query == False`)**:
   - Traversal follows standard **out-edges** and caller hierarchies.
   - Test files encountered during traversal are penalized by $0.1\times$ to avoid pulling test collateral into implementation targets.

---

## 5. Performance and Profiling

Benchmarked across 422 files in `clap-rs`:
- **Graph Construction Time**: 0.975 seconds (432.9 files/sec).
- **RAM Footprint**: 4.32 MB for full adjacency index.
- **2-Hop Traversal Latency per Query**:
  - **Mean Latency**: **0.016 ms** (16 microseconds).
  - **P95 Latency**: **0.017 ms**.
- **Conclusion**: Multi-hop structural retrieval introduces virtually zero computational overhead to the ranking pipeline, adding less than 20 microseconds per query.

