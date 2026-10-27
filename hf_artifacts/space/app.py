"""
RepoNeedle Interactive Playground - Hugging Face Space.
Demonstrates live token-budget-aware repository context retrieval and baseline comparison.
"""

import sys
import os
import json
import time
from typing import Dict, List, Any

# Ensure local packages are importable
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    import gradio as gr
except ImportError:
    gr = None
from reponeedle.models import FileDoc, Query, TaskType, BudgetConfig
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex
from reponeedle.core.graph import RepoGraph
from reponeedle.core.tokenizer import estimate_tokens

# Mock / embedded corpora for real in-space execution
from reponeedle.core.graph import RepoGraph


def create_embedded_corpora() -> Dict[str, List[FileDoc]]:
    """Creates the standard permissively licensed benchmark corpora."""
    # Micro-Flask
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
    
    # Micro-Requests
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
            docs.append(FileDoc(
                path=p,
                content=c,
                token_count=estimate_tokens(c),
                symbols=syms,
                imports=imps,
                is_test="test" in p.lower(),
                line_count=len(c.splitlines()),
            ))
        corpora[name] = docs

    return corpora


CORPORA = create_embedded_corpora()

EXAMPLES = [
    [
        "pallets/flask",
        "auto",
        4000,
        "Traceback (most recent call last):\n  File \"src/flask/app.py\", line 28, in wsgi_app\n    response = self.dispatch_request()\n  File \"src/flask/wrappers.py\", line 14, in get_json\nAttributeError: 'NoneType' object has no attribute 'get'",
    ],
    [
        "pallets/flask",
        "code2test",
        4000,
        "Find unit and regression tests for SecureCookieSessionInterface cookie saving and modification.",
    ],
    [
        "pallets/flask",
        "edit2ripple",
        4000,
        "We are changing RequestContext in src/flask/ctx.py. What files import or depend on RequestContext?",
    ],
    [
        "pallets/flask",
        "selective",
        4000,
        "Fix compilation error in Cargo.toml regarding serde_json feature flag dependency in rust kernel.",
    ],
    [
        "psf/requests",
        "code2test",
        4000,
        "Find test suites that verify HTTPBasicAuth headers and authentication credentials formatting.",
    ],
]


def run_reponeedle_demo(repo_name: str, task_mode: str, budget: int, query: str):
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
    t0 = time.perf_counter()
    res = engine.retrieve(query=query, budget_tokens=budget, task_type=t_type)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Decision summary
    if res.abstained:
        status_md = (
            f"### 🛑 Decision: **ABSTAINED**\n\n"
            f"- **Confidence Score**: `{res.confidence_score:.3f}` (Below threshold)\n"
            f"- **Inferred Task**: `{res.task_type.value}`\n"
            f"- **Tokens Consumed**: `0 / {budget}` (**100% Budget Saved!**)\n"
            f"- **Latency**: `{elapsed_ms:.2f} ms`\n\n"
            f"> **Diagnostic Explanation**: {res.explanation}"
        )
        rn_rows = []
        file_preview = "System abstained from context retrieval to prevent context window dilution."
    else:
        status_md = (
            f"### ✅ Decision: **RETRIEVED CONTEXT**\n\n"
            f"- **Retrieved Files**: `{len(res.selected_files)}`\n"
            f"- **Tokens Packed**: `{res.total_tokens} / {budget}`\n"
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
                f.explanation,
            ]
            for idx, f in enumerate(res.selected_files)
        ]
        file_preview = (
            f"### Selected Context Preview ({res.selected_files[0].path} - Tier: {res.selected_files[0].tier.value.upper()}):\n\n"
            f"```python\n{res.selected_files[0].rendered_content}\n```"
        ) if res.selected_files else "No files selected."

    # Baseline comparison (BM25 and RepoMap)
    bm25 = BM25Index().fit(docs)
    bm25_scores = bm25.score(query)
    graph = RepoGraph().fit(docs)
    pr_scores = graph.pagerank_scores

    # Rank baselines
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
    theme = gr.themes.Soft(primary_hue="blue")
    with gr.Blocks(theme=theme, title="RepoNeedle Playground") as demo:
        gr.Markdown(
            "# 🪡 RepoNeedle Playground\n"
            "### Token-Budget-Aware, Workflow-Adaptive Repository Context Retrieval for AI Coding Agents\n"
            "RepoNeedle finds the exact repository files needed for coding tasks under strict context-token constraints."
        )

        with gr.Row():
            with gr.Column(scale=1):
                repo_select = gr.Dropdown(
                    label="Target Repository",
                    choices=["pallets/flask", "psf/requests"],
                    value="pallets/flask",
                )
                task_select = gr.Dropdown(
                    label="Task Routing Mode",
                    choices=["auto", "code2test", "comment2context", "trace2code", "edit2ripple", "selective"],
                    value="auto",
                )
                budget_slider = gr.Slider(
                    label="Token Budget Limit",
                    minimum=500,
                    maximum=8000,
                    value=4000,
                    step=500,
                )
                query_input = gr.Textbox(
                    label="Coding Task / Issue / Stack Trace",
                    placeholder="Enter an issue description, traceback, or test retrieval request...",
                    lines=4,
                )
                submit_btn = gr.Button("🔍 Retrieve Context", variant="primary")

            with gr.Column(scale=2):
                status_box = gr.Markdown("### Retrieval Status will appear here.")
                table_rn = gr.Dataframe(
                    headers=["Rank", "File Path", "Tier", "Tokens", "Score", "Explanation"],
                    datatype=["number", "str", "str", "number", "str", "str"],
                    label="RepoNeedle Packed Context Selection",
                )
                gr.Markdown("### ⚖️ Multi-System Baseline Comparison")
                table_comp = gr.Dataframe(
                    headers=["Rank", "RepoNeedle (Adaptive + Budgeted)", "BM25 (Sparse Lexical)", "RepoMap (PageRank Centrality)"],
                    datatype=["number", "str", "str", "str"],
                    label="Side-by-Side Comparison",
                )
                preview_box = gr.Markdown("File preview will appear here.")

        gr.Examples(
            examples=EXAMPLES,
            inputs=[repo_select, task_select, budget_slider, query_input],
            outputs=[status_box, table_rn, table_comp, preview_box],
            fn=run_reponeedle_demo,
            cache_examples=False,
        )

        submit_btn.click(
            fn=run_reponeedle_demo,
            inputs=[repo_select, task_select, budget_slider, query_input],
            outputs=[status_box, table_rn, table_comp, preview_box],
        )

    return demo


if __name__ == "__main__":
    app = build_interface()
    app.launch()
