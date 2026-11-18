"""
Engine integration of the persistent index cache: the cached ``from_directory()`` build and ``refresh()``.

A build:
1. verifies and loads the current published generation (one read snapshot; ``store.load_generation``);
2. scans the repository with the unchanged discovery code. For each file it computes the SHA-256 of the decoded
   text; when the manifest entry for the path has the same digest and its document-metadata artifact was produced
   by the current metadata fingerprint, the FileDoc is rebuilt from that verified metadata instead of re-extracted;
3. seeds the per-document caches of BM25, the semantic index, the abstainer and the function graph with verified
   artifacts, only where the artifact key recomputed from the CURRENT inputs (path, text digest, metadata digest,
   extractor fingerprint and the extractor's Stage 0 input signature) matches;
4. runs the existing ``RepoNeedleEngine._fit()``: every global structure is recomputed in full by the existing code;
5. writes artifacts for new or changed files, then publishes a complete generation (``store.CacheWriter``).

Nothing about files matching ``persist_exclude`` is written: no manifest row, artifact, path, digest or ordinal.
The engine's indexes never depend on whether persistence succeeded.
"""

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import pathspec

from reponeedle.core.function_graph import FunctionGraphEngine
from reponeedle.core.index_cache import codecs
from reponeedle.core.index_cache.connection import open_reader, open_writer
from reponeedle.core.index_cache.errors import CacheUnusable, IndexCacheError, PersistenceUnavailable
from reponeedle.core.index_cache.fingerprints import (discovery_fingerprint, extractor_fingerprints,
                                                      index_fingerprint, unsupported_configuration)
from reponeedle.core.index_cache.paths import locate, prepare_cache_dir, restrict_permissions
from reponeedle.core.index_cache.schema import KINDS, SCHEMA_VERSION, doc_meta_digest
from reponeedle.core.index_cache.store import (CacheWriter, LoadedGeneration, enforce_total_limit,
                                               load_generation, make_artifact_row, quarantine)
from reponeedle.core.signatures import stable_signature
from reponeedle.models import FileDoc, IndexCacheConfig, IndexUpdateReport

GLOBAL_STRUCTURES = {name: "recomputed in full" for name in (
    "bm25", "semantic", "repo_graph", "function_graph", "abstainer")}


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
        report = IndexUpdateReport(state="disabled", validation="content", global_structures=dict(GLOBAL_STRUCTURES))
        if validation == "stat":
            report.reason = "validation='stat' runs as 'content': Stage 1 reads every file, so digests are compared"

        unsupported = unsupported_configuration(engine)
        if unsupported:
            return self._uncached(engine, report, timer, "disabled", unsupported)
        try:
            prepare_cache_dir(self.location, create=not cfg.read_only)
        except PersistenceUnavailable as exc:
            return self._unavailable(engine, report, timer, exc.reason)

        fps_hex = extractor_fingerprints(engine)
        fps = {k: bytes.fromhex(v) for k, v in fps_hex.items()}
        loaded: Optional[LoadedGeneration] = None
        db = self.location.db_path
        if cfg.rebuild_policy == "always":
            report.rebuilt_from_scratch = True
        elif db.exists():
            try:
                conn = open_reader(db, cfg.busy_timeout_s, cfg.read_only)
                try:
                    loaded = load_generation(conn, self.location.repo_root, self.location.repo_id, fps, cfg.verify)
                finally:
                    conn.close()
            except PersistenceUnavailable as exc:
                return self._unavailable(engine, report, timer, exc.reason)
            except (CacheUnusable, Exception) as exc:  # noqa: BLE001 - any failure to read makes the cache unusable
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
                report.reason = f"unusable cache set aside as {moved} and rebuilt: {reason}"
                report.rebuilt_from_scratch = True
        elif cfg.rebuild_policy == "never":
            raise IndexCacheError("index cache missing and rebuild_policy='never'")
        timer.lap("load_ms")

        infos: Dict[str, _DocInfo] = {}
        self._hash_s = 0.0
        scan = self._scan(engine, loaded, fps, infos)
        timer.lap("scan_ms")
        timer.ms["of_which_hashing_ms"] = round(self._hash_s * 1000, 3)
        reused = self._seed(engine, loaded, fps, scan.docs, infos)
        timer.lap("seed_ms")
        self._fit(engine, scan)
        timer.lap("fit_ms")

        persisted_docs = [d for d in scan.docs if not infos[d.path].excluded]
        report.files_indexed = len(scan.docs)
        report.files_persist_excluded = len(scan.docs) - len(persisted_docs)
        report.files_reused = sum(1 for d in persisted_docs if all((d.path, k) in reused for k in KINDS))
        report.files_extracted = len(scan.docs) - report.files_reused
        self._diff(report, loaded, persisted_docs, infos)

        if cfg.read_only:
            report.state = "loaded_read_only" if loaded is not None else "not_persisted"
            if loaded is None:
                report.reason = report.reason or "read-only cache: nothing to load and nothing written"
            report.generation = loaded.gen_id if loaded else None
            report.artifacts_reused = len(reused)
            return self._finish(report, timer)

        self._persist(engine, report, scan, persisted_docs, infos, reused, fps, fps_hex, loaded, refresh)
        timer.lap("persist_ms")
        return self._finish(report, timer)

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
        }

    def _seed(self, engine, loaded, fps, docs, infos) -> Dict[Tuple[str, str], bytes]:
        """Seeds per-document caches with verified artifacts whose key matches the current inputs."""
        from reponeedle.core.index_cache.schema import artifact_key

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
                data = art.data
                if kind == "lexical":
                    cache[doc.path] = (sig, data[0], data[1])
                else:
                    cache[doc.path] = (sig, data)
                reused[(doc.path, kind)] = key
        return reused

    def _fit(self, engine, scan) -> None:
        """The existing fit, then the same scan diagnostics as an uncached from_directory()."""
        from reponeedle.engine import _finish_directory_engine

        # Mirrors the constructor (which fits only non-empty documents); an engine that already holds documents
        # (refresh) is refitted even when the scan is empty, so nothing from the previous state survives.
        if scan.docs or engine.docs:
            engine._fit(scan.docs)
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

    def _payload(self, engine, doc, kind, info) -> Tuple[bytes, bytes]:
        """(input_sig, payload) for one artifact, from the engine's caches after the fit."""
        if kind == "doc_meta":
            return _doc_meta_input_sig(doc.path, info.text_sha256), codecs.encode_doc_meta(info.meta)
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

    def _persist(self, engine, report, scan, persisted_docs, infos, reused, fps, fps_hex, loaded, refresh) -> None:
        cfg, loc = self.config, self.location
        try:
            try:
                conn = open_writer(loc.db_path, cfg.busy_timeout_s)
            except PersistenceUnavailable as exc:
                if not (exc.corrupt and cfg.rebuild_policy != "never"):
                    raise
                moved = quarantine(loc.db_path)   # not a usable database (e.g. rebuild_policy="always" skipped reading)
                report.reason = (report.reason + "; " if report.reason else "") +                     f"unusable database set aside as {moved}: {exc.reason}"
                conn = open_writer(loc.db_path, cfg.busy_timeout_s)
        except PersistenceUnavailable as exc:
            if cfg.rebuild_policy == "never":
                raise IndexCacheError(f"index cache cannot be written: {exc.reason}") from exc
            report.state = "not_persisted"
            report.reason = (report.reason + "; " if report.reason else "") + exc.reason
            return
        writer = CacheWriter(conn)
        gen_id = None
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
                    for kind in KINDS:
                        key = reused.get((doc.path, kind))
                        if key is not None:
                            file_fa.append((doc.path, kind, key))
                            rebuild[key] = (doc, kind)
                            continue
                        input_sig, payload = self._payload(engine, doc, kind, info)
                        row = make_artifact_row(kind, fps[kind], doc.path, info.text_sha256, info.doc_meta_sha256,
                                                input_sig, payload, gen_id)
                        file_rows.append(row)
                        file_fa.append((doc.path, kind, row[0]))
                except (UnicodeEncodeError, PersistenceUnavailable, codecs.CodecError):
                    skipped.append(doc.path)      # this file is indexed in memory but not persisted
                    continue
                rows += file_rows
                fa_rows += file_fa
                m = info.meta
                manifest_rows.append((doc.path, len(manifest_rows), info.text_sha256, m["language"],
                                      int(m["is_test"]), m["line_count"], m["token_count"], info.doc_meta_sha256))
            t0 = time.perf_counter()
            report.artifacts_written = writer.write_artifacts(rows)
            report.artifacts_reused = len(reused)
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
                input_sig, payload = self._payload(engine, doc, kind, info)
                return make_artifact_row(kind, fps[kind], doc.path, info.text_sha256, info.doc_meta_sha256,
                                         input_sig, payload, gen_id)

            meta = {"repo_root": loc.repo_root, "repo_id": loc.repo_id, "schema_version": str(SCHEMA_VERSION),
                    "created_by": _package_version(), "extractor_fps": json_dumps(fps_hex),
                    "index_fp": fingerprints["index"], "discovery_fp": fingerprints["discovery"],
                    "doc_meta_fp": fingerprints["doc_meta"]}
            excluded_rows = self._excluded_rows(scan)
            optional_rows = [("scip", "not configured"), ("structural_parser", "regex")]
            counters = {"files_reused": report.files_reused, "files_extracted": report.files_extracted,
                        "artifacts_written": report.artifacts_written, "global_structures": "recomputed in full"}
            t0 = time.perf_counter()
            writer.publish(gen_id, meta, manifest_rows, fa_rows, excluded_rows, optional_rows,
                           {"persisted_files": len(manifest_rows), "stage": 1, "kinds": list(KINDS)},
                           artifact_for, counters)
            report.timings_ms["publish_ms"] = round((time.perf_counter() - t0) * 1000, 3)
            report.generation, report.state = gen_id, "published"
            report.files_persisted = len(manifest_rows)
            if skipped:
                report.reason = (report.reason + "; " if report.reason else "") + \
                    f"{len(skipped)} file(s) could not be encoded and were not persisted"
            t0 = time.perf_counter()
            report.artifacts_collected = writer.collect_garbage()
            report.timings_ms["gc_ms"] = round((time.perf_counter() - t0) * 1000, 3)
            t0 = time.perf_counter()
            maintenance = writer.maintain()
            report.timings_ms["maintenance_ms"] = round((time.perf_counter() - t0) * 1000, 3)
            if maintenance["checkpoint_busy"]:
                report.reason = (report.reason + "; " if report.reason else "") + \
                    "WAL checkpoint postponed: another connection is reading"
            restrict_permissions(loc)
            removed = enforce_total_limit(loc.cache_dir, loc.db_path, cfg.max_total_bytes)
            if removed:
                report.reason = (report.reason + "; " if report.reason else "") + \
                    f"removed {len(removed)} other cache database(s) to respect max_total_bytes"
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
