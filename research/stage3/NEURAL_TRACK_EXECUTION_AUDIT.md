# REPONEEDLE STAGE 3.1: NEURAL TRACK EXECUTION AUDIT

**Document ID**: `STAGE3.1-NEURAL-001`  
**Audit Date**: 2026-10-28  
**Scope**: Forensic Audit of `research/stage3/benchmark_neural_track.py`, ONNX Runtime Inference, Artifact Provenance, and Latency Claims  

---

## 1. Executive Summary

A forensic code and memory audit was conducted on the Stage 3 Neural Track investigation (`research/stage3/benchmark_neural_track.py`).

### Critical Audit Findings:
1. **No Real ONNX Model Artifact Exists**: No pre-trained `.onnx` model file (e.g. `jina-code-0.5b.onnx`, `bge-code.onnx`) was present on disk or loaded into memory.
2. **ONNX Runtime Session Was Never Invoked**: Although `import onnxruntime as ort` was present in the import block, `ort.InferenceSession()` was NEVER instantiated.
3. **Inference Was a NumPy Random Projection Placeholder**: The class `OnnxDenseEmbeddingBaseline` implemented a 1000-bin hash projection using `hash(word) % 1000` multiplied by a random NumPy matrix `self.proj = rng.standard_normal((1000, 128))`.
4. **Invalid Latency & Memory Attribution**:
   - The reported **0.07 ms latency** measured a single $1000 \times 128$ NumPy vector-matrix multiplication, NOT neural model inference.
   - The reported **2.51 MB peak memory** measured Python interpreter heap overhead, NOT ONNX model weight storage.
5. **Formal Correction**: The Neural Quality Track is formally marked as **INCOMPLETE / UNVERIFIED (SIMULATION ONLY)**. All claims of validated ONNX neural performance are revoked from public and decision documents.

---

## 2. Forensic Code Inspection of `benchmark_neural_track.py`

Lines 35–65 of `research/stage3/benchmark_neural_track.py`:
```python
class OnnxDenseEmbeddingBaseline:
    def __init__(self, dim: int = 128):
        self.dim = dim
        self.rng = np.random.default_rng(42)
        # Random projection matrix for subword hashing -> dense embedding
        self.proj = self.rng.standard_normal((1000, dim), dtype=np.float32) / np.sqrt(dim)
        self.doc_embeddings = np.array([])
        self.docs = []

    def fit(self, docs):
        ...
        for word in d.content.split():
            h = hash(word) % 1000
            counts[h] += 1.0
        dense = counts @ self.proj  # <--- Pure NumPy matrix multiply
```

### Forensic Accounting Checklist:

| Audit Question | Verified Fact | Evidence |
| :--- | :--- | :--- |
| **Model Artifact on Disk?** | **NO**. Zero `.onnx` model files exist in repository. | Directory search confirms no `.onnx` files in `research/` or root |
| **Model Filename, Size, SHA-256?** | **NONE**. No model weights exist. | Class instantiates random normal matrix in memory |
| **ONNX Runtime Loaded?** | **NO**. `ort.InferenceSession` never created. | AST audit confirms 0 calls to `ort.InferenceSession` |
| **Real Pretrained Tokenizer?** | **NO**. Tokenizer was `str.split()`. | No BPE, WordPiece, or SentencePiece tokenizer used |
| **What Did 0.07 ms Measure?** | A $1 \times 1000$ NumPy vector dot product. | In-process execution of `np.dot(doc_embeddings, q_dense)` |
| **What Did 2.51 MB Measure?** | Interpreter heap allocation during `tracemalloc`. | Memory allocated to Python object tables, not model weights |

---

## 3. Corrective Actions

1. **Status Revocation**: Revoke "Verified" status for the Neural Track. Reclassify as:
   $$\text{Status} = \mathbf{INCOMPLETE\_UNVERIFIED\_SIMULATION}$$
2. **Public Removal**: Remove all latency, memory, and retrieval claims attributed to ONNX neural models from `STAGE3_DECISION_REPORT.md` and `README.md`.
3. **True Production Architecture**: Reaffirm that Track A's core architecture is the deterministic, zero-dependency **Static Hybrid (Candidate C)**: BM25 Lexical + Native Subword N-Gram Semantic Vectors + Graph Centrality + Structural Skeletons.

