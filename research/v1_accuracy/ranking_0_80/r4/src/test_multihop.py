import os
import sys
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")))
from reponeedle.models import FileDoc
from reponeedle.core.function_graph import FunctionGraphEngine
from multihop_graph import MultiHopGraphEngine

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

fg = FunctionGraphEngine()
fg.build_graph(docs)
engine = MultiHopGraphEngine(fg, hop_decay=0.5, hub_degree_threshold=5)

# Seed from a core command file
seeds = {"clap_builder/src/builder/command.rs": 10.0}

print("=== 1-Hop Expansion ===")
exp1 = engine.expand_multihop(seeds, max_hops=1, intent="reference_seeking")
print(f"1-Hop expanded to {len(exp1)} nodes:")
for k, v in sorted(exp1.items(), key=lambda x: -x[1])[:5]:
    print(f"  {k}: {v:.3f}")

print("\n=== 2-Hop Expansion ===")
exp2 = engine.expand_multihop(seeds, max_hops=2, intent="reference_seeking")
print(f"2-Hop expanded to {len(exp2)} nodes:")
for k, v in sorted(exp2.items(), key=lambda x: -x[1])[:5]:
    print(f"  {k}: {v:.3f}")

