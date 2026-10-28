# Failure Analysis & Error Taxonomy

- **Queries with Zero Gold Hit**: 0 / 345 (0.0%)
- **Queries Regressing against BM25**: 179 / 345
- **Queries Regressing against RepoMap**: 197 / 345

### Ranked Failure Taxonomy

1. **Symbol Vocabulary Mismatch (Lexical Deficiency)**: Queries where the issue description uses colloquial natural language ('endpoint crashes') while the gold implementation uses domain-specific identifiers without exact term overlap.
2. **Disconnected Leaf Node in Graph**: Regression test files that have zero inbound references in import graphs and cannot be reached via standard PageRank walks without inverted test mapping.
3. **Context Budget Saturation**: Repositories containing multi-thousand-line monolithic files where including full content crowds out supporting secondary modules.

### Representative Regression Cases

- **Sample ID**: `597f32e9b482833bed151a23` (code2test in `clap-rs/clap`)
  - Gold: `['tests/builder/help.rs']`
  - RepoNeedle MRR: `0.0021` | BM25 MRR: `0.5000` | RepoMap MRR: `0.5000`

- **Sample ID**: `30fded9a7b09048b5c8f39de` (edit2ripple in `clap-rs/clap`)
  - Gold: `['clap_mangen/Cargo.toml', 'clap_mangen/tests/testsuite/common.rs']`
  - RepoNeedle MRR: `0.0035` | BM25 MRR: `0.0122` | RepoMap MRR: `0.1667`

- **Sample ID**: `0c60e782db37a60abbcd178d` (code2test in `etcd-io/etcd`)
  - Gold: `['cache/demux_test.go', 'tests/integration/cache_test.go']`
  - RepoNeedle MRR: `0.0087` | BM25 MRR: `0.1111` | RepoMap MRR: `0.1250`

- **Sample ID**: `191c9a48dcea15ffd9b74793` (comment2context in `etcd-io/etcd`)
  - Gold: `['cache/demux_test.go', 'tests/integration/cache_test.go']`
  - RepoNeedle MRR: `0.0093` | BM25 MRR: `0.0400` | RepoMap MRR: `0.1000`

- **Sample ID**: `fa3c694a355ce304193a46e8` (comment2context in `etcd-io/etcd`)
  - Gold: `['cache/cache.go', 'cache/demux.go']`
  - RepoNeedle MRR: `0.0095` | BM25 MRR: `0.1667` | RepoMap MRR: `0.0526`

- **Sample ID**: `a9432b3d44a06f48f40060bb` (trace2code in `etcd-io/etcd`)
  - Gold: `['cache/cache.go', 'cache/demux.go']`
  - RepoNeedle MRR: `0.0526` | BM25 MRR: `0.0714` | RepoMap MRR: `0.0714`

- **Sample ID**: `120f8ebe03b4feba2ac74c51` (code2test in `etcd-io/etcd`)
  - Gold: `['tests/e2e/etcd_grpcproxy_test.go']`
  - RepoNeedle MRR: `0.0010` | BM25 MRR: `0.0189` | RepoMap MRR: `0.0455`

- **Sample ID**: `15959167576a87987d8f9f1f` (code2test in `etcd-io/etcd`)
  - Gold: `['cache/cache_test.go', 'cache/demux_test.go']`
  - RepoNeedle MRR: `0.0093` | BM25 MRR: `0.0175` | RepoMap MRR: `0.1667`

- **Sample ID**: `d5f1198f6fb5e19244fd4ac7` (comment2context in `etcd-io/etcd`)
  - Gold: `['server/etcdserver/txn/txn_test.go', 'server/storage/mvcc/index_test.go']`
  - RepoNeedle MRR: `0.1250` | BM25 MRR: `0.3333` | RepoMap MRR: `0.0667`

- **Sample ID**: `e1280404f66f39671f1939e5` (comment2context in `etcd-io/etcd`)
  - Gold: `['cache/cache_test.go', 'cache/demux_test.go']`
  - RepoNeedle MRR: `0.2000` | BM25 MRR: `0.3333` | RepoMap MRR: `0.5000`

