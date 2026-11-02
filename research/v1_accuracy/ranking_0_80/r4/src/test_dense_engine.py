import os
import sys
import json
import time
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))
from reponeedle.models import FileDoc
from dense_engine import DenseSemanticEngine

# Load sample corpus snapshot: clap-rs
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

# Test DenseSemanticEngine
t0 = time.time()
engine = DenseSemanticEngine(dimension=128, metric="cosine")
engine.fit(docs)
fit_time = time.time() - t0
print(f"Fit DenseSemanticEngine on {len(docs)} docs in {fit_time:.3f}s")
print(f"Doc embeddings shape: {engine.doc_embeddings.shape}")
print(f"Singular values preview: {engine.singular_values[:5]}")

query = "quote empty default values in help template"
t1 = time.time()
q_emb = engine.embed_query(query)
scores = engine.score(query)
score_time = time.time() - t1
print(f"Inference latency: {score_time*1000.0:.3f}ms")
top5_idx = np.argsort(scores)[::-1][:5]
print("Top 5 Dense Semantic Matches:")
for idx in top5_idx:
    print(f"  Score: {scores[idx]:.4f} | Path: {engine.doc_paths[idx]}")

