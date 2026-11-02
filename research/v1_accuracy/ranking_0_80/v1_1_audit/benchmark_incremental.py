import time
import math
import tracemalloc
import numpy as np
import json
import os
from typing import List, Dict, Tuple, Any

from reponeedle.models import FileDoc, Query
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex


def create_test_docs(n: int = 200) -> List[FileDoc]:
    docs = []
    for i in range(n):
        docs.append(
            FileDoc(
                path=f"pkg/sub_{i % 15}/module_{i}.py",
                content=f"""
class Service_{i}:
    def __init__(self):
        self.val = {i}
    def process_data(self, query):
        from pkg.sub_{(i + 1) % 15}.module_{(i + 1) % 200} import Service_{(i + 1) % 200}
        return self.val * 2
""",
                symbols=[f"Service_{i}", "process_data"],
                imports=[f"pkg.sub_{(i + 1) % 15}.module_{(i + 1) % 200}"],
                line_count=8,
                token_count=45,
            )
        )
    return docs


def run_benchmark():
    tracemalloc.start()
    docs = create_test_docs(200)

    # 1. Full Rebuild Benchmark
    t0 = time.perf_counter()
    engine_full = RepoNeedleEngine(docs)
    t_full_ms = (time.perf_counter() - t0) * 1000.0

    _, peak_ram_full = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()

    print(f"1. Full Rebuild Latency (200 docs): {t_full_ms:.2f} ms")
    print(f"   Peak RAM: {peak_ram_full / (1024 * 1024):.2f} MB")

    # 2. Single-File Update Benchmark
    updated_doc_1 = FileDoc(
        path="pkg/sub_0/module_0.py",
        content="""
class Service_0:
    def process_data(self, query):
        return 99999
""",
        symbols=["Service_0", "process_data"],
        imports=[],
        line_count=5,
        token_count=20,
    )

    engine_single = RepoNeedleEngine(docs)
    t0 = time.perf_counter()
    engine_single.update_document(updated_doc_1)
    t_single_ms = (time.perf_counter() - t0) * 1000.0
    _, peak_ram_single = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()

    # Compare against fresh rebuild with updated doc
    docs_updated_1 = [updated_doc_1 if d.path == updated_doc_1.path else d for d in docs]
    engine_fresh_1 = RepoNeedleEngine(docs_updated_1)

    # Query consistency check
    test_q = Query(text="process_data Service_0", anchor_files=["pkg/sub_0/module_0.py"], budget_tokens=4000)
    res_inc_1 = engine_single.retrieve(test_q, ranking_engine="change_impact")
    res_fresh_1 = engine_fresh_1.retrieve(test_q, ranking_engine="change_impact")

    inc_paths_1 = [f.path for f in res_inc_1.selected_files]
    fresh_paths_1 = [f.path for f in res_fresh_1.selected_files]
    inc_scores_1 = [f.score for f in res_inc_1.selected_files]
    fresh_scores_1 = [f.score for f in res_fresh_1.selected_files]

    rank_diff_1 = inc_paths_1 != fresh_paths_1
    score_diff_1 = np.max(np.abs(np.array(inc_scores_1) - np.array(fresh_scores_1))) if inc_scores_1 else 0.0

    print(f"\n2. Single-File Update Latency: {t_single_ms:.2f} ms")
    print(f"   Peak RAM: {peak_ram_single / (1024 * 1024):.2f} MB")
    print(f"   Ranking Bit-Identical: {not rank_diff_1}")
    print(f"   Max Score Delta: {score_diff_1:.8f}")

    # 3. Five-File Update Benchmark
    updated_5 = [
        FileDoc(
            path=f"pkg/sub_{i % 15}/module_{i}.py",
            content=f"def new_service_{i}(): return {i * 100}\n",
            symbols=[f"new_service_{i}"],
            imports=[],
            line_count=2,
            token_count=12,
        )
        for i in range(5)
    ]
    engine_5 = RepoNeedleEngine(docs)
    t0 = time.perf_counter()
    engine_5.update_documents(updated_5)
    t_5_ms = (time.perf_counter() - t0) * 1000.0

    docs_updated_5 = [next((u for u in updated_5 if u.path == d.path), d) for d in docs]
    engine_fresh_5 = RepoNeedleEngine(docs_updated_5)
    res_inc_5 = engine_5.retrieve(Query(text="new_service_3", budget_tokens=4000), ranking_engine="change_impact")
    res_fresh_5 = engine_fresh_5.retrieve(Query(text="new_service_3", budget_tokens=4000), ranking_engine="change_impact")
    score_diff_5 = np.max(np.abs(np.array([f.score for f in res_inc_5.selected_files]) - np.array([f.score for f in res_fresh_5.selected_files])))

    print(f"\n3. Five-File Update Latency: {t_5_ms:.2f} ms")
    print(f"   Max Score Delta: {score_diff_5:.8f}")

    # 4. Twenty-File Update Benchmark
    updated_20 = [
        FileDoc(
            path=f"pkg/sub_{i % 15}/module_{i}.py",
            content=f"def batch_service_{i}(): return {i * 500}\n",
            symbols=[f"batch_service_{i}"],
            imports=[],
            line_count=2,
            token_count=12,
        )
        for i in range(20)
    ]
    engine_20 = RepoNeedleEngine(docs)
    t0 = time.perf_counter()
    engine_20.update_documents(updated_20)
    t_20_ms = (time.perf_counter() - t0) * 1000.0

    docs_updated_20 = [next((u for u in updated_20 if u.path == d.path), d) for d in docs]
    engine_fresh_20 = RepoNeedleEngine(docs_updated_20)
    res_inc_20 = engine_20.retrieve(Query(text="batch_service_12", budget_tokens=4000), ranking_engine="change_impact")
    res_fresh_20 = engine_fresh_20.retrieve(Query(text="batch_service_12", budget_tokens=4000), ranking_engine="change_impact")
    score_diff_20 = np.max(np.abs(np.array([f.score for f in res_inc_20.selected_files]) - np.array([f.score for f in res_fresh_20.selected_files])))

    print(f"\n4. Twenty-File Update Latency: {t_20_ms:.2f} ms")
    print(f"   Max Score Delta: {score_diff_20:.8f}")

    tracemalloc.stop()

    results = {
        "full_rebuild_ms": round(t_full_ms, 2),
        "single_file_update_ms": round(t_single_ms, 2),
        "five_file_update_ms": round(t_5_ms, 2),
        "twenty_file_update_ms": round(t_20_ms, 2),
        "peak_ram_mb": round(peak_ram_full / (1024 * 1024), 2),
        "index_consistency_single_delta": float(score_diff_1),
        "index_consistency_five_delta": float(score_diff_5),
        "index_consistency_twenty_delta": float(score_diff_20),
    }

    out_file = os.path.join(os.path.dirname(__file__), "incremental_benchmarks.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved incremental benchmarks to {out_file}")
    return results


if __name__ == "__main__":
    run_benchmark()
