# Token Budget & Context Yield Analysis

### Canonical Budgeted Context Yield (BCY) Comparison

Evaluated across all 345 positive samples using canonical token counting (`regex_code_tokenizer_v1`):

| System | BCY@4k | BCY@8k | BCY@16k | BCY@32k |
| :--- | :---: | :---: | :---: | :---: |
| **RepoNeedle** | **0.2436** | **0.3450** | **0.4192** | **0.4279** |
| **RepoMap (Official)** | 0.2024 | 0.3788 | 0.5235 | 0.6166 |
| **Lexical (Official)** | 0.1488 | 0.2650 | 0.3886 | 0.4882 |
| **BM25 (Official)** | 0.1220 | 0.2051 | 0.3184 | 0.4365 |

### Payload Compression Verification
Structural skeletons reduce token usage by 52.8% to 90.4% across Python, Rust, TypeScript, and Go while preserving class headers, function signatures, and docstrings.
