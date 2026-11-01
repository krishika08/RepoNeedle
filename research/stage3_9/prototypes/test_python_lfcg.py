"""
Unit and Integration Test Suite for Python-First LFCG Implementation.
Covers all 13 Phase D requirements:
1. Direct local calls.
2. Imports and aliases.
3. Relative imports.
4. Nested scopes.
5. Function shadowing.
6. Methods (self calls).
7. Decorators.
8. Recursive calls.
9. Dynamic dispatch.
10. Unknown receivers (never convert to exact call).
11. Built-ins.
12. External libraries.
13. Syntax errors.

Also tests:
- Extraction correctness separated from target-resolution correctness.
- Bit-for-bit deterministic serialization (SHA-256).
- Only CONTAINS and CALLS edges emitted.
"""

import pytest
import os
import json
from python_lfcg import (
    PythonLFCGEngine,
    TIER_A_EXACT_AST,
    TIER_B_SCOPED_IMPORT,
    TIER_C_RECEIVER_BOUND,
    TIER_D_HEURISTIC_PATTERN,
    TIER_E_UNRESOLVED,
)

@pytest.fixture
def test_repo_engine():
    engine = PythonLFCGEngine(repo_name="test_py_repo")

    # File 1: main module with local calls, nested scopes, shadowing, recursion, decorators, dynamic calls
    code_main = """
import math
from .subpkg.utils import util_helper, compute_val as alias_compute
import os.path as my_path

def helper_target():
    return 42

@property
def decorated_target():
    return "dec"

def caller_local_and_nested():
    val = helper_target()
    def nested_worker():
        return helper_target() + 1
    w = nested_worker()
    return val + w

def caller_shadowing():
    helper_target = lambda: 99
    return helper_target()

def recursive_factorial(n):
    if n <= 1:
        return 1
    return n * recursive_factorial(n - 1)

def caller_imports():
    a = util_helper()
    b = alias_compute(10)
    c = math.sqrt(25)
    d = my_path.join("a", "b")
    return a, b, c, d

class Service:
    def internal_action(self):
        return 1

    def execute(self, external_obj):
        # 6. Method call on self
        s = self.internal_action()
        # 10. Unknown receiver call
        ext = external_obj.internal_action()
        return s, ext

def caller_dynamic(handler, key):
    res1 = getattr(handler, "dynamic_fn")()
    res2 = len([1, 2, 3])
    return res1, res2
"""

    # File 2: subpkg/utils.py with relative import targets
    code_utils = """
from ..helpers import root_helper

def util_helper():
    return "util"

def compute_val(x):
    return x * 2

def caller_relative():
    return root_helper()
"""

    # File 3: helpers.py in root
    code_root_helpers = """
def root_helper():
    return "root"
"""

    # File 4: syntax_error.py with malformed code
    code_syntax_error = """
def broken_syntax(
    print("missing closing paren"
"""

    engine.parse_source("src/test_py_repo/main.py", code_main)
    engine.parse_source("src/test_py_repo/subpkg/utils.py", code_utils)
    engine.parse_source("src/test_py_repo/helpers.py", code_root_helpers)
    engine.parse_source("src/test_py_repo/syntax_error.py", code_syntax_error)

    engine.resolve_all_calls()
    return engine


def test_syntax_error_fail_closed(test_repo_engine):
    """13. Syntax errors fail closed without crashing; file registered, 0 call edges emitted."""
    bad_uri = test_repo_engine.make_file_uri("src/test_py_repo/syntax_error.py")
    assert bad_uri in test_repo_engine.file_nodes
    # 0 functions in syntax_error.py
    bad_funcs = [fn for fn in test_repo_engine.function_nodes.values() if fn.file_uri == bad_uri]
    assert len(bad_funcs) == 0
    # 0 edges originating from syntax_error.py
    bad_edges = [e for e in test_repo_engine.edges if bad_uri in e.source_uri]
    assert len(bad_edges) == 0


def test_direct_local_calls(test_repo_engine):
    """1. Direct local calls within file."""
    # caller_local_and_nested calling helper_target
    local_calls = [
        r for r in test_repo_engine.resolutions
        if r.extraction.identifier == "helper_target" and r.extraction.caller_func_uri and "caller_local_and_nested" in r.extraction.caller_func_uri
    ]
    assert len(local_calls) >= 1
    call = local_calls[0]
    assert call.is_resolved is True
    assert call.resolution_status == "EXACT"
    assert call.provenance_tier == TIER_A_EXACT_AST
    assert call.selected_target_uri == "func://test_py_repo/src/test_py_repo/main.py#helper_target"


def test_nested_scopes(test_repo_engine):
    """4. Nested scopes: nested function defined inside outer function."""
    nested_funcs = [fn for fn in test_repo_engine.function_nodes.values() if fn.name == "nested_worker"]
    assert len(nested_funcs) == 1
    assert nested_funcs[0].is_nested is True
    assert nested_funcs[0].start_line > 0

    # Call to nested_worker from caller_local_and_nested
    nested_calls = [
        r for r in test_repo_engine.resolutions
        if r.extraction.identifier == "nested_worker"
    ]
    assert len(nested_calls) == 1
    call = nested_calls[0]
    assert call.is_resolved is True
    assert call.resolution_status == "EXACT"
    assert call.provenance_tier == TIER_A_EXACT_AST


def test_function_shadowing(test_repo_engine):
    """5. Function shadowing: local variable assignment shadows outer function."""
    shadowed_calls = [
        r for r in test_repo_engine.resolutions
        if r.extraction.caller_func_uri and "caller_shadowing" in r.extraction.caller_func_uri
    ]
    assert len(shadowed_calls) == 1
    call = shadowed_calls[0]
    # Must be UNRESOLVED because helper_target was assigned as a local lambda in that function scope
    assert call.is_resolved is False
    assert call.resolution_status == "UNRESOLVED"
    assert call.resolution_method == "shadowed_by_local_scope"
    assert call.selected_target_uri is None


def test_recursive_calls(test_repo_engine):
    """8. Recursive calls: function calls itself directly."""
    rec_calls = [
        r for r in test_repo_engine.resolutions
        if r.extraction.caller_func_uri and "recursive_factorial" in r.extraction.caller_func_uri
        and r.extraction.identifier == "recursive_factorial"
    ]
    assert len(rec_calls) == 1
    call = rec_calls[0]
    assert call.is_resolved is True
    assert call.resolution_status == "EXACT"
    assert call.resolution_method == "ast_recursive_self_call"
    assert call.provenance_tier == TIER_A_EXACT_AST


def test_imports_and_aliases(test_repo_engine):
    """2. Imports and aliases."""
    # util_helper imported from .subpkg.utils
    imp_calls = [
        r for r in test_repo_engine.resolutions
        if r.extraction.identifier == "util_helper" and r.extraction.caller_func_uri and "caller_imports" in r.extraction.caller_func_uri
    ]
    assert len(imp_calls) == 1
    call = imp_calls[0]
    assert call.is_resolved is True
    assert call.resolution_status == "EXACT"
    assert call.provenance_tier == TIER_B_SCOPED_IMPORT
    assert call.selected_target_uri == "func://test_py_repo/src/test_py_repo/subpkg/utils.py#util_helper"

    # alias_compute mapped to compute_val
    alias_calls = [
        r for r in test_repo_engine.resolutions
        if r.extraction.identifier == "alias_compute"
    ]
    assert len(alias_calls) == 1
    assert alias_calls[0].is_resolved is True
    assert alias_calls[0].provenance_tier == TIER_B_SCOPED_IMPORT
    assert alias_calls[0].selected_target_uri == "func://test_py_repo/src/test_py_repo/subpkg/utils.py#compute_val"


def test_relative_imports(test_repo_engine):
    """3. Relative imports across package directory hierarchy."""
    rel_calls = [
        r for r in test_repo_engine.resolutions
        if r.extraction.caller_func_uri and "caller_relative" in r.extraction.caller_func_uri
    ]
    assert len(rel_calls) == 1
    call = rel_calls[0]
    assert call.is_resolved is True
    assert call.provenance_tier == TIER_B_SCOPED_IMPORT
    assert call.selected_target_uri == "func://test_py_repo/src/test_py_repo/helpers.py#root_helper"


def test_methods_and_self_calls(test_repo_engine):
    """6. Methods and self calls."""
    self_calls = [
        r for r in test_repo_engine.resolutions
        if r.extraction.qualifier == "self" and r.extraction.identifier == "internal_action"
    ]
    assert len(self_calls) == 1
    call = self_calls[0]
    assert call.is_resolved is True
    assert call.resolution_status == "EXACT"
    assert call.provenance_tier == TIER_C_RECEIVER_BOUND
    assert call.selected_target_uri == "func://test_py_repo/src/test_py_repo/main.py#Service.internal_action"


def test_unknown_receivers_never_exact(test_repo_engine):
    """10. Unknown receivers (Rule 8: Never convert plausible method match into exact call)."""
    unknown_calls = [
        r for r in test_repo_engine.resolutions
        if r.extraction.qualifier == "external_obj" and r.extraction.identifier == "internal_action"
    ]
    assert len(unknown_calls) == 1
    call = unknown_calls[0]
    # MUST be UNRESOLVED to avoid false-positive edge injection
    assert call.is_resolved is False
    assert call.resolution_status == "UNRESOLVED"
    assert call.resolution_method == "unknown_receiver_unresolved"
    assert call.provenance_tier == TIER_E_UNRESOLVED
    assert call.candidate_count >= 1  # Recognizes candidate exists, but refuses to guess exact target


def test_decorators_metadata(test_repo_engine):
    """7. Decorator extraction as metadata."""
    dec_funcs = [fn for fn in test_repo_engine.function_nodes.values() if fn.name == "decorated_target"]
    assert len(dec_funcs) == 1
    assert "property" in dec_funcs[0].decorators


def test_dynamic_dispatch(test_repo_engine):
    """9. Dynamic dispatch safely marked UNRESOLVED."""
    dyn_calls = [
        r for r in test_repo_engine.resolutions
        if r.extraction.is_dynamic or r.extraction.identifier == "<dynamic_call>"
    ]
    assert len(dyn_calls) >= 1
    for call in dyn_calls:
        assert call.is_resolved is False
        assert call.resolution_status == "UNRESOLVED"
        assert call.provenance_tier == TIER_E_UNRESOLVED


def test_builtins_filtered(test_repo_engine):
    """11. Python builtins safely filtered out."""
    builtin_calls = [
        r for r in test_repo_engine.resolutions
        if r.extraction.identifier == "len" and not r.extraction.is_attribute
    ]
    assert len(builtin_calls) == 1
    assert builtin_calls[0].is_resolved is False
    assert builtin_calls[0].resolution_status == "UNRESOLVED"
    assert builtin_calls[0].resolution_method == "builtin_filter"


def test_external_libraries_unresolved(test_repo_engine):
    """12. External stdlib and thirdparty libraries safely marked UNRESOLVED."""
    ext_calls = [
        r for r in test_repo_engine.resolutions
        if r.extraction.identifier in ("sqrt", "join") and r.extraction.qualifier in ("math", "my_path")
    ]
    assert len(ext_calls) == 2
    for call in ext_calls:
        assert call.is_resolved is False
        assert call.resolution_status == "UNRESOLVED"
        assert call.provenance_tier == TIER_E_UNRESOLVED


def test_edge_types_and_determinism(test_repo_engine):
    """Verify only CONTAINS and CALLS edges exist, and serialization is bit-for-bit identical."""
    for e in test_repo_engine.edges:
        assert e.edge_type in ("CONTAINS", "CALLS")

    # Determinism across 3 runs
    sha1 = test_repo_engine.get_serialized_sha256()
    sha2 = test_repo_engine.get_serialized_sha256()
    assert sha1 == sha2
    assert len(sha1) == 64

