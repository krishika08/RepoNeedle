import sys
import json
import time
from pathlib import Path
from collections import defaultdict
import networkx as nx
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import read_jsonl, target_gold_files, query_text_for_eval, sample_metrics
from reponeedle.models import FileDoc, AblationConfig
from reponeedle.core.graph import RepoGraph
from reponeedle.engine import RepoNeedleEngine

def test_graph_edges():
    print("Testing Graph Connectivity with Manifest-Aware Resolution across Polyglot Repos...")
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    repos_to_test = ["clap-rs/clap", "astral-sh/ruff", "caddyserver/caddy", "vitejs/vite", "tokio-rs/tokio"]

    manifest = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            if row["repo"] in repos_to_test and row["repo"] not in manifest:
                manifest[row["repo"]] = ARB_DIR / row["chunks_path"]

    for repo, cpath in manifest.items():
        chunks = read_jsonl(cpath)
        file_texts = {}
        for c in chunks:
            p = c.get("path")
            t = c.get("text", "")
            if p and (p not in file_texts or len(t) > len(file_texts[p])):
                file_texts[p] = t

        # Extract polyglot symbols
        docs = []
        for p, t in file_texts.items():
            syms, imps = RepoGraph.extract_polyglot_symbols(t[:25000], p)
            docs.append(FileDoc(path=p, content=t[:25000], symbols=syms, imports=imps, is_test="test" in p.lower()))

        g = RepoGraph()
        g.fit(docs)
        print(f"Repo: {repo:20} | Docs: {len(docs):4} | Graph Nodes: {g.graph.number_of_nodes():4} | Graph Edges: {g.graph.number_of_edges():4} | Manifest Crates: {len(g.manifest_crates)}")

if __name__ == "__main__":
    test_graph_edges()

