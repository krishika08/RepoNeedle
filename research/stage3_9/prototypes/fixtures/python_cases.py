"""
Python Synthetic Parser & Resolution Fixture.
Covers 9 required constructs for LFCG extraction and resolution:
1. Local direct calls
2. Module imports and aliases
3. Relative imports
4. Function shadowing
5. Nested functions
6. Methods and self calls
7. Decorators
8. Dynamic dispatch
9. Built-in calls
"""

# 2. Module imports and aliases
import math
import os.path as path_alias
from collections import defaultdict as ddict

# 3. Relative imports (simulated syntax)
# from .sibling_module import helper_fn
# from ..parent_module import parent_util

def local_target_a():
    return "target_a"

def local_target_b():
    return "target_b"

# 7. Decorators
def simple_decorator(fn):
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

# 1. Local direct calls
def caller_local_direct():
    val1 = local_target_a()
    val2 = local_target_b()
    return val1 + val2

# 2. Module imports and aliases in function
def caller_imported_calls():
    c = math.sqrt(16)
    p = path_alias.join("a", "b")
    d = ddict(list)
    return c, p, d

# 4. Function shadowing
def caller_shadowing():
    # Local variable shadows global function name
    local_target_a = lambda: "shadowed"
    res = local_target_a()  # Should resolve to local variable or be ambiguous, NOT local_target_a() function
    return res

# 5. Nested functions
def outer_enclosing_func():
    def inner_nested_worker():
        return local_target_a()
    return inner_nested_worker()

# 6. Methods and self calls
class ServiceWorker:
    def __init__(self, name: str):
        self.name = name

    def internal_helper(self):
        return f"helper_{self.name}"

    def execute_task(self):
        # Self method call
        h = self.internal_helper()
        # Direct local function call from inside method
        loc = local_target_a()
        return f"{h}:{loc}"

# 7. Decorated function call
@simple_decorator
def decorated_target():
    return "decorated"

def caller_decorated():
    return decorated_target()

# 8. Dynamic dispatch
def caller_dynamic_dispatch(target_name: str, handler_obj: object):
    func_map = {"a": local_target_a, "b": local_target_b}
    res1 = func_map.get(target_name, local_target_a)()  # Dynamic dictionary dispatch
    res2 = getattr(handler_obj, "dynamic_method")()     # Dynamic getattr dispatch
    return res1, res2

# 9. Built-in calls
def caller_builtins():
    items = [1, 2, 3]
    l = len(items)
    s = sum(items)
    print(l, s)
    return l, s

