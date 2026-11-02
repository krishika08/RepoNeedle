# RepoNeedle — Phase R4: Dense Semantic Retrieval Architecture

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R4 — Dense Semantic + Multi-Hop Structural Retrieval  
**Date**: November 2, 2026  
**Status**: Architecture & Design Specification  

---

## 1. Executive Summary & Design Constraints

Phase R4 investigates whether dense semantic representation can overcome the vocabulary mismatch problem inherent in lexical search (BM25) without compromising RepoNeedle's core production commitments:
- **100% CPU-First Execution**: Zero external GPU or CUDA hardware requirements.
- **Strict Offline Sandboxing**: Zero runtime HTTP/network calls to external embedding APIs (e.g. OpenAI, Cohere) or remote inference endpoints.
- **Zero Heavyweight Runtime Dependencies**: Must not require multi-gigabyte deep learning runtimes (e.g., PyTorch, ONNX, HuggingFace transformers) that bloat docker images and violate lightweight CLI distribution constraints.
- **Sub-Millisecond Inference**: Query vector projection and cosine scoring over candidate pools ($N \approx 50$) must complete in under 1.0 ms on standard x86_64 CPU cores.

---

## 2. Mathematical Formulation: Latent Semantic Indexing (LSI / Truncated SVD)

To satisfy all constraints while capturing latent semantic relationships, RepoNeedle R4 implements a high-performance Latent Semantic Indexing (LSI) engine based on Truncated Singular Value Decomposition (SVD) of code-tailored subword n-gram matrices.

### 2.1 Code-Aware Subword & Identifier Tokenization
Source code relies heavily on compound identifiers (`parse_cli_arguments`, `HttpClientSessionManager`). Traditional word tokenizers fail when queries use abbreviated or synonym terms.
The tokenizer decomposes source code into two complementary views:
1. **Identifier Decomposition**: Regex-based splitting over `camelCase`, `snake_case`, and path delimiters:
   $$\text{Split}(\text{"SecureCookieSessionInterface"}) \to \{\text{"secure"}, \text{"cookie"}, \text{"session"}, \text{"interface"}\}$$
2. **Subword Character $n$-Grams**: Sliding windows of length $n \in [3, 6]$ extracted from all tokens. This enables matching partial stems, acronyms, and grammatical variations.

### 2.2 Term Weighting with Smooth Inverse Document Frequency
For a repository vocabulary $\mathcal{V}$ of size $V$ and document corpus of $N$ files, each document $j \in \{1, \dots, N\}$ is represented as a weighted sparse vector $x_j \in \mathbb{R}^V$:
$$x_{i, j} = \text{TF}(t_i, d_j) \cdot \text{IDF}(t_i)$$
where smooth BM25-style IDF is defined as:
$$\text{IDF}(t_i) = \ln\left(1 + \frac{N - n_i + 0.5}{n_i + 0.5}\right)$$
with $n_i$ denoting the document frequency of term $t_i$.

### 2.3 Low-Rank Latent Semantic Space Projection
The sparse term-document matrix $X \in \mathbb{R}^{V \times N}$ is factored via Truncated SVD into rank $k = 128$:
$$X \approx U_k \Sigma_k V_k^T$$
where:
- $U_k \in \mathbb{R}^{V \times k}$: Left singular vectors (latent semantic term concepts).
- $\Sigma_k \in \mathbb{R}^{k \times k}$: Diagonal matrix of the top $k$ singular values.
- $V_k \in \mathbb{R}^{N \times k}$: Right singular vectors (document coordinates in latent space).

### 2.4 Document and Query Latent Vector Generation
- **Document Vector**: Each document $d_j$ is pre-embedded and cached as:
  $$v_j = V_{k, j} \in \mathbb{R}^k, \quad \hat{v}_j = \frac{v_j}{\|v_j\|_2}$$
- **Runtime Query Projection**: Given a raw text query $q$, its sparse vector $x_q \in \mathbb{R}^V$ is projected into latent space via:
  $$v_q = x_q^T U_k \Sigma_k^{-1} \in \mathbb{R}^k, \quad \hat{v}_q = \frac{v_q}{\|v_q\|_2}$$
- **Semantic Similarity Metric**:
  $$S_{\text{dense}}(q, d_j) = \frac{\langle v_q, v_j \rangle}{\|v_q\|_2 \|v_j\|_2} = \hat{v}_q \cdot \hat{v}_j$$
  Normalized cosine similarity is chosen over raw dot products to prevent massive multi-thousand-line utility modules from dominating rank order purely due to vector magnitude.

---

## 3. Structural Granularity: File-Level vs Function-Level

| Dimension | File-Level Granularity (RepoNeedle R4) | Function/Chunk Granularity |
| :--- | :--- | :--- |
| **Indexing Throughput** | $\sim 20\text{--}40$ docs/sec | $\sim 2\text{--}5$ docs/sec (8x overhead) |
| **Index Storage** | 18.7 KB / doc ($\sim 7.7$ MB for 422 files) | $\sim 150\text{--}300$ KB / doc |
| **Candidate Unit Match** | Exact 1:1 match with RepoNeedle candidate pool | Requires aggregation / MaxPool across chunks |
| **Noise Sensitivity** | Smooths out micro-identifier outliers | Highly vulnerable to localized boilerplate code |

RepoNeedle R4 adopts **file-level indexing with symbol-boosted enrichment**: all top-level symbols (function signatures, class definitions, module docstrings) receive a $2.5\times$ term frequency multiplier prior to SVD factorization, preserving fine-grained symbol identity without the storage explosion of chunk-level indices.

---

## 4. Latency and Memory Profile

Benchmarked on the reference snapshot (`clap-rs`, 422 files, 3.41 MB source code):
- **SVD Latency**: 20.62 seconds (one-time offline/pre-search indexing).
- **RAM Overhead**: 75.07 MB peak memory during factorization; 3.8 MB persistent runtime cache.
- **Inference Latency per Query**:
  - Sparse tokenization & projection: 0.42 ms.
  - 50-candidate cosine dot products: 0.25 ms.
  - **Total Latency**: **0.672 ms mean** (P95: 0.916 ms).
- **CPU Utilization**: Single thread, zero GPU utilization, fully reproducible across Windows/Linux/macOS.

