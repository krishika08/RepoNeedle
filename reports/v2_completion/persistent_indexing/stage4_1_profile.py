"""Stage 4.1 Phase A: per-step cost of semantic per-document representations, one variant per fresh process.

usage: python stage4_1_profile.py <code_root> <repo> <variant> <out.json>   (Windows: memory from process counters)
The code root is a checkout of the revision whose fit, codec and loader are measured (here 643fa22, Stage 4); the
variants are re-implemented in this file on top of it. Results: stage4_1_profile.json.
variants: plain (Stage 3 / 60fbfc0), intern (Stage 4 / c5d9d22), pool (private canonical dict),
          ids (integer ids in a per-index pool + vectorised first-seen fit), ids_bin (ids + a binary id payload: the
          upper bound of a persisted integer-id format; measured for decode cost only)
"""
import gc
import hashlib
import json
import sys
import time
import zlib

code_root, repo, variant, out = sys.argv[1:5]
sys.path.insert(0, code_root)
sys.path.insert(0, code_root + "/tests")

import ctypes  # noqa: E402
from ctypes import wintypes  # noqa: E402

import numpy as np  # noqa: E402

from reponeedle.core.index_cache import codecs  # noqa: E402
from reponeedle.core.semantic import SubwordSemanticIndex  # noqa: E402
from reponeedle.engine import _build_file_doc, _scan_repository  # noqa: E402
from reponeedle.models import AblationConfig  # noqa: E402


class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]


_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.GetCurrentProcess.restype = wintypes.HANDLE
_k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
_k32.K32GetProcessMemoryInfo.restype = wintypes.BOOL


def mem():
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    if not _k32.K32GetProcessMemoryInfo(_k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
        raise OSError(ctypes.get_last_error())
    return {"private_mb": round(c.PrivateUsage / 2 ** 20, 1), "ws_mb": round(c.WorkingSetSize / 2 ** 20, 1),
            "peak_ws_mb": round(c.PeakWorkingSetSize / 2 ** 20, 1)}


R = {"variant": variant}
T = {}


def repr_size(reps):
    """Deep bytes of the per-document representation: containers, each distinct key object once, the pool."""
    total, seen = 0, set()
    if variant.startswith("ids"):
        for ids, cnt in reps:
            total += sys.getsizeof(ids) + sys.getsizeof(cnt) + 64     # arrays own their buffers (+ tuple)
        total += sys.getsizeof(pool) + sys.getsizeof(pool.strings) + sum(sys.getsizeof(s) for s in pool.strings)
        return round(total / 2 ** 20, 1)
    for c in reps:
        total += sys.getsizeof(c)
        for k in c:
            if id(k) not in seen:
                seen.add(id(k))
                total += sys.getsizeof(k)
        total += sum(sys.getsizeof(v) for v in c.values() if v > 256)
    if variant == "pool":
        total += sys.getsizeof(canon)
    return round(total / 2 ** 20, 1)


def lap(name, t0):
    T[name] = round(time.perf_counter() - t0, 3)
    return time.perf_counter()


abl = AblationConfig()
docs = _scan_repository(repo, None, 10 ** 7, 10 * 1024 * 1024,
                        lambda rel, ext, content: _build_file_doc(rel, ext, content, abl)).docs
gc.collect()
R["mem_docs_loaded"] = mem()
sem = SubwordSemanticIndex()

# ---------------------------------------------------------------- representations
intern = sys.intern


class Pool(dict):
    """feature -> id; new features get the next id (only first occurrences reach __missing__)."""

    def __init__(self):
        super().__init__()
        self.strings = []

    def __missing__(self, f):
        i = self[f] = len(self.strings)
        self.strings.append(f)
        return i


pool = Pool()
canon = {}


def convert(counts):
    if variant == "plain":
        return counts
    if variant == "intern":
        return dict(zip(map(intern, counts), counts.values()))
    if variant == "pool":
        return dict(zip(map(canon.setdefault, counts, counts), counts.values()))
    n = len(counts)        # ids / ids_bin
    return (np.fromiter(map(pool.__getitem__, counts), dtype=np.int32, count=n),
            np.fromiter(counts.values(), dtype=np.int32, count=n))


# ---------------------------------------------------------------- 1. extraction + conversion
t = time.perf_counter()
raw = [sem._count_features(d) for d in docs]
t = lap("extract_s", t)
reps = [convert(c) for c in raw]
t = lap("convert_s", t)
R["pairs"] = sum(len(c) for c in raw)
R["intern_or_pool_calls_on_extraction"] = R["pairs"] if variant != "plain" else 0
del raw
gc.collect()
R["mem_after_extraction"] = mem()
R["retained_repr_mb_extraction"] = repr_size(reps)

# ---------------------------------------------------------------- 2. fit


def fit_dicts(reps):
    sem._doc_feature_cache = {d.path: (sem.doc_signature(d), c) for d, c in zip(docs, reps)}
    t0 = time.perf_counter()
    sem.fit(docs)
    return time.perf_counter() - t0, dict(sem.fit_stats)


def fit_ids(reps):
    """Exact first-seen-order fit over integer ids (prototype of the candidate algorithm)."""
    import math
    from scipy import sparse
    t0 = time.perf_counter()
    P = len(pool.strings)
    seen = np.zeros(P, dtype=bool)
    order_parts = []
    for ids, _ in reps:
        new = ids[~seen[ids]]
        seen[new] = True
        order_parts.append(new)
    first_seen = np.concatenate(order_parts) if order_parts else np.zeros(0, np.int32)
    all_ids = np.concatenate([r[0] for r in reps])
    all_counts = np.concatenate([r[1] for r in reps])
    lengths = np.fromiter((len(r[0]) for r in reps), dtype=np.int64, count=len(reps))
    df_pool = np.bincount(all_ids, minlength=P)
    n_features = len(first_seen)
    pool_len = np.fromiter(map(len, pool.strings), dtype=np.int64, count=P)
    df = df_pool[first_seen].astype(np.int64)
    feat_len = pool_len[first_seen]
    order = np.lexsort((np.arange(n_features, dtype=np.int64), -feat_len, -df))
    selected = order[: sem.max_features]
    sel_pids = first_seen[selected]
    strings = pool.strings
    vocabulary = {strings[p]: idx for idx, p in enumerate(sel_pids.tolist())}
    num = len(vocabulary)
    idf = np.zeros(num, dtype=np.float32)
    dfs = df[selected].tolist()
    N = len(docs)
    for idx in range(num):
        idf[idx] = math.log((1.0 + N) / (1.0 + dfs[idx])) + 1.0
    column_of = np.full(P, -1, dtype=np.int64)
    column_of[sel_pids] = np.arange(num, dtype=np.int64)
    cols = column_of[all_ids]
    keep = cols >= 0
    cols = cols[keep]
    rows = np.repeat(np.arange(N, dtype=np.int64), lengths)[keep]
    tf_counts = all_counts[keep].astype(np.int64)
    data, _, _ = SubwordSemanticIndex._matrix_values(tf_counts, cols, idf)
    mat = sparse.csr_matrix((data, (rows, cols)), shape=(N, num), dtype=np.float32)
    row_norms = sparse.linalg.norm(mat, axis=1)
    row_norms[row_norms == 0.0] = 1.0
    mat = mat.multiply(sparse.csr_matrix(1.0 / row_norms[:, np.newaxis])).tocsr()
    sem.vocabulary, sem.idf, sem.doc_matrix, sem.num_docs = vocabulary, idf, mat, N
    sem.doc_paths = [d.path for d in docs]
    sem._query_cache.clear()
    return time.perf_counter() - t0, {"distinct_features": n_features, "document_feature_pairs": int(len(all_ids))}


def fit(reps):
    return fit_ids(reps) if variant.startswith("ids") else fit_dicts(reps)


def digest():
    h = hashlib.sha256()
    h.update(json.dumps(list(sem.vocabulary.items())).encode())
    h.update(sem.idf.tobytes())
    m = sem.doc_matrix
    for a in (m.data, m.indices, m.indptr):
        h.update(np.ascontiguousarray(a).tobytes())
    h.update(str(m.dtype).encode() + str(m.indices.dtype).encode())
    return h.hexdigest()


s, st = fit(reps)
T["fit_s"] = round(s, 3)
R["fit_stats"] = {k: st.get(k) for k in ("distinct_features", "document_feature_pairs", "feature_collection_ms",
                                         "feature_counting_ms", "vocabulary_selection_ms", "matrix_assembly_ms",
                                         "normalisation_ms")}
R["digest_fit"] = digest()

# ---------------------------------------------------------------- 3. encode (existing semantic-counts-json/1)
t = time.perf_counter()
if variant.startswith("ids"):
    strings = pool.strings
    payloads = [codecs.encode_semantic(dict(zip(map(strings.__getitem__, ids.tolist()), cnt.tolist())))
                for ids, cnt in reps]
else:
    payloads = [codecs.encode_semantic(c) for c in reps]
t = lap("encode_s", t)
R["payload_mb"] = round(sum(map(len, payloads)) / 2 ** 20, 1)
if variant == "ids_bin":
    t = time.perf_counter()
    bin_payloads = [zlib.compress(ids.tobytes() + cnt.tobytes(), 1) for ids, cnt in reps]
    dict_payload = zlib.compress(json.dumps(pool.strings, ensure_ascii=False).encode(), 1)
    t = lap("encode_bin_s", t)
    R["bin_payload_mb"] = round((sum(map(len, bin_payloads)) + len(dict_payload)) / 2 ** 20, 1)

# ---------------------------------------------------------------- 4. warm restart: decode into a fresh process state
del reps
sem._doc_feature_cache = {}
sem.vocabulary = {}
sem.doc_matrix = None
gc.collect()
R["mem_before_decode"] = mem()
if variant.startswith("ids"):
    old = pool.strings
    pool = Pool()            # a restarted process has an empty pool (the old strings stay alive only via `old`)
    del old
    gc.collect()
t = time.perf_counter()
if variant == "ids_bin":
    strings = json.loads(zlib.decompress(dict_payload))
    pool = Pool()
    for f in strings:
        pool[f]
    decoded = []
    for b in bin_payloads:
        raw_b = zlib.decompress(b)
        half = len(raw_b) // 2
        decoded.append((np.frombuffer(raw_b[:half], dtype=np.int32), np.frombuffer(raw_b[half:], dtype=np.int32)))
else:
    decoded = [convert(codecs.decode_semantic(p)) for p in payloads]
t = lap("decode_convert_s", t)
if not variant.startswith("ids"):
    t = time.perf_counter()
    _ = [codecs.decode_semantic(p) for p in payloads[:2000]]
    T["decode_only_2000_s"] = round(time.perf_counter() - t, 3)
    del _
R["intern_or_pool_calls_on_decode"] = R["pairs"] if variant in ("intern", "pool", "ids") else 0
del payloads
gc.collect()
R["mem_after_decode"] = mem()
R["retained_repr_mb_decode"] = repr_size(decoded)

s, st = fit(decoded)
T["refit_after_decode_s"] = round(s, 3)
R["digest_refit"] = digest()
R["refit_stats"] = {k: st.get(k) for k in ("feature_collection_ms", "feature_counting_ms")}

# ---------------------------------------------------------------- 5. semantic scoring (warm-restart state)
from index_equivalence import load_queries  # noqa: E402

qs = [q["text"] for q in load_queries()[::9]]
lat = []
for rep in range(5):
    sem._query_cache.clear()
    for q in qs:
        t0 = time.perf_counter()
        sem.score(q)
        lat.append((time.perf_counter() - t0) * 1000)
lat.sort()
R["semantic_score_ms"] = {"n": len(lat), "median": round(lat[len(lat) // 2], 3),
                          "p90": round(lat[int(len(lat) * 0.9)], 3), "max": round(lat[-1], 3)}

# ---------------------------------------------------------------- 6. garbage collector
t = time.perf_counter()
gc.collect()
T["gc_collect_s"] = round(time.perf_counter() - t, 3)
R["gc_tracked_objects"] = len(gc.get_objects())
R["mem_end"] = mem()
R["timings_s"] = T
json.dump(R, open(out, "w"), indent=1)
print(json.dumps(R))
