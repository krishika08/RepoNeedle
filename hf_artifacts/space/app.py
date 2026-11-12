"""
RepoNeedle Interactive Playground - Hugging Face Space.
Demonstrates live token-budget-aware repository context retrieval, Change-Impact ranking, and baseline comparisons.
"""

import sys
import os
import json
import time
from typing import Dict, List, Any, Optional

# Ensure bundled reponeedle package is preferred over any global install
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    import gradio as gr
except ImportError:
    gr = None

from reponeedle.models import FileDoc, Query, TaskType, BudgetConfig, RankerType
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex
from reponeedle.core.graph import RepoGraph
from reponeedle.core.tokenizer import estimate_tokens
from reponeedle.core.change_impact import ChangeImpactConfig
from reponeedle.core.packer import CUDPackOptimizer


def create_embedded_corpora() -> Dict[str, List[FileDoc]]:
    """
    Creates lightweight embedded demonstration repository snapshots.
    These are small, self-contained micro-snapshots used exclusively for interactive demonstration.
    """
    # Micro-Flask demonstration snapshot
    flask_files = {
        "src/flask/__init__.py": "'''Flask package.'''\nfrom .app import Flask\nfrom .blueprints import Blueprint\nfrom .ctx import RequestContext\n__version__ = '3.0.0'\n",
        "src/flask/app.py": "'''Flask application.'''\nfrom .ctx import RequestContext\nfrom .wrappers import Request, Response\nfrom .sessions import SecureCookieSessionInterface\nclass Flask:\n    def __init__(self, name):\n        self.blueprints = {}\n        self.session_interface = SecureCookieSessionInterface()\n    def dispatch_request(self):\n        return Response('OK')\n",
        "src/flask/blueprints.py": "'''Blueprints.'''\nclass Blueprint:\n    def __init__(self, name, url_prefix=None):\n        self.name = name\n        self.url_prefix = url_prefix\n",
        "src/flask/ctx.py": "'''Context locals.'''\nclass RequestContext:\n    def __init__(self, app):\n        self.app = app\n    def push(self): pass\n    def pop(self): pass\n",
        "src/flask/sessions.py": "'''Secure Sessions.'''\nclass SecureCookieSessionInterface:\n    def open_session(self, app, req):\n        return {'user': 'guest'}\n    def save_session(self, app, sess, resp):\n        resp.headers['Set-Cookie'] = 'session=val'\n",
        "src/flask/wrappers.py": "'''Request and Response.'''\nclass Request:\n    def get_json(self): return {'data': 1}\nclass Response:\n    def __init__(self, text): self.text = text; self.headers = {}\n",
        "tests/test_app.py": "from src.flask.app import Flask\ndef test_app():\n    app = Flask('test')\n    assert app.dispatch_request().text == 'OK'\n",
        "tests/test_sessions.py": "from src.flask.sessions import SecureCookieSessionInterface\ndef test_sessions():\n    si = SecureCookieSessionInterface()\n    assert si.open_session(None, None)['user'] == 'guest'\n",
        "tests/test_blueprints.py": "from src.flask.blueprints import Blueprint\ndef test_bp():\n    bp = Blueprint('api')\n    assert bp.name == 'api'\n",
    }

    # Micro-Requests demonstration snapshot
    requests_files = {
        "requests/__init__.py": "from .api import get, post\nfrom .sessions import Session\nfrom .models import Response\n",
        "requests/api.py": "from .sessions import Session\ndef get(url): return Session().get(url)\ndef post(url, data=None): return Session().post(url, data=data)\n",
        "requests/sessions.py": "from .models import Request, PreparedRequest, Response\nfrom .adapters import HTTPAdapter\nfrom .auth import HTTPBasicAuth\nclass Session:\n    def __init__(self):\n        self.adapter = HTTPAdapter()\n    def send(self, req): return self.adapter.send(req)\n",
        "requests/models.py": "class Request:\n    def prepare(self): return PreparedRequest()\nclass PreparedRequest:\n    pass\nclass Response:\n    def json(self): return {}\n",
        "requests/adapters.py": "from .models import Response\nclass HTTPAdapter:\n    def send(self, req): return Response()\n",
        "requests/auth.py": "class HTTPBasicAuth:\n    def __init__(self, u, p):\n        self.u = u; self.p = p\n",
        "tests/test_requests.py": "import requests\ndef test_get():\n    r = requests.get('http://test')\n    assert isinstance(r, requests.Response)\n",
        "tests/test_auth.py": "from requests.auth import HTTPBasicAuth\ndef test_auth():\n    a = HTTPBasicAuth('u', 'p')\n    assert a.u == 'u'\n",
        "tests/test_adapters.py": "from requests.adapters import HTTPAdapter\ndef test_adapter():\n    ad = HTTPAdapter()\n    assert ad.send(None) is not None\n",
    }

    corpora = {}
    for name, fdict in [("pallets/flask", flask_files), ("psf/requests", requests_files)]:
        docs = []
        for p, c in fdict.items():
            syms, imps = RepoGraph.extract_python_ast(c, p)
            docs.append(
                FileDoc(
                    path=p,
                    content=c,
                    token_count=estimate_tokens(c),
                    symbols=syms,
                    imports=imps,
                    is_test="test" in p.lower(),
                    line_count=len(c.splitlines()),
                )
            )
        corpora[name] = docs

    return corpora


CORPORA = create_embedded_corpora()

EXAMPLES = [
    [
        "pallets/flask",
        "legacy",
        "auto",
        4000,
        "",
        "Traceback (most recent call last):\n  File \"src/flask/app.py\", line 28, in wsgi_app\n    response = self.dispatch_request()\n  File \"src/flask/wrappers.py\", line 14, in get_json\nAttributeError: 'NoneType' object has no attribute 'get'",
        False,
    ],
    [
        "pallets/flask",
        "change_impact",
        "auto",
        4000,
        "src/flask/sessions.py",
        "Fix cookie attribute handling during session modification in SecureCookieSessionInterface.",
        False,
    ],
    [
        "pallets/flask",
        "change_impact",
        "auto",
        4000,
        "",
        "Fix cookie attribute handling during session modification without specifying a seed file.",
        False,
    ],
    [
        "pallets/flask",
        "legacy",
        "code2test",
        4000,
        "",
        "Find unit and regression tests for SecureCookieSessionInterface cookie saving and modification.",
        False,
    ],
    [
        "psf/requests",
        "legacy",
        "code2test",
        4000,
        "",
        "Find test suites that verify HTTPBasicAuth headers and authentication credentials formatting.",
        False,
    ],
    [
        "pallets/flask",
        "legacy",
        "selective",
        4000,
        "",
        "Fix compilation error in Cargo.toml regarding serde_json feature flag dependency in rust kernel.",
        # Explicit opt-in: the experimental abstention heuristic is disabled by default in 1.2.0.
        True,
    ],
]


def run_reponeedle_demo(
    repo_name: str,
    ranker_choice: str,
    task_mode: str,
    budget: int,
    seed_files_input: str,
    query: str,
    enable_experimental_abstention: bool = False,
):
    if not query.strip():
        return (
            "⚠️ Please enter a query or select an example below.",
            [],
            [],
            "No content to display.",
        )

    docs = CORPORA.get(repo_name, CORPORA["pallets/flask"])
    engine = RepoNeedleEngine.from_documents(docs)

    t_type = TaskType(task_mode) if task_mode != "auto" else TaskType.AUTO
    effective_ranker = ranker_choice.lower().strip()

    # Parse optional seed / anchor files
    seed_list = [s.strip() for s in seed_files_input.replace("\n", ",").split(",") if s.strip()]

    # Construct the Query object
    query_obj = Query(
        text=query.strip(),
        anchor_files=seed_list,
        budget_tokens=budget,
        task_type=t_type,
    )

    t0 = time.perf_counter()
    abstention_opt_in = bool(enable_experimental_abstention)
    res = engine.retrieve(
        query=query_obj,
        ranker=effective_ranker,
        enable_experimental_abstention=abstention_opt_in,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Format diagnostic notes based on ranker and seeds
    if effective_ranker == "change_impact":
        if seed_list:
            ranker_note = (
                f"- **Ranking Engine**: `change_impact` (Opt-in)\n"
                f"- **Active Seed Files**: `{', '.join(seed_list)}`\n"
                f"- **Relationship Scoring**: Seed-relative dependency scoring (AST imports, symbols, calls) and Seed File Suppression (SFS) are **ACTIVE**.\n"
            )
        else:
            ranker_note = (
                f"- **Ranking Engine**: `change_impact` (Opt-in)\n"
                f"- **Active Seed Files**: *(None provided)*\n"
                f"> ℹ️ **Change-Impact Mode (Seedless)**: No seed files provided via `anchor_files`. Lexical and semantic scoring remain active; Test Intent Prior adjustments remain available according to detected intent; seed-relative relationship boosts and Seed File Suppression (SFS) are **INACTIVE**.\n"
            )
    else:
        ranker_note = (
            f"- **Ranking Engine**: `legacy` (V1.0 Default)\n"
            f"- **Behavior**: Standard multi-signal hybrid scoring with workflow routing and AST centrality.\n"
        )

    if abstention_opt_in:
        ranker_note += (
            "- **Experimental Abstention**: **opt-in enabled**. The heuristic is experimental and "
            "uncalibrated (it correctly abstained on 0 of 82 out-of-scope queries in the ARB v2 "
            "selective split); treat an abstention as a diagnostic, not a reliable out-of-scope signal.\n"
        )
    else:
        ranker_note += (
            "- **Experimental Abstention**: disabled (the 1.2.0 default). Ranked context is returned "
            "even for out-of-scope queries.\n"
        )

    # Decision summary
    if res.abstained:
        status_md = (
            f"### 🛑 Decision: **ABSTAINED (experimental abstention, opt-in)**\n\n"
            f"{ranker_note}\n"
            f"- **Confidence Score**: `{res.confidence_score:.3f}` (below the experimental threshold; uncalibrated)\n"
            f"- **Inferred Task**: `{res.task_type.value}`\n"
            f"- **Tokens Consumed**: `0 / {budget}`\n"
            f"- **Latency**: `{elapsed_ms:.2f} ms`\n\n"
            f"> **Diagnostic Reason**: {res.explanation}\n"
        )
        rn_rows = []
        file_preview = "No context returned: the opt-in experimental abstention heuristic abstained on this query."
    else:
        # Tier counts
        tier_counts: Dict[str, int] = {}
        for f in res.selected_files:
            tier_name = f.tier.value.upper()
            tier_counts[tier_name] = tier_counts.get(tier_name, 0) + 1
        tier_summary = ", ".join(f"{cnt} {t}" for t, cnt in tier_counts.items())

        status_md = (
            f"### ✅ Decision: **RETRIEVED CONTEXT**\n\n"
            f"{ranker_note}\n"
            f"- **Retrieved Files**: `{len(res.selected_files)}` ({tier_summary})\n"
            f"- **Tokens Packed**: `{res.total_tokens} / {budget}` ({res.total_tokens / budget * 100:.1f}% capacity)\n"
            f"- **Inferred Task**: `{res.task_type.value}`\n"
            f"- **Confidence Score**: `{res.confidence_score:.3f}`\n"
            f"- **Latency**: `{elapsed_ms:.2f} ms`\n\n"
            f"> {res.explanation}"
        )
        rn_rows = [
            [
                idx + 1,
                f.path,
                f.tier.value.upper(),
                f.token_count,
                f"{f.score:.3f}",
                f.explanation or "Lexical/semantic relevance",
            ]
            for idx, f in enumerate(res.selected_files)
        ]
        file_preview = (
            f"### Selected Context Preview ({res.selected_files[0].path} - Tier: `{res.selected_files[0].tier.value.upper()}`):\n\n"
            f"```python\n{res.selected_files[0].rendered_content}\n```"
        ) if res.selected_files else "No files selected."

    # Baseline comparison (BM25 and RepoMap)
    bm25 = BM25Index().fit(docs)
    bm25_scores = bm25.score(query_obj.text)
    graph = RepoGraph().fit(docs)
    pr_scores = graph.pagerank_scores

    bm25_top = [docs[i].path for i in (-bm25_scores).argsort()[:3]]
    repo_top = [docs[i].path for i in (-pr_scores).argsort()[:3]]

    baseline_rows = []
    max_len = max(len(res.selected_files), len(bm25_top), len(repo_top))
    for r in range(max_len):
        rn_file = res.selected_files[r].path if r < len(res.selected_files) else "(none)"
        bm_file = bm25_top[r] if r < len(bm25_top) else "(none)"
        rm_file = repo_top[r] if r < len(repo_top) else "(none)"
        baseline_rows.append([r + 1, rn_file, bm_file, rm_file])

    return status_md, rn_rows, baseline_rows, file_preview


def build_interface():
    if gr is None:
        print("Note: Gradio is not installed in the local environment. Interface definition requires 'gradio'.")
        return None

    theme = gr.themes.Soft(primary_hue="blue")
    with gr.Blocks(theme=theme, title="RepoNeedle Playground") as demo:
        gr.Markdown(
            "# 🪡 RepoNeedle Playground (V1.2.0)\n"
            "### Token-Budget-Aware, Workflow-Adaptive Repository Context Retrieval for AI Coding Agents\n\n"
            "> ⚠️ **Methodological Disclosure**: This Playground uses embedded demonstration repository snapshots. "
            "It is an interactive demonstration, not a reproduction of the complete ARB v2 evaluation. "
            "The embedded corpora are lightweight demonstration slices, not full upstream repository checkouts."
        )

        with gr.Row():
            with gr.Column(scale=1):
                repo_select = gr.Dropdown(
                    label="Target Repository",
                    choices=["pallets/flask", "psf/requests"],
                    value="pallets/flask",
                )
                ranker_select = gr.Radio(
                    label="Ranking Engine",
                    choices=["legacy", "change_impact"],
                    value="legacy",
                    info="Select 'legacy' for V1.0 behavior, or 'change_impact' for seed-relative dependency scoring.",
                )
                task_select = gr.Dropdown(
                    label="Task Routing Mode",
                    choices=["auto", "code2test", "comment2context", "trace2code", "edit2ripple", "selective"],
                    value="auto",
                )
                budget_slider = gr.Slider(
                    label="Context Token Budget Constraint",
                    minimum=500,
                    maximum=8000,
                    value=4000,
                    step=500,
                )
                seed_input = gr.Textbox(
                    label="Seed / Anchor Files (Optional for Change-Impact)",
                    placeholder="e.g. src/flask/sessions.py (comma-separated)",
                    lines=1,
                    info="Used by Change-Impact ranker for seed-relative graph propagation. Leave empty for seedless mode.",
                )
                query_input = gr.Textbox(
                    label="Coding Task / Issue / Stack Trace",
                    placeholder="Enter an issue description, traceback, or test retrieval request...",
                    lines=4,
                )
                abstention_checkbox = gr.Checkbox(
                    label="Enable experimental abstention (opt-in)",
                    value=False,
                    info=(
                        "Off by default in RepoNeedle 1.2.0. The heuristic is experimental and uncalibrated: "
                        "it correctly abstained on 0 of 82 out-of-scope queries in the ARB v2 selective split."
                    ),
                )
                submit_btn = gr.Button("🔍 Retrieve Context", variant="primary")

            with gr.Column(scale=2):
                status_box = gr.Markdown("### Retrieval Status will appear here.")
                table_rn = gr.Dataframe(
                    headers=["Rank", "File Path", "Tier", "Tokens", "Score", "Explanation"],
                    datatype=["number", "str", "str", "number", "str", "str"],
                    label="RepoNeedle Context Selection (CUD-Pack Optimized)",
                )
                gr.Markdown("### ⚖️ Multi-System Baseline Comparison")
                table_comp = gr.Dataframe(
                    headers=["Rank", "RepoNeedle (Adaptive + Budgeted)", "BM25 (Sparse Lexical)", "RepoMap (PageRank Centrality)"],
                    datatype=["number", "str", "str", "str"],
                    label="Side-by-Side Candidate Ranking",
                )
                preview_box = gr.Markdown("File preview will appear here.")

        gr.Examples(
            examples=EXAMPLES,
            inputs=[repo_select, ranker_select, task_select, budget_slider, seed_input, query_input, abstention_checkbox],
            outputs=[status_box, table_rn, table_comp, preview_box],
            fn=run_reponeedle_demo,
            cache_examples=False,
        )

        submit_btn.click(
            fn=run_reponeedle_demo,
            inputs=[repo_select, ranker_select, task_select, budget_slider, seed_input, query_input, abstention_checkbox],
            outputs=[status_box, table_rn, table_comp, preview_box],
        )

    return demo


if __name__ == "__main__":
    app = build_interface()
    if app is not None:
        app.launch()
