"""
Differential index-equivalence harness (V2 Stage 0; design: docs/PERSISTENT_INDEXING_DESIGN.md, section 14).

Compares an engine whose indexes were produced by some lifecycle (a rebuild, ``remove_documents()``,
``update_documents()``, and later persistent or incremental loading) with a *fresh full build* over the same
documents, in the same order and with the same configuration.

What is compared:
- documents: order, content digests and every ``FileDoc`` field, plus ``IndexingDiagnostics``;
- BM25: configuration, arrays (bit-exact), term statistics, IDF and ordered postings;
- semantic: vocabulary with its order, IDF and the CSR matrix (``indptr``/``indices``/``data``, bit-exact);
- repository graph: nodes and edges with attributes in insertion order, every map, PageRank (bit-exact);
- function graph: functions, call sites, edges (all fields, in order), file-to-file edges, the NetworkX graph,
  callers/callees maps, module/package maps, Tree-sitter/SCIP diagnostics and SCIP relationships;
- abstainer: vocabulary and configuration;
- per-query BM25 and semantic score arrays (bit-exact);
- retrieval: every ranker x task type over the frozen query corpus, with full ranked lists, per-file scores
  and component scores, explanations, abstention diagnostics; plus the experimental-abstention path and
  anchored change-impact retrieval;
- CUD-Pack: selected files (order, tier, tokens, rendered content), total tokens and the rendered context, for
  budgets {512, 2000, 4000, 8192} x modes {compact, complete} x focus-span strategies {legacy, ast_blocks}.

Comparisons are exact. Ordered containers are compared in order (dicts by key order, then values). Sets are compared
as sets, because Python set iteration order is not part of any index's defined state. Floats and arrays are
compared by bit pattern. Nothing is sorted to make two results agree.

Index state is captured before any retrieval, because retrieval can insert keys into the function graph's
``defaultdict`` maps. The only fields excluded are wall-clock ones: ``execution_time_ms`` in results and keys ending in
``_ms`` in function-graph diagnostics (SCIP parse and ingest timings).
"""

import dataclasses
import hashlib
import json
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from reponeedle.core.packer import BudgetOptimizer
from reponeedle.models import BudgetConfig, TaskType

QUERIES_PATH = Path(__file__).resolve().parent / "fixtures" / "equivalence" / "queries_v1.json"
RANKERS = ("legacy", "bm25", "arm101", "cascade", "change_impact")
TASK_TYPES: Tuple[Optional[TaskType], ...] = (
    None, TaskType.CODE2TEST, TaskType.COMMENT2CONTEXT, TaskType.TRACE2CODE, TaskType.EDIT2RIPPLE,
    TaskType.SELECTIVE,
)
PACK_BUDGETS = (512, 2000, 4000, 8192)
PACK_MODES = ("compact", "complete")
FOCUS_SPAN_STRATEGIES = ("legacy", "ast_blocks")
ANCHOR_CANDIDATES = ("shop/pricing.py", "shop/cart.py", "web/src/format.ts", "legacy/utils.py")
MAX_MISMATCHES = 30


def load_queries() -> List[Dict[str, str]]:
    data = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    assert data["version"] == 1 and data["count"] == len(data["queries"])
    return data["queries"]


# ---------------------------------------------------------------------------------------------------------------
# Plain, comparable representations
# ---------------------------------------------------------------------------------------------------------------

def plain(obj: Any) -> Any:
    """Converts dataclasses, pydantic models and defaultdicts into plain containers without losing order."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        return plain(obj.model_dump())
    if isinstance(obj, (dict, defaultdict)):
        return {k: plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [plain(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(plain(v) for v in obj)
    if isinstance(obj, (set, frozenset)):
        return set(obj)
    return obj


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def capture_documents(engine) -> Dict[str, Any]:
    return {
        "order": [d.path for d in engine.docs],
        "path_to_doc_keys": list(engine.path_to_doc),
        "docs": [
            {"path": d.path, "content_sha256": _digest(d.content), "content_len": len(d.content),
             "token_count": d.token_count, "language": d.language, "symbols": list(d.symbols),
             "imports": list(d.imports), "is_test": d.is_test, "line_count": d.line_count,
             "metadata": plain(d.metadata)}
            for d in engine.docs
        ],
        "indexing_diagnostics": plain(engine.indexing_diagnostics),
    }


def capture_bm25(lex) -> Dict[str, Any]:
    return {
        "config": {"k1": lex.k1, "b": lex.b, "path_weight": lex.path_weight, "symbol_weight": lex.symbol_weight,
                   "body_weight": lex.body_weight, "decouple_symbols": lex.decouple_symbols},
        "num_docs": lex.num_docs,
        "docs": [d.path for d in lex.docs],
        "doc_paths": list(lex.doc_paths),
        "avg_doc_len": lex.avg_doc_len,
        "doc_lengths": np.array(lex.doc_lengths),
        "doc_len_norms": np.array(lex.doc_len_norms),
        "doc_term_freqs": [dict(d) for d in lex.doc_term_freqs],
        "doc_frequencies": dict(lex.doc_frequencies),
        "idf": dict(lex.idf),
        "inverted_index": {t: list(p) for t, p in lex.inverted_index.items()},
    }


def capture_semantic(sem) -> Dict[str, Any]:
    m = sem.doc_matrix
    return {
        "config": {"min_n": sem.min_n, "max_n": sem.max_n, "max_features": sem.max_features},
        "num_docs": sem.num_docs,
        "doc_paths": list(sem.doc_paths),
        "vocabulary": dict(sem.vocabulary),
        "idf": np.array(sem.idf),
        "matrix_format": m.format,
        "matrix_shape": tuple(m.shape),
        "indptr": np.array(m.indptr),
        "indices": np.array(m.indices),
        "data": np.array(m.data),
    }


def _graph(g) -> Dict[str, Any]:
    return {"nodes": [(n, plain(d)) for n, d in g.nodes(data=True)],
            "edges": [(u, v, plain(d)) for u, v, d in g.edges(data=True)],
            "graph_attrs": plain(g.graph)}


def capture_repo_graph(rg) -> Dict[str, Any]:
    return {
        "num_docs": rg.num_docs,
        "doc_paths": list(rg.doc_paths),
        "path_to_idx": dict(rg.path_to_idx),
        "graph": _graph(rg.graph),
        "module_to_path": dict(rg.module_to_path),
        "symbol_to_paths": plain(rg.symbol_to_paths),
        "package_to_files": plain(rg.package_to_files),
        "manifest_crates": dict(rg.manifest_crates),
        "crate_dependencies": plain(rg.crate_dependencies),
        "test_to_target_map": plain(rg.test_to_target_map),
        "target_to_test_map": plain(rg.target_to_test_map),
        "flags": {"enable_class_to_test": rg.enable_class_to_test,
                  "enable_degree_matched_control": rg.enable_degree_matched_control},
        "invocation_edges": plain(rg.invocation_edges),
        "prod_to_test_invocations": plain(rg.prod_to_test_invocations),
        "test_to_prod_invocations": plain(rg.test_to_prod_invocations),
        "degree_matched_prod_to_test": plain(rg.degree_matched_prod_to_test),
        "degree_matched_test_to_prod": plain(rg.degree_matched_test_to_prod),
        "unresolved_diagnostics": plain(rg.unresolved_diagnostics),
        "pagerank_scores": np.array(rg.pagerank_scores),
    }


def _without_timings(obj: Any) -> Any:
    """Drops wall-clock fields (keys ending in ``_ms``) from diagnostics; nothing else is excluded."""
    if isinstance(obj, dict):
        return {k: _without_timings(v) for k, v in obj.items() if not (isinstance(k, str) and k.endswith("_ms"))}
    if isinstance(obj, list):
        return [_without_timings(v) for v in obj]
    return obj


def capture_function_graph(fg) -> Dict[str, Any]:
    return {
        "config": {"enable_verified_calls": fg.enable_verified_calls,
                   "enable_structural_edges": fg.enable_structural_edges,
                   "min_confidence": fg.min_confidence, "structural_parser": fg.structural_parser},
        "doc_paths": list(fg.doc_paths),
        "path_to_idx": dict(fg.path_to_idx),
        "module_to_path": dict(fg.module_to_path),
        "package_to_files": plain(fg.package_to_files),
        "functions": plain(fg.functions),
        "call_sites": plain(fg.call_sites),
        "edges": plain(fg.edges),
        "file_to_file_edges": plain(fg.file_to_file_edges),
        "graph": _graph(fg.graph),
        "callers_map": plain(fg.callers_map),
        "callees_map": plain(fg.callees_map),
        "diagnostics": _without_timings(plain(fg.diagnostics)),
        "scip_relationships": plain(fg.scip_relationships),
    }


def capture_abstainer(ab) -> Dict[str, Any]:
    return {"confidence_threshold": ab.confidence_threshold, "repo_vocabulary": set(ab.repo_vocabulary)}


def capture_index_state(engine) -> Dict[str, Any]:
    return {
        "documents": capture_documents(engine),
        "bm25": capture_bm25(engine.lexical_index),
        "semantic": capture_semantic(engine.semantic_index),
        "repo_graph": capture_repo_graph(engine.repo_graph),
        "function_graph": capture_function_graph(engine.function_graph),
        "abstainer": capture_abstainer(engine.abstainer),
    }


def capture_scores(engine, queries: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    return {q["id"]: {"bm25": np.array(engine.lexical_index.score(q["text"])),
                      "semantic": np.array(engine.semantic_index.score(q["text"]))}
            for q in queries}


def _result(res) -> Dict[str, Any]:
    out = res.model_dump()  # already plain containers; wall-clock time is the only field excluded
    out.pop("execution_time_ms", None)
    return out


def capture_retrieval(engine, queries: Sequence[Dict[str, str]], rankers: Iterable[str] = RANKERS,
                      task_types: Iterable[Optional[TaskType]] = (None,)) -> Dict[str, Any]:
    rankers, task_types = tuple(rankers), tuple(task_types)
    out: Dict[str, Any] = {}
    for q in queries:
        for r in rankers:
            for t in task_types:
                res = engine.retrieve(q["text"], ranker=r, task_type=t)
                out[f"{q['id']}|{r}|{t.value if t else 'auto'}"] = _result(res)
    return out


def capture_abstention_and_anchors(engine, queries: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    present = [p for p in ANCHOR_CANDIDATES if p in engine.path_to_doc]
    for q in queries:
        out[f"{q['id']}|legacy|abstention"] = _result(
            engine.retrieve(q["text"], ranker="legacy", enable_experimental_abstention=True))
        if present:
            out[f"{q['id']}|change_impact|anchors"] = _result(
                engine.retrieve(q["text"], ranker="change_impact", anchor_files=present[:2]))
    return out


@contextmanager
def budget_config(engine, cfg: BudgetConfig):
    """Temporarily packs with ``cfg``: the engine reads its BudgetConfig only through these two attributes."""
    saved = engine.budget_config, engine.budget_optimizer
    engine.budget_config, engine.budget_optimizer = cfg, BudgetOptimizer(cfg)
    try:
        yield engine
    finally:
        engine.budget_config, engine.budget_optimizer = saved


def capture_packing(engine, queries: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for mode in PACK_MODES:
        for strategy in FOCUS_SPAN_STRATEGIES:
            cfg = engine.budget_config.model_copy(update={"mode": mode, "focus_span_strategy": strategy})
            with budget_config(engine, cfg):
                for budget in PACK_BUDGETS:
                    for q in queries:
                        res = engine.retrieve(q["text"], budget_tokens=budget, ranker="legacy")
                        out[f"{q['id']}|{mode}|{strategy}|{budget}"] = {
                            "selected_files": [
                                {"path": f.path, "tier": f.tier.value, "token_count": f.token_count,
                                 "rendered_content": f.rendered_content}
                                for f in res.selected_files],
                            "total_tokens": res.total_tokens,
                            "rendered_context": res.rendered_context,
                        }
    return out


# ---------------------------------------------------------------------------------------------------------------
# Exact comparison with located mismatches
# ---------------------------------------------------------------------------------------------------------------

def _fmt(v: Any, width: int = 160) -> str:
    if isinstance(v, float):
        return f"{v!r} ({v.hex()})"
    s = repr(v)
    return s if len(s) <= width else s[:width] + "..."


def diff(expected: Any, actual: Any, where: str, out: List[str], limit: int = MAX_MISMATCHES) -> None:
    """Appends a located description of every difference (up to ``limit``) between expected and actual."""
    if len(out) >= limit:
        return
    if type(expected) is not type(actual):
        out.append(f"{where}: type {type(expected).__name__} != {type(actual).__name__}: "
                   f"expected {_fmt(expected)}, actual {_fmt(actual)}")
        return
    if isinstance(expected, np.ndarray):
        if expected.dtype != actual.dtype or expected.shape != actual.shape:
            out.append(f"{where}: array dtype/shape {expected.dtype}{expected.shape} != {actual.dtype}{actual.shape}")
            return
        if expected.tobytes() != actual.tobytes():
            a, b = expected.ravel(), actual.ravel()
            width = a.dtype.itemsize
            av = np.frombuffer(a.tobytes(), dtype=np.uint8).reshape(-1, width) if a.size else a
            bv = np.frombuffer(b.tobytes(), dtype=np.uint8).reshape(-1, width) if b.size else b
            idx = np.nonzero((av != bv).any(axis=1))[0]
            first = int(idx[0])
            out.append(f"{where}: {len(idx)} of {a.size} elements differ bitwise; first at flat index {first}: "
                       f"expected {a[first]!r}, actual {b[first]!r}")
        return
    if isinstance(expected, float):
        if expected.hex() != actual.hex() and not (expected != expected and actual != actual):
            out.append(f"{where}: expected {_fmt(expected)}, actual {_fmt(actual)}")
        return
    if isinstance(expected, dict):
        ek, ak = list(expected), list(actual)
        if ek != ak:
            missing = [k for k in ek if k not in actual]
            extra = [k for k in ak if k not in expected]
            if missing or extra:
                out.append(f"{where}: keys missing {_fmt(missing)}, unexpected {_fmt(extra)}")
            else:
                pos = next(i for i, (x, y) in enumerate(zip(ek, ak)) if x != y)
                out.append(f"{where}: same keys in a different order; first difference at position {pos}: "
                           f"expected {_fmt(ek[pos])}, actual {_fmt(ak[pos])}")
        for k in ek:
            if k in actual:
                diff(expected[k], actual[k], f"{where}[{k!r}]", out, limit)
        return
    if isinstance(expected, (list, tuple)):
        if len(expected) != len(actual):
            out.append(f"{where}: length {len(expected)} != {len(actual)}")
        for i, (x, y) in enumerate(zip(expected, actual)):
            diff(x, y, f"{where}[{i}]", out, limit)
            if len(out) >= limit:
                return
        return
    if isinstance(expected, set):
        if expected != actual:
            missing = sorted(map(repr, expected - actual))[:10]
            extra = sorted(map(repr, actual - expected))[:10]
            out.append(f"{where}: set differs; missing {missing}, unexpected {extra}")
        return
    if expected != actual:
        out.append(f"{where}: expected {_fmt(expected)}, actual {_fmt(actual)}")


def compare_index_state(actual, reference) -> Dict[str, List[str]]:
    """Mismatches per component between two engines' index state (no retrieval is run)."""
    exp, act = capture_index_state(reference), capture_index_state(actual)
    result = {}
    for component in exp:
        found: List[str] = []
        diff(exp[component], act[component], component, found)
        result[component] = found
    return result


def capture_all(engine, *, queries: Optional[Sequence[Dict[str, str]]] = None, retrieval: bool = True,
                task_types: Iterable[Optional[TaskType]] = (None,), packing_queries: Optional[int] = 12
                ) -> Dict[str, Any]:
    """
    Everything the harness compares, as one plain structure (index state first, then retrieval stages). It can be
    pickled, so an engine built in another process (for example a warm restart from a persistent cache) can be
    captured there and compared here with ``compare_captures``.
    """
    queries = load_queries() if queries is None else list(queries)
    task_types = tuple(task_types)
    captured: Dict[str, Any] = dict(capture_index_state(engine))
    if retrieval:
        captured["scores"] = capture_scores(engine, queries)
        captured["retrieval"] = capture_retrieval(engine, queries, RANKERS, task_types)
        captured["abstention_and_anchors"] = capture_abstention_and_anchors(engine, queries)
        if packing_queries:
            captured["packing"] = capture_packing(engine, queries[::packing_queries])
    return captured


def compare_captures(actual: Dict[str, Any], reference: Dict[str, Any], *, label: str,
                     mutations: Sequence[str] = (), config: Optional[Dict[str, Any]] = None,
                     description: str = "") -> None:
    """Raises AssertionError listing every located mismatch between two ``capture_all`` results."""
    report: Dict[str, List[str]] = {}
    for component in reference:
        found: List[str] = []
        if component not in actual:
            found.append(f"{component}: missing from the actual capture")
        else:
            diff(reference[component], actual[component], component, found)
        report[component] = found
    extra = [c for c in actual if c not in reference]
    if extra:
        report["capture"] = [f"components only in the actual capture: {extra}"]
    failing = {k: v for k, v in report.items() if v}
    if failing:
        lines = [f"Index equivalence failed: {label}",
                 f"  configuration: {config or {}}",
                 f"  mutation sequence: {list(mutations) or '(none)'}"]
        if description:
            lines.append(f"  {description}")
        for component, items in failing.items():
            lines.append(f"  [{component}] {len(items)} mismatch(es)" + (" (truncated)" if len(items) >= MAX_MISMATCHES else ""))
            lines += [f"    - {m}" for m in items]
        raise AssertionError("\n".join(lines))


def assert_equivalent(actual, reference, *, label: str, mutations: Sequence[str] = (),
                      queries: Optional[Sequence[Dict[str, str]]] = None, retrieval: bool = True,
                      task_types: Iterable[Optional[TaskType]] = (None,), packing_queries: Optional[int] = 12,
                      config: Optional[Dict[str, Any]] = None) -> None:
    """
    Raises AssertionError listing every located mismatch between ``actual`` and the fresh ``reference``.

    ``queries`` defaults to the full frozen corpus. ``packing_queries`` takes every n-th query for the CUD-Pack
    matrix (None disables packing). Index state is always compared in full. Each engine's index state is captured
    before any retrieval runs on it.
    """
    queries = load_queries() if queries is None else list(queries)
    task_types = tuple(task_types)
    kwargs = dict(queries=queries, retrieval=retrieval, task_types=task_types, packing_queries=packing_queries)
    compare_captures(capture_all(actual, **kwargs), capture_all(reference, **kwargs), label=label,
                     mutations=mutations, config=config,
                     description=f"queries: {len(queries)}; task types: "
                                 f"{[t.value if t else 'auto' for t in task_types]}")
