"""
Sizes of the per-file artifacts a persistent index would store, measured on the current extractors. Measurement only.

    python reports/v2_completion/persistent_indexing/artifact_size_estimate.py [--out artifact_sizes.json]

For each workload it builds the current indexes once, then reads the per-document caches the extractors already keep
(BM25 weighted term counts, semantic feature counts, abstainer vocabularies, function-graph functions/call sites) and
encodes them the way the design proposes:

* "json+zlib": canonical JSON of the artifact, zlib level 6 (a simple, inspectable baseline);
* "dict-coded": strings replaced by integer ids from a shared per-index string table (counted once), with the
  per-file payload as varint-packed (id, count) pairs, zlib level 6.

Figures are bytes of encoded payload (no SQLite page overhead); the 100,000-file projection scales the per-file mean
linearly and is an estimate, not a measurement.
"""

import argparse
import json
import statistics
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from profile_current import write_synthetic_repo  # noqa: E402
from reponeedle.engine import RepoNeedleEngine  # noqa: E402


def varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def measure(repo: str):
    engine = RepoNeedleEngine.from_directory(repo, max_files=10 ** 7)
    lex = engine.lexical_index._doc_term_cache
    sem = engine.semantic_index._doc_feature_cache
    abst = engine.abstainer._doc_vocab_cache
    fg = engine.function_graph._polyglot_cache
    strings = {}

    def sid(s):
        return strings.setdefault(s, len(strings))

    rows = {"lexical_terms": [], "semantic_features": [], "abstainer_vocab": [], "functions": [], "call_sites": []}
    sizes = {k: {"json_zlib": [], "dict_coded": []} for k in ("lexical", "semantic", "abstainer", "function_graph")}
    for doc in engine.docs:
        _, counts, _ = lex[doc.path]
        rows["lexical_terms"].append(len(counts))
        sizes["lexical"]["json_zlib"].append(len(zlib.compress(json.dumps(counts, sort_keys=False).encode(), 6)))
        sizes["lexical"]["dict_coded"].append(len(zlib.compress(b"".join(
            varint(sid(t)) + varint(int(round(v * 2))) for t, v in counts.items()), 6)))   # weights are multiples of 0.5

        feats = sem[doc.path][1]
        rows["semantic_features"].append(len(feats))
        sizes["semantic"]["json_zlib"].append(len(zlib.compress(json.dumps(feats).encode(), 6)))
        sizes["semantic"]["dict_coded"].append(len(zlib.compress(b"".join(
            varint(sid(f)) + varint(c) for f, c in feats.items()), 6)))

        vocab = sorted(abst[doc.path][1])
        rows["abstainer_vocab"].append(len(vocab))
        sizes["abstainer"]["json_zlib"].append(len(zlib.compress(json.dumps(vocab).encode(), 6)))
        sizes["abstainer"]["dict_coded"].append(len(zlib.compress(b"".join(varint(sid(t)) for t in vocab), 6)))

        funcs, calls, syms, imps = fg[doc.path][1]
        rows["functions"].append(len(funcs))
        rows["call_sites"].append(len(calls))
        payload = {"functions": [[f.name, f.parent_class, f.is_method, f.is_test, f.start_line, f.arg_names]
                                 for f in funcs],
                   "calls": [[c.caller_func, c.callee_name, c.is_attribute, c.qualifier, c.start_line]
                             for c in calls], "symbols": syms, "imports": imps}
        enc = zlib.compress(json.dumps(payload).encode(), 6)
        sizes["function_graph"]["json_zlib"].append(len(enc))
        sizes["function_graph"]["dict_coded"].append(len(enc))      # same encoding: small, string-heavy records

    string_table = sum(len(s.encode()) + 4 for s in strings)
    n = len(engine.docs)
    per_file = {k: {enc: round(statistics.mean(v), 1) for enc, v in d.items()} for k, d in sizes.items()}
    totals = {enc: sum(sum(d[enc]) for d in sizes.values()) for enc in ("json_zlib", "dict_coded")}
    return {
        "files": n, "source_bytes": sum(len(d.content.encode()) for d in engine.docs),
        "mean_per_file_counts": {k: round(statistics.mean(v), 1) for k, v in rows.items()},
        "unique_strings": len(strings), "string_table_bytes": string_table,
        "mean_encoded_bytes_per_file": per_file,
        "total_encoded_bytes": {**totals, "dict_coded_plus_string_table": totals["dict_coded"] + string_table},
        "projection_100k_files_bytes (linear, estimate)": {
            enc: int(totals[enc] / n * 100_000) for enc in ("json_zlib", "dict_coded")},
    }


def main():
    import shutil
    import tempfile
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    result = {"this repository": measure(str(ROOT))}
    tmp = Path(tempfile.mkdtemp(prefix="rn_sizes_"))
    try:
        write_synthetic_repo(tmp, 3000)
        result["synthetic 3000 files"] = measure(str(tmp))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps(result, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
