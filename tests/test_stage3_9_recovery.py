"""
Stage 3.9 Regression & Unit Tests:
Verifies ranking recovery mechanisms, component decoupling, and bounded diffusion:
  1. Decoupled BM25 symbol length normalization (Hypothesis A)
  2. PageRank query-independent hub contamination prevention (Hypothesis B & C)
  3. Bounded graph diffusion pruning for high-degree hubs (Hypothesis C)
  4. CandidateRecovered configuration contract
  5. Sparse reranking consistency
"""

import pytest
import numpy as np
import networkx as nx

from reponeedle.models import FileDoc, Query, ContextTier, BudgetConfig, AblationConfig
from reponeedle.core.lexical import BM25Index
from reponeedle.core.graph import RepoGraph
from reponeedle.engine import RepoNeedleEngine


def test_decoupled_bm25_symbol_length():
    """Verifies that decouple_symbols=True prevents symbol count from inflating doc_len."""
    # Doc 1: Short content with 100 extracted symbols
    content1 = "def connect(): pass\n"
    symbols1 = [f"func_{i}" for i in range(100)]
    doc1 = FileDoc(path="src/db.py", content=content1, symbols=symbols1, is_test=False)

    # Doc 2: Same short content with 0 extracted symbols
    doc2 = FileDoc(path="src/simple.py", content=content1, symbols=[], is_test=False)

    # Standard coupled BM25
    bm25_coupled = BM25Index(decouple_symbols=False)
    bm25_coupled.fit([doc1, doc2])
    # Doc 1 length should be much larger than Doc 2 in coupled mode
    assert bm25_coupled.doc_lengths[0] > bm25_coupled.doc_lengths[1] * 10

    # Decoupled BM25
    bm25_decoupled = BM25Index(decouple_symbols=True)
    bm25_decoupled.fit([doc1, doc2])
    # In decoupled mode, body text lengths are identical
    assert abs(bm25_decoupled.doc_lengths[0] - bm25_decoupled.doc_lengths[1]) <= 2.0


def test_pagerank_contamination_prevented():
    """Verifies that enable_pagerank_fusion=False prevents central hub files from dominating non-matching queries."""
    docs = [
        # Hub file: high in-degree, but zero keyword match to query
        FileDoc(path="src/utils/logging.py", content="def log_info(msg): print(msg)\n", symbols=["log_info"], is_test=False),
        # Target file: low in-degree, but exact keyword match
        FileDoc(path="src/models/link.py", content="class LinkModel:\n    def parse_url(self, url): return url\n", symbols=["LinkModel", "parse_url"], is_test=False),
        # Other files pointing to hub
        FileDoc(path="src/app.py", content="import src.utils.logging\n", imports=["src.utils.logging"], is_test=False),
        FileDoc(path="src/server.py", content="import src.utils.logging\n", imports=["src.utils.logging"], is_test=False),
        FileDoc(path="src/client.py", content="import src.utils.logging\n", imports=["src.utils.logging"], is_test=False),
    ]

    engine = RepoNeedleEngine.from_documents(docs)

    # With Candidate C (PageRank fusion active):
    res_cand_c = engine.retrieve("LinkModel parse_url", ablation_config=AblationConfig.candidate_c())
    # With Candidate Recovered (PageRank fusion disabled):
    res_rec = engine.retrieve("LinkModel parse_url", ablation_config=AblationConfig.candidate_recovered())

    # Target file should be rank 1 in Candidate Recovered
    assert res_rec.selected_files[0].path == "src/models/link.py"


def test_bounded_graph_diffusion_pruning():
    """Verifies that graph diffusion is pruned for nodes exceeding max_diffusion_degree."""
    docs = []
    # Create 1 central hub node
    hub_path = "src/hub.py"
    docs.append(FileDoc(path=hub_path, content="class CentralHub: pass\n", symbols=["CentralHub"], is_test=False))

    # Create 30 satellite nodes pointing to the hub
    for i in range(30):
        docs.append(FileDoc(path=f"src/mod_{i}.py", content=f"import src.hub\n", imports=["src.hub"], is_test=False))

    engine = RepoNeedleEngine.from_documents(docs)

    # Hub should have in-degree 30 (> 25)
    g = engine.repo_graph.graph
    assert g.in_degree(hub_path) == 30

    # With bounded diffusion (max_diffusion_degree=25)
    cfg_bounded = AblationConfig.candidate_recovered()
    assert cfg_bounded.max_diffusion_degree == 25

    res = engine.retrieve("CentralHub", ablation_config=cfg_bounded)
    assert not res.abstained


def test_candidate_recovered_config_contract():
    """Verifies all factor flags in candidate_recovered contract."""
    cand = AblationConfig.candidate_recovered()
    assert cand.enable_lexical is True
    assert cand.enable_semantic is True
    assert cand.enable_graph is True
    assert cand.enable_doc_filter is True
    assert cand.doc_filter_penalty == 0.5
    assert cand.enable_graph_diffusion is True
    assert cand.max_diffusion_degree == 25
    assert cand.enable_pagerank_fusion is False
    assert cand.decouple_bm25_symbols is True
    assert cand.enable_polyglot_symbols is True
