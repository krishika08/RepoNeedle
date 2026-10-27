"""
RepoNeedle-Bench dataset generator and benchmark suite.
Generates structured repository corpora and realistic evaluation tasks across 5 categories:
code2test, comment2context, trace2code, edit2ripple, and selective.
All repositories are permissively licensed (BSD-3-Clause, Apache-2.0, MIT).
"""

import json
import os
from typing import List, Dict, Any, Set
from pydantic import BaseModel, Field

from reponeedle.models import FileDoc, TaskType
from reponeedle.core.tokenizer import estimate_tokens
from reponeedle.core.graph import RepoGraph


class BenchmarkSample(BaseModel):
    id: str
    repo_name: str
    task_type: TaskType
    query: str
    gold_files: List[str] = Field(default_factory=list)
    anchor_files: List[str] = Field(default_factory=list)
    budget_tokens: int = 4000
    description: str = ""
    is_held_out_repo: bool = False


def build_flask_corpus() -> List[FileDoc]:
    """Generates micro-Flask repository (BSD-3-Clause)."""
    raw_files = {
        "src/flask/__init__.py": (
            "'''Flask web framework package.'''\n"
            "from .app import Flask\n"
            "from .blueprints import Blueprint\n"
            "from .ctx import RequestContext, AppContext\n"
            "from .helpers import url_for, make_response, flash\n"
            "from .wrappers import Request, Response\n"
            "__version__ = '3.0.0'\n"
        ),
        "src/flask/app.py": (
            "'''Core Flask application implementation.'''\n"
            "from .ctx import RequestContext, AppContext\n"
            "from .wrappers import Request, Response\n"
            "from .sessions import SecureCookieSessionInterface\n"
            "class Flask:\n"
            "    def __init__(self, import_name: str):\n"
            "        self.import_name = import_name\n"
            "        self.blueprints = {}\n"
            "        self.session_interface = SecureCookieSessionInterface()\n"
            "        self.view_functions = {}\n"
            "    def add_url_rule(self, rule: str, endpoint: str, view_func):\n"
            "        self.view_functions[endpoint] = view_func\n"
            "    def route(self, rule: str):\n"
            "        def decorator(f):\n"
            "            self.add_url_rule(rule, f.__name__, f)\n"
            "            return f\n"
            "        return decorator\n"
            "    def wsgi_app(self, environ, start_response):\n"
            "        ctx = RequestContext(self, environ)\n"
            "        ctx.push()\n"
            "        try:\n"
            "            response = self.dispatch_request()\n"
            "            return response(environ, start_response)\n"
            "        finally:\n"
            "            ctx.pop()\n"
            "    def dispatch_request(self):\n"
            "        req = Request(self)\n"
            "        return self.view_functions.get(req.endpoint, Response('Not Found', 404))\n"
            "    def register_blueprint(self, blueprint):\n"
            "        self.blueprints[blueprint.name] = blueprint\n"
            "        blueprint.register(self)\n"
        ),
        "src/flask/blueprints.py": (
            "'''Blueprint modular application organization.'''\n"
            "from .helpers import url_for\n"
            "class Blueprint:\n"
            "    def __init__(self, name: str, import_name: str, url_prefix: str = None):\n"
            "        self.name = name\n"
            "        self.import_name = import_name\n"
            "        self.url_prefix = url_prefix\n"
            "        self.deferred_functions = []\n"
            "    def route(self, rule: str):\n"
            "        def decorator(f):\n"
            "            self.deferred_functions.append((rule, f))\n"
            "            return f\n"
            "        return decorator\n"
            "    def register(self, app):\n"
            "        for rule, func in self.deferred_functions:\n"
            "            full_rule = (self.url_prefix or '') + rule\n"
            "            app.add_url_rule(full_rule, f'{self.name}.{func.__name__}', func)\n"
        ),
        "src/flask/ctx.py": (
            "'''Request and Application context locals.'''\n"
            "class AppContext:\n"
            "    def __init__(self, app):\n"
            "        self.app = app\n"
            "        self.g = {}\n"
            "    def push(self):\n"
            "        pass\n"
            "    def pop(self):\n"
            "        pass\n"
            "class RequestContext:\n"
            "    def __init__(self, app, environ):\n"
            "        self.app = app\n"
            "        self.environ = environ\n"
            "        self.request = app.request_class(environ) if hasattr(app, 'request_class') else None\n"
            "        self.session = None\n"
            "    def push(self):\n"
            "        if self.app.session_interface:\n"
            "            self.session = self.app.session_interface.open_session(self.app, self.request)\n"
            "    def pop(self):\n"
            "        pass\n"
        ),
        "src/flask/sessions.py": (
            "'''Secure Cookie and Server-side session interfaces.'''\n"
            "class SessionMixin(dict):\n"
            "    modified = False\n"
            "    accessed = False\n"
            "class SecureCookieSession(SessionMixin):\n"
            "    pass\n"
            "class SessionInterface:\n"
            "    def open_session(self, app, request):\n"
            "        raise NotImplementedError()\n"
            "    def save_session(self, app, session, response):\n"
            "        raise NotImplementedError()\n"
            "class SecureCookieSessionInterface(SessionInterface):\n"
            "    def __init__(self, cookie_name: str = 'session'):\n"
            "        self.cookie_name = cookie_name\n"
            "    def open_session(self, app, request):\n"
            "        cookie = request.cookies.get(self.cookie_name) if request and hasattr(request, 'cookies') else None\n"
            "        if not cookie:\n"
            "            return SecureCookieSession()\n"
            "        return SecureCookieSession({'user': 'authenticated'})\n"
            "    def save_session(self, app, session, response):\n"
            "        if session and session.modified:\n"
            "            response.set_cookie(self.cookie_name, 'encoded_session')\n"
        ),
        "src/flask/wrappers.py": (
            "'''WSGI Request and Response objects.'''\n"
            "class Request:\n"
            "    def __init__(self, environ):\n"
            "        self.environ = environ\n"
            "        self.cookies = {}\n"
            "        self.endpoint = environ.get('PATH_INFO', '/')\n"
            "        self.headers = {}\n"
            "    def get_json(self, force: bool = False):\n"
            "        if 'application/json' in self.headers.get('Content-Type', '') or force:\n"
            "            return {'parsed': True}\n"
            "        return None\n"
            "class Response:\n"
            "    def __init__(self, response_text: str, status: int = 200):\n"
            "        self.response = [response_text.encode('utf-8')]\n"
            "        self.status = status\n"
            "        self.headers = [('Content-Type', 'text/html; charset=utf-8')]\n"
            "    def set_cookie(self, key: str, value: str):\n"
            "        self.headers.append(('Set-Cookie', f'{key}={value}'))\n"
        ),
        "src/flask/helpers.py": (
            "'''Helper functions for response creation, flashing, and url formatting.'''\n"
            "from .wrappers import Response\n"
            "def make_response(*args):\n"
            "    if not args:\n"
            "        return Response('')\n"
            "    if isinstance(args[0], Response):\n"
            "        return args[0]\n"
            "    return Response(str(args[0]))\n"
            "def url_for(endpoint: str, **values):\n"
            "    return f'/{endpoint}'\n"
            "def flash(message: str, category: str = 'message'):\n"
            "    pass\n"
        ),
        "tests/__init__.py": "# Flask test suite\n",
        "tests/test_app.py": (
            "'''Unit tests for core Flask application.'''\n"
            "from src.flask.app import Flask\n"
            "from src.flask.wrappers import Response\n"
            "def test_app_route():\n"
            "    app = Flask('test_app')\n"
            "    @app.route('/hello')\n"
            "    def hello():\n"
            "        return Response('Hello World')\n"
            "    assert '/hello' in app.view_functions or 'hello' in app.view_functions\n"
            "def test_wsgi_dispatch():\n"
            "    app = Flask('test_app')\n"
            "    res = app.dispatch_request()\n"
            "    assert res.status in (200, 404)\n"
        ),
        "tests/test_blueprints.py": (
            "'''Tests for Blueprint registration and prefix handling.'''\n"
            "from src.flask.app import Flask\n"
            "from src.flask.blueprints import Blueprint\n"
            "def test_blueprint_prefix():\n"
            "    app = Flask('test_bp')\n"
            "    bp = Blueprint('admin', 'admin_pkg', url_prefix='/admin')\n"
            "    @bp.route('/dashboard')\n"
            "    def dashboard():\n"
            "        return 'Dashboard'\n"
            "    app.register_blueprint(bp)\n"
            "    assert 'admin' in app.blueprints\n"
        ),
        "tests/test_sessions.py": (
            "'''Tests for SecureCookieSessionInterface and session persistence.'''\n"
            "from src.flask.sessions import SecureCookieSessionInterface, SecureCookieSession\n"
            "from src.flask.wrappers import Request, Response\n"
            "def test_open_session():\n"
            "    interface = SecureCookieSessionInterface()\n"
            "    sess = interface.open_session(None, None)\n"
            "    assert isinstance(sess, SecureCookieSession)\n"
            "def test_save_session_cookie():\n"
            "    interface = SecureCookieSessionInterface()\n"
            "    sess = SecureCookieSession({'user': 'test'})\n"
            "    sess.modified = True\n"
            "    resp = Response('ok')\n"
            "    interface.save_session(None, sess, resp)\n"
            "    assert any('session=' in h[1] for h in resp.headers if h[0] == 'Set-Cookie')\n"
        ),
        "tests/test_helpers.py": (
            "'''Tests for make_response and url_for helpers.'''\n"
            "from src.flask.helpers import make_response, url_for\n"
            "from src.flask.wrappers import Response\n"
            "def test_make_response():\n"
            "    r = make_response('body text')\n"
            "    assert isinstance(r, Response)\n"
            "def test_url_for():\n"
            "    assert url_for('index') == '/index'\n"
        ),
    }

    docs = []
    for path, content in raw_files.items():
        symbols, imports = RepoGraph.extract_python_ast(content, path)
        docs.append(
            FileDoc(
                path=path,
                content=content,
                token_count=estimate_tokens(content),
                language="python",
                symbols=symbols,
                imports=imports,
                is_test="test" in path.lower(),
                line_count=len(content.splitlines()),
            )
        )
    return docs


def build_requests_corpus() -> List[FileDoc]:
    """Generates micro-Requests repository (Apache-2.0)."""
    raw_files = {
        "requests/__init__.py": (
            "'''Requests HTTP Client package.'''\n"
            "from .api import get, post, put, delete, request\n"
            "from .sessions import Session\n"
            "from .models import Request, Response, PreparedRequest\n"
            "from .exceptions import RequestException, HTTPError\n"
            "__version__ = '2.31.0'\n"
        ),
        "requests/api.py": (
            "'''Direct HTTP request convenience wrappers.'''\n"
            "from .sessions import Session\n"
            "def request(method: str, url: str, **kwargs):\n"
            "    with Session() as session:\n"
            "        return session.request(method=method, url=url, **kwargs)\n"
            "def get(url: str, **kwargs):\n"
            "    return request('get', url, **kwargs)\n"
            "def post(url: str, data=None, json=None, **kwargs):\n"
            "    return request('post', url, data=data, json=json, **kwargs)\n"
        ),
        "requests/sessions.py": (
            "'''Client Session management, cookie persistence, and connection reuse.'''\n"
            "from .models import Request, PreparedRequest, Response\n"
            "from .adapters import HTTPAdapter\n"
            "from .auth import HTTPBasicAuth\n"
            "class Session:\n"
            "    def __init__(self):\n"
            "        self.headers = {'User-Agent': 'python-requests/2.31.0'}\n"
            "        self.auth = None\n"
            "        self.adapters = {'http://': HTTPAdapter(), 'https://': HTTPAdapter()}\n"
            "        self.cookies = {}\n"
            "    def request(self, method: str, url: str, params=None, data=None, headers=None, auth=None):\n"
            "        req = Request(method=method.upper(), url=url, headers=headers, auth=auth or self.auth)\n"
            "        prep = req.prepare()\n"
            "        return self.send(prep)\n"
            "    def send(self, request: PreparedRequest, **kwargs) -> Response:\n"
            "        adapter = self.get_adapter(request.url)\n"
            "        return adapter.send(request, **kwargs)\n"
            "    def get_adapter(self, url: str) -> HTTPAdapter:\n"
            "        for prefix, adapter in self.adapters.items():\n"
            "            if url.startswith(prefix):\n"
            "                return adapter\n"
            "        return HTTPAdapter()\n"
            "    def __enter__(self):\n"
            "        return self\n"
            "    def __exit__(self, *args):\n"
            "        pass\n"
        ),
        "requests/models.py": (
            "'''Core Request and Response representations.'''\n"
            "from .exceptions import HTTPError\n"
            "class Request:\n"
            "    def __init__(self, method: str, url: str, headers=None, auth=None):\n"
            "        self.method = method\n"
            "        self.url = url\n"
            "        self.headers = headers or {}\n"
            "        self.auth = auth\n"
            "    def prepare(self) -> 'PreparedRequest':\n"
            "        p = PreparedRequest()\n"
            "        p.method = self.method\n"
            "        p.url = self.url\n"
            "        p.headers = self.headers.copy()\n"
            "        if self.auth:\n"
            "            p = self.auth(p)\n"
            "        return p\n"
            "class PreparedRequest:\n"
            "    def __init__(self):\n"
            "        self.method = None\n"
            "        self.url = None\n"
            "        self.headers = {}\n"
            "        self.body = None\n"
            "class Response:\n"
            "    def __init__(self):\n"
            "        self.status_code = 200\n"
            "        self.headers = {}\n"
            "        self.content = b''\n"
            "        self.url = ''\n"
            "    def json(self):\n"
            "        import json\n"
            "        return json.loads(self.content.decode('utf-8'))\n"
            "    def raise_for_status(self):\n"
            "        if 400 <= self.status_code < 600:\n"
            "            raise HTTPError(f'Status {self.status_code}')\n"
        ),
        "requests/adapters.py": (
            "'''Transport adapters for HTTP/HTTPS pools.'''\n"
            "from .models import Response, PreparedRequest\n"
            "from .exceptions import ConnectionError\n"
            "class BaseAdapter:\n"
            "    def send(self, request: PreparedRequest, **kwargs):\n"
            "        raise NotImplementedError()\n"
            "class HTTPAdapter(BaseAdapter):\n"
            "    def __init__(self, pool_connections: int = 10, max_retries: int = 3):\n"
            "        self.pool_connections = pool_connections\n"
            "        self.max_retries = max_retries\n"
            "    def send(self, request: PreparedRequest, **kwargs) -> Response:\n"
            "        resp = Response()\n"
            "        resp.url = request.url\n"
            "        resp.status_code = 200\n"
            "        resp.content = b'{\"success\": true}'\n"
            "        return resp\n"
        ),
        "requests/auth.py": (
            "'''Authentication handlers (Basic, Digest).'''\n"
            "import base64\n"
            "from .models import PreparedRequest\n"
            "class AuthBase:\n"
            "    def __call__(self, r: PreparedRequest) -> PreparedRequest:\n"
            "        raise NotImplementedError()\n"
            "class HTTPBasicAuth(AuthBase):\n"
            "    def __init__(self, username: str, password: str):\n"
            "        self.username = username\n"
            "        self.password = password\n"
            "    def __call__(self, r: PreparedRequest) -> PreparedRequest:\n"
            "        creds = f'{self.username}:{self.password}'.encode('latin1')\n"
            "        auth_header = 'Basic ' + base64.b64encode(creds).decode('ascii')\n"
            "        r.headers['Authorization'] = auth_header\n"
            "        return r\n"
        ),
        "requests/exceptions.py": (
            "'''Exception hierarchy for Requests.'''\n"
            "class RequestException(IOError):\n"
            "    '''Base request exception.'''\n"
            "class HTTPError(RequestException):\n"
            "    '''HTTP error code response.'''\n"
            "class ConnectionError(RequestException):\n"
            "    '''Network connection failure.'''\n"
            "class Timeout(RequestException):\n"
            "    '''Request socket timeout.'''\n"
        ),
        "tests/test_requests.py": (
            "'''Tests for top-level requests API and session routing.'''\n"
            "import requests\n"
            "def test_get_request():\n"
            "    resp = requests.get('http://example.com')\n"
            "    assert resp.status_code == 200\n"
            "def test_post_json():\n"
            "    resp = requests.post('http://example.com', json={'key': 'val'})\n"
            "    assert resp.status_code == 200\n"
        ),
        "tests/test_models.py": (
            "'''Tests for Request, Response, and PreparedRequest.'''\n"
            "from requests.models import Request, Response\n"
            "from requests.exceptions import HTTPError\n"
            "import pytest\n"
            "def test_response_json():\n"
            "    r = Response()\n"
            "    r.content = b'{\"msg\": \"hello\"}'\n"
            "    assert r.json() == {'msg': 'hello'}\n"
            "def test_raise_for_status():\n"
            "    r = Response()\n"
            "    r.status_code = 500\n"
            "    with pytest.raises(HTTPError):\n"
            "        r.raise_for_status()\n"
        ),
        "tests/test_auth.py": (
            "'''Tests for HTTPBasicAuth credentials formatting.'''\n"
            "from requests.auth import HTTPBasicAuth\n"
            "from requests.models import Request\n"
            "def test_basic_auth_header():\n"
            "    auth = HTTPBasicAuth('alice', 'secret123')\n"
            "    req = Request('GET', 'http://example.com', auth=auth)\n"
            "    prep = req.prepare()\n"
            "    assert prep.headers['Authorization'].startswith('Basic ')\n"
        ),
        "tests/test_adapters.py": (
            "'''Tests for HTTPAdapter connection configuration.'''\n"
            "from requests.adapters import HTTPAdapter\n"
            "from requests.models import PreparedRequest\n"
            "def test_adapter_send():\n"
            "    adapter = HTTPAdapter()\n"
            "    p = PreparedRequest()\n"
            "    p.url = 'http://test.org'\n"
            "    res = adapter.send(p)\n"
            "    assert res.status_code == 200\n"
        ),
    }

    docs = []
    for path, content in raw_files.items():
        symbols, imports = RepoGraph.extract_python_ast(content, path)
        docs.append(
            FileDoc(
                path=path,
                content=content,
                token_count=estimate_tokens(content),
                language="python",
                symbols=symbols,
                imports=imports,
                is_test="test" in path.lower(),
                line_count=len(content.splitlines()),
            )
        )
    return docs


def build_fastapi_held_out_corpus() -> List[FileDoc]:
    """Generates held-out FastAPI repository (MIT License)."""
    raw_files = {
        "fastapi/__init__.py": (
            "'''FastAPI web framework package.'''\n"
            "from .applications import FastAPI\n"
            "from .routing import APIRouter, APIRoute\n"
            "from .params import Depends, Security, Body, Query, Header, Path\n"
            "from .responses import JSONResponse, Response\n"
            "from .exceptions import HTTPException\n"
            "__version__ = '0.110.0'\n"
        ),
        "fastapi/applications.py": (
            "'''Core FastAPI Application.'''\n"
            "from .routing import APIRouter\n"
            "from .responses import JSONResponse\n"
            "class FastAPI:\n"
            "    def __init__(self, title: str = 'FastAPI App'):\n"
            "        self.title = title\n"
            "        self.router = APIRouter()\n"
            "    def get(self, path: str, **kwargs):\n"
            "        return self.router.get(path, **kwargs)\n"
            "    def post(self, path: str, **kwargs):\n"
            "        return self.router.post(path, **kwargs)\n"
            "    def include_router(self, router: APIRouter, prefix: str = ''):\n"
            "        self.router.include_router(router, prefix=prefix)\n"
            "    async def __call__(self, scope, receive, send):\n"
            "        await self.router(scope, receive, send)\n"
        ),
        "fastapi/routing.py": (
            "'''API routing and endpoint dependency resolution.'''\n"
            "from .responses import JSONResponse, Response\n"
            "from .dependencies.utils import solve_dependencies\n"
            "class APIRoute:\n"
            "    def __init__(self, path: str, endpoint, methods=None):\n"
            "        self.path = path\n"
            "        self.endpoint = endpoint\n"
            "        self.methods = methods or ['GET']\n"
            "    async def handle(self, request):\n"
            "        values, errors = await solve_dependencies(request, self.endpoint)\n"
            "        if errors:\n"
            "            return JSONResponse({'errors': errors}, status_code=422)\n"
            "        res = await self.endpoint(**values) if hasattr(self.endpoint, '__await__') else self.endpoint(**values)\n"
            "        return JSONResponse(res)\n"
            "class APIRouter:\n"
            "    def __init__(self):\n"
            "        self.routes = []\n"
            "    def add_api_route(self, path: str, endpoint, methods=None):\n"
            "        route = APIRoute(path, endpoint, methods)\n"
            "        self.routes.append(route)\n"
            "    def get(self, path: str, **kwargs):\n"
            "        def dec(f):\n"
            "            self.add_api_route(path, f, ['GET'])\n"
            "            return f\n"
            "        return dec\n"
            "    def post(self, path: str, **kwargs):\n"
            "        def dec(f):\n"
            "            self.add_api_route(path, f, ['POST'])\n"
            "            return f\n"
            "        return dec\n"
            "    def include_router(self, router: 'APIRouter', prefix: str = ''):\n"
            "        for r in router.routes:\n"
            "            self.add_api_route(prefix + r.path, r.endpoint, r.methods)\n"
        ),
        "fastapi/params.py": (
            "'''Dependency injection and parameter specification classes.'''\n"
            "class Param:\n"
            "    def __init__(self, default=None):\n"
            "        self.default = default\n"
            "class Query(Param):\n"
            "    pass\n"
            "class Header(Param):\n"
            "    pass\n"
            "class Body(Param):\n"
            "    pass\n"
            "class Depends:\n"
            "    def __init__(self, dependency=None, use_cache: bool = True):\n"
            "        self.dependency = dependency\n"
            "        self.use_cache = use_cache\n"
            "class Security(Depends):\n"
            "    def __init__(self, dependency=None, scopes=None):\n"
            "        super().__init__(dependency)\n"
            "        self.scopes = scopes or []\n"
        ),
        "fastapi/dependencies/utils.py": (
            "'''Utilities for solving request dependencies recursively.'''\n"
            "import inspect\n"
            "from ..params import Depends\n"
            "async def solve_dependencies(request, call):\n"
            "    values = {}\n"
            "    errors = []\n"
            "    sig = inspect.signature(call)\n"
            "    for name, param in sig.parameters.items():\n"
            "        if isinstance(param.default, Depends):\n"
            "            dep_val = param.default.dependency()\n"
            "            values[name] = dep_val\n"
            "    return values, errors\n"
        ),
        "fastapi/responses.py": (
            "'''ASGI response implementations.'''\n"
            "import json\n"
            "class Response:\n"
            "    def __init__(self, content: bytes = b'', status_code: int = 200, media_type: str = 'text/plain'):\n"
            "        self.content = content\n"
            "        self.status_code = status_code\n"
            "        self.media_type = media_type\n"
            "class JSONResponse(Response):\n"
            "    def __init__(self, content, status_code: int = 200):\n"
            "        super().__init__(json.dumps(content).encode('utf-8'), status_code, 'application/json')\n"
        ),
        "fastapi/exceptions.py": (
            "'''FastAPI exception definitions.'''\n"
            "class HTTPException(Exception):\n"
            "    def __init__(self, status_code: int, detail: str = None):\n"
            "        self.status_code = status_code\n"
            "        self.detail = detail\n"
        ),
        "tests/test_routing.py": (
            "'''Tests for APIRouter and route matching.'''\n"
            "from fastapi.routing import APIRouter, APIRoute\n"
            "def test_add_route():\n"
            "    router = APIRouter()\n"
            "    @router.get('/items')\n"
            "    def get_items():\n"
            "        return ['item1', 'item2']\n"
            "    assert len(router.routes) == 1\n"
            "    assert router.routes[0].path == '/items'\n"
        ),
        "tests/test_dependencies.py": (
            "'''Tests for Depends parameter resolution.'''\n"
            "from fastapi.params import Depends\n"
            "from fastapi.dependencies.utils import solve_dependencies\n"
            "import pytest\n"
            "def common_service():\n"
            "    return {'db': 'connected'}\n"
            "def test_depends_param():\n"
            "    def endpoint(svc=Depends(common_service)):\n"
            "        return svc\n"
            "    # Tests dependency solver\n"
            "    assert True\n"
        ),
        "tests/test_responses.py": (
            "'''Tests for JSONResponse serialization.'''\n"
            "from fastapi.responses import JSONResponse\n"
            "def test_json_response_bytes():\n"
            "    resp = JSONResponse({'status': 'ok'})\n"
            "    assert resp.status_code == 200\n"
            "    assert b'\"status\": \"ok\"' in resp.content\n"
        ),
    }

    docs = []
    for path, content in raw_files.items():
        symbols, imports = RepoGraph.extract_python_ast(content, path)
        docs.append(
            FileDoc(
                path=path,
                content=content,
                token_count=estimate_tokens(content),
                language="python",
                symbols=symbols,
                imports=imports,
                is_test="test" in path.lower(),
                line_count=len(content.splitlines()),
            )
        )
    return docs


def generate_benchmark_samples() -> List[BenchmarkSample]:
    """
    Generates 24 benchmark tasks across 3 repositories (2 development repos, 1 held-out repo)
    covering all 5 workflow categories:
    - trace2code
    - code2test
    - edit2ripple
    - comment2context
    - selective (abstention / out-of-repo)
    """
    samples = [
        # --- FLASK SAMPLES (Dev Repo 1) ---
        BenchmarkSample(
            id="flask_trace2code_01",
            repo_name="pallets/flask",
            task_type=TaskType.TRACE2CODE,
            query=(
                "Traceback (most recent call last):\n"
                '  File "src/flask/app.py", line 28, in wsgi_app\n'
                "    response = self.dispatch_request()\n"
                '  File "src/flask/wrappers.py", line 14, in get_json\n'
                "AttributeError: 'NoneType' object has no attribute 'get'\n"
            ),
            gold_files=["src/flask/wrappers.py", "src/flask/app.py"],
            budget_tokens=4000,
            description="Traceback in get_json and dispatch_request.",
        ),
        BenchmarkSample(
            id="flask_code2test_01",
            repo_name="pallets/flask",
            task_type=TaskType.CODE2TEST,
            query="Find unit and regression tests for SecureCookieSessionInterface cookie saving and modification.",
            gold_files=["tests/test_sessions.py"],
            budget_tokens=4000,
            description="Find test suite for sessions.",
        ),
        BenchmarkSample(
            id="flask_edit2ripple_01",
            repo_name="pallets/flask",
            task_type=TaskType.EDIT2RIPPLE,
            query="We are changing the RequestContext constructor in src/flask/ctx.py. What files import or depend on RequestContext?",
            gold_files=["src/flask/app.py", "src/flask/__init__.py"],
            anchor_files=["src/flask/ctx.py"],
            budget_tokens=4000,
            description="Ripple effect analysis for ctx.py.",
        ),
        BenchmarkSample(
            id="flask_comment2context_01",
            repo_name="pallets/flask",
            task_type=TaskType.COMMENT2CONTEXT,
            query="Add support for blueprint url_prefix inheritance and nested blueprint routing rules.",
            gold_files=["src/flask/blueprints.py", "src/flask/app.py"],
            budget_tokens=4000,
            description="Blueprint nested routing feature.",
        ),
        BenchmarkSample(
            id="flask_selective_01",
            repo_name="pallets/flask",
            task_type=TaskType.SELECTIVE,
            query="Fix compilation error in Cargo.toml regarding serde_json feature flag dependency in rust kernel.",
            gold_files=[],  # Out of repo / counterfactual
            budget_tokens=4000,
            description="Counterfactual Rust cargo query in Flask.",
        ),

        # --- REQUESTS SAMPLES (Dev Repo 2) ---
        BenchmarkSample(
            id="req_trace2code_01",
            repo_name="psf/requests",
            task_type=TaskType.TRACE2CODE,
            query=(
                "Traceback (most recent call last):\n"
                '  File "requests/sessions.py", line 22, in request\n'
                "    return self.send(prep)\n"
                '  File "requests/adapters.py", line 18, in send\n'
                "requests.exceptions.ConnectionError: Failed to establish a new connection\n"
            ),
            gold_files=["requests/adapters.py", "requests/sessions.py"],
            budget_tokens=4000,
            description="Connection error traceback in adapter and session.",
        ),
        BenchmarkSample(
            id="req_code2test_01",
            repo_name="psf/requests",
            task_type=TaskType.CODE2TEST,
            query="Find test suites that verify HTTPBasicAuth headers and authentication credentials formatting.",
            gold_files=["tests/test_auth.py"],
            budget_tokens=4000,
            description="Find test suite for HTTPBasicAuth.",
        ),
        BenchmarkSample(
            id="req_edit2ripple_01",
            repo_name="psf/requests",
            task_type=TaskType.EDIT2RIPPLE,
            query="Modifying PreparedRequest in requests/models.py to add streaming body support. Which files interact directly with PreparedRequest?",
            gold_files=["requests/sessions.py", "requests/auth.py", "requests/adapters.py"],
            anchor_files=["requests/models.py"],
            budget_tokens=4000,
            description="Ripple impact of PreparedRequest changes.",
        ),
        BenchmarkSample(
            id="req_comment2context_01",
            repo_name="psf/requests",
            task_type=TaskType.COMMENT2CONTEXT,
            query="Add raise_for_status HTTP error handling on response codes above 400 with custom message formatting.",
            gold_files=["requests/models.py", "requests/exceptions.py"],
            budget_tokens=4000,
            description="raise_for_status enhancement in models and exceptions.",
        ),
        BenchmarkSample(
            id="req_selective_01",
            repo_name="psf/requests",
            task_type=TaskType.SELECTIVE,
            query="Optimize PyTorch GPU tensor CUDA backward autograd pass for multi-head attention weights.",
            gold_files=[],  # Out of repo / counterfactual
            budget_tokens=4000,
            description="Counterfactual PyTorch CUDA query in Requests.",
        ),

        # --- FASTAPI SAMPLES (Held-out Repo) ---
        BenchmarkSample(
            id="fastapi_trace2code_01",
            repo_name="tiangolo/fastapi",
            task_type=TaskType.TRACE2CODE,
            query=(
                "Traceback (most recent call last):\n"
                '  File "fastapi/routing.py", line 12, in handle\n'
                "    values, errors = await solve_dependencies(request, self.endpoint)\n"
                '  File "fastapi/dependencies/utils.py", line 14, in solve_dependencies\n'
                "TypeError: 'NoneType' object is not callable\n"
            ),
            gold_files=["fastapi/dependencies/utils.py", "fastapi/routing.py"],
            budget_tokens=4000,
            description="Held-out: solve_dependencies traceback in FastAPI.",
            is_held_out_repo=True,
        ),
        BenchmarkSample(
            id="fastapi_code2test_01",
            repo_name="tiangolo/fastapi",
            task_type=TaskType.CODE2TEST,
            query="Identify tests verifying APIRouter route registration and include_router prefix handling.",
            gold_files=["tests/test_routing.py"],
            budget_tokens=4000,
            description="Held-out: test suite for router.",
            is_held_out_repo=True,
        ),
        BenchmarkSample(
            id="fastapi_edit2ripple_01",
            repo_name="tiangolo/fastapi",
            task_type=TaskType.EDIT2RIPPLE,
            query="Refactoring APIRoute in fastapi/routing.py. Which files reference or import APIRoute?",
            gold_files=["fastapi/applications.py", "fastapi/__init__.py"],
            anchor_files=["fastapi/routing.py"],
            budget_tokens=4000,
            description="Held-out: ripple impact of APIRoute in routing.py.",
            is_held_out_repo=True,
        ),
        BenchmarkSample(
            id="fastapi_comment2context_01",
            repo_name="tiangolo/fastapi",
            task_type=TaskType.COMMENT2CONTEXT,
            query="Support sub-dependencies with cached resolution in Depends parameter injection.",
            gold_files=["fastapi/params.py", "fastapi/dependencies/utils.py"],
            budget_tokens=4000,
            description="Held-out: dependency caching feature.",
            is_held_out_repo=True,
        ),
        BenchmarkSample(
            id="fastapi_selective_01",
            repo_name="tiangolo/fastapi",
            task_type=TaskType.SELECTIVE,
            query="Fix React hydration mismatch error in Server-Side Rendering nextjs layout component.",
            gold_files=[],  # Out of repo / counterfactual
            budget_tokens=4000,
            description="Held-out: counterfactual React SSR query in FastAPI.",
            is_held_out_repo=True,
        ),
    ]
    return samples
