# RepoNeedle Stage 3.20 — Candidate F Invalidation Evidentiary Dossier

**Authoritative Classification:** **`FORMALLY_INVALIDATED`**  
**Audit Standard:** Independent Reproduction & Forensic Evidence Ledger  

---

## 1. Evidentiary Proof Pillars

The invalidation of Candidate F is established upon five independent evidentiary pillars:

### Pillar 1: Candidate Pool Corruption in Stage 3.5
- **Proof:** In `research/stage3_5/evaluate_graph_retrieval.py` and `reponeedle/core/graph.py`, `code2test` queries evaluated candidates exclusively against test files by enforcing `tests_only = True`.
- **Consequence:** In a real codebase, the retrieval engine must search the entire repository to discover tests without an oracle filtering out non-test files. When non-test files are included, Candidate F's MRR drops from 0.25+ to **0.0601**.

### Pillar 2: The Ripgrep String Bypass
- **Proof:** In Stage 3.5 commit `4f78cc3`, lines 145–152 of `reponeedle/core/graph.py` explicitly inspected document paths for string literals `"search.rs"`, `"standard.rs"`, and `"printer"` to artificially synthesize cross-crate edges for `BurntSushi/ripgrep`.
- **Consequence:** Removing these non-generalizable strings revealed that Candidate F could not solve cross-crate resolution generally.

### Pillar 3: PageRank Supernode Trapping
- **Proof:** Polyglot manifest parsing generated 27,125 cross-crate edges. High-degree crate entry points (`src/lib.rs`, `main.rs`, `index.ts`) acted as random-walk probability sinks.
- **Consequence:** During bidirectional diffusion, random walks accumulated on top-level root files rather than specific target functions.

### Pillar 4: Statistical Proof of Inferiority
- **Proof:** Paired two-sided Wilcoxon test between unconstrained Candidate F ($0.1351$ MRR) and decoupled BM25 ($0.1752$ MRR) yields:
  $$W = 19,852.5, \quad p = 0.00854$$
- **Consequence:** Candidate F is statistically significantly worse than basic lexical BM25 with $99.1\%$ confidence.

### Pillar 5: Failure on Full Caddy Corpus
- **Proof:** Stage 3.5 evaluated Caddy capped at 250 files. When the full 605-file Caddy corpus is loaded, Candidate F's MRR falls by $38\%$.

---

## 2. Invalidation Certification

Candidate F represents a failed research exploration that cannot be rescued or deployed. All claims that Candidate F achieved $0.2152$ MRR or outperformed RepoMap are permanently retracted and formally invalidated.
