"""
Persistent index cache (V2 Stage 1). Opt-in via ``RepoNeedleEngine.from_directory(..., index_cache=IndexCacheConfig())``.

Per-file derived data is stored in a per-repository SQLite database (standard-library ``sqlite3``) and reused on
later starts for files whose decoded text and extraction inputs are unchanged. Every global structure is
recomputed by the existing index code, so results are identical to a build without a cache. Design:
docs/PERSISTENT_INDEXING_DESIGN.md.

Modules:
- ``paths``: repository identity, cache location, permissions, network-filesystem detection;
- ``fingerprints``: extractor, document-metadata, discovery and index fingerprints;
- ``codecs``: versioned, validated payload encodings (no pickle, no eval);
- ``schema``: DDL, artifact keys, checksums and the manifest digest;
- ``connection``: writer/reader connection lifecycle with verified settings;
- ``store``: verified loading of a published generation, and the writer protocol (batches, publish, GC);
- ``session``: the engine integration (cached build and ``refresh()``).
"""

from reponeedle.core.index_cache.errors import IndexCacheError

__all__ = ["IndexCacheError"]
