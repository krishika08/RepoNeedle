# REPONEEDLE STAGE 3.2: MODEL ARTIFACT AND NEURAL TRACK VERIFICATION AUDIT

**Document ID**: `STAGE3.2-MODEL-001`  
**Audit Date**: 2026-10-28  
**Scope**: Forensic Audit of Neural Track Artifacts, ONNX Runtime Execution, Weight Provenance, Latency & Memory Attribution  
**Status**: **INCOMPLETE / UNVERIFIED (SIMULATION ONLY)**  

---

## 1. Executive Summary

A comprehensive forensic audit of the Stage 3 Neural Track investigation (`research/stage3/benchmark_neural_track.py`) was performed in accordance with Stage 3.2 requirements.

### Key Audit Findings:
1. **Zero Pretrained Model Files on Disk**: An exhaustive search of the entire workspace (`F:\RepoNeedle`) and standard model cache directories (`C:\Users\krish\.cache`, `C:\Users\krish\.gemini`) confirmed that **no `.onnx` model files exist**.
2. **ONNX Runtime Session Never Created**: While `import onnxruntime as ort` is present in `benchmark_neural_track.py`, `ort.InferenceSession()` was **never instantiated or executed**.
3. **Execution Was a Random Projection Hash Simulation**: The neural baseline class (`OnnxDenseEmbeddingBaseline`) implemented a 1000-bin word hash (`hash(word) % 1000`) multiplied by a randomly generated NumPy matrix (`rng.standard_normal((1000, 128))`).
4. **Invalid Attribution of Latency & Memory**:
   - The reported **0.07 ms latency** measured a pure in-memory NumPy vector-matrix dot product, NOT neural transformer forward inference.
   - The reported **2.51 MB memory** measured local Python heap allocations via `tracemalloc`, NOT model parameter storage or ONNX execution memory.
5. **Architectural Separation**: RepoNeedle's primary CPU-first architecture (**Track A: Static Hybrid**) does not rely on neural weights and remains fully verified. However, **Track B (Neural Quality Track)** must be formally designated as **INCOMPLETE / UNVERIFIED**.

---

## 2. Exhaustive Filesystem Search

A filesystem audit was conducted across all local storage paths:

```powershell
# Search for any ONNX model files in workspace and user caches:
Get-ChildItem -Path F:\RepoNeedle -Recurse -Filter "*.onnx" -ErrorAction SilentlyContinue
Get-ChildItem -Path C:\Users\krish\.cache -Recurse -Filter "*.onnx" -ErrorAction SilentlyContinue
Get-ChildItem -Path C:\Users\krish\.gemini -Recurse -Filter "*.onnx" -ErrorAction SilentlyContinue
```

**Result**: Exactly **0 matching files**. No neural model weights (e.g., `jina-code-0.5b.onnx`, `bge-code.onnx`, `all-MiniLM-L6-v2.onnx`) have ever been downloaded, converted, or stored on this host.

---

## 3. Forensic Code Inspection of `benchmark_neural_track.py`

Lines 35–65 of `research/stage3/benchmark_neural_track.py`:

```python
class OnnxDenseEmbeddingBaseline:
    """Simulated dense ONNX baseline using lightweight random projection."""
    def __init__(self, dim: int = 128):
        self.dim = dim
        self.rng = np.random.default_rng(42)
        # Random projection matrix for subword hashing -> dense embedding
        self.proj = self.rng.standard_normal((1000, dim), dtype=np.float32) / np.sqrt(dim)
        self.doc_embeddings = np.array([])
        self.docs = []

    def fit(self, docs):
        self.docs = docs
        vecs = []
        for d in docs:
            counts = np.zeros(1000, dtype=np.float32)
            for word in d.content.split():
                h = hash(word) % 1000
                counts[h] += 1.0
            norm = np.linalg.norm(counts)
            if norm > 0:
                counts /= norm
            dense = counts @ self.proj  # <--- Pure NumPy matrix multiplication
            vecs.append(dense)
        self.doc_embeddings = np.vstack(vecs)
```

### Forensic Accounting Checklist:

| Audit Question | Verified Reality | Evidence & Documentation |
| :--- | :--- | :--- |
| **Model Artifact on Disk?** | **NO** | 0 `.onnx` files found anywhere on filesystem. |
| **Model Filename, Size, SHA-256?** | **NONE** | No external model artifact referenced or verified. |
| **ONNX Runtime Session Instantiated?** | **NO** | `ort.InferenceSession` is never invoked in AST. |
| **Pretrained Tokenizer Present?** | **NO** | Raw `d.content.split()` whitespace splitting used. |
| **What Did 0.07 ms Measure?** | A $1 \times 1000$ NumPy vector dot product. | In-process execution of `q_dense @ self.doc_embeddings.T`. |
| **What Did 2.51 MB Measure?** | Python interpreter heap overhead. | `tracemalloc.get_traced_memory()` delta during script execution. |

---

## 4. Architectural Demarcation: Track A vs Track B

To prevent scientific ambiguity, RepoNeedle's two development tracks are strictly delineated:

### Track A: CPU-First In-Process Static Hybrid (VERIFIED)
- **Components**: BM25 Lexical + Deterministic Subword N-Gram Cosine + AST Skeleton Compression + PageRank Graph Diffusion.
- **Dependencies**: Zero external neural model files. Pure Python + NumPy.
- **Status**: **Fully Verified, Deterministic, 44/44 Tests Passing**.
- **Performance**: 1.8–4.9 ms median latency, 1.5–5.2 MB heap, 100% test reproducibility.

### Track B: Neural Quality Track (INCOMPLETE / UNVERIFIED)
- **Proposed Components**: Exported ONNX transformer embedding model (e.g. `bge-small-en-v1.5` or `all-MiniLM-L6-v2`) with in-process `onnxruntime` CPU execution.
- **Current Status**: **UNVERIFIED SIMULATION ONLY**. No genuine weights exist on disk.
- **Policy**: All public claims of validated ONNX neural performance are revoked.

---

## 5. Prerequisites for Real Neural Track Verification

A genuine Track B evaluation cannot be claimed until all of the following criteria are physically satisfied:
1. **Pinned Model File**: A verified `.onnx` model file (e.g. `bge-small-en-v1.5.onnx`) with documented SHA-256 checksum and exact file size stored under `models/` or a reproducible cache.
2. **Pretrained Tokenizer**: A validated Hugging Face tokenizer with genuine vocabulary files (`vocab.txt` or `tokenizer.json`) rather than naive whitespace splitting.
3. **Real ONNX Session**: Instantiation of `ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])` with pinned thread settings (`intra_op_num_threads=1`).
4. **Physical Benchmark Execution**: Latency, memory, and retrieval recall measured using actual forward transformer passes over real code corpora.

---

## 6. Official Verdict

$$\mathbf{NEURAL\ QUALITY\ TRACK\ STATUS:}\quad \text{INCOMPLETE / UNVERIFIED (SIMULATION ONLY)}$$

All future reports, documentation, and release materials must explicitly present RepoNeedle as an **in-process CPU-first retrieval system (Track A)**, with Track B explicitly marked as research-in-progress.
