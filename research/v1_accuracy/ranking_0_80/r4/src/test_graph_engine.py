import os
import sys
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))
from reponeedle.models import FileDoc
from reponeedle.core.function_graph import FunctionGraphEngine

# Load sample corpus snapshot: clap-rs
p = "external/agent-retrieval-bench/data/corpus/v2_code2test/clap-rs__clap/68b5ff900bae8ee1a0e328c1a2301a7985e4f1c6.chunks.jsonl"
print("Loading chunks from:", p)
t0 = time.time()
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
print(f"Loaded {len(docs)} code docs in {time.time() - t0:.2f}s")

# Build FunctionGraphEngine
t1 = time.time()
engine = FunctionGraphEngine()
engine.build_graph(docs)
print(f"Built function graph in {time.time() - t1:.2f}s")
print(f"Nodes: {engine.graph.number_of_nodes()}, Edges: {engine.graph.number_of_edges()}")
print(f"Functions registered: {len(engine.functions)}")
print(f"Call sites registered: {len(engine.call_sites)}")
print(f"Edges registered: {len(engine.edges)}")

