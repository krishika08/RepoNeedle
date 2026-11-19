"""
Engine integration of the persistent index cache: the cached ``from_directory()`` build and ``refresh()``.

A build (V2 Stage 2):
1. takes a shared cache-use lease (``lease.CacheLease``) for as long as it uses the database, so size-limit eviction
   by another process can never delete it meanwhile;
2. verifies and loads the current published generation (one read snapshot; ``store.load_generation``), migrating
   an older minor schema in place first (writers only);
3. scans the repository with the unchanged discovery code. For each file it computes the SHA-256 of the decoded
   text; when the manifest entry for the path has the same digest and its document-metadata artifact was produced
   by the current metadata fingerprint, the FileDoc is rebuilt from that verified metadata instead of re-extracted;
4. seeds the per-document caches (BM25, semantic, abstainer, function-graph extraction, RepoGraph class-to-test
   facts) with verified artifacts, only where the artifact key recomputed from the CURRENT inputs matches;
5. assembles the indexes through ``engine._fit(docs, assembly=CachedAssembly(...))``: BM25 partially incrementally
   when the in-process index can be updated, the semantic index in full (Stage 3), both graphs with
   dependency-scoped re-resolution (only affected files are resolved; every other file's stored edges are replayed
   in discovery order; PageRank and the other global graph quantities are recomputed), the abstainer from reference
   counts. Every path leaves the indexes exactly as the existing fits would;
6. writes artifacts for new or changed files, then publishes a complete generation (``store.CacheWriter``), with
   file ids allocated in the publish transaction.

Nothing about files matching ``persist_exclude`` is written: no manifest row, file id, artifact, path, digest,
ordinal, provider or consumer key, resolved edge or reference count. While any such file is indexed, graph
contributions are neither reused nor persisted (their resolution can depend on the excluded file).
The engine's indexes never depend on whether persistence succeeded.
"""

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import pathspec

from reponeedle.core.function_graph import FunctionGraphEngine
from reponeedle.core.index_cache import codecs
from reponeedle.core.index_cache.connection import open_reader, open_writer
from reponeedle.core.index_cache.dependencies import (ContextDigests, GraphPlan, affected_files,
                                                      changed_provider_keys, consumer_index, resolution_input_sig)
from reponeedle.core.index_cache.errors import CacheUnusable, IndexCacheError, PersistenceUnavailable
from reponeedle.core.index_cache.fingerprints import (discovery_fingerprint, extractor_fingerprints,
                                                      index_fingerprint, unsupported_configuration)
from reponeedle.core.index_cache.incremental import (MODE_FALLBACK, MODE_FULL, MODE_INCREMENTAL,
                                                     abstainer_assemble, bm25_update)
from reponeedle.core.index_cache.lease import CacheLease
from reponeedle.core.index_cache.paths import locate, prepare_cache_dir, restrict_permissions
from reponeedle.core.index_cache.schema import (RESOLUTION_KINDS, SCHEMA_VERSION, STAGE1_KINDS, artifact_key,
                                                doc_meta_digest)
from reponeedle.core.index_cache.store import (CacheWriter, LoadedGeneration, enforce_total_limit,
                                               load_generation, make_artifact_row, quarantine)
from reponeedle.core.signatures import stable_signature
from reponeedle.models import FileDoc, IndexCacheConfig, IndexUpdateReport

PER_FILE_KINDS = STAGE1_KINDS + ("repo_graph_facts", "provides")
REFCOUNTS_STATE = "abstainer.refcounts/"     # + abstainer extractor fingerprint (hex)
REFCOUNTS_CODEC = "abstainer-refcounts-json/1"
GLOBAL_ONLY = {"semantic": MODE_FULL, "repo_graph.maps_and_replay": MODE_FULL, "repo_graph.test_links": MODE_FULL,
               "repo_graph.class_to_test": MODE_FULL, "repo_graph.degree_matched_control": MODE_FULL,
               "repo_graph.pagerank": MODE_FULL, "function_graph.maps_and_replay": MODE_FULL}


@dataclass
class _DocInfo:
    text_sha256: bytes
    excluded: bool
    meta: Dict[str, Any]
    doc_meta_sha256: bytes
    meta_reused: bool


def _text_digest(content: str) -> bytes:
    return hashlib.sha256(content.encode("utf-8", "surrogatepass")).digest()


def _doc_meta_input_sig(path: str, text_sha256: bytes) -> bytes:
    return bytes.fromhex(stable_signature("doc-meta-input/1", path, text_sha256.hex()))


class _Timer:
    def __init__(self):
        self.ms: Dict[str, float] = {}
        self._t = time.perf_counter()

    def lap(self, name: str) -> None:
        now = time.perf_counter()
        self.ms[name] = round((now - self._t) * 1000, 3)
        self._t = now


def build_cached_engine(cls, repo_dir: str, config: IndexCacheConfig, engine_kwargs: Dict[str, Any], max_files: int,
                        extra_ignore: Optional[List[str]], max_file_size_bytes: int):
    engine = cls(docs=None, **engine_kwargs)
    session = IndexCacheSession(repo_dir, config, max_files, extra_ignore, max_file_size_bytes)
    engine._index_cache_session = session
    session.build(engine, refresh=False)
    return engine


class CachedAssembly:
    """
    ``engine._fit(docs, assembly=...)`` for a cached build: the five index fits, in the existing order, through
    their incremental paths. Every path leaves the index exactly as its ``fit`` would (tests compare them).
    """

    def __init__(self, session: "IndexCacheSession", loaded: Optional[LoadedGeneration], infos: Dict[str, "_DocInfo"],
                 fps: Dict[str, bytes], fps_hex: Dict[str, str], reused: Dict[Tuple[str, str], bytes]):
        self.session = session
        self.loaded = loaded
        self.infos = infos
        self.fps = fps
        self.fps_hex = fps_hex
        self.reused = reused
        self.labels: Dict[str, str] = dict(GLOBAL_ONLY)
        self.fallbacks: Dict[str, str] = {}
        self.counters: Dict[str, Dict[str, Any]] = {}
        self.timings: Dict[str, float] = {}
        self.events: Dict[str, Dict[str, List[Tuple[str, str]]]] = {}
        self.plans: Dict[str, GraphPlan] = {}
        self.refcounts: Dict[str, int] = {}
        self.dependencies_enabled = False
        self.ran = False

    def _lap(self, name: str, t0: float) -> float:
        now = time.perf_counter()
        self.timings[name] = round((now - t0) * 1000, 3)
        return now

    def fit_all(self, engine, docs: List[FileDoc]) -> None:
        self.ran = True
        t = time.perf_counter()
        lex = engine.lexical_index
        allow = lex.num_docs > 0                  # an index from an earlier fit in this process (refresh)
        mode, counters = bm25_update(lex, docs, allow=allow)
        self.labels["bm25"] = mode
        if "reason" in counters:
            self.fallbacks["bm25"] = counters.pop("reason")
        self.counters["bm25"] = counters
        t = self._lap("bm25_ms", t)

        engine.semantic_index.fit(docs)
        self.counters["semantic"] = {"documents": len(docs), "reason": "vocabulary maintenance is Stage 3"}
        t = self._lap("semantic_ms", t)

        excluded = [d for d in docs if self.infos[d.path].excluded]
        self.dependencies_enabled = not excluded
        if excluded:
            reason = "persist_exclude matched indexed files; their contributions may affect other files' edges"
            for g in ("repo_graph.import_edges", "function_graph.call_resolution"):
                self.labels[g] = MODE_FALLBACK
                self.fallbacks[g] = reason
            # Provider events are per-file data: they are still derived (and persisted) for persisted files only.
            self._provider_events(engine, [d for d in docs if not self.infos[d.path].excluded])
            t = self._lap("provider_index_ms", t)
            engine.repo_graph.fit(docs)
            t = self._lap("repo_graph_ms", t)
            engine.function_graph.build_graph(docs)
            t = self._lap("function_graph_ms", t)
            self.counters["repo_graph"] = dict(engine.repo_graph.resolution_stats)
            self.counters["function_graph"] = dict(engine.function_graph.resolution_stats)
        else:
            self._provider_events(engine, docs)
            t = self._lap("provider_index_ms", t)
            self.plans["rg"] = self._plan(engine, docs, "rg", "rg_edges", lambda doc: b"")
            engine.repo_graph.fit(docs, reuse=self.plans["rg"], track=True)
            t = self._lap("repo_graph_ms", t)
            self.plans["fg"] = self._plan(engine, docs, "fg", "fg_edges",
                                          lambda doc: bytes.fromhex(FunctionGraphEngine.polyglot_signature(doc)))
            engine.function_graph.build_graph(docs, reuse=self.plans["fg"], track=True)
            t = self._lap("function_graph_ms", t)
            for g, graph, label in (("rg", engine.repo_graph, "repo_graph"),
                                    ("fg", engine.function_graph, "function_graph")):
                plan = self.plans[g]
                c = dict(graph.resolution_stats)
                c.update(plan.stats)
                c["context_mismatches_outside_dependency_index"] = len(plan.context_mismatch)
                c["dependency_keys_evaluated"] = plan.digests.keys_evaluated if plan.digests else 0
                self.counters[label] = c

        persisted = {d.path for d in docs if not self.infos[d.path].excluded}
        previous, old_vocab = None, {}
        if self.loaded is not None:
            row = self.loaded.global_state.get(REFCOUNTS_STATE + self.fps_hex["abstainer"])
            if row is not None and row[0] == REFCOUNTS_CODEC:
                try:
                    previous = codecs.decode_refcounts(row[1])
                except codecs.CodecError:
                    previous = None
            old_vocab = {p: self.loaded.data(p, "abstainer") for p in self.loaded.manifest}
        unchanged = {p for p in persisted if (p, "abstainer") in self.reused}
        mode, self.refcounts, counters = abstainer_assemble(engine.abstainer, docs, persisted, previous, old_vocab,
                                                            unchanged)
        self.labels["abstainer"] = mode
        if mode != MODE_INCREMENTAL:
            self.fallbacks["abstainer"] = counters.pop("fallback", None) or (
                "no reference counts in the previous generation" if previous is None else
                "a previous vocabulary was not available")
        self.counters["abstainer"] = counters
        self._lap("abstainer_ms", t)

    # ---------------------------------------------------------------------------------- dependency-scoped graphs

    def provides_input_sig(self, doc: FileDoc) -> bytes:
        return bytes.fromhex(FunctionGraphEngine.polyglot_signature(doc))

    def _provider_events(self, engine, docs) -> None:
        """Current provider events per file: the verified stored ones when the artifact key matches, else derived."""
        loaded, derived = self.loaded, 0
        for doc in docs:
            info = self.infos[doc.path]
            entry = loaded.manifest.get(doc.path) if loaded is not None else None
            events = None
            if entry is not None and entry.text_sha256 == info.text_sha256:
                key = entry.artifacts.get("provides")
                data = loaded.data(doc.path, "provides")
                if data is not None and key == artifact_key("provides", self.fps["provides"], doc.path,
                                                            info.text_sha256, info.doc_meta_sha256,
                                                            self.provides_input_sig(doc)):
                    events = data
                    self.reused[(doc.path, "provides")] = key
            if events is None:
                events = {"fg": engine.function_graph.provides(doc), "rg": engine.repo_graph.provides(doc)}
                derived += 1
            self.events[doc.path] = events
        self.counters["provider_index"] = {"files_derived": derived, "files_reused": len(docs) - derived}

    def _plan(self, engine, docs, g: str, kind: str, own: Callable[[FileDoc], bytes]) -> GraphPlan:
        """Design section 9.1: affected = files whose own inputs changed + consumers of changed provider keys."""
        loaded, infos = self.loaded, self.infos
        stored: Dict[str, Tuple[bytes, Any]] = {}
        own_changed: Set[str] = set()
        docs_by_path = {d.path: d for d in docs}
        for doc in docs:
            info = infos[doc.path]
            entry = loaded.manifest.get(doc.path) if loaded is not None else None
            data = loaded.data(doc.path, kind) if entry is not None else None
            if (entry is None or data is None or entry.text_sha256 != info.text_sha256
                    or entry.doc_meta_sha256 != info.doc_meta_sha256):
                own_changed.add(doc.path)
                continue
            stored[doc.path] = (entry.artifacts[kind], data)

        def expected_key(path: str, context: bytes) -> bytes:
            info, doc = infos[path], docs_by_path[path]
            return artifact_key(kind, self.fps[kind], path, info.text_sha256, info.doc_meta_sha256,
                                resolution_input_sig(own(doc), context))

        label = {"rg": "repo_graph.import_edges", "fg": "function_graph.call_resolution"}[g]
        stats = {"files_own_changed": len(own_changed), "provider_keys_changed": 0, "files_affected": 0,
                 "files_affected_by_dependencies": 0}
        if loaded is None:
            affected = set(docs_by_path)
            self.labels[label] = MODE_FULL
            self.fallbacks[label] = "no previous generation"
        else:
            old_order = loaded.ordered_paths
            old_all = {p: loaded.data(p, "provides") for p in old_order}
            if any(e is None for e in old_all.values()) or not stored:
                affected = set(docs_by_path)
                self.labels[label] = MODE_FALLBACK
                self.fallbacks[label] = ("the previous generation has no provider index (for example a migrated "
                                         "Stage 1 cache, or a different extractor version)"
                                         if any(e is None for e in old_all.values()) else
                                         "the previous generation has no reusable resolutions")
            else:
                unchanged = {p for p in old_all if (p, "provides") in self.reused}
                changed, how = changed_provider_keys(
                    old_order, {p: e[g] for p, e in old_all.items()},
                    [d.path for d in docs], {d.path: self.events[d.path][g] for d in docs}, unchanged)
                if changed:
                    consumers = consumer_index({p: res.consumed for p, (_k, res) in stored.items()})
                    affected = affected_files(own_changed, changed, consumers)
                else:
                    affected = set(own_changed)
                stats["provider_keys_changed"] = len(changed)
                stats["files_affected_by_dependencies"] = len(affected - own_changed)
                stats.update(how)
                self.labels[label] = MODE_INCREMENTAL
        stats["files_affected"] = len(affected)
        plan = GraphPlan(g, stored, affected, expected_key)
        plan.stats = stats
        return plan

    def resolution_artifact(self, engine, doc: FileDoc, kind: str) -> Tuple[bytes, bytes]:
        """(input_sig, payload) of a file's resolution artifact, from the build's tracked resolution."""
        g = "fg" if kind == "fg_edges" else "rg"
        graph = engine.function_graph if g == "fg" else engine.repo_graph
        plan = self.plans[g]
        res = graph.file_resolutions[doc.path]
        if plan.digests is None:
            plan.digests = ContextDigests(graph.key_value)
        own = bytes.fromhex(FunctionGraphEngine.polyglot_signature(doc)) if g == "fg" else b""
        payload = codecs.encode_fg_resolution(res) if g == "fg" else codecs.encode_rg_resolution(res)
        return resolution_input_sig(own, plan.digests.context(res.consumed)), payload


class IndexCacheSession:
    def __init__(self, repo_dir: str, config: IndexCacheConfig, max_files: int, extra_ignore: Optional[List[str]],
                 max_file_size_bytes: int):
        self.repo_dir = repo_dir
        self.config = config
        self.max_files = max_files
        self.extra_ignore = extra_ignore
        self.max_file_size_bytes = max_file_size_bytes
        self.location = locate(repo_dir, config.cache_dir)
        self.exclude = pathspec.PathSpec.from_lines("gitwildmatch", config.persist_exclude) \
            if config.persist_exclude else None
        self.last_report: Optional[IndexUpdateReport] = None
        self.in_memory_modified = False

    # ------------------------------------------------------------------------------------------------ public API

    def note_in_memory_change(self) -> None:
        self.in_memory_modified = True

    def refresh(self, engine, validation: Optional[str]) -> IndexUpdateReport:
        return self.build(engine, refresh=True, validation=validation)

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "database": str(self.location.db_path),
            "repo_id": self.location.repo_id,
            "schema_version": SCHEMA_VERSION,
            "in_memory_changes_not_persisted": self.in_memory_modified,
            "last_update": self.last_report.model_dump() if self.last_report else None,
        }

    # ------------------------------------------------------------------------------------------------ the build

    def build(self, engine, refresh: bool, validation: Optional[str] = None) -> IndexUpdateReport:
        validation = validation or self.config.validation
        if validation not in ("content", "stat"):
            raise ValueError("validation must be 'content' or 'stat'")
        timer = _Timer()
        cfg = self.config
        report = IndexUpdateReport(state="disabled", validation="content")
        if validation == "stat":
            report.reason = "validation='stat' runs as 'content': every file is read, so digests are compared"

        unsupported = unsupported_configuration(engine)
        if unsupported:
            return self._uncached(engine, report, timer, "disabled", unsupported)
        try:
            prepare_cache_dir(self.location, create=not cfg.read_only)
        except PersistenceUnavailable as exc:
            return self._unavailable(engine, report, timer, exc.reason)

        lease = CacheLease(self.location.db_path)
        try:
            leased = lease.acquire_shared(cfg.busy_timeout_s, create=not cfg.read_only)
        except PersistenceUnavailable as exc:
            return self._unavailable(engine, report, timer, exc.reason)
        try:
            if not leased:
                if not self.location.db_path.exists():
                    # read-only and nothing to protect: no cache to read
                    return self._uncached(engine, report, timer, "not_persisted",
                                          "read-only cache: nothing to load and nothing written")
                report.reason = self._join(report.reason, "the cache-use lease file could not be created "
                                                          "(read-only directory); eviction is not coordinated")
            return self._build_leased(engine, refresh, report, timer)
        finally:
            lease.release()

    def _build_leased(self, engine, refresh: bool, report: IndexUpdateReport, timer: _Timer) -> IndexUpdateReport:
        cfg = self.config
        fps_hex = extractor_fingerprints(engine)
        fps = {k: bytes.fromhex(v) for k, v in fps_hex.items()}
        loaded = self._load(engine, report, timer, fps)
        if isinstance(loaded, IndexUpdateReport):
            return loaded
        timer.lap("load_ms")

        infos: Dict[str, _DocInfo] = {}
        self._hash_s = 0.0
        scan = self._scan(engine, loaded, fps, infos)
        timer.lap("scan_ms")
        timer.ms["of_which_hashing_ms"] = round(self._hash_s * 1000, 3)
        reused = self._seed(engine, loaded, fps, scan.docs, infos)
        timer.lap("seed_ms")
        assembly = CachedAssembly(self, loaded, infos, fps, fps_hex, reused)
        self._fit(engine, scan, assembly)
        timer.lap("fit_ms")
        for name, ms in assembly.timings.items():
            timer.ms[f"of_which_{name}"] = ms
        if assembly.dependencies_enabled and assembly.ran:
            for g, kind in (("fg", "fg_edges"), ("rg", "rg_edges")):
                for path in assembly.plans[g].reused:
                    reused[(path, kind)] = assembly.plans[g].stored[path][0]
        report.global_structures = assembly.labels if assembly.ran else {}
        report.fallbacks = assembly.fallbacks
        report.work_counters = assembly.counters

        persisted_docs = [d for d in scan.docs if not infos[d.path].excluded]
        report.files_indexed = len(scan.docs)
        report.files_persist_excluded = len(scan.docs) - len(persisted_docs)
        # Per-file EXTRACTION reuse (Stage 1 semantics); reuse of resolved graph contributions, which depends on
        # other files, is reported in work_counters.
        report.files_reused = sum(1 for d in persisted_docs if all((d.path, k) in reused for k in PER_FILE_KINDS))
        report.files_extracted = len(scan.docs) - report.files_reused
        self._diff(report, loaded, persisted_docs, infos)

        if cfg.read_only:
            report.state = "loaded_read_only" if loaded is not None else "not_persisted"
            if loaded is None:
                report.reason = report.reason or "read-only cache: nothing to load and nothing written"
            report.generation = loaded.gen_id if loaded else None
            report.artifacts_reused = len(reused)
            if loaded is not None and loaded.purge_pending:
                report.privacy_purge = "pending"
            return self._finish(report, timer)

        self._persist(engine, report, scan, persisted_docs, infos, reused, fps, fps_hex, loaded, assembly)
        timer.lap("persist_ms")
        return self._finish(report, timer)

    @staticmethod
    def _kinds(assembly: CachedAssembly) -> Tuple[str, ...]:
        return PER_FILE_KINDS + (RESOLUTION_KINDS if assembly.dependencies_enabled and assembly.ran else ())

    @staticmethod
    def _join(a: str, b: str) -> str:
        return f"{a}; {b}" if a else b

    def _load(self, engine, report, timer, fps):
        """The verified previous generation, None (cold build), or an IndexUpdateReport when the build is over."""
        cfg, db = self.config, self.location.db_path
        if cfg.rebuild_policy == "always":
            report.rebuilt_from_scratch = True
            return None
        if not db.exists():
            if cfg.rebuild_policy == "never":
                raise IndexCacheError("index cache missing and rebuild_policy='never'")
            return None
        migrated = False
        while True:
            try:
                conn = open_reader(db, cfg.busy_timeout_s, cfg.read_only)
                try:
                    return load_generation(conn, self.location.repo_root, self.location.repo_id, fps, cfg.verify)
                finally:
                    conn.close()
            except PersistenceUnavailable as exc:
                return self._unavailable(engine, report, timer, exc.reason)
            except (CacheUnusable, Exception) as exc:  # noqa: BLE001 - any failure to read makes the cache unusable
                if isinstance(exc, CacheUnusable) and exc.migratable and not migrated:
                    if cfg.read_only:
                        return self._uncached(engine, report, timer, "not_persisted",
                                              f"{exc.reason}: the cache needs an in-place schema migration, which "
                                              "read-only clients never perform")
                    try:
                        wconn = open_writer(db, cfg.busy_timeout_s)
                        try:
                            if wconn.migrated_from:
                                report.migrated_from_schema = wconn.migrated_from[0]
                        finally:
                            wconn.close()
                        migrated = True
                        continue
                    except PersistenceUnavailable as wexc:
                        return self._unavailable(engine, report, timer, wexc.reason)
                    except (CacheUnusable, Exception) as wexc:  # noqa: BLE001
                        exc = wexc
                reason = exc.reason if isinstance(exc, CacheUnusable) else f"{type(exc).__name__}: {exc}"
                if cfg.rebuild_policy == "never":
                    raise IndexCacheError(f"index cache unusable: {reason}") from exc
                if cfg.read_only:
                    return self._uncached(engine, report, timer, "not_persisted",
                                          f"cache unusable (read-only, not modified): {reason}")
                try:
                    moved = quarantine(db)
                except PersistenceUnavailable as qexc:
                    return self._uncached(engine, report, timer, "not_persisted", f"{reason}; {qexc.reason}")
                report.reason = self._join(report.reason, f"unusable cache set aside as {moved} and rebuilt: {reason}")
                report.rebuilt_from_scratch = True
                return None

    # ------------------------------------------------------------------------------------------------ helpers

    def _scan(self, engine, loaded, fps, infos):
        from reponeedle.engine import _build_file_doc, _scan_repository

        doc_meta_fp = fps["doc_meta"]

        def make_doc(rel_path: str, ext: str, content: str) -> FileDoc:
            t0 = time.perf_counter()
            text_sha = _text_digest(content)
            self._hash_s += time.perf_counter() - t0
            excluded = bool(self.exclude and self.exclude.match_file(rel_path))
            entry = loaded.manifest.get(rel_path) if (loaded is not None and not excluded) else None
            if entry is not None and entry.text_sha256 == text_sha:
                art = loaded.artifacts.get(entry.artifacts.get("doc_meta"))
                if art is not None and art.data is not None and art.extractor_fp == doc_meta_fp:
                    m = art.data
                    infos[rel_path] = _DocInfo(text_sha, False, m, entry.doc_meta_sha256, True)
                    return FileDoc(path=rel_path, content=content, token_count=m["token_count"],
                                   language=m["language"], symbols=list(m["symbols"]), imports=list(m["imports"]),
                                   is_test=m["is_test"], line_count=m["line_count"])
            doc = _build_file_doc(rel_path, ext, content, engine.ablation_config)
            meta = {"language": doc.language, "is_test": doc.is_test, "line_count": doc.line_count,
                    "token_count": doc.token_count, "symbols": list(doc.symbols), "imports": list(doc.imports)}
            infos[rel_path] = _DocInfo(text_sha, excluded, meta, doc_meta_digest(meta), False)
            return doc

        return _scan_repository(self.repo_dir, self.extra_ignore, self.max_files, self.max_file_size_bytes,
                                make_doc)

    @staticmethod
    def _caches(engine) -> Dict[str, Tuple[dict, Callable[[FileDoc], str]]]:
        return {
            "lexical": (engine.lexical_index._doc_term_cache, engine.lexical_index.doc_signature),
            "semantic": (engine.semantic_index._doc_feature_cache, engine.semantic_index.doc_signature),
            "abstainer": (engine.abstainer._doc_vocab_cache, engine.abstainer.doc_signature),
            "function_graph": (engine.function_graph._polyglot_cache, FunctionGraphEngine.polyglot_signature),
            "repo_graph_facts": (engine.repo_graph._doc_facts_cache, engine.repo_graph.facts_signature),
        }

    def _seed(self, engine, loaded, fps, docs, infos) -> Dict[Tuple[str, str], bytes]:
        """
        Seeds per-document caches with verified artifacts whose key matches the current inputs. An in-process cache
        entry that already has the current signature is kept as is (its object identity lets BM25 recognise
        unchanged documents without comparing their contents).
        """
        reused: Dict[Tuple[str, str], bytes] = {}
        if loaded is None:
            return reused
        caches = self._caches(engine)
        for doc in docs:
            info = infos[doc.path]
            entry = loaded.manifest.get(doc.path)
            if info.excluded or entry is None or entry.text_sha256 != info.text_sha256:
                continue
            if info.meta_reused:
                reused[(doc.path, "doc_meta")] = entry.artifacts["doc_meta"]
            # Keys use the CURRENT metadata digest: when re-extracted metadata is unchanged (for example after a
            # metadata-algorithm fingerprint change that did not alter the values), dependent artifacts stay valid.
            for kind, (cache, signature) in caches.items():
                key = entry.artifacts.get(kind)
                art = loaded.artifacts.get(key) if key else None
                if art is None or art.data is None:
                    continue
                sig = signature(doc)
                expected = artifact_key(kind, fps[kind], doc.path, info.text_sha256, info.doc_meta_sha256,
                                        bytes.fromhex(sig))
                if expected != key:
                    continue
                current = cache.get(doc.path)
                if current is None or current[0] != sig:
                    data = art.data
                    if kind == "lexical":
                        cache[doc.path] = (sig, data[0], data[1])
                    else:
                        cache[doc.path] = (sig, data)
                reused[(doc.path, kind)] = key
        return reused

    def _fit(self, engine, scan, assembly: Optional[CachedAssembly] = None) -> None:
        """The existing fit (through ``assembly`` when given), then the scan diagnostics of from_directory()."""
        from reponeedle.engine import _finish_directory_engine

        # Mirrors the constructor (which fits only non-empty documents); an engine that already holds documents
        # (refresh) is refitted even when the scan is empty, so nothing from the previous state survives.
        if scan.docs or engine.docs:
            engine._fit(scan.docs, assembly)
        _finish_directory_engine(engine, scan, self.max_file_size_bytes, self.max_files)

    def _diff(self, report, loaded, persisted_docs, infos) -> None:
        if loaded is None:
            return
        before = {p: e.text_sha256 for p, e in loaded.manifest.items()}
        now = {d.path: infos[d.path].text_sha256 for d in persisted_docs}
        added = [p for p in now if p not in before]
        deleted = [p for p in before if p not in now]
        report.modified = [p for p in now if p in before and before[p] != now[p]]
        by_digest: Dict[bytes, List[str]] = {}
        for p in deleted:
            by_digest.setdefault(before[p], []).append(p)
        renamed = []
        for p in list(added):
            candidates = by_digest.get(now[p])
            if candidates and len(candidates) == 1 and sum(1 for q in added if now[q] == now[p]) == 1:
                old = candidates.pop()
                renamed.append((old, p))
                added.remove(p)
                deleted.remove(old)
        report.added, report.deleted, report.renamed = added, deleted, renamed

    def _payload(self, engine, doc, kind, info, assembly: CachedAssembly) -> Tuple[bytes, bytes]:
        """(input_sig, payload) for one artifact, from the engine's state after the fit."""
        if kind == "doc_meta":
            return _doc_meta_input_sig(doc.path, info.text_sha256), codecs.encode_doc_meta(info.meta)
        if kind == "provides":
            return assembly.provides_input_sig(doc), codecs.encode_provides(assembly.events[doc.path])
        if kind in RESOLUTION_KINDS:
            return assembly.resolution_artifact(engine, doc, kind)
        cache, signature = self._caches(engine)[kind]
        sig = signature(doc)
        cached = cache.get(doc.path)
        if cached is None or cached[0] != sig:
            raise PersistenceUnavailable(f"{kind} extraction for a document is not available")
        if kind == "lexical":
            payload = codecs.encode_lexical(cached[1], cached[2])
        else:
            payload = codecs.ENCODERS[kind](cached[1])
        return bytes.fromhex(sig), payload

    def _persist(self, engine, report, scan, persisted_docs, infos, reused, fps, fps_hex, loaded,
                 assembly: CachedAssembly) -> None:
        cfg, loc = self.config, self.location
        try:
            try:
                conn = open_writer(loc.db_path, cfg.busy_timeout_s)
            except (PersistenceUnavailable, CacheUnusable) as exc:
                if not ((isinstance(exc, CacheUnusable) or exc.corrupt) and cfg.rebuild_policy != "never"):
                    raise PersistenceUnavailable(exc.reason) from exc
                moved = quarantine(loc.db_path)   # not a usable database (e.g. rebuild_policy="always" skipped reading)
                report.reason = self._join(report.reason, f"unusable database set aside as {moved}: {exc.reason}")
                conn = open_writer(loc.db_path, cfg.busy_timeout_s)
        except (PersistenceUnavailable, CacheUnusable) as exc:
            if cfg.rebuild_policy == "never":
                raise IndexCacheError(f"index cache cannot be written: {exc.reason}") from exc
            report.state = "not_persisted"
            report.reason = self._join(report.reason, exc.reason)
            return
        writer = CacheWriter(conn)
        gen_id = None
        kinds = self._kinds(assembly)
        try:
            fingerprints = {"index": index_fingerprint(engine, fps_hex),
                            "discovery": discovery_fingerprint(scan.ignore_patterns, self.max_files,
                                                               self.max_file_size_bytes),
                            "doc_meta": fps_hex["doc_meta"]}
            gen_id = writer.begin_generation("refresh" if loaded is not None else "cold", fingerprints)
            rows, manifest_rows, fa_rows, skipped = [], [], [], []
            rebuild: Dict[bytes, Tuple[FileDoc, str]] = {}
            for doc in persisted_docs:
                info = infos[doc.path]
                try:
                    file_rows, file_fa = [], []
                    for kind in kinds:
                        key = reused.get((doc.path, kind))
                        if key is not None:
                            file_fa.append((doc.path, kind, key))
                            rebuild[key] = (doc, kind)
                            continue
                        input_sig, payload = self._payload(engine, doc, kind, info, assembly)
                        row = make_artifact_row(kind, fps[kind], doc.path, info.text_sha256, info.doc_meta_sha256,
                                                input_sig, payload, gen_id)
                        file_rows.append(row)
                        file_fa.append((doc.path, kind, row[0]))
                except (UnicodeEncodeError, PersistenceUnavailable, codecs.CodecError, KeyError):
                    skipped.append(doc.path)      # this file is indexed in memory but not persisted
                    continue
                rows += file_rows
                fa_rows += file_fa
                m = info.meta
                manifest_rows.append((doc.path, len(manifest_rows), info.text_sha256, m["language"],
                                      int(m["is_test"]), m["line_count"], m["token_count"], info.doc_meta_sha256))
            if skipped and assembly.dependencies_enabled:
                # A file missing from the manifest would be missing from the next build's provider index: publish
                # no resolutions at all rather than a dependency index that does not describe the indexed files.
                fa_rows = [r for r in fa_rows if r[1] not in RESOLUTION_KINDS]
                rows = [r for r in rows if r[1] not in RESOLUTION_KINDS]
            t0 = time.perf_counter()
            report.artifacts_written = writer.write_artifacts(rows)
            report.artifacts_reused = sum(1 for r in fa_rows) - sum(1 for r in rows)
            report.timings_ms["write_artifacts_ms"] = round((time.perf_counter() - t0) * 1000, 3)
            if writer.database_bytes() > cfg.max_db_bytes:
                writer.abandon(gen_id)
                report.artifacts_collected = writer.collect_garbage()
                writer.maintain()
                report.state = "not_persisted"
                report.reason = (f"max_db_bytes={cfg.max_db_bytes} would be exceeded; the previous generation "
                                 "(if any) was kept and nothing new was published")
                return

            def artifact_for(key: bytes):
                if key not in rebuild:
                    return None
                doc, kind = rebuild[key]
                info = infos[doc.path]
                input_sig, payload = self._payload(engine, doc, kind, info, assembly)
                return make_artifact_row(kind, fps[kind], doc.path, info.text_sha256, info.doc_meta_sha256,
                                         input_sig, payload, gen_id)

            meta = {"repo_root": loc.repo_root, "repo_id": loc.repo_id, "schema_version": str(SCHEMA_VERSION),
                    "created_by": _package_version(), "extractor_fps": json_dumps(fps_hex),
                    "index_fp": fingerprints["index"], "discovery_fp": fingerprints["discovery"],
                    "doc_meta_fp": fingerprints["doc_meta"]}
            excluded_rows = self._excluded_rows(scan)
            optional_rows = [("scip", "not configured"), ("structural_parser", "regex")]
            global_rows = []
            if assembly.ran:
                global_rows.append((REFCOUNTS_STATE + fps_hex["abstainer"], REFCOUNTS_CODEC,
                                    codecs.encode_refcounts(assembly.refcounts)))
            purge_required = loaded is not None and (loaded.purge_pending or bool(
                self.exclude and any(self.exclude.match_file(p) for p in loaded.manifest)))
            counters = {"files_reused": report.files_reused, "files_extracted": report.files_extracted,
                        "artifacts_written": report.artifacts_written, "global_structures": report.global_structures,
                        "work": report.work_counters}
            t0 = time.perf_counter()
            published = writer.publish(gen_id, meta, manifest_rows, fa_rows, excluded_rows, optional_rows,
                                       {"persisted_files": len(manifest_rows), "stage": 2,
                                        "kinds": list(kinds)},
                                       artifact_for, counters, global_rows, purge_required)
            report.timings_ms["publish_ms"] = round((time.perf_counter() - t0) * 1000, 3)
            report.generation, report.state = gen_id, "published"
            report.files_persisted = len(manifest_rows)
            report.file_ids_assigned = published["file_ids_assigned"]
            report.file_ids_retired = published["file_ids_retired"]
            if skipped:
                report.reason = self._join(report.reason,
                                           f"{len(skipped)} file(s) could not be encoded and were not persisted")
            t0 = time.perf_counter()
            report.artifacts_collected = writer.collect_garbage()
            report.timings_ms["gc_ms"] = round((time.perf_counter() - t0) * 1000, 3)
            t0 = time.perf_counter()
            maintenance = writer.maintain()
            report.timings_ms["maintenance_ms"] = round((time.perf_counter() - t0) * 1000, 3)
            if maintenance["purge"] is not None:
                report.privacy_purge = maintenance["purge"]
            if maintenance["purge"] == "pending":
                report.reason = self._join(report.reason, (
                    "privacy purge pending: another connection holds an older read snapshot, so pages of files that "
                    "became persist_exclude'd may remain in the database file or WAL until a later refresh() "
                    "checkpoints them"))
            elif maintenance["checkpoint_busy"]:
                report.reason = self._join(report.reason, "WAL checkpoint postponed: another connection is reading")
            restrict_permissions(loc)
            eviction = enforce_total_limit(loc.cache_dir, loc.db_path, cfg.max_total_bytes)
            if eviction["removed"]:
                report.reason = self._join(report.reason, f"removed {len(eviction['removed'])} other cache "
                                                          "database(s) to respect max_total_bytes")
            if eviction["in_use"]:
                report.reason = self._join(report.reason, f"{len(eviction['in_use'])} other cache database(s) over "
                                                          "max_total_bytes were in use and were kept")
        except Exception as exc:  # noqa: BLE001 - persistence must never break the in-memory build
            if gen_id is not None:
                writer.abandon(gen_id)
            if cfg.rebuild_policy == "never":
                raise IndexCacheError(f"index cache could not be written: {type(exc).__name__}: {exc}") from exc
            report.state = "not_persisted"
            report.reason = f"writing the cache failed: {type(exc).__name__}: {exc}"
        finally:
            conn.close()

    def _excluded_rows(self, scan) -> List[Tuple[str, str]]:
        rows: Dict[str, str] = {}
        for reason, paths in (("skipped_large", scan.skipped_large), ("unreadable", scan.unreadable),
                              ("symlink_outside_repository", scan.outside_root),
                              ("directory_skipped", scan.skipped_dirs)):
            for p in paths:
                if not (self.exclude and self.exclude.match_file(p)):
                    rows.setdefault(p, reason)
        return sorted(rows.items())

    def _uncached(self, engine, report, timer, state, reason) -> IndexUpdateReport:
        """The original in-memory build, with no database access."""
        from reponeedle.engine import _build_file_doc, _scan_repository

        scan = _scan_repository(self.repo_dir, self.extra_ignore, self.max_files, self.max_file_size_bytes,
                                lambda rel, ext, content: _build_file_doc(rel, ext, content, engine.ablation_config))
        timer.lap("scan_ms")
        self._fit(engine, scan)
        timer.lap("fit_ms")
        report.state, report.reason = state, reason
        report.files_indexed = report.files_extracted = len(scan.docs)
        report.global_structures = {k: MODE_FULL for k in ("bm25", "semantic", "repo_graph", "function_graph",
                                                           "abstainer")}
        return self._finish(report, timer)

    def _unavailable(self, engine, report, timer, reason) -> IndexUpdateReport:
        if self.config.rebuild_policy == "never":
            raise IndexCacheError(f"index cache unavailable: {reason}")
        return self._uncached(engine, report, timer, "disabled", reason)

    def _finish(self, report, timer) -> IndexUpdateReport:
        phases = {k: v for k, v in timer.ms.items() if not k.startswith("of_which")}
        report.timings_ms = {**timer.ms, **report.timings_ms, "total_ms": round(sum(phases.values()), 3)}
        self.last_report = report
        self.in_memory_modified = False
        return report


def json_dumps(obj) -> str:
    import json

    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _package_version() -> str:
    from reponeedle import __version__

    return __version__
