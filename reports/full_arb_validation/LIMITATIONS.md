# Limitations & Open Challenges

1. **CPU Native Scope**: RepoNeedle runs without GPUs. Deep neural checkpoints (Qwen3-Embedding-4B/8B) were not evaluated locally due to environment limits (absence of PyTorch/CUDA drivers).
2. **Repository Clustering Imbalance**: Gin and Tokio account for a significant share of positive samples. While repository-clustered bootstrap confirms significance, broader multi-language validation remains desirable.
3. **Span Gold**: RepoNeedle currently optimizes file-level retrieval. Span-level and block-level slicing remain active research topics.
