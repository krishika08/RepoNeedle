"""Public demo API for the RepoNeedle Playground.

This service exposes the existing embedded Flask/Requests demonstration corpora.
It does not accept repository uploads and does not persist visitor queries.
"""
from __future__ import annotations

import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Reuse the exact embedded demo snapshots already shipped with the HF Space.
ROOT = Path(__file__).resolve().parent
SPACE_DIR = ROOT / "hf_artifacts" / "space"
sys.path.insert(0, str(SPACE_DIR))

# app.py handles Gradio as optional; it can be imported without installing Gradio.
from app import CORPORA  # noqa: E402
from reponeedle.engine import RepoNeedleEngine  # noqa: E402
from reponeedle.models import Query, TaskType  # noqa: E402
from reponeedle.core.lexical import BM25Index  # noqa: E402
from reponeedle.core.graph import RepoGraph  # noqa: E402


app = FastAPI(
    title="RepoNeedle Demo API",
    description=(
        "Browser-facing API for the RepoNeedle V1.1.0 demonstration. "
        "Uses embedded sample snapshots of Flask and Requests."
    ),
    version="1.1.0",
)

# Hugging Face Static Spaces are served from a different origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class RetrieveRequest(BaseModel):
    repo_name: Literal["pallets/flask", "psf/requests"] = "pallets/flask"
    ranker: Literal["legacy", "change_impact"] = "legacy"
    task_mode: Literal[
        "auto", "code2test", "comment2context", "trace2code", "edit2ripple", "selective"
    ] = "auto"
    budget_tokens: int = Field(default=4000, ge=500, le=8000)
    seed_files: list[str] = Field(default_factory=list, max_length=10)
    query: str = Field(min_length=2, max_length=3000)


@lru_cache(maxsize=2)
def get_engine(repo_name: str) -> RepoNeedleEngine:
    docs = CORPORA.get(repo_name)
    if docs is None:
        raise ValueError("Unknown demonstration repository")
    return RepoNeedleEngine.from_documents(docs)


@lru_cache(maxsize=2)
def get_baselines(repo_name: str):
    docs = CORPORA[repo_name]
    bm25 = BM25Index().fit(docs)
    graph = RepoGraph().fit(docs)
    return docs, bm25, graph


@app.get("/")
def root():
    return {
        "name": "RepoNeedle Demo API",
        "version": "1.1.0",
        "health": "/health",
        "docs": "/docs",
        "disclosure": "Embedded demonstration snapshots only; not full upstream repositories.",
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "reponeedle-demo-api", "version": "1.1.0"}


@app.post("/api/retrieve")
def retrieve_context(payload: RetrieveRequest):
    query_text = payload.query.strip()
    if not query_text:
        raise HTTPException(status_code=422, detail="Please enter a non-empty coding task or query.")
    if any(len(seed.strip()) > 180 for seed in payload.seed_files):
        raise HTTPException(status_code=422, detail="Each seed file path must be 180 characters or fewer.")

    try:
        engine = get_engine(payload.repo_name)
        docs, bm25, graph = get_baselines(payload.repo_name)

        seed_files = [seed.strip() for seed in payload.seed_files if seed.strip()]
        task = TaskType(payload.task_mode)
        query_obj = Query(
            text=query_text,
            anchor_files=seed_files,
            budget_tokens=payload.budget_tokens,
            task_type=task,
        )

        started = time.perf_counter()
        result = engine.retrieve(query=query_obj, ranker=payload.ranker)
        elapsed_ms = (time.perf_counter() - started) * 1000

        selected = []
        for index, item in enumerate(result.selected_files, start=1):
            selected.append({
                "rank": index,
                "path": item.path,
                "tier": item.tier.value.upper(),
                "tokens": item.token_count,
                "score": round(float(item.score), 5),
                "explanation": item.explanation or "Lexical/semantic relevance",
                "content": item.rendered_content,
            })

        bm25_scores = bm25.score(query_text)
        graph_scores = graph.pagerank_scores
        bm25_top = sorted(range(len(bm25_scores)), key=lambda i: float(bm25_scores[i]), reverse=True)[:3]
        graph_top = sorted(range(len(graph_scores)), key=lambda i: float(graph_scores[i]), reverse=True)[:3]

        comparison = []
        max_rows = max(len(selected), len(bm25_top), len(graph_top))
        for index in range(max_rows):
            comparison.append({
                "rank": index + 1,
                "reponeedle": selected[index]["path"] if index < len(selected) else "(none)",
                "bm25": docs[bm25_top[index]].path if index < len(bm25_top) else "(none)",
                "repomap": docs[graph_top[index]].path if index < len(graph_top) else "(none)",
            })

        if payload.ranker == "change_impact":
            ranker_note = (
                "Change-Impact is enabled. Seed-relative dependency boosts and seed-file "
                "suppression are active only when anchor files are supplied."
            )
            if not seed_files:
                ranker_note += " No seed files were supplied, so seed-relative boosts and suppression are inactive."
        else:
            ranker_note = "Legacy ranking is active (the backwards-compatible default ranker)."

        return {
            "query": query_text,
            "repository": payload.repo_name,
            "ranker": payload.ranker,
            "ranker_note": ranker_note,
            "decision": "ABSTAINED" if result.abstained else "RETRIEVED CONTEXT",
            "abstained": bool(result.abstained),
            "task_type": result.task_type.value,
            "confidence": round(float(result.confidence_score), 4),
            "tokens_used": int(result.total_tokens),
            "token_budget": int(payload.budget_tokens),
            "candidate_count": int(result.candidate_count),
            "latency_ms": round(elapsed_ms, 2),
            "explanation": result.explanation,
            "selected_files": selected,
            "comparison": comparison,
            "preview": selected[0] if selected else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        # Do not return stack traces or local filesystem details to public callers.
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {type(exc).__name__}: {exc}") from exc
