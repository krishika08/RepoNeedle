# BASELINE SUITE SPECIFICATION: 12 RETRIEVAL FAMILIES

**Document ID**: `BSS-2026-001`  
**Version**: 1.0.0  
**Date**: 2026-10-28  
**Author**: Principal Retrieval Researcher & Lead Systems Engineer  

---

## 1. Overview of the 12 Baseline Families

To establish a comprehensive, unassailable empirical benchmark, RepoNeedle defines and evaluates 12 distinct retrieval baseline families spanning sparse, graph-based, dense neural, hybrid, two-stage reranked, and learned ranking architectures.

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                          12 Retrieval Baseline Families                            │
├───────────────────────────────────┬───────────────────────────────────────────────┤
│ Track A: Lightweight / CPU-Native │ Track B: High-Compute / Neural / Hybrid       │
├───────────────────────────────────┼───────────────────────────────────────────────┤
│ 1. Classical BM25 / Sparse        │ 5. General-Purpose Dense Embeddings           │
│ 2. Official Lexical (BM25+Subword)│ 6. Code-Specific Dense Embeddings             │
│ 3. RepoMap (PageRank Centrality)  │ 7. Official ARB Reference Embedding Models    │
│ 4. Subword TF-IDF / Character-Gram│ 8. Two-Stage Retrieve-and-Rerank (Cross-Enc)  │
│ 9. RepoNeedle Baseline v0.1.0     │ 10. Multi-Signal Hybrid with Learned Fusion   │
│ 11. Lightweight CPU Alternatives  │ 12. Maximum-Quality Neural Graph Architectures│
└───────────────────────────────────┴───────────────────────────────────────────────┘
```

---

## 2. Detailed Family Specifications

### Family 1: Classical BM25 (Sparse Term Frequency)
- **Model Identifier**: Standard Okapi BM25 ($k_1=1.5, b=0.75$).
- **Implementation**: `reponeedle.core.lexical.BM25Index` and official `agent_retrieval_bench.baseline.bm25`.
- **Tokenizer**: Standard regex code subword tokenizer (`regex_code_tokenizer_v1`).
- **Input Fields**: Full file content + relative file path tokens.
- **Hardware Profile**: Pure CPU, single-thread, ~1GB RAM peak.
- **Query Latency**: Mean: `994.4 ms`, Median: `1,158.3 ms`.
- **License**: MIT / Apache 2.0.
- **Strengths**: Strong on exact symbol matches and keyword-dense code queries.
- **Weaknesses**: Zero semantic generalization; vulnerable to vocabulary mismatch; blind to test linkages.

### Family 2: Official Lexical Baseline
- **Model Identifier**: ARB Official Lexical Ranker (`agent_retrieval_bench.baseline.lexical`).
- **Architecture**: Combined BM25 word scoring + character bigram / subword overlap scoring.
- **Tokenizer**: Custom multi-field code splitter.
- **Hardware Profile**: Pure CPU, single-thread.
- **Query Latency**: Mean: `884.1 ms`, Median: `1,005.2 ms`.
- **License**: MIT.
- **Performance Reference**: ARB v2 MRR: `0.1574`, Recall@20: `0.4940`.

### Family 3: RepoMap (Repository Graph Centrality)
- **Model Identifier**: Aider-style RepoMap PageRank Centrality (`agent_retrieval_bench.baseline.repomap`).
- **Architecture**: Directed reference graph of identifiers, functions, and imports; personalized PageRank with damping factor $d = 0.85$.
- **Tokenizer**: Regex tree-sitter symbol extractor.
- **Hardware Profile**: Pure CPU; memory scales with edge count ($O(V + E)$).
- **Query Latency**: Mean: `157.5 ms`, Median: `192.1 ms` (fast vector lookup).
- **License**: Apache 2.0.
- **Performance Reference**: ARB v2 MRR: `0.2140`, Recall@20: `0.6306` (leads on deep recall).
- **Weaknesses**: Cannot find leaf test nodes (0 in-degree); blind to specific query intent.

### Family 4: Subword TF-IDF / Character N-Gram Matching
- **Model Identifier**: `scikit-learn` TfidfVectorizer / FastText Character $n$-gram embeddings.
- **Vocabulary**: 3-to-6 character subword grams covering camelCase and snake_case fragments.
- **Hardware Profile**: Pure CPU, fast vector space cosine similarity.
- **Target Track**: Track A (Lightweight CPU candidate).
- **Query Latency**: Projected $< 50\text{ ms}$.

### Family 5: General-Purpose Dense Embeddings
- **Model Identifier**: `BAAI/bge-small-en-v1.5`, `BAAI/bge-base-en-v1.5`, `text-embedding-3-small`.
- **Architecture**: Transformer encoder producing 384/768-dimensional dense vectors.
- **Tokenizer**: WordPiece / cl100k BPE.
- **Inference Mode**: Local PyTorch CPU / CUDA inference or batch API.
- **Strengths**: Strong on natural language conceptual queries and documentation.
- **Weaknesses**: Suboptimal on precise identifier casing and syntax structures without fine-tuning.

### Family 6: Code-Specific Dense Embeddings
- **Model Identifier**: `jinaai/jina-embeddings-v2-base-code` (8k context), `Salesforce/SFR-Embedding-Code-400M_R`.
- **Architecture**: Code-pretrained transformer supporting long contexts (up to 8,192 tokens).
- **Hardware Profile**: 4GB–8GB VRAM GPU (or float32/int8 CPU inference with ONNX Runtime).
- **Strengths**: Trained on syntax trees and repository pull requests; handles cross-lingual code representations.

### Family 7: Official ARB Reference Embedding Baselines
- **Model Identifiers**:
  - `Qwen/Qwen3-Embedding-0.6B` / `4B` / `8B`
  - `perplexity/pplx-embed-v1-4b`
  - `jinaai/jina-code-0.5b`
- **Published Reference Performance on ARB v2 ($N=345$)**:
  - `Qwen3-Embedding-4B`: MRR `0.2379`, Recall@20 `0.6306`, BCY@8k `0.3409`
  - `Qwen3-Embedding-8B`: MRR `0.2336`, Recall@20 `0.7029`, BCY@8k `0.3732`
  - `pplx-embed-v1-4b`: MRR `0.2267`, Recall@20 `0.6072`, BCY@8k `0.3549`
  - `jina-code-0.5b`: MRR `0.1914`, Recall@20 `0.4823`, BCY@8k `0.2783`
- **Deployment Requirement**: Heavy GPU infrastructure (16GB–48GB VRAM) for 4B/8B models.

### Family 8: Two-Stage Retrieve-and-Rerank (Bi-Encoder + Cross-Encoder)
- **First Stage**: Fast candidate generator (top 50 files via BM25 + RepoNeedle graph).
- **Second Stage**: Cross-encoder reranker (e.g. `BAAI/bge-reranker-large`, `cross-encoder/ms-marco-MiniLM-L-6-v2`).
- **Mechanism**: Jointly tokenizes `[CLS] Query [SEP] Code [SEP]`, allowing full cross-attention between error messages and source lines.
- **Latency Target**: $200\text{ ms} - 800\text{ ms}$ on top 30 candidate files.

### Family 9: Current RepoNeedle Implementation (v0.1.0 Baseline)
- **Architecture**: Tri-signal scoring (BM25 + Subword-Semantic + AST Graph) with rule-based `WorkflowRouter` and greedy knapsack context packing.
- **Hardware Profile**: Commodity CPU native (NumPy/SciPy/NetworkX).
- **Audited Metrics**: ARB v2 MRR: `0.2287`, Recall@20: `0.4279`, BCY@4k: `0.2436`, BCY@8k: `0.3450`.
- **Query Latency**: Mean: `317.7 ms`, Median: `142.4 ms`.

### Family 10: Multi-Signal Hybrid with Learned Score Fusion
- **Architecture**: Combines lexical (BM25), structural (PageRank + inverted test graph), and dense semantic representations via a learned fusion model (RankSVM, LightGBM Ranker, or calibrated reciprocal rank fusion RRF).
- **Feature Set**: BM25 score, path depth, in-degree centrality, test-indicator, identifier match count, skeleton compressibility ratio.
- **Training Constraints**: Trained strictly on development splits with repository grouping.

### Family 11: Optimized Lightweight CPU Alternatives (Track A Candidates)
- **Candidates**:
  - `BM25 + Fast Personalized PageRank` (Graph diffusion without heavy parsing)
  - `Path-Penalized Inverted Index` (Explicit documentation filtering)
  - `Precomputed AST Test-Inversion Index`
- **Objective**: Maximize MRR and BCY@4k while keeping query latency under 100ms on single-core CPU.

### Family 12: Maximum-Quality Neural Graph Architectures (Track B Candidates)
- **Architecture**: Graph Neural Network (GNN) or Graph-Augmented Transformer operating over the code dependency graph combined with dense bi-encoder embeddings.
- **Objective**: Push upper bound on both MRR and Recall@20; evaluate against Qwen3-Embedding-8B.

