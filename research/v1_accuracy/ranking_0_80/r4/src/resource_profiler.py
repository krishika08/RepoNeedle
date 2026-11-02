"""
Resource Profiler for RepoNeedle Phase R4.
Profiles CPU latency, memory footprint, indexing throughput, and storage footprint
for Dense Semantic Retrieval and Multi-Hop Structural Retrieval.
"""
import os
import sys
import time
import json
import tracemalloc
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))

from reponeedle.models import FileDoc
from dense_engine import DenseSemanticEngine
from reponeedle.core.function_graph import FunctionGraphEngine
from multihop_graph import MultiHopGraphEngine


def profile_resources():
    print("=== Profiling CPU-First Resource Footprint for R4 ===")

    # Load representative corpus: clap-rs snapshot
    p = "external/agent-retrieval-bench/data/corpus/v2_code2test/clap-rs__clap/68b5ff900bae8ee1a0e328c1a2301a7985e4f1c6.chunks.jsonl"
    file_chunks = {}
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            path = c["path"]
            text = c.get("text", "")
            if path not in file_chunks:
                file_chunks[path] = []
            file_chunks[path].append(text)

    docs = [FileDoc(path=path, content="\n".join(texts)) for path, texts in file_chunks.items() if path.endswith((".rs", ".toml", ".md"))]
    num_docs = len(docs)
    total_source_bytes = sum(len(d.content.encode("utf-8")) for d in docs)

    # 1. Profile Dense Semantic Indexing
    tracemalloc.start()
    t0 = time.time()
    dense_engine = DenseSemanticEngine(dimension=128, metric="cosine")
    dense_engine.fit(docs)
    dense_fit_time = time.time() - t0
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    dense_index_bytes = dense_engine.doc_embeddings.nbytes + dense_engine.projection_matrix.nbytes
    dense_throughput = num_docs / dense_fit_time if dense_fit_time > 0 else 0.0

    # 2. Profile Multi-Hop Graph Indexing
    tracemalloc.start()
    t1 = time.time()
    fg = FunctionGraphEngine()
    fg.build_graph(docs)
    multihop_engine = MultiHopGraphEngine(fg)
    graph_fit_time = time.time() - t1
    current_g_mem, peak_g_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    graph_throughput = num_docs / graph_fit_time if graph_fit_time > 0 else 0.0

    # 3. Profile CPU Inference Latencies (100 query iterations)
    dense_latencies = []
    sample_queries = [
        "quote empty default values in help template",
        "missing_copy_implementations in util mod",
        "parser value_parser error reporting",
        "custom derive attribute parsing",
        "subcommand help generation formatting",
    ]
    for _ in range(20):
        for q in sample_queries:
            t_start = time.perf_counter()
            _ = dense_engine.score(q)
            dense_latencies.append((time.perf_counter() - t_start) * 1000.0)

    # Multi-hop query latency
    graph_latencies = []
    seeds = {"clap_builder/src/builder/command.rs": 10.0}
    for _ in range(100):
        t_start = time.perf_counter()
        _ = multihop_engine.expand_multihop(seeds, max_hops=2)
        graph_latencies.append((time.perf_counter() - t_start) * 1000.0)

    profile_results = {
        "corpus_docs": num_docs,
        "corpus_source_mb": total_source_bytes / (1024 * 1024),
        "dense_indexing": {
            "fit_time_seconds": dense_fit_time,
            "throughput_docs_per_sec": dense_throughput,
            "peak_memory_mb": peak_mem / (1024 * 1024),
            "index_storage_kb": dense_index_bytes / 1024.0,
            "storage_per_doc_bytes": dense_index_bytes / num_docs if num_docs else 0,
            "inference_mean_ms": float(np.mean(dense_latencies)),
            "inference_p50_ms": float(np.median(dense_latencies)),
            "inference_p95_ms": float(np.percentile(dense_latencies, 95)),
        },
        "graph_indexing": {
            "fit_time_seconds": graph_fit_time,
            "throughput_docs_per_sec": graph_throughput,
            "peak_memory_mb": peak_g_mem / (1024 * 1024),
            "nodes": fg.graph.number_of_nodes(),
            "edges": fg.graph.number_of_edges(),
            "expansion_mean_ms": float(np.mean(graph_latencies)),
            "expansion_p50_ms": float(np.median(graph_latencies)),
            "expansion_p95_ms": float(np.percentile(graph_latencies, 95)),
        },
    }

    print("\n--- Dense Semantic Profile ---")
    print(f"  Fit Time:       {dense_fit_time:.3f} s ({dense_throughput:.1f} docs/sec)")
    print(f"  Peak RAM:       {peak_mem / (1024*1024):.2f} MB")
    print(f"  Index Storage:  {dense_index_bytes / 1024.0:.1f} KB ({dense_index_bytes / num_docs:.1f} bytes/doc)")
    print(f"  CPU Latency:    Mean = {np.mean(dense_latencies):.3f} ms | P95 = {np.percentile(dense_latencies, 95):.3f} ms")

    print("\n--- Multi-Hop Call-Graph Profile ---")
    print(f"  Fit Time:       {graph_fit_time:.3f} s ({graph_throughput:.1f} docs/sec)")
    print(f"  Peak RAM:       {peak_g_mem / (1024*1024):.2f} MB")
    print(f"  Graph Topology: {fg.graph.number_of_nodes()} nodes, {fg.graph.number_of_edges()} edges")
    print(f"  2-Hop Latency:  Mean = {np.mean(graph_latencies):.3f} ms | P95 = {np.percentile(graph_latencies, 95):.3f} ms")

    out_path = os.path.join(os.path.dirname(__file__), "..", "resource_benchmarks.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(profile_results, f, indent=2)
    print(f"\nSaved resource benchmarks to: {out_path}")

    return profile_results


if __name__ == "__main__":
    profile_resources()

