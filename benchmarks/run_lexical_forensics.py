"""
Milestone 2C: lexical retrieval forensics and DEV-ONLY ablations. EXPERIMENTAL; not an official ARB score.

Data: the 15 Milestone 2B DEVELOPMENT repositories only (previously used development data). The 10
Milestone 2B held-out repositories are never loaded (asserted). No fresh confirmatory data exists
locally: every local ARB split uses the same 25 repositories.

Framework: Phase 1 product-aligned evaluation (whole-file input reconstructed from ARB chunks, file
unit, full ranking, score desc / path asc ties, file-level MRR and Recall@K).

Steps (each refuses to run out of order):
  register  -> protocol.json + sha256 (experiment matrix and selection rules), before any variant result
  lexical   -> stage 1: lexical-only rankings for every registered variant + forensic statistics
  stage1    -> applies the registered stage-1 rule; writes stage1_results.json and hybrid_candidates.json
  hybrid    -> stage 2: full RepoNeedle hybrid ranking with the candidate lexical variants swapped in
  stage2    -> applies the registered stage-2 rule; writes dev_selection.json

Production code is not modified by this script: variants are harness subclasses of BM25Index.
"""

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT_DIR / "reports" / "experimental" / "phase3_lexical_retrieval"
PHASE2_DIR = ROOT_DIR / "reports" / "experimental" / "phase2_documentation_filter"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT_DIR))

import run_arb_product_aligned_eval as P1  # noqa: E402
from reponeedle.core.lexical import BM25Index  # noqa: E402
from reponeedle.core.tokenizer import CodeTokenizer, WORD_REGEX, split_identifier  # noqa: E402

TASKS = ["comment2context", "code2test", "trace2code", "edit2ripple"]
METRICS = ["mrr", "recall@5", "recall@10", "recall@20"]

# Registered lexical variants: one factor changed relative to L0 (current production defaults).
VARIANTS = {
    "L0_baseline": {},
    "L1_path_weight_1.0": {"path_weight": 1.0},
    "L2_b_0.4": {"b": 0.4},
    "L3_b_0.9": {"b": 0.9},
    "L4_query_term_frequency": {"query_tf": True},
    "L5_no_duplicate_tokens": {"dedupe": True},
    "L6_json_values_only": {"json_values_only": True},
}
DIAGNOSTICS = {
    "D_path_field_only": {"body_weight": 0.0},
    "D_body_field_only": {"path_weight": 0.0},
}

PROTOCOL = {
    "milestone": "2C lexical retrieval forensics and dev-only optimisation (EXPERIMENTAL; not an official ARB score)",
    "data": "Milestone 2B DEVELOPMENT repositories only (previously used development data); 2B held-out repositories excluded",
    "phase2_split_sha256": None,  # filled at registration
    "framework": "Phase 1 product-aligned evaluation: whole-file input, file unit, full ranking",
    "variants": VARIANTS,
    "variant_semantics": {
        "path_weight / b": "existing BM25Index constructor parameters",
        "query_tf": "multiply each query term's BM25 contribution by its query count (ARB BM25 behaviour)",
        "dedupe": "emit each token at most once per source word (current tokenizer emits plain words twice: raw form and identical piece)",
        "json_values_only": "if the query parses as a JSON object, score only its leaf values (key names dropped); otherwise unchanged",
    },
    "diagnostics": DIAGNOSTICS,
    "stage1_rule": "Lexical-only, dev. A variant is a hybrid candidate if its dev mean (variant - L0) comment2context Recall@20 is > 0 "
                   "and its dev mean for MRR and Recall@20 of every task is >= -0.02. At most the 3 candidates with the largest "
                   "comment2context Recall@20 gain go to stage 2, plus 'C_combined' = all candidates applied together when >= 2 qualify.",
    "stage2_rule": "Full hybrid, dev. Select the arm with the largest dev mean comment2context Recall@20 gain over the hybrid baseline "
                   "among arms whose dev mean MRR and Recall@20 for every task (and comment2context MRR) is >= -0.02. The selection is "
                   "'dev-supported' only if its repository-clustered 95% CI for comment2context Recall@20 excludes zero (positive). "
                   "If no arm is dev-supported, no default change is made; any implementation stays opt-in.",
    "bootstrap": {"type": "paired, repository-clustered percentile", "resamples": P1.BOOT_N, "seed": P1.BOOT_SEED},
    "confirmatory_requirement": "Fresh repositories disjoint from all 25 ARB v2 repositories, independently labelled, covering all four "
                                "tasks, split at repository level with a recorded hash, protocol registered before treatment results. "
                                "If unavailable: no confirmatory claim (INCONCLUSIVE).",
}


def canonical_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Variant lexical index (harness only)
# ---------------------------------------------------------------------------

class DedupeTokenizer(CodeTokenizer):
    """Same tokens as CodeTokenizer, but each token at most once per source word."""

    def tokenize_text(self, text, include_raw_identifiers=True):
        if not text:
            return []
        out = []
        for word in WORD_REGEX.findall(text):
            seen = set()
            lw = word.lower()
            if include_raw_identifiers and lw not in self.stop_words:
                out.append(lw)
                seen.add(lw)
            for p in split_identifier(word):
                if p not in self.stop_words and len(p) > 1 and p not in seen:
                    out.append(p)
                    seen.add(p)
        return out


def json_leaf_text(query: str) -> str:
    try:
        obj = json.loads(query)
    except (ValueError, TypeError):
        return query
    if not isinstance(obj, dict):
        return query
    leaves = []

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif x is not None:
            leaves.append(str(x))
    walk(obj)
    return "\n".join(leaves)


class VariantBM25(BM25Index):
    def __init__(self, query_tf=False, dedupe=False, json_values_only=False, **kw):
        super().__init__(**kw)
        self.query_tf, self.json_values_only = query_tf, json_values_only
        if dedupe:
            self.tokenizer = DedupeTokenizer()

    def score(self, query):
        if self.json_values_only:
            query = json_leaf_text(query)
        if not self.query_tf:
            return super().score(query)
        if self.num_docs == 0:
            return np.array([], dtype=np.float32)
        q_tokens = self.tokenizer.tokenize_text(query)
        scores = np.zeros(self.num_docs, dtype=np.float32)
        counts = Counter(q_tokens)
        k1p = self.k1 + 1.0
        for term, q_cnt in counts.items():
            idf = self.idf.get(term, 0.0)
            if idf <= 0.0:
                continue
            for doc_idx, tf in self.inverted_index.get(term, []):
                scores[doc_idx] += q_cnt * idf * (tf * k1p) / (tf + self.doc_len_norms[doc_idx])
        m = float(scores.max()) if len(scores) else 0.0
        return scores / m if m > 0 else scores


    def fit_tokens(self, docs, tokens):
        """Exact replica of BM25Index.fit using pre-computed (path_tokens, symbol_tokens, body_tokens) per doc.
        Equality with fit() is asserted at runtime on every snapshot."""
        self.docs, self.num_docs, self.doc_paths = docs, len(docs), [d.path for d in docs]
        self.doc_frequencies, self.doc_term_freqs, lengths = {}, [], []
        for doc in docs:
            path_tokens, symbol_tokens, body_tokens = tokens[doc.path]
            wc = {}
            for t in path_tokens:
                wc[t] = wc.get(t, 0.0) + self.path_weight
            for t in symbol_tokens:
                wc[t] = wc.get(t, 0.0) + self.symbol_weight
            for t in body_tokens:
                wc[t] = wc.get(t, 0.0) + self.body_weight
            eff = max(1.0, float(len(body_tokens) + len(path_tokens))) if self.decouple_symbols else sum(wc.values())
            lengths.append(eff)
            self.doc_term_freqs.append(wc)
            for term in set(wc.keys()):
                self.doc_frequencies[term] = self.doc_frequencies.get(term, 0) + 1
        self.doc_lengths = np.array(lengths, dtype=np.float32)
        self.avg_doc_len = float(np.mean(self.doc_lengths)) if len(self.doc_lengths) > 0 else 1.0
        inv = defaultdict(list)
        for i, tc in enumerate(self.doc_term_freqs):
            for term, tf in tc.items():
                inv[term].append((i, tf))
        self.inverted_index = dict(inv)
        self.doc_len_norms = (self.k1 * (1.0 - self.b + self.b * (self.doc_lengths / self.avg_doc_len))
                              if self.avg_doc_len > 0 else np.ones(self.num_docs, dtype=np.float32) * self.k1)
        import math
        self.idf = {t: max(0.0, math.log((self.num_docs - df + 0.5) / (df + 0.5) + 1.0)) for t, df in self.doc_frequencies.items()}
        return self


def make_index(cfg):
    return VariantBM25(**cfg)


def shared_tokens(docs, tokenizer):
    return {d.path: (tokenizer.tokenize_path(d.path),
                     [t for s in d.symbols for t in tokenizer.tokenize_text(s)],
                     tokenizer.tokenize_text(d.content)) for d in docs}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def dev_repos():
    split = json.loads((PHASE2_DIR / "split.json").read_text(encoding="utf-8"))
    recorded = (PHASE2_DIR / "split.sha256").read_text(encoding="utf-8").split()[0]
    assert canonical_hash(split) == recorded, "Milestone 2B split hash mismatch"
    return {r for r, s in split["assignment"].items() if s == "dev"}, recorded


def snapshot_docs(key, manifest):
    from agent_retrieval_bench.baseline import read_jsonl
    from run_arb_evaluator_audit import reconstruct_file
    from reponeedle.models import FileDoc
    p2c = defaultdict(list)
    for c in read_jsonl(manifest[key]):
        if c.get("path"):
            p2c[c["path"]].append(c)
    return [FileDoc(path=p, content=reconstruct_file(cs), is_test="test" in p.lower()) for p, cs in p2c.items()]


def rank_by(scores, paths):
    return P1.rank_files(list(zip(paths, [float(s) for s in scores])))


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def register():
    if (OUT_DIR / "protocol.json").exists():
        raise SystemExit("protocol.json already registered.")
    _, split_hash = dev_repos()
    proto = dict(PROTOCOL, phase2_split_sha256=split_hash, registered_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "protocol.json").write_text(json.dumps(proto, indent=2), encoding="utf-8")
    (OUT_DIR / "protocol.sha256").write_text(canonical_hash(proto) + "  protocol.json\n", encoding="utf-8")
    return proto


def verify_protocol():
    proto = json.loads((OUT_DIR / "protocol.json").read_text(encoding="utf-8"))
    assert canonical_hash(proto) == (OUT_DIR / "protocol.sha256").read_text(encoding="utf-8").split()[0], "protocol modified"
    return proto


def run_lexical(shard, num_shards):
    from agent_retrieval_bench.baseline import target_gold_files, query_text_for_eval, tokenize as arb_tokenize
    verify_protocol()
    allowed, _ = dev_repos()
    manifest, by = P1._load()
    keys = sorted(k for k in by if k[0] in allowed)
    mine = [k for i, k in enumerate(keys) if i % num_shards == shard]
    out = OUT_DIR / "lexical" / f"shard_{shard}_of_{num_shards}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["sample_id"] for l in open(out, encoding="utf-8")} if out.exists() else set()
    tok = CodeTokenizer()
    t0 = time.time()
    guard_checked = False
    with open(out, "a", encoding="utf-8") as f:
        for n, key in enumerate(mine, start=1):
            assert key[0] in allowed, "held-out repository leaked into dev analysis"
            group = [s for s in by[key] if s["id"] not in done and target_gold_files(s)]
            if not group:
                continue
            docs = snapshot_docs(key, manifest)
            paths = [d.path for d in docs]
            toks = {False: shared_tokens(docs, CodeTokenizer()), True: shared_tokens(docs, DedupeTokenizer())}
            indexes = {name: make_index(cfg).fit_tokens(docs, toks[bool(cfg.get("dedupe"))])
                       for name, cfg in {**VARIANTS, **DIAGNOSTICS}.items()}
            base = indexes["L0_baseline"]
            # Exactness guard (first snapshot processed by each shard run): shared-token construction must
            # equal the production fit() bit for bit, for the default and the de-duplicating tokenizer.
            if not guard_checked:
                probe = query_text_for_eval(group[0])
                assert np.array_equal(base.score(probe), BM25Index().fit(docs).score(probe)), "fit_tokens != BM25Index.fit"
                assert np.array_equal(indexes["L5_no_duplicate_tokens"].score(probe),
                                      make_index(VARIANTS["L5_no_duplicate_tokens"]).fit(docs).score(probe)), "dedupe fit mismatch"
                guard_checked = True
                print(f"[lexical {shard}/{num_shards}] exactness guard passed on {key[0]}", file=sys.stderr, flush=True)
            eff_len = dict(zip(paths, base.doc_lengths.tolist()))
            median_len = float(np.median(base.doc_lengths))
            for s in group:
                gold = target_gold_files(s)
                q = query_text_for_eval(s)
                rec = {"sample_id": s["id"], "task_type": s.get("task_type", s["_subset_name"]), "repo": key[0],
                       "n_files": len(paths), "gold_files": gold, "variants": {}}
                for name, idx in indexes.items():
                    ranking = rank_by(idx.score(q), paths)
                    rec["variants"][name] = {"metrics": P1.file_metrics(gold, ranking),
                                             "gold_positions": P1.gold_positions(gold, ranking),
                                             "top10": ranking[:10]}
                # Query tokenisation forensics
                rn_tokens = tok.tokenize_text(q)
                is_json = False
                key_tokens = 0
                field_tokens = {}
                try:
                    obj = json.loads(q)
                    if isinstance(obj, dict):
                        is_json = True
                        key_tokens = sum(len(tok.tokenize_text(k)) for k in obj)
                        field_tokens = {k: len(tok.tokenize_text(json.dumps(v) if not isinstance(v, str) else v)) for k, v in obj.items()}
                except ValueError:
                    pass
                counts = Counter(rn_tokens)
                rec["query"] = {
                    "is_json": is_json, "chars": len(q), "rn_tokens": len(rn_tokens), "rn_unique": len(counts),
                    "arb_tokens": len(arb_tokenize(q)), "key_tokens": key_tokens, "field_tokens": field_tokens,
                    "numeric_token_share": sum(c for t, c in counts.items() if t.isdigit()) / max(1, len(rn_tokens)),
                    "max_term_repeat": max(counts.values()) if counts else 0,
                }
                # Length forensics (effective BM25 length, baseline index)
                top10 = rec["variants"]["L0_baseline"]["top10"]
                rec["length"] = {
                    "corpus_median": median_len,
                    "gold": [eff_len.get(g) for g in gold],
                    "gold_percentile": [float(np.mean(base.doc_lengths <= eff_len[g])) if g in eff_len else None for g in gold],
                    "top10_nongold_median": float(np.median([eff_len[p] for p in top10 if p not in set(gold)] or [0])),
                }
                f.write(json.dumps(rec) + "\n")
            f.flush()
            print(f"[lexical {shard}/{num_shards}] {n}/{len(mine)} snapshots, {time.time() - t0:.0f}s", file=sys.stderr, flush=True)


def load(stage):
    rows = {}
    for p in sorted((OUT_DIR / stage).glob("shard_*.jsonl")):
        for l in open(p, encoding="utf-8"):
            r = json.loads(l)
            rows[r["sample_id"]] = r
    return rows


def contrast(rows, a, b, key="variants"):
    out = {}
    for t in ["overall"] + TASKS:
        sel = sorted(i for i, r in rows.items() if t == "overall" or r["task_type"] == t)
        if not sel:
            continue
        repos = [rows[i]["repo"] for i in sel]
        blk = {"n_queries": len(sel), "n_repositories": len(set(repos))}
        for m in METRICS:
            va = np.array([rows[i][key][a]["metrics"][m] for i in sel])
            vb = np.array([rows[i][key][b]["metrics"][m] for i in sel])
            d = va - vb
            blk[m] = {"a": float(va.mean()), "b": float(vb.mean()), "mean_diff": float(d.mean()),
                      "wins": int((d > 0).sum()), "ties": int((d == 0).sum()), "losses": int((d < 0).sum()),
                      "ci95": P1.clustered_bootstrap_ci(d, repos)}
        out[t] = blk
    return out


def stage1():
    verify_protocol()
    rows = load("lexical")
    p1 = {}
    for p in (P1.OUT_DIR / "per_query").glob("shard_*.jsonl"):
        for l in open(p, encoding="utf-8"):
            r = json.loads(l)
            p1[r["sample_id"]] = r
    results = {name: contrast(rows, name, "L0_baseline") for name in list(VARIANTS)[1:] + list(DIAGNOSTICS)}
    # Absolute dev metrics for every variant and for the matched BM25 / hybrid references (Phase 1 rows)
    absolute = {}
    for t in ["overall"] + TASKS:
        sel = [i for i, r in rows.items() if t == "overall" or r["task_type"] == t]
        absolute[t] = {name: {m: float(np.mean([rows[i]["variants"][name]["metrics"][m] for i in sel])) for m in METRICS}
                       for name in {**VARIANTS, **DIAGNOSTICS}}
        absolute[t]["REF_bm25_wholefile"] = {m: float(np.mean([p1[i]["metrics"]["bm25_wholefile"][m] for i in sel])) for m in METRICS}
        absolute[t]["REF_hybrid_wholefile"] = {m: float(np.mean([p1[i]["metrics"]["rn_wholefile"][m] for i in sel])) for m in METRICS}
        absolute[t]["n_queries"] = len(sel)
    candidates = []
    for name in list(VARIANTS)[1:]:
        c = results[name]
        gain = c["comment2context"]["recall@20"]["mean_diff"]
        guard = min(c[t][m]["mean_diff"] for t in TASKS if t in c for m in ("mrr", "recall@20"))
        if gain > 0 and guard >= -0.02:
            candidates.append((gain, name))
    candidates = [n for _, n in sorted(candidates, reverse=True)[:3]]
    (OUT_DIR / "stage1_results.json").write_text(json.dumps({"contrasts_vs_L0": results, "absolute": absolute,
                                                             "n_queries": len(rows)}, indent=2), encoding="utf-8")
    hc = {"candidates": candidates, "combined": len(candidates) >= 2,
          "combined_config": {k: v for n in candidates for k, v in VARIANTS[n].items()} if len(candidates) >= 2 else None}
    (OUT_DIR / "hybrid_candidates.json").write_text(json.dumps(hc, indent=2), encoding="utf-8")
    (OUT_DIR / "hybrid_candidates.sha256").write_text(canonical_hash(hc) + "  hybrid_candidates.json\n", encoding="utf-8")
    return hc, absolute, results


def hybrid_arms():
    hc = json.loads((OUT_DIR / "hybrid_candidates.json").read_text(encoding="utf-8"))
    assert canonical_hash(hc) == (OUT_DIR / "hybrid_candidates.sha256").read_text(encoding="utf-8").split()[0]
    arms = {"H0_baseline": {}}
    for n in hc["candidates"]:
        arms[f"H_{n}"] = VARIANTS[n]
    if hc["combined"]:
        arms["H_C_combined"] = hc["combined_config"]
    return arms


def run_hybrid(shard, num_shards):
    from agent_retrieval_bench.baseline import target_gold_files, query_text_for_eval
    from reponeedle.engine import RepoNeedleEngine
    from reponeedle.models import TaskType, AblationConfig
    verify_protocol()
    arms = hybrid_arms()
    allowed, _ = dev_repos()
    manifest, by = P1._load()
    keys = sorted(k for k in by if k[0] in allowed)
    mine = [k for i, k in enumerate(keys) if i % num_shards == shard]
    out = OUT_DIR / "hybrid" / f"shard_{shard}_of_{num_shards}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["sample_id"] for l in open(out, encoding="utf-8")} if out.exists() else set()
    enum = {"code2test": TaskType.CODE2TEST, "trace2code": TaskType.TRACE2CODE, "edit2ripple": TaskType.EDIT2RIPPLE}
    t0 = time.time()
    with open(out, "a", encoding="utf-8") as f:
        for n, key in enumerate(mine, start=1):
            assert key[0] in allowed
            group = [s for s in by[key] if s["id"] not in done and target_gold_files(s)]
            if not group:
                continue
            docs = snapshot_docs(key, manifest)
            engine = RepoNeedleEngine.from_documents(docs)
            production_index = engine.lexical_index
            arm_index = {a: (production_index if not cfg else make_index(cfg).fit(engine.docs)) for a, cfg in arms.items()}
            universe = {d.path for d in docs}
            for s in group:
                gold = target_gold_files(s)
                task = s.get("task_type", s["_subset_name"])
                rec = {"sample_id": s["id"], "task_type": task, "repo": key[0], "gold_files": gold, "arms": {}}
                for a, idx in arm_index.items():
                    engine.lexical_index = idx
                    cap = {}
                    orig = engine.budget_optimizer.pack_context

                    def capture(candidate_files, *x, **kw):
                        cap["r"] = [(d.path, float(sc)) for d, sc, _ in candidate_files]
                        return orig(candidate_files, *x, **kw)
                    engine.budget_optimizer.pack_context = capture
                    try:
                        res = engine.retrieve(query=query_text_for_eval(s), budget_tokens=P1.BUDGET,
                                              task_type=enum.get(task, TaskType.COMMENT2CONTEXT), ablation_config=AblationConfig())
                    finally:
                        engine.budget_optimizer.pack_context = orig
                    ranking = [p for p, _ in cap["r"]]
                    packed = {sf.path for sf in res.selected_files if sf.path in universe}
                    rec["arms"][a] = {"metrics": P1.file_metrics(gold, ranking), "gold_positions": P1.gold_positions(gold, ranking),
                                      "packed_gold_coverage": len(set(gold) & packed) / len(gold)}
                engine.lexical_index = production_index
                f.write(json.dumps(rec) + "\n")
            f.flush()
            print(f"[hybrid {shard}/{num_shards}] {n}/{len(mine)} snapshots, {time.time() - t0:.0f}s", file=sys.stderr, flush=True)


def stage2():
    verify_protocol()
    rows = load("hybrid")
    arms = [a for a in hybrid_arms() if a != "H0_baseline"]
    results = {a: contrast(rows, a, "H0_baseline", key="arms") for a in arms}
    eligible = []
    for a, c in results.items():
        guard = min(c[t][m]["mean_diff"] for t in TASKS if t in c for m in ("mrr", "recall@20"))
        gain = c["comment2context"]["recall@20"]["mean_diff"]
        if guard >= -0.02:
            eligible.append((gain, a))
    sel = max(eligible)[1] if eligible else None
    supported = bool(sel and results[sel]["comment2context"]["recall@20"]["ci95"][0] > 0)
    decision = {"selected_arm": sel, "dev_supported": supported, "eligible": [{"arm": a, "c2c_recall20_gain": g} for g, a in eligible],
                "selected_config": hybrid_arms().get(sel) if sel else None,
                "note": "development evidence only (previously used development repositories); not confirmatory"}
    (OUT_DIR / "dev_selection.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
    (OUT_DIR / "dev_selection.sha256").write_text(canonical_hash(decision) + "  dev_selection.json\n", encoding="utf-8")
    (OUT_DIR / "stage2_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return decision, results


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["register", "lexical", "stage1", "hybrid", "stage2"])
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--num-shards", type=int, default=1)
    a = ap.parse_args(argv)
    if a.step == "register":
        print(json.dumps({"protocol_sha256": canonical_hash(register())}, indent=2))
    elif a.step == "lexical":
        run_lexical(a.shard, a.num_shards)
    elif a.step == "stage1":
        hc, _, _ = stage1()
        print(json.dumps(hc, indent=2))
    elif a.step == "hybrid":
        run_hybrid(a.shard, a.num_shards)
    elif a.step == "stage2":
        d, _ = stage2()
        print(json.dumps(d, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
