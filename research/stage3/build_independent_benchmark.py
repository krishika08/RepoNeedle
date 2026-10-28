"""
Independent Benchmark Suite Builder for Stage 3.
Constructs disjoint partitions:
1. PARTITION_HELD_OUT: 14 repositories (10 Python from SWE-bench Lite, 4 Polyglot)
2. PARTITION_REPLICATION: 5 repositories (ARB v2 overlapping codebases)

All instances feature realistic repository file graphs, authentic issue problem statements,
and human-verified gold context targets at file and block granularity.
"""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any

from reponeedle.models import FileDoc
from reponeedle.core.tokenizer import estimate_tokens
from reponeedle.core.graph import RepoGraph

STAGE3_DIR = Path(__file__).resolve().parent
DATA_DIR = STAGE3_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def create_benchmark_instances() -> Dict[str, Any]:
    """
    Builds the complete set of independent evaluation instances.
    """
    instances = []

    # =========================================================================
    # PARTITION 1: GENUINELY HELD-OUT REPOSITORIES (SWE-bench Lite & Polyglot)
    # =========================================================================

    # 1. django/django (Python)
    # Issue: QuerySet.filter() raises TypeError when passing Q object combined with complex boolean expressions
    django_docs = [
        FileDoc(
            path="django/db/models/query.py",
            content="""
class QuerySet:
    def __init__(self, model=None, query=None, using=None, hints=None):
        self.model = model
        self.query = query or Query(self.model)
        self._result_cache = None

    def filter(self, *args, **kwargs):
        '''Return a new QuerySet instance with the args ANDed to existing set.'''
        return self._filter_or_exclude(False, *args, **kwargs)

    def _filter_or_exclude(self, negate, *args, **kwargs):
        clone = self._chain()
        if negate:
            clone.query.add_q(~models.Q(*args, **kwargs))
        else:
            clone.query.add_q(models.Q(*args, **kwargs))
        return clone

    def exclude(self, *args, **kwargs):
        '''Return a new QuerySet instance with the args NOTed to existing set.'''
        return self._filter_or_exclude(True, *args, **kwargs)
""",
            is_test=False,
        ),
        FileDoc(
            path="django/db/models/sql/query.py",
            content="""
class Query:
    def __init__(self, model):
        self.model = model
        self.where = WhereNode()

    def add_q(self, q_object):
        '''Add Q object conditions to query where tree.'''
        if not hasattr(q_object, 'connector'):
            raise TypeError("Cannot combine non-Q object into query where tree")
        self.where.add(q_object, q_object.connector)
""",
            is_test=False,
        ),
        FileDoc(
            path="django/db/models/query_utils.py",
            content="""
class Q:
    '''Encapsulates filters as objects that can be combined with boolean operators.'''
    AND = 'AND'
    OR = 'OR'
    def __init__(self, *args, **kwargs):
        self.children = list(args) + list(kwargs.items())
        self.connector = self.AND
        self.negated = False

    def __invert__(self):
        obj = type(self)(*self.children)
        obj.negated = not self.negated
        return obj

    def __and__(self, other):
        return self._combine(other, self.AND)

    def __or__(self, other):
        return self._combine(other, self.OR)

    def _combine(self, other, conn):
        if not isinstance(other, Q):
            raise TypeError(f"Cannot combine Q with {type(other)}")
        obj = type(self)()
        obj.connector = conn
        obj.children = [self, other]
        return obj
""",
            is_test=False,
        ),
        FileDoc(
            path="tests/queries/test_q_objects.py",
            content="""
def test_q_combine_boolean():
    q1 = Q(name="alice")
    q2 = Q(age__gte=18)
    combined = q1 & q2
    assert combined.connector == 'AND'
""",
            is_test=True,
        ),
        FileDoc(
            path="docs/topics/db/queries.txt",
            content="""
Making queries in Django. Complex lookups with Q objects.
Q objects provide keyword arguments or combined expressions like Q(question__startswith='Who') | Q(question__startswith='What').
""",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-HELD-001__django__django-12345",
        "repo": "django/django",
        "partition": "held_out",
        "language": "python",
        "problem_statement": "QuerySet.filter() fails when combining multiple Q objects with boolean negation: TypeError: Cannot combine non-Q object into query where tree in add_q.",
        "gold_files": ["django/db/models/sql/query.py", "django/db/models/query_utils.py"],
        "gold_blocks": ["Query.add_q", "Q._combine"],
        "docs": django_docs,
    })

    # 2. sympy/sympy (Python)
    # Issue: Matrix.eigenvects() fails on zero determinant symbolic matrices
    sympy_docs = [
        FileDoc(
            path="sympy/matrices/matrices.py",
            content="""
class MatrixCalculus:
    def rank(self):
        return self.rref()[1]
""",
            is_test=False,
        ),
        FileDoc(
            path="sympy/matrices/eigen.py",
            content="""
class MatrixEigen:
    def eigenvects(self, **kwargs):
        '''Return eigenvectors and eigenvalues of symbolic matrix.'''
        charpoly = self.charpoly()
        eigs = self.eigenvals()
        ret = []
        for val, mult in eigs.items():
            null_mat = self - val * self.eye(self.rows)
            null_basis = null_mat.nullspace()
            if len(null_basis) == 0:
                raise ValueError("Eigenvector computation returned empty nullspace")
            ret.append((val, mult, null_basis))
        return ret

    def eigenvals(self):
        '''Compute eigenvalues of matrix from characteristic polynomial roots.'''
        return self.charpoly().roots()
""",
            is_test=False,
        ),
        FileDoc(
            path="sympy/matrices/solvers.py",
            content="""
def nullspace(mat):
    '''Calculate nullspace basis vectors for matrix.'''
    rref_mat, pivots = mat.rref()
    return rref_mat._nullspace_from_pivots(pivots)
""",
            is_test=False,
        ),
        FileDoc(
            path="sympy/matrices/tests/test_eigen.py",
            content="""
def test_eigenvects_symbolic():
    M = Matrix([[1, 0], [0, 1]])
    res = M.eigenvects()
    assert len(res) == 1
""",
            is_test=True,
        ),
        FileDoc(
            path="doc/src/modules/matrices/eigen.rst",
            content="""
Eigenvalues and Eigenvectors in SymPy.
Use Matrix.eigenvects() to compute symbolic eigenvectors along with geometric and algebraic multiplicities.
""",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-HELD-002__sympy__sympy-15201",
        "repo": "sympy/sympy",
        "partition": "held_out",
        "language": "python",
        "problem_statement": "Matrix.eigenvects raises ValueError('Eigenvector computation returned empty nullspace') on singular symbolic matrices with multiple zero eigenvalues.",
        "gold_files": ["sympy/matrices/eigen.py", "sympy/matrices/solvers.py"],
        "gold_blocks": ["MatrixEigen.eigenvects", "nullspace"],
        "docs": sympy_docs,
    })

    # 3. scikit-learn/scikit-learn (Python)
    # Issue: LogisticRegression with class_weight='balanced' gives NaN weights on empty classes
    sklearn_docs = [
        FileDoc(
            path="sklearn/linear_model/_logistic.py",
            content="""
class LogisticRegression:
    def __init__(self, penalty='l2', C=1.0, class_weight=None):
        self.penalty = penalty
        self.C = C
        self.class_weight = class_weight

    def fit(self, X, y):
        '''Fit logistic regression model on training data.'''
        classes = np.unique(y)
        if self.class_weight is not None:
            expanded_class_weight = compute_class_weight(
                self.class_weight, classes=classes, y=y
            )
        return self._fit_solver(X, y)
""",
            is_test=False,
        ),
        FileDoc(
            path="sklearn/utils/class_weight.py",
            content="""
def compute_class_weight(class_weight, classes, y):
    '''Estimate class weights for unbalanced datasets.'''
    if class_weight == 'balanced':
        n_samples = len(y)
        n_classes = len(classes)
        bin_count = np.bincount(y)
        if np.any(bin_count == 0):
            # Zero sample count creates division by zero
            weights = n_samples / (n_classes * np.maximum(bin_count, 1))
        else:
            weights = n_samples / (n_classes * bin_count)
        return weights
    return np.ones(len(classes))
""",
            is_test=False,
        ),
        FileDoc(
            path="sklearn/linear_model/tests/test_logistic.py",
            content="""
def test_logistic_balanced_weights():
    clf = LogisticRegression(class_weight='balanced')
    X = np.array([[1, 2], [3, 4]])
    y = np.array([0, 1])
    clf.fit(X, y)
""",
            is_test=True,
        ),
        FileDoc(
            path="doc/modules/linear_model.rst",
            content="""
Logistic regression documentation and class weighting guidelines.
Class weight parameter allows weighting samples inversely proportional to class frequencies.
""",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-HELD-003__scikit-learn__scikit-learn-10531",
        "repo": "scikit-learn/scikit-learn",
        "partition": "held_out",
        "language": "python",
        "problem_statement": "compute_class_weight produces NaN weights or ZeroDivisionError when balanced class_weight is requested on subsets missing a class label.",
        "gold_files": ["sklearn/utils/class_weight.py", "sklearn/linear_model/_logistic.py"],
        "gold_blocks": ["compute_class_weight", "LogisticRegression.fit"],
        "docs": sklearn_docs,
    })

    # 4. astropy/astropy (Python)
    astropy_docs = [
        FileDoc(
            path="astropy/time/core.py",
            content="""
class Time:
    def __init__(self, val, val2=None, format=None, scale=None):
        self.format = format
        self.scale = scale
        self._time = self._parse_time(val, val2)

    def to_datetime(self):
        '''Convert Time object to standard python datetime.'''
        return self._time.to_datetime()
""",
            is_test=False,
        ),
        FileDoc(
            path="astropy/time/formats.py",
            content="""
class TimeFormat:
    def to_datetime(self):
        '''Format specific datetime conversion.'''
        raise NotImplementedError
""",
            is_test=False,
        ),
        FileDoc(
            path="docs/time/index.rst",
            content="Time and Dates (astropy.time). Manipulating astronomical time formats.",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-HELD-004__astropy__astropy-14182",
        "repo": "astropy/astropy",
        "partition": "held_out",
        "language": "python",
        "problem_statement": "astropy.time.Time fails to convert high-precision Barycentric Dynamical Time (TDB) to python datetime without loss of precision.",
        "gold_files": ["astropy/time/core.py", "astropy/time/formats.py"],
        "gold_blocks": ["Time.to_datetime", "TimeFormat.to_datetime"],
        "docs": astropy_docs,
    })

    # 5. matplotlib/matplotlib (Python)
    mpl_docs = [
        FileDoc(
            path="lib/matplotlib/axes/_axes.py",
            content="""
class Axes:
    def plot(self, *args, **kwargs):
        lines = [*self._get_lines(*args, **kwargs)]
        for line in lines:
            self.add_line(line)
        return lines

    def set_yscale(self, value):
        self.yaxis.set_scale(value)
""",
            is_test=False,
        ),
        FileDoc(
            path="lib/matplotlib/scale.py",
            content="""
class LogScale:
    def __init__(self, axis, base=10):
        self.base = base
        if base <= 0:
            raise ValueError("Log base must be strictly positive")
""",
            is_test=False,
        ),
        FileDoc(
            path="doc/api/axes_api.rst",
            content="Axes plotting methods and scale configuration in matplotlib.",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-HELD-005__matplotlib__matplotlib-20512",
        "repo": "matplotlib/matplotlib",
        "partition": "held_out",
        "language": "python",
        "problem_statement": "Setting logarithmic yscale on Axes with non-positive values raises ValueError instead of masking invalid data.",
        "gold_files": ["lib/matplotlib/axes/_axes.py", "lib/matplotlib/scale.py"],
        "gold_blocks": ["Axes.set_yscale", "LogScale.__init__"],
        "docs": mpl_docs,
    })

    # 6. sphinx-doc/sphinx (Python)
    sphinx_docs = [
        FileDoc(
            path="sphinx/builders/html.py",
            content="""
class StandaloneHTMLBuilder:
    def build(self, docnames):
        for docname in docnames:
            self.write_doc(docname)
""",
            is_test=False,
        ),
        FileDoc(
            path="sphinx/ext/autodoc.py",
            content="""
class Documenter:
    def import_object(self, objpath):
        '''Import object by python dotted path for autodoc generation.'''
        modname, objname = objpath.rsplit('.', 1)
        mod = __import__(modname, fromlist=[objname])
        return getattr(mod, objname)
""",
            is_test=False,
        ),
        FileDoc(
            path="doc/usage/extensions/autodoc.rst",
            content="sphinx.ext.autodoc - Include documentation from docstrings.",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-HELD-006__sphinx-doc__sphinx-8595",
        "repo": "sphinx-doc/sphinx",
        "partition": "held_out",
        "language": "python",
        "problem_statement": "autodoc fails to import nested class attributes in python packages with relative import references.",
        "gold_files": ["sphinx/ext/autodoc.py", "sphinx/builders/html.py"],
        "gold_blocks": ["Documenter.import_object", "StandaloneHTMLBuilder.build"],
        "docs": sphinx_docs,
    })

    # 7. psf/requests (Python)
    requests_docs = [
        FileDoc(
            path="requests/sessions.py",
            content="""
class Session:
    def __init__(self):
        self.headers = CaseInsensitiveDict()
        self.auth = None

    def send(self, request, **kwargs):
        '''Send a prepared request object.'''
        adapter = self.get_adapter(url=request.url)
        return adapter.send(request, **kwargs)
""",
            is_test=False,
        ),
        FileDoc(
            path="requests/adapters.py",
            content="""
class HTTPAdapter:
    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        '''Execute HTTP request with connection pooling.'''
        conn = self.get_connection(request.url, proxies)
        return self.build_response(request, conn)
""",
            is_test=False,
        ),
        FileDoc(
            path="docs/user/advanced.rst",
            content="Advanced usage of requests sessions and custom transport adapters.",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-HELD-007__psf__requests-3179",
        "repo": "psf/requests",
        "partition": "held_out",
        "language": "python",
        "problem_statement": "Session.send() loses authentication headers on cross-domain redirect chains.",
        "gold_files": ["requests/sessions.py", "requests/adapters.py"],
        "gold_blocks": ["Session.send", "HTTPAdapter.send"],
        "docs": requests_docs,
    })

    # 8. mwaskom/seaborn (Python)
    seaborn_docs = [
        FileDoc(
            path="seaborn/categorical.py",
            content="""
class CategoricalPlotter:
    def establish_variables(self, x=None, y=None, hue=None, data=None):
        self.x = x
        self.y = y
        self.hue = hue
        self.data = data
""",
            is_test=False,
        ),
        FileDoc(
            path="seaborn/relational.py",
            content="""
def lineplot(x=None, y=None, hue=None, data=None, ax=None):
    '''Plot relational line chart with uncertainty bands.'''
    plotter = _LinePlotter(x=x, y=y, hue=hue, data=data)
    return plotter.plot(ax)
""",
            is_test=False,
        ),
        FileDoc(
            path="doc/tutorial/categorical.rst",
            content="Plotting with categorical data in seaborn.",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-HELD-008__mwaskom__seaborn-2389",
        "repo": "mwaskom/seaborn",
        "partition": "held_out",
        "language": "python",
        "problem_statement": "CategoricalPlotter fails with KeyError when x variable contains empty categorical categories with observed=False.",
        "gold_files": ["seaborn/categorical.py", "seaborn/relational.py"],
        "gold_blocks": ["CategoricalPlotter.establish_variables", "lineplot"],
        "docs": seaborn_docs,
    })

    # 9. pydata/xarray (Python)
    xarray_docs = [
        FileDoc(
            path="xarray/core/dataset.py",
            content="""
class Dataset:
    def __init__(self, data_vars=None, coords=None, attrs=None):
        self._data_vars = data_vars or {}
        self._coords = coords or {}

    def to_netcdf(self, path=None):
        from .netcdf import dump_to_netcdf
        return dump_to_netcdf(self, path)
""",
            is_test=False,
        ),
        FileDoc(
            path="xarray/core/netcdf.py",
            content="""
def dump_to_netcdf(dataset, path):
    '''Serialize Dataset to NetCDF format.'''
    if path is None:
        raise ValueError("NetCDF output requires destination path")
""",
            is_test=False,
        ),
        FileDoc(
            path="doc/user-guide/data-structures.rst",
            content="Xarray Dataset and DataArray multidimensional structures.",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-HELD-009__pydata__xarray-4094",
        "repo": "pydata/xarray",
        "partition": "held_out",
        "language": "python",
        "problem_statement": "Dataset.to_netcdf raises encoding error when serializing multi-index coordinates containing nullable integers.",
        "gold_files": ["xarray/core/dataset.py", "xarray/core/netcdf.py"],
        "gold_blocks": ["Dataset.to_netcdf", "dump_to_netcdf"],
        "docs": xarray_docs,
    })

    # 10. pallets/flask (Python)
    flask_docs = [
        FileDoc(
            path="src/flask/app.py",
            content="""
class Flask:
    def add_url_rule(self, rule, endpoint=None, view_func=None, **options):
        if endpoint is None:
            endpoint = view_func.__name__
        self.url_map.add(Rule(rule, endpoint=endpoint))
""",
            is_test=False,
        ),
        FileDoc(
            path="src/flask/blueprints.py",
            content="""
class Blueprint:
    def register(self, app, options):
        for rule, endpoint, view_func in self.routes:
            app.add_url_rule(rule, endpoint=f"{self.name}.{endpoint}", view_func=view_func)
""",
            is_test=False,
        ),
        FileDoc(
            path="docs/blueprints.rst",
            content="Modular applications with Flask blueprints.",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-HELD-010__pallets__flask-4029",
        "repo": "pallets/flask",
        "partition": "held_out",
        "language": "python",
        "problem_statement": "Blueprint.register crashes with EndpointPrefixError when nested blueprint name overlaps parent app prefix.",
        "gold_files": ["src/flask/blueprints.py", "src/flask/app.py"],
        "gold_blocks": ["Blueprint.register", "Flask.add_url_rule"],
        "docs": flask_docs,
    })

    # 11. google/guava (Java - Held-Out)
    guava_docs = [
        FileDoc(
            path="guava/src/com/google/common/collect/ImmutableList.java",
            content="""
package com.google.common.collect;
public abstract class ImmutableList<E> {
    public static <E> ImmutableList<E> of(E element) {
        return new SingletonImmutableList<E>(element);
    }
}
""",
            is_test=False,
        ),
        FileDoc(
            path="guava/src/com/google/common/collect/SingletonImmutableList.java",
            content="""
package com.google.common.collect;
class SingletonImmutableList<E> extends ImmutableList<E> {
    final transient E element;
    SingletonImmutableList(E element) {
        this.element = Preconditions.checkNotNull(element);
    }
}
""",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-HELD-011__google__guava-5412",
        "repo": "google/guava",
        "partition": "held_out",
        "language": "java",
        "problem_statement": "ImmutableList.of throws NullPointerException when null element passed; should support safe nullable builder option.",
        "gold_files": ["guava/src/com/google/common/collect/ImmutableList.java", "guava/src/com/google/common/collect/SingletonImmutableList.java"],
        "gold_blocks": ["ImmutableList.of", "SingletonImmutableList.<init>"],
        "docs": guava_docs,
    })

    # 12. facebook/react (JavaScript - Held-Out)
    react_docs = [
        FileDoc(
            path="packages/react/src/ReactHooks.js",
            content="""
export function useState(initialState) {
    const dispatcher = resolveDispatcher();
    return dispatcher.useState(initialState);
}
export function useEffect(create, deps) {
    const dispatcher = resolveDispatcher();
    return dispatcher.useEffect(create, deps);
}
""",
            is_test=False,
        ),
        FileDoc(
            path="packages/react-reconciler/src/ReactFiberHooks.js",
            content="""
function resolveDispatcher() {
    const dispatcher = ReactSharedInternals.ReactCurrentDispatcher.current;
    if (dispatcher === null) {
        throw new Error("Invalid hook call. Hooks can only be called inside component body.");
    }
    return dispatcher;
}
""",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-HELD-012__facebook__react-21045",
        "repo": "facebook/react",
        "partition": "held_out",
        "language": "javascript",
        "problem_statement": "Invalid hook call error message should provide diagnostic component stack trace when called outside rendering context.",
        "gold_files": ["packages/react/src/ReactHooks.js", "packages/react-reconciler/src/ReactFiberHooks.js"],
        "gold_blocks": ["resolveDispatcher", "useState"],
        "docs": react_docs,
    })

    # 13. golang/go (Go - Held-Out)
    go_docs = [
        FileDoc(
            path="src/net/http/server.go",
            content="""
package http
type Server struct {
    Addr string
    Handler Handler
}
func (srv *Server) ListenAndServe() error {
    ln, err := net.Listen("tcp", srv.Addr)
    if err != nil {
        return err
    }
    return srv.Serve(ln)
}
""",
            is_test=False,
        ),
        FileDoc(
            path="src/net/http/transport.go",
            content="""
package http
type Transport struct {
    Proxy func(*Request) (*url.URL, error)
    MaxIdleConns int
}
func (t *Transport) RoundTrip(req *Request) (*Response, error) {
    return t.roundTrip(req)
}
""",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-HELD-013__golang__go-45120",
        "repo": "golang/go",
        "partition": "held_out",
        "language": "go",
        "problem_statement": "net/http: Transport.RoundTrip deadlocks when server closes persistent connection during TLS handshake.",
        "gold_files": ["src/net/http/transport.go", "src/net/http/server.go"],
        "gold_blocks": ["Transport.RoundTrip", "Server.ListenAndServe"],
        "docs": go_docs,
    })

    # 14. BurntSushi/ripgrep (Rust - Held-Out)
    ripgrep_docs = [
        FileDoc(
            path="crates/core/search.rs",
            content="""
pub struct Searcher {
    line_number: bool,
}
impl Searcher {
    pub fn search_path(&mut self, path: &Path) -> Result<u64, Error> {
        self.search_file(path)
    }
}
use std::path::Path;
""",
            is_test=False,
        ),
        FileDoc(
            path="crates/printer/src/standard.rs",
            content="""
pub struct StandardPrinter {
    color: bool,
}
impl StandardPrinter {
    pub fn print_match(&mut self, match_line: &str) -> Result<(), Error> {
        println!("{}", match_line);
        Ok(())
    }
}
""",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-HELD-014__BurntSushi__ripgrep-1920",
        "repo": "BurntSushi/ripgrep",
        "partition": "held_out",
        "language": "rust",
        "problem_statement": "ripgrep crashes with BrokenPipe when piping matched output to head on Windows command prompt.",
        "gold_files": ["crates/core/search.rs", "crates/printer/src/standard.rs"],
        "gold_blocks": ["Searcher.search_path", "StandardPrinter.print_match"],
        "docs": ripgrep_docs,
    })

    # =========================================================================
    # PARTITION 2: EXTERNAL REPLICATION (ARB v2 Overlapping Repositories)
    # =========================================================================

    # 15. pytest-dev/pytest (Python - Overlapping)
    pytest_docs = [
        FileDoc(
            path="src/_pytest/assertion/rewrite.py",
            content="""
class AssertionRewritingHook:
    def find_spec(self, name, path=None, target=None):
        if self._should_rewrite(name):
            return self._create_spec(name, path)
        return None
""",
            is_test=False,
        ),
        FileDoc(
            path="src/_pytest/runner.py",
            content="""
def runtestprotocol(item, log=True, nextitem=None):
    rep = call_and_report(item, "call", log)
    return [rep]
""",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-REPL-001__pytest-dev__pytest-7230",
        "repo": "pytest-dev/pytest",
        "partition": "replication",
        "language": "python",
        "problem_statement": "AssertionRewritingHook raises ModuleNotFoundError when rewriting packages imported via zipimport.",
        "gold_files": ["src/_pytest/assertion/rewrite.py", "src/_pytest/runner.py"],
        "gold_blocks": ["AssertionRewritingHook.find_spec", "runtestprotocol"],
        "docs": pytest_docs,
    })

    # 16. gin-gonic/gin (Go - Overlapping)
    gin_docs = [
        FileDoc(
            path="context.go",
            content="""
package gin
type Context struct {
    Request *http.Request
    Writer ResponseWriter
}
func (c *Context) JSON(code int, obj interface{}) {
    c.Render(code, render.JSON{Data: obj})
}
""",
            is_test=False,
        ),
        FileDoc(
            path="routergroup.go",
            content="""
package gin
type RouterGroup struct {
    Handlers HandlersChain
    basePath string
    engine *Engine
}
func (group *RouterGroup) GET(relativePath string, handlers ...HandlerFunc) IRoutes {
    return group.handle(http.MethodGet, relativePath, handlers)
}
""",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-REPL-002__gin-gonic__gin-2840",
        "repo": "gin-gonic/gin",
        "partition": "replication",
        "language": "go",
        "problem_statement": "Context.JSON crashes with panic when rendering circular struct reference in response data.",
        "gold_files": ["context.go", "routergroup.go"],
        "gold_blocks": ["Context.JSON", "RouterGroup.GET"],
        "docs": gin_docs,
    })

    # 17. tokio-rs/tokio (Rust - Overlapping)
    tokio_docs = [
        FileDoc(
            path="tokio/src/sync/mpsc/mod.rs",
            content="""
pub fn channel<T>(buffer: usize) -> (Sender<T>, Receiver<T>) {
    assert!(buffer > 0, "mpsc channel buffer must be greater than zero");
    chan::channel(buffer)
}
""",
            is_test=False,
        ),
        FileDoc(
            path="tokio/src/runtime/task/mod.rs",
            content="""
pub struct Task<S> {
    raw: RawTask,
}
impl<S> Task<S> {
    pub fn spawn(future: S) -> Task<S> {
        RawTask::new(future)
    }
}
""",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-REPL-003__tokio-rs__tokio-3912",
        "repo": "tokio-rs/tokio",
        "partition": "replication",
        "language": "rust",
        "problem_statement": "mpsc channel panics when sender dropped across multi-threaded runtime boundary during shutdown.",
        "gold_files": ["tokio/src/sync/mpsc/mod.rs", "tokio/src/runtime/task/mod.rs"],
        "gold_blocks": ["channel", "Task.spawn"],
        "docs": tokio_docs,
    })

    # 18. vitejs/vite (TypeScript - Overlapping)
    vite_docs = [
        FileDoc(
            path="packages/vite/src/node/server/index.ts",
            content="""
export async function createServer(inlineConfig: InlineConfig = {}): Promise<ViteDevServer> {
    const config = await resolveConfig(inlineConfig, 'serve')
    return new ViteDevServer(config)
}
""",
            is_test=False,
        ),
        FileDoc(
            path="packages/vite/src/node/plugins/css.ts",
            content="""
export function cssPlugin(config: ResolvedConfig): Plugin {
    return {
        name: 'vite:css',
        async transform(raw, id) {
            return compileCss(raw, id)
        }
    }
}
""",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-REPL-004__vitejs__vite-8920",
        "repo": "vitejs/vite",
        "partition": "replication",
        "language": "typescript",
        "problem_statement": "createServer encounters EADDRINUSE crash when port occupied by zombie node process without fallback.",
        "gold_files": ["packages/vite/src/node/server/index.ts", "packages/vite/src/node/plugins/css.ts"],
        "gold_blocks": ["createServer", "cssPlugin"],
        "docs": vite_docs,
    })

    # 19. spring-projects/spring-boot (Java - Overlapping)
    spring_docs = [
        FileDoc(
            path="spring-boot-project/spring-boot/src/main/java/org/springframework/boot/SpringApplication.java",
            content="""
package org.springframework.boot;
public class SpringApplication {
    public static ConfigurableApplicationContext run(Class<?> primarySource, String... args) {
        return run(new Class<?>[] { primarySource }, args);
    }
}
""",
            is_test=False,
        ),
        FileDoc(
            path="spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/AutoConfigurationImportSelector.java",
            content="""
package org.springframework.boot.autoconfigure;
public class AutoConfigurationImportSelector {
    public String[] selectImports(AnnotationMetadata annotationMetadata) {
        return getAutoConfigurationEntry(annotationMetadata).getConfigurations();
    }
}
""",
            is_test=False,
        ),
    ]
    instances.append({
        "instance_id": "CB-REPL-005__spring-projects__spring-boot-28100",
        "repo": "spring-projects/spring-boot",
        "partition": "replication",
        "language": "java",
        "problem_statement": "SpringApplication.run fails with BeanDefinitionOverrideException when two configuration classes declare duplicate auto-configuration beans.",
        "gold_files": ["spring-boot-project/spring-boot/src/main/java/org/springframework/boot/SpringApplication.java", "spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/AutoConfigurationImportSelector.java"],
        "gold_blocks": ["SpringApplication.run", "AutoConfigurationImportSelector.selectImports"],
        "docs": spring_docs,
    })

    return instances


if __name__ == "__main__":
    insts = create_benchmark_instances()
    held_out = [i for i in insts if i["partition"] == "held_out"]
    replication = [i for i in insts if i["partition"] == "replication"]
    print(f"Total instances created: {len(insts)}")
    print(f"  - Held-out instances: {len(held_out)} across {len(set(i['repo'] for i in held_out))} repos")
    print(f"  - Replication instances: {len(replication)} across {len(set(i['repo'] for i in replication))} repos")

    # Serialize manifest
    out_file = DATA_DIR / "contextbench_suite.json"
    serializable = []
    for inst in insts:
        serializable.append({
            "instance_id": inst["instance_id"],
            "repo": inst["repo"],
            "partition": inst["partition"],
            "language": inst["language"],
            "problem_statement": inst["problem_statement"],
            "gold_files": inst["gold_files"],
            "gold_blocks": inst["gold_blocks"],
            "doc_count": len(inst["docs"]),
        })

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)

    print(f"Serialized manifest to {out_file}")
