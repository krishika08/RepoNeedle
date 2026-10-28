# Evaluation Methodology

1. **Frozen Benchmark Snapshots**: All 345 positive queries and 82 selective queries were evaluated on frozen base-commit snapshots from the official ARB release.
2. **Strict Information Boundary**: No future commit data, gold paths, or PR metadata was exposed to the index or query stages.
3. **Canonical Metrics**: Evaluated using the official ARB `sample_metrics` and `pack_files` implementations.
4. **Matched Sample IDs**: Paired comparisons were calculated strictly on identical sample IDs across all systems.
