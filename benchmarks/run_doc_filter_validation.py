"""
Milestone 2B: held-out repository validation of the EXISTING documentation filter
(`AblationConfig.enable_doc_filter` / `doc_filter_penalty`). EXPERIMENTAL; not an official ARB score.

Pre-registered workflow (each step refuses to run out of order):
  1. split  -> split.json, split.sha256, protocol.json   (dataset metadata only: repository x task coverage)
  2. dev    -> filter OFF + predeclared penalty grid on DEVELOPMENT repositories only; selects and
               freezes selected_filter_config.json (+ sha256) with the predeclared dev rule
  3. test   -> verifies both hashes, runs OFF vs selected config ONCE on TEST repositories only
  4. report -> aggregates, CIs, Holm-adjusted guardrails, decision

Evaluation framework: the Phase 1 product-aligned evaluation (file unit, whole-file input, full
ranking; packed context reported separately). Production code is not modified; the filter is applied
per call via `retrieve(ablation_config=...)`, and both arms pass an explicit AblationConfig.

Usage:
    python benchmarks/run_doc_filter_validation.py split
    python benchmarks/run_doc_filter_validation.py dev --shard 0 --num-shards 4      (x4)
    python benchmarks/run_doc_filter_validation.py select
    python benchmarks/run_doc_filter_validation.py test --shard 0 --num-shards 4     (x4)
    python benchmarks/run_doc_filter_validation.py report
"""

import argparse
import hashlib
import json
import platform
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT_DIR / "reports" / "experimental" / "phase2_documentation_filter"
PHASE1_DIR = ROOT_DIR / "reports" / "experimental" / "phase1_product_aligned_evaluation"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT_DIR))

import run_arb_product_aligned_eval as P1  # noqa: E402  (shared loaders, metrics, bootstrap)

TASKS = ["comment2context", "code2test", "trace2code", "edit2ripple"]
METRICS = ["mrr", "recall@5", "recall@10", "recall@20"]

PROTOCOL = {
    "milestone": "2B documentation-filter held-out validation (EXPERIMENTAL; not an official ARB score)",
    "framework": "Phase 1 product-aligned evaluation: file unit, whole-file input, full ranking; packed context separate",
    "treatment": "AblationConfig(enable_doc_filter=True, doc_filter_penalty=p) passed per call to retrieve()",
    "control": "AblationConfig() (enable_doc_filter=False) passed per call to retrieve()",
    "doc_predicate": "engine.py legacy ranker: path contains /doc/, /docs/, doc/, docs/, documentation/, guide/, tutorial/, .github/ "
                     "OR ends with .md, .rst, .txt, .adoc, .html (case-insensitive)",
    "split": {
        "unit": "repository", "test_repositories": 10, "dev_repositories": 15,
        "seed": "reponeedle-2B-split-v1",
        "algorithm": "For attempt a = 0, 1, ...: shuffle the sorted repository list with random.Random(f'{seed}:{a}'); test = first 10. "
                     "Accept the first attempt where, for every task with n repositories, the test count is within +-1 of round(0.4*n) "
                     "and both splits contain >= 1 repository with that task.",
        "inputs_used": "repository ids and task coverage (presence of >=1 gold-labelled query per task) only",
    },
    "primary": {"task": "comment2context", "metric": "recall@20", "contrast": "filter ON - filter OFF on TEST repositories",
                "success": "paired repository-clustered 95% percentile CI lower bound > 0"},
    "guardrails": {
        "hypotheses": [["comment2context", "mrr"], ["code2test", "mrr"], ["code2test", "recall@20"],
                       ["trace2code", "mrr"], ["trace2code", "recall@20"], ["edit2ripple", "mrr"], ["edit2ripple", "recall@20"]],
        "test": "one-sided regression test: bootstrap p = (1 + #{resampled mean diff >= 0}) / (B + 1)",
        "correction": "Holm-Bonferroni over the 7 guardrail hypotheses, family-wise alpha = 0.05",
        "note": "Recall@5 and Recall@10 for every task are reported with uncorrected CIs (descriptive)",
    },
    "bootstrap": {"type": "paired, repository-clustered percentile", "resamples": P1.BOOT_N, "seed": P1.BOOT_SEED, "ci": 0.95},
    "dev_grid": [0.5, 0.25, 0.0],
    "dev_selection_rule": "Among grid values whose DEV mean (ON - OFF) for comment2context MRR and for MRR and Recall@20 of every "
                          "other task is >= -0.02, choose the one maximising DEV mean comment2context Recall@20 gain, provided it is > 0; "
                          "ties -> larger penalty (milder). If none qualifies, freeze the existing default penalty 0.5 and record the dev failure.",
    "decision_rule": {
        "VALIDATED": "primary CI lower bound > 0 AND no Holm-supported guardrail regression",
        "NOT VALIDATED": "any Holm-supported guardrail regression, OR primary point estimate <= 0",
        "INCONCLUSIVE": "no Holm-supported regression, primary point estimate > 0, but primary CI includes 0; "
                        "or fewer than 5 test repositories contain comment2context queries",
    },
    "budget_tokens": P1.BUDGET,
    "task_label_passed_to_engine": True,
}


def canonical_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def is_doc(path: str) -> bool:
    """Exact replica of the engine's documentation predicate (engine.py, legacy ranker)."""
    p = path.lower()
    return any(seg in p for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) \
        or p.endswith((".md", ".rst", ".txt", ".adoc", ".html"))


def holm(pvalues):
    """Holm-Bonferroni step-down adjusted p-values (monotone, capped at 1)."""
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    m, adj, running = len(pvalues), [0.0] * len(pvalues), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adj[i] = running
    return adj


def bootstrap(diffs, clusters, n_boot=P1.BOOT_N, seed=P1.BOOT_SEED):
    """Returns (two-sided 95% percentile CI, one-sided regression p-value)."""
    rng = np.random.default_rng(seed)
    by = defaultdict(list)
    for d, c in zip(diffs, clusters):
        by[c].append(d)
    groups = [np.asarray(v, dtype=float) for _, v in sorted(by.items())]
    boots = np.array([np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))]).mean()
                      for _ in range(n_boot)])
    ci = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
    p_regression = float((1 + np.sum(boots >= 0)) / (n_boot + 1))
    return ci, p_regression


# ---------------------------------------------------------------------------
# Step 1: split (metadata only)
# ---------------------------------------------------------------------------

def make_split():
    if (OUT_DIR / "split.json").exists():
        raise SystemExit("split.json already exists; the split is frozen and must not be regenerated.")
    from agent_retrieval_bench.baseline import read_jsonl, target_gold_files
    coverage = defaultdict(set)
    counts = defaultdict(Counter)
    for t in TASKS:
        for s in read_jsonl(P1.ARB_DIR / "data" / "benchmark" / f"v2_{t}" / "samples.jsonl"):
            if target_gold_files(s):
                coverage[s["repo"]].add(t)
                counts[s["repo"]][t] += 1
    repos = sorted(coverage)
    n_task = {t: sum(t in coverage[r] for r in repos) for t in TASKS}
    target = {t: round(0.4 * n_task[t]) for t in TASKS}
    seed = PROTOCOL["split"]["seed"]
    for attempt in range(10_000):
        order = list(repos)
        random.Random(f"{seed}:{attempt}").shuffle(order)
        test = set(order[: PROTOCOL["split"]["test_repositories"]])
        ok = all(abs(sum(t in coverage[r] for r in test) - target[t]) <= 1
                 and 1 <= sum(t in coverage[r] for r in test) < n_task[t] for t in TASKS)
        if ok:
            break
    else:
        raise SystemExit("No split satisfied the stratification constraints; stop for review.")
    split = {
        "seed": seed, "accepted_attempt": attempt, "algorithm": PROTOCOL["split"]["algorithm"],
        "assignment": {r: ("test" if r in test else "dev") for r in repos},
        "task_coverage": {r: sorted(coverage[r]) for r in repos},
        "query_counts_not_used_for_selection": {r: dict(counts[r]) for r in repos},
        "repositories_per_task": {t: {"total": n_task[t], "target_test": target[t],
                                      "test": sum(t in coverage[r] for r in test),
                                      "dev": sum(t in coverage[r] for r in repos if r not in test)} for t in TASKS},
        "queries_per_task": {t: {"dev": sum(counts[r][t] for r in repos if r not in test),
                                 "test": sum(counts[r][t] for r in test)} for t in TASKS},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "split.json").write_text(json.dumps(split, indent=2, sort_keys=True), encoding="utf-8")
    h = canonical_hash(split)
    (OUT_DIR / "split.sha256").write_text(f"{h}  split.json (canonical JSON: sort_keys, compact separators)\n", encoding="utf-8")
    protocol = dict(PROTOCOL, split_sha256=h, registered_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    (OUT_DIR / "protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    (OUT_DIR / "protocol.sha256").write_text(canonical_hash(protocol) + "  protocol.json\n", encoding="utf-8")
    return split, h


def load_split(verify=True):
    split = json.loads((OUT_DIR / "split.json").read_text(encoding="utf-8"))
    if verify:
        recorded = (OUT_DIR / "split.sha256").read_text(encoding="utf-8").split()[0]
        assert canonical_hash(split) == recorded, "split.json hash mismatch: split was modified"
        protocol = json.loads((OUT_DIR / "protocol.json").read_text(encoding="utf-8"))
        assert protocol["split_sha256"] == recorded, "protocol does not reference this split"
    return split


# ---------------------------------------------------------------------------
# Evaluation of arms on a set of repositories
# ---------------------------------------------------------------------------

def evaluate(phase, arms, shard, num_shards):
    from agent_retrieval_bench.baseline import read_jsonl, target_gold_files, query_text_for_eval
    from run_arb_evaluator_audit import reconstruct_file
    from reponeedle.engine import RepoNeedleEngine
    from reponeedle.models import FileDoc, TaskType, AblationConfig

    split = load_split()
    allowed = {r for r, s in split["assignment"].items() if s == phase}
    manifest, by_corpus = P1._load()
    keys = sorted(k for k in by_corpus if k[0] in allowed)
    mine = [k for i, k in enumerate(keys) if i % num_shards == shard]
    out = OUT_DIR / phase / f"shard_{shard}_of_{num_shards}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["sample_id"] for l in open(out, encoding="utf-8")} if out.exists() else set()
    enum = {"code2test": TaskType.CODE2TEST, "trace2code": TaskType.TRACE2CODE, "edit2ripple": TaskType.EDIT2RIPPLE}
    configs = {name: (AblationConfig() if pen is None else AblationConfig(enable_doc_filter=True, doc_filter_penalty=pen))
               for name, pen in arms.items()}
    t0 = time.time()
    with open(out, "a", encoding="utf-8") as f:
        for n, key in enumerate(mine, start=1):
            assert key[0] in allowed, "repository leakage across splits"
            group = [s for s in by_corpus[key] if s["id"] not in done and target_gold_files(s)]
            if not group:
                continue
            chunks = read_jsonl(manifest[key])
            p2c = defaultdict(list)
            for c in chunks:
                if c.get("path"):
                    p2c[c["path"]].append(c)
            universe = set(p2c)
            engine = RepoNeedleEngine.from_documents(
                [FileDoc(path=p, content=reconstruct_file(cs), is_test="test" in p.lower()) for p, cs in p2c.items()])
            for s in group:
                gold = target_gold_files(s)
                task = s.get("task_type", s["_subset_name"])
                q = query_text_for_eval(s)
                rec = {"sample_id": s["id"], "task_type": task, "repo": key[0], "base_commit": key[1], "phase": phase,
                       "gold_files": gold, "gold_docs": [g for g in gold if is_doc(g)],
                       "n_candidate_files": len(universe), "n_doc_files": sum(is_doc(p) for p in universe), "arms": {}}
                for name, cfg in configs.items():
                    captured = {}
                    orig = engine.budget_optimizer.pack_context

                    def capture(candidate_files, *a, **kw):
                        captured["r"] = [(d.path, float(sc)) for d, sc, _ in candidate_files]
                        return orig(candidate_files, *a, **kw)

                    engine.budget_optimizer.pack_context = capture
                    try:
                        t_q = time.perf_counter()
                        res = engine.retrieve(query=q, budget_tokens=P1.BUDGET, task_type=enum.get(task, TaskType.COMMENT2CONTEXT),
                                              ablation_config=cfg)
                        lat = (time.perf_counter() - t_q) * 1000
                    finally:
                        engine.budget_optimizer.pack_context = orig
                    ranking = [p for p, _ in captured["r"]]
                    assert ranking == P1.rank_files(captured["r"]) and set(ranking) <= universe
                    packed = [sf.path for sf in res.selected_files if sf.path in universe]
                    gs, ps = set(gold), set(packed)
                    rec["arms"][name] = {
                        "metrics": P1.file_metrics(gold, ranking),
                        "gold_positions": P1.gold_positions(gold, ranking),
                        "docs_top": {k: sum(is_doc(p) for p in ranking[:k]) for k in (5, 10, 20)},
                        "packed": {"gold_coverage": len(gs & ps) / len(gs), "success": bool(gs & ps),
                                   "utilisation": res.total_tokens / P1.BUDGET, "n_files": len(packed),
                                   "n_doc_files": sum(is_doc(p) for p in packed), "gold_packed": sorted(gs & ps)},
                        "latency_ms": lat,
                        "top20": ranking[:20],
                        "ranking_sha": hashlib.sha256("\n".join(ranking).encode()).hexdigest()[:16],
                    }
                f.write(json.dumps(rec) + "\n")
            f.flush()
            print(f"[{phase} {shard}/{num_shards}] {n}/{len(mine)} snapshots, {time.time() - t0:.0f}s", file=sys.stderr, flush=True)


def load_rows(phase):
    rows = {}
    for p in sorted((OUT_DIR / phase).glob("shard_*.jsonl")):
        for l in open(p, encoding="utf-8"):
            r = json.loads(l)
            rows[r["sample_id"]] = r
    return rows


def contrasts(rows, arm_on, arm_off="off"):
    out = {}
    for t in ["overall"] + TASKS:
        sel = sorted(i for i, r in rows.items() if t == "overall" or r["task_type"] == t)
        if not sel:
            continue
        repos = [rows[i]["repo"] for i in sel]
        block = {"n_queries": len(sel), "n_repositories": len(set(repos)), "metrics": {}}
        for m in METRICS:
            on = np.array([rows[i]["arms"][arm_on]["metrics"][m] for i in sel])
            off = np.array([rows[i]["arms"][arm_off]["metrics"][m] for i in sel])
            d = on - off
            ci, p_reg = bootstrap(d, repos)
            block["metrics"][m] = {"off": float(off.mean()), "on": float(on.mean()), "mean_diff": float(d.mean()),
                                   "wins": int((d > 0).sum()), "ties": int((d == 0).sum()), "losses": int((d < 0).sum()),
                                   "ci95": ci, "p_regression_one_sided": p_reg}
        for arm in (arm_off, arm_on):
            a = [rows[i]["arms"][arm] for i in sel]
            block[arm] = {
                "docs_top5": float(np.mean([x["docs_top"]["5"] if "5" in x["docs_top"] else x["docs_top"][5] for x in a])),
                "docs_top10": float(np.mean([x["docs_top"]["10"] if "10" in x["docs_top"] else x["docs_top"][10] for x in a])),
                "docs_top20": float(np.mean([x["docs_top"]["20"] if "20" in x["docs_top"] else x["docs_top"][20] for x in a])),
                "packed_gold_coverage": float(np.mean([x["packed"]["gold_coverage"] for x in a])),
                "packed_success": float(np.mean([x["packed"]["success"] for x in a])),
                "packed_utilisation": float(np.mean([x["packed"]["utilisation"] for x in a])),
                "latency_ms_mean": float(np.mean([x["latency_ms"] for x in a])),
                "latency_ms_p50": float(np.median([x["latency_ms"] for x in a])),
            }
        out[t] = block
    return out


def gold_effects(rows, arm_on, arm_off="off"):
    """Gold files that leave the top 20 or the packed context under the filter (false negatives)."""
    examples, counts = [], Counter()
    for i, r in sorted(rows.items()):
        on, off = r["arms"][arm_on], r["arms"][arm_off]
        for g in r["gold_files"]:
            doc = is_doc(g)
            counts[("gold_doc" if doc else "gold_nondoc", "total")] += 1
            lost_top20 = g in off["top20"] and g not in on["top20"]
            lost_pack = g in off["packed"]["gold_packed"] and g not in on["packed"]["gold_packed"]
            gained_top20 = g not in off["top20"] and g in on["top20"]
            for flag, v in [("lost_top20", lost_top20), ("lost_packed", lost_pack), ("gained_top20", gained_top20)]:
                if v:
                    counts[("gold_doc" if doc else "gold_nondoc", flag)] += 1
            if lost_top20 or lost_pack:
                examples.append({"sample_id": i, "task": r["task_type"], "repo": r["repo"], "gold": g, "gold_is_doc": doc,
                                 "rank_off": off["gold_positions"].get(g), "rank_on": on["gold_positions"].get(g),
                                 "lost_top20": lost_top20, "lost_packed": lost_pack})
    return {f"{a}:{b}": v for (a, b), v in sorted(counts.items())}, examples


# ---------------------------------------------------------------------------
# Step 2b: dev selection (dev data only)
# ---------------------------------------------------------------------------

def select():
    if (OUT_DIR / "selected_filter_config.json").exists():
        raise SystemExit("selected_filter_config.json already frozen.")
    split = load_split()
    rows = load_rows("dev")
    dev_repos = {r for r, s in split["assignment"].items() if s == "dev"}
    assert {r["repo"] for r in rows.values()} <= dev_repos, "non-dev repository in dev results"
    results, eligible = {}, []
    for pen in PROTOCOL["dev_grid"]:
        name = f"on_p{pen}"
        c = contrasts(rows, name)
        results[name] = c
        guard = [c["comment2context"]["metrics"]["mrr"]["mean_diff"]] + \
                [c[t]["metrics"][m]["mean_diff"] for t in ["code2test", "trace2code", "edit2ripple"] if t in c for m in ("mrr", "recall@20")]
        gain = c["comment2context"]["metrics"]["recall@20"]["mean_diff"]
        if min(guard) >= -0.02 and gain > 0:
            eligible.append((gain, pen))
    if eligible:
        best_gain = max(g for g, _ in eligible)
        chosen = max(p for g, p in eligible if abs(g - best_gain) < 1e-12)
        status = "selected by dev rule"
    else:
        chosen, status = 0.5, "no grid value met the dev rule; existing default penalty 0.5 frozen (dev failure recorded)"
    effects = {f"on_p{p}": gold_effects(rows, f"on_p{p}")[0] for p in PROTOCOL["dev_grid"]}
    (OUT_DIR / "dev_results.json").write_text(json.dumps({"contrasts": results, "gold_effects": effects}, indent=2), encoding="utf-8")
    cfg = {"enable_doc_filter": True, "doc_filter_penalty": chosen, "status": status,
           "dev_eligible": [{"penalty": p, "dev_c2c_recall20_gain": g} for g, p in eligible],
           "split_sha256": (OUT_DIR / "split.sha256").read_text(encoding="utf-8").split()[0],
           "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (OUT_DIR / "selected_filter_config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    (OUT_DIR / "selected_filter_config.sha256").write_text(canonical_hash(cfg) + "  selected_filter_config.json\n", encoding="utf-8")
    return cfg, results


def frozen_penalty():
    cfg = json.loads((OUT_DIR / "selected_filter_config.json").read_text(encoding="utf-8"))
    recorded = (OUT_DIR / "selected_filter_config.sha256").read_text(encoding="utf-8").split()[0]
    assert canonical_hash(cfg) == recorded, "selected config hash mismatch"
    assert cfg["split_sha256"] == (OUT_DIR / "split.sha256").read_text(encoding="utf-8").split()[0]
    return cfg["doc_filter_penalty"]


# ---------------------------------------------------------------------------
# Step 4: confirmatory report (test data)
# ---------------------------------------------------------------------------

def report():
    split = load_split()
    pen = frozen_penalty()
    rows = load_rows("test")
    test_repos = {r for r, s in split["assignment"].items() if s == "test"}
    assert {r["repo"] for r in rows.values()} <= test_repos, "non-test repository in test results"
    arm = "on_selected"
    c = contrasts(rows, arm)
    hyps = PROTOCOL["guardrails"]["hypotheses"]
    pvals = [c[t]["metrics"][m]["p_regression_one_sided"] for t, m in hyps]
    adj = holm(pvals)
    guard = [{"task": t, "metric": m, "mean_diff": c[t]["metrics"][m]["mean_diff"], "ci95": c[t]["metrics"][m]["ci95"],
              "p_one_sided": p, "p_holm": a, "regression_supported": a < 0.05} for (t, m), p, a in zip(hyps, pvals, adj)]
    prim = c["comment2context"]["metrics"]["recall@20"]
    n_c2c_repos = c["comment2context"]["n_repositories"]
    if any(g["regression_supported"] for g in guard) or prim["mean_diff"] <= 0:
        decision = "NOT VALIDATED"
    elif prim["ci95"][0] > 0 and n_c2c_repos >= 5:
        decision = "VALIDATED"
    else:
        decision = "INCONCLUSIVE"
    effects, examples = gold_effects(rows, arm)
    result = {"decision": decision, "frozen_penalty": pen, "primary": prim, "guardrails": guard, "contrasts": c,
              "gold_effects": effects, "n_test_queries": len(rows), "n_test_repositories": len({r['repo'] for r in rows.values()})}
    (OUT_DIR / "test_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (OUT_DIR / "false_negative_examples.json").write_text(json.dumps(examples, indent=2), encoding="utf-8")
    meta = {"git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True).stdout.strip(),
            "python": sys.version.split()[0], "numpy": np.__version__, "platform": platform.platform(),
            "reported_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (OUT_DIR / "run_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["split", "dev", "select", "test", "report"])
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--num-shards", type=int, default=1)
    args = ap.parse_args(argv)
    if args.step == "split":
        split, h = make_split()
        print(json.dumps({"sha256": h, "accepted_attempt": split["accepted_attempt"],
                          "repositories_per_task": split["repositories_per_task"],
                          "queries_per_task": split["queries_per_task"]}, indent=2))
    elif args.step == "dev":
        if (OUT_DIR / "selected_filter_config.json").exists():
            raise SystemExit("Configuration already frozen; dev evaluation is closed.")
        arms = {"off": None, **{f"on_p{p}": p for p in PROTOCOL["dev_grid"]}}
        evaluate("dev", arms, args.shard, args.num_shards)
    elif args.step == "select":
        cfg, _ = select()
        print(json.dumps(cfg, indent=2))
    elif args.step == "test":
        pen = frozen_penalty()
        evaluate("test", {"off": None, "on_selected": pen}, args.shard, args.num_shards)
    elif args.step == "report":
        r = report()
        print(json.dumps({"decision": r["decision"], "penalty": r["frozen_penalty"], "primary": r["primary"],
                          "guardrails": r["guardrails"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
