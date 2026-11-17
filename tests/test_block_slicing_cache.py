"""
AST block-slicing caches (digest keys, LRU with entry and estimated-byte budgets) and the ``cap_lines`` contract.

No optional extras: Python fixtures only. Estimated sizes are compared with tracemalloc measurements only within a
wide tolerance; they are estimates of retained Python objects, not process memory.
"""

import gc
import hashlib
import textwrap
import tracemalloc
import weakref

import pytest

from block_slicing_support import LANGUAGE_FIXTURES, assert_exact, read
from reponeedle.core import block_slicing as bs
from reponeedle.core.bounded_cache import ByteBudgetLRU
from reponeedle.core.packer import CodeSpanExtractor

INVENTORY = read(LANGUAGE_FIXTURES["python"])


def many_functions(n: int, body_lines: int = 3, prefix: str = "f") -> str:
    out = ["import math", ""]
    for i in range(n):
        out += [f"def {prefix}{i}(x):"] + [f"    y{k} = math.floor(x) + {i} + {k}  # term" for k in range(body_lines)]
        out += ["    return x", ""]
    return "\n".join(out) + "\n"


# --- ByteBudgetLRU -------------------------------------------------------------------------------------

def test_lru_evicts_least_recently_used_first():
    c = ByteBudgetLRU(max_entries=3, max_bytes=10_000)
    for k in "abc":
        c.put(k, k.upper(), 10)
    assert c.get("a") == "A"                       # refreshes "a"
    c.put("d", "D", 10)
    assert "b" not in c and list(c._data) == ["c", "a", "d"]
    assert c.get("b") is ByteBudgetLRU.MISSING
    assert c.stats()["evictions"] == 1 and c.hits == 1 and c.misses == 1


def test_lru_enforces_the_byte_budget_and_rejects_oversized_entries():
    c = ByteBudgetLRU(max_entries=100, max_bytes=1000, max_entry_fraction=0.25)
    assert c.max_entry_bytes == 250
    for i in range(10):
        assert c.put(i, i, 200)
        assert c.estimated_bytes <= 1000
    assert len(c) == 5 and list(c._data) == [5, 6, 7, 8, 9]
    assert not c.put("huge", "x", 251)             # > 25 % of the budget: not cached
    assert "huge" not in c and c.rejected_oversized == 1 and len(c) == 5
    c.put(9, "again", 100)                          # replacing an entry updates the accounting
    assert c.estimated_bytes == 4 * 200 + 100
    c.clear()
    assert len(c) == 0 and c.estimated_bytes == 0


@pytest.mark.parametrize("kwargs", [dict(max_entries=0, max_bytes=1), dict(max_entries=1, max_bytes=0),
                                    dict(max_entries=1, max_bytes=1, max_entry_fraction=0)])
def test_lru_rejects_invalid_limits(kwargs):
    with pytest.raises(ValueError):
        ByteBudgetLRU(**kwargs)


# --- digest keys -------------------------------------------------------------------------------------------

def test_cache_keys_hold_a_sha256_digest_not_the_content():
    ex = CodeSpanExtractor()
    ex.extract_block_span(INVENTORY, "inv.py", {"ceil"})
    digest = hashlib.sha256(INVENTORY.encode("utf-8")).digest()
    for cache in (ex._structure_cache, ex._block_cache):
        for key in cache._data:
            assert key[0] == "inv.py" and key[1] == digest
            assert all(part is not INVENTORY and part != INVENTORY for part in key)


def test_same_content_under_different_paths_is_cached_separately():
    ex = CodeSpanExtractor()
    a = ex.extract_block_span(INVENTORY, "a/inv.py", {"ceil"})
    b = ex.extract_block_span(INVENTORY, "b/inv.py", {"ceil"})
    t = ex.extract_block_span(INVENTORY, "b/inv.txt", {"ceil"})       # other language: legacy fallback
    assert a == b and t == CodeSpanExtractor().extract_focus_span(INVENTORY, "b/inv.txt", {"ceil"})
    assert len(ex._structure_cache) == 3 and len(ex._block_cache) == 3


def test_changed_content_is_never_served_from_the_cache():
    ex = CodeSpanExtractor()
    first, _ = ex.extract_block_span(INVENTORY, "inv.py", {"ceil"})
    modified = INVENTORY.replace("math.ceil((threshold - current) * 1.5)", "math.ceil((threshold - current) * 2.5)")
    second, _ = ex.extract_block_span(modified, "inv.py", {"ceil"})
    assert "* 2.5" in second and "* 1.5" not in second and "* 1.5" in first
    assert_exact(second, modified)
    third, _ = ex.extract_block_span(INVENTORY, "inv.py", {"ceil"})     # original content again: original result
    assert third == first


def test_query_terms_are_cached_separately_and_the_structure_is_shared():
    ex = CodeSpanExtractor()
    results = {frozenset(q): ex.extract_block_span(INVENTORY, "inv.py", q)
               for q in ({"ceil"}, {"release"}, {"ceil", "release"})}
    assert len(set(results.values())) == 3
    stats = ex.block_cache_stats()
    assert stats["span"]["entries"] == 3
    assert stats["structure"]["entries"] == 1 and stats["structure"]["misses"] == 1 and stats["structure"]["hits"] == 2


def test_repeated_queries_reuse_the_cached_result():
    ex = CodeSpanExtractor()
    first = ex.slice_blocks(INVENTORY, "inv.py", {"ceil"})
    for _ in range(3):
        assert ex.slice_blocks(INVENTORY, "inv.py", {"ceil"}) is first
    assert ex.block_cache_stats()["span"]["hits"] == 3
    assert ex.extract_block_span(INVENTORY, "inv.py", ["ceil"]) == ex.extract_block_span(INVENTORY, "inv.py", {"ceil"})


# --- budgets and eviction ----------------------------------------------------------------------------------

def test_span_cache_respects_its_byte_budget_under_churn():
    ex = CodeSpanExtractor(span_cache_bytes=60_000, structure_cache_bytes=400_000)
    for i in range(60):
        content = many_functions(25, prefix=f"g{i}_")
        ex.extract_block_span(content, f"m{i}.py", {"term"})
        stats = ex.block_cache_stats()
        assert stats["span"]["estimated_bytes"] <= 60_000
        assert stats["structure"]["estimated_bytes"] <= 400_000
    assert stats["span"]["evictions"] > 0 and stats["structure"]["evictions"] > 0
    assert len(ex._block_cache) < 60


def test_entry_count_limit_still_applies(monkeypatch):
    monkeypatch.setattr(CodeSpanExtractor, "BLOCK_SPAN_CACHE_SIZE", 4)
    ex = CodeSpanExtractor()
    for i in range(10):
        ex.extract_block_span(INVENTORY, f"m{i}.py", {"ceil"})
    assert len(ex._block_cache) == 4 and list(k[0] for k in ex._block_cache._data) == ["m6.py", "m7.py", "m8.py",
                                                                                       "m9.py"]


def test_oversized_entries_are_computed_but_not_retained(monkeypatch):
    big = many_functions(400)
    calls = []
    real = bs.analyze_structure
    monkeypatch.setattr(bs, "analyze_structure", lambda c, p: calls.append(p) or real(c, p))
    ex = CodeSpanExtractor(structure_cache_bytes=200_000)            # one entry may use at most 25,000 bytes
    small = ex.extract_block_span(INVENTORY, "small.py", {"ceil"})
    first = ex.extract_block_span(big, "big.py", {"f399"})
    assert "def f399(x):" in first[0]
    stats = ex.block_cache_stats()["structure"]
    assert stats["rejected_oversized"] == 1 and stats["entries"] == 1     # the small file stays cached
    assert ex.extract_block_span(big, "big.py", {"f398"})[0] != first[0]
    assert calls.count("big.py") == 2 and calls.count("small.py") == 1    # big file re-parsed, never cached
    assert ex.extract_block_span(INVENTORY, "small.py", {"ceil"}) == small


def test_eviction_releases_the_cached_objects():
    ex = CodeSpanExtractor()
    ex._structure_cache = ByteBudgetLRU(1, 10 ** 9)
    ex._block_cache = ByteBudgetLRU(1, 10 ** 9)
    ex.extract_block_span(INVENTORY, "old.py", {"ceil"})
    structure_ref = weakref.ref(next(iter(ex._structure_cache._data.values()))[0])
    slice_ref = weakref.ref(next(iter(ex._block_cache._data.values()))[0][1])
    assert structure_ref() is not None and slice_ref() is not None
    ex.extract_block_span(INVENTORY.replace("ceil", "floor"), "new.py", {"floor"})
    gc.collect()
    assert structure_ref() is None and slice_ref() is None


def test_estimated_bytes_track_measured_retained_allocations():
    content = many_functions(300)
    gc.collect()
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    result = bs.analyze_structure(content, "m.py")
    gc.collect()
    measured = tracemalloc.get_traced_memory()[0] - before
    tracemalloc.stop()
    estimated = bs.estimate_structure_bytes(result)
    assert 0.5 * measured <= estimated <= 2.0 * measured, (estimated, measured)


# --- cap_lines: a soft budget that never truncates a block ---------------------------------------------------

def _span_lines(sliced):
    return [(name, start, end) for _, name, start, end in sliced.selected]


def test_default_cap_matches_the_slicer_defaults():
    ex = CodeSpanExtractor()
    content = many_functions(12, body_lines=20)
    assert ex.slice_blocks(content, "m.py", {"term"}).selected == bs.slice_blocks(content, "m.py", {"term"}).selected
    assert len(ex.slice_blocks(content, "m.py", {"term"}).selected) == 5


@pytest.mark.parametrize("cap,expected_blocks", [(1, 1), (21, 1), (43, 1), (44, 2), (66, 3), (500, 5)])
def test_cap_lines_limits_additional_blocks_only(cap, expected_blocks):
    content = many_functions(12, body_lines=20)                         # each function is 22 lines
    ex = CodeSpanExtractor()
    sliced = ex.slice_blocks(content, "m.py", {"term"}, cap_lines=cap)
    assert len(sliced.selected) == expected_blocks
    text, _ = ex.extract_block_span(content, "m.py", {"term"}, cap_lines=cap)
    assert_exact(text, content)
    lines = bs.split_lines(content)
    for _, start, end in _span_lines(sliced):                            # every selected block is complete
        assert "\n".join(lines[start - 1:end]) in text
        assert end - start + 1 == 22


def test_a_block_longer_than_the_cap_is_returned_whole():
    content = textwrap.dedent("""\
        import math


        def long_function(x):
        """) + "".join(f"    step_{i} = math.floor(x) + {i}  # target\n" for i in range(90)) + \
        "    return x\n" + "".join(f"\nCONST_{i} = {i}" for i in range(10)) + "\n"
    ex = CodeSpanExtractor()
    sliced = ex.slice_blocks(content, "m.py", {"target"}, cap_lines=10)
    assert _span_lines(sliced) == [("long_function", 4, 95)]
    text, _ = ex.extract_block_span(content, "m.py", {"target"}, cap_lines=10)
    assert "step_89" in text and "    return x" in text
    assert_exact(text, content)


def test_oversized_blocks_keep_their_rule_whatever_the_cap():
    huge = "def huge():\n" + "".join(f"    s{i} = target\n" for i in range(150)) + "    return 0\n"
    content = huge + "".join(f"\nC{i} = {i}" for i in range(10)) + "\n"
    ex = CodeSpanExtractor()
    for cap in (None, 10, 1000):
        sliced = ex.slice_blocks(content, "m.py", {"target"}, cap_lines=cap)
        assert sliced.text is None and sliced.fallback_reason == "oversized_block"


def test_cap_lines_is_part_of_the_cache_key():
    content = many_functions(12, body_lines=20)
    ex = CodeSpanExtractor()
    one = ex.extract_block_span(content, "m.py", {"term"}, cap_lines=30)
    five = ex.extract_block_span(content, "m.py", {"term"})
    assert one != five and len(ex._block_cache) == 2
    assert ex.extract_block_span(content, "m.py", {"term"}, cap_lines=30) == one


def test_cap_lines_reaches_the_legacy_fallback_unchanged():
    content = "\n".join(f"function reserve{i}() {{ return {i}; }}" for i in range(80)) + "\n"
    for cap in (3, 30, None):
        expected = CodeSpanExtractor().extract_focus_span(content, "app.js", {"reserve"},
                                                          65 if cap is None else cap)
        assert CodeSpanExtractor().extract_block_span(content, "app.js", {"reserve"}, cap_lines=cap) == expected


@pytest.mark.parametrize("bad", [0, -5, 2.5, True, "10"])
def test_invalid_cap_lines_is_rejected(bad):
    with pytest.raises(ValueError):
        CodeSpanExtractor().extract_block_span(INVENTORY, "inv.py", {"ceil"}, cap_lines=bad)
