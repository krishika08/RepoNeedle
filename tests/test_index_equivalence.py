"""
V2 Stage 0: differential equivalence of engine lifecycles against fresh full builds.

Lifecycle operations available today and what they can match exactly:

| Operation                                   | Equals a fresh build over ...                                      |
| update_documents() replacing a path         | the same documents in the same order (exact)                       |
| update_documents() adding a new path        | the documents with the new one APPENDED; a fresh directory scan    |
|                                             | that places it elsewhere diverges (asserted below, not hidden)     |
| remove_documents()                          | the remaining documents in their existing order (exact)            |
| rename = remove_documents + update_documents | the renamed document appended (same caveat as additions)          |

Most scenarios use in-memory document lists, whose order is the discovery order, so results do not depend on the
platform's os.walk order. Directory scenarios cover only order-safe operations.
"""

import random
from pathlib import Path

import pytest

from equivalence_fixture import FILES, write_files
from index_equivalence import (TASK_TYPES, assert_equivalent, compare_index_state, load_queries)
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import FileDoc

ALL_QUERIES = load_queries()
SAMPLE = ALL_QUERIES[::15]           # 15 queries across the categories; the full corpus runs once below


def docs_from(files):
    """FileDocs as from_directory() would build them (symbols, imports, is_test, tokens, line counts)."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        root = write_files(Path(tmp), files)
        engine = RepoNeedleEngine.from_directory(str(root))
        by_path = {d.path: d for d in engine.docs}
    return [by_path[p] for p in files if p in by_path]


BASE_DOCS = docs_from(FILES)


def build(docs):
    return RepoNeedleEngine.from_documents([d.model_copy(deep=True) for d in docs])


def doc_with(path, text):
    return docs_from({path: text})[0]


def replace(docs, new):
    return [new if d.path == new.path else d for d in docs]


def check(engine, reference_docs, label, mutations, queries=SAMPLE, **kw):
    assert_equivalent(engine, build(reference_docs), label=label, mutations=mutations, queries=queries,
                      packing_queries=kw.pop("packing_queries", 5), **kw)


# ---------------------------------------------------------------------------------------------------------------
# The harness itself
# ---------------------------------------------------------------------------------------------------------------

def test_query_corpus_is_frozen_and_large_enough():
    assert len(ALL_QUERIES) >= 200
    assert len({q["id"] for q in ALL_QUERIES}) == len(ALL_QUERIES)
    categories = {q["category"] for q in ALL_QUERIES}
    assert {"identifier", "function_name", "path", "natural_language", "test_discovery", "stack_trace",
            "empty_match", "out_of_scope", "tie_candidates", "multi_signal", "unicode"} <= categories


def test_corpus_contains_exact_score_ties():
    engine = build(BASE_DOCS)
    tied = 0
    for q in ALL_QUERIES:
        scores = [float(s) for s in engine.lexical_index.score(q["text"]) if s > 0]
        tied += len(scores) != len(set(scores))
    assert tied > 0, "at least one query must produce an exact tie between non-zero BM25 scores"


def test_full_corpus_equivalence_after_a_lifecycle_round_trip():
    """All 225 queries x 5 rankers, abstention, anchored change impact, and the CUD-Pack matrix."""
    engine = build(BASE_DOCS)
    removed = engine.remove_documents(["shop/cart.py", "legacy/utils.py"])
    engine.update_documents([d for d in BASE_DOCS if d.path in removed])
    order = [d for d in BASE_DOCS if d.path not in removed] + [d for d in BASE_DOCS if d.path in removed]
    assert_equivalent(engine, build(order), label="remove + re-add round trip", queries=ALL_QUERIES,
                      mutations=["remove shop/cart.py, legacy/utils.py", "update_documents (re-add, appended)"],
                      packing_queries=12)


def test_task_type_matrix_equivalence():
    engine = build(BASE_DOCS)
    engine.update_documents(list(engine.docs))
    assert_equivalent(engine, build(BASE_DOCS), label="task-type matrix after a full in-place refit",
                      queries=ALL_QUERIES[::3], task_types=TASK_TYPES, packing_queries=None)


def test_harness_detects_a_different_discovery_order():
    """Order is an input of every index: the harness must report it, never sort it away."""
    report = compare_index_state(build(list(reversed(BASE_DOCS))), build(BASE_DOCS))
    for component in ("documents", "bm25", "semantic", "repo_graph", "function_graph"):
        assert report[component], f"{component}: a reversed document order went undetected"


def test_harness_reports_location_and_mutation_sequence():
    engine = build(BASE_DOCS)
    engine.semantic_index.idf[0] += 1.0
    with pytest.raises(AssertionError) as err:
        assert_equivalent(engine, build(BASE_DOCS), label="perturbed", mutations=["idf[0] += 1"],
                          retrieval=False)
    text = str(err.value)
    assert "semantic['idf']" in text and "flat index 0" in text and "idf[0] += 1" in text


# ---------------------------------------------------------------------------------------------------------------
# Mutation scenarios
# ---------------------------------------------------------------------------------------------------------------

def test_modify_body_without_changing_symbols():
    new = doc_with("shop/pricing.py", FILES["shop/pricing.py"].replace("round(amount", "round(1.0 * amount"))
    old = next(d for d in BASE_DOCS if d.path == new.path)
    assert new.symbols == old.symbols and new.content != old.content
    engine = build(BASE_DOCS)
    engine.update_documents([new])
    check(engine, replace(BASE_DOCS, new), "body-only edit", ["update shop/pricing.py (body)"])


def test_modify_symbols():
    new = doc_with("shop/pricing.py", FILES["shop/pricing.py"] + "\n\ndef surcharge(amount):\n    return amount + 1\n")
    assert "surcharge" in new.symbols
    engine = build(BASE_DOCS)
    engine.update_documents([new])
    check(engine, replace(BASE_DOCS, new), "symbol-adding edit", ["update shop/pricing.py (adds surcharge)"])


NEW_DOC_TEXT = "from shop.pricing import apply_discount\n\n\ndef loyalty(amount):\n    return apply_discount(amount, 5)\n"


def test_add_document_matches_a_build_with_it_appended():
    new = doc_with("shop/loyalty.py", NEW_DOC_TEXT)
    engine = build(BASE_DOCS)
    engine.update_documents([new])
    check(engine, BASE_DOCS + [new], "addition (appended)", ["update_documents(add shop/loyalty.py)"])


def test_add_document_diverges_from_a_discovery_ordered_build():
    """Known Stage 0 limitation: update_documents() appends; a fresh scan may place the file elsewhere."""
    new = doc_with("shop/loyalty.py", NEW_DOC_TEXT)
    engine = build(BASE_DOCS)
    engine.update_documents([new])
    position = [d.path for d in BASE_DOCS].index("shop/inventory.py") + 1
    discovery_ordered = BASE_DOCS[:position] + [new] + BASE_DOCS[position:]
    report = compare_index_state(engine, build(discovery_ordered))
    assert report["documents"] and any("order" in m for m in report["documents"]), report["documents"]
    assert report["bm25"] and report["semantic"], "order-dependent index state must differ"


def test_remove_document():
    engine = build(BASE_DOCS)
    engine.remove_documents(["shop/inventory.py"])
    check(engine, [d for d in BASE_DOCS if d.path != "shop/inventory.py"], "removal",
          ["remove_documents(shop/inventory.py)"])


def test_rename_document():
    old = "shop/api/routes.py"
    new = doc_with("shop/api/handlers.py", FILES[old])
    engine = build(BASE_DOCS)
    engine.remove_documents([old])
    engine.update_documents([new])
    check(engine, [d for d in BASE_DOCS if d.path != old] + [new], "rename (remove + add)",
          [f"remove_documents({old})", "update_documents(add shop/api/handlers.py)"])


def test_remove_one_of_two_duplicate_definitions():
    engine = build(BASE_DOCS)
    engine.remove_documents(["legacy/utils.py"])
    check(engine, [d for d in BASE_DOCS if d.path != "legacy/utils.py"], "remove a duplicate normalize()",
          ["remove_documents(legacy/utils.py)"])


def test_add_a_second_global_definition():
    new = doc_with("shop/api/slug.py", "def slugify(value):\n    return value\n")
    engine = build(BASE_DOCS)
    engine.update_documents([new])
    check(engine, BASE_DOCS + [new], "second definition of slugify()", ["update_documents(add shop/api/slug.py)"])


def test_remove_an_imported_module():
    engine = build(BASE_DOCS)
    engine.remove_documents(["shop/utils/config.py"])
    check(engine, [d for d in BASE_DOCS if d.path != "shop/utils/config.py"], "remove shop.utils.config",
          ["remove_documents(shop/utils/config.py)"])


def test_change_a_module_and_package_name():
    moved = doc_with("shop/text/strings.py", FILES["shop/utils/strings.py"])
    importers = [doc_with(p, FILES[p].replace("shop.utils.strings", "shop.text.strings")
                          .replace(".utils.strings", ".text.strings"))
                 for p in ("shop/cart.py", "shop/inventory.py")]
    engine = build(BASE_DOCS)
    engine.remove_documents(["shop/utils/strings.py"])
    engine.update_documents(importers + [moved])
    expected = [d for d in BASE_DOCS if d.path != "shop/utils/strings.py"]
    for imp in importers:
        expected = replace(expected, imp)
    check(engine, expected + [moved], "module/package rename",
          ["remove_documents(shop/utils/strings.py)", "update importers", "update_documents(add shop/text/strings.py)"])


def test_repeated_in_place_refits():
    engine = build(BASE_DOCS)
    for _ in range(3):
        engine.update_documents(list(engine.docs))
    check(engine, BASE_DOCS, "three full in-place refits", ["update_documents(all) x3"])


def test_rebuild_in_a_different_discovery_order():
    engine = build(BASE_DOCS)
    engine.remove_documents([d.path for d in BASE_DOCS])
    engine.update_documents(list(reversed(BASE_DOCS)))
    check(engine, list(reversed(BASE_DOCS)), "rebuild in reversed order", ["remove all", "add all reversed"])


def test_empty_repository(tmp_path):
    (tmp_path / "empty").mkdir()
    scanned = RepoNeedleEngine.from_directory(str(tmp_path / "empty"))
    assert scanned.docs == []
    lifecycle = build(BASE_DOCS[:3])
    lifecycle.remove_documents([d.path for d in BASE_DOCS[:3]])
    assert_equivalent(lifecycle, RepoNeedleEngine(), label="emptied engine vs never-fitted engine",
                      queries=SAMPLE, packing_queries=5)
    found = compare_index_state(scanned, RepoNeedleEngine())
    assert [m for m in found["documents"] if "indexing_diagnostics" not in m] == []
    assert not any(v for k, v in found.items() if k != "documents")


def test_single_file_repository():
    only = doc_with("solo.py", "def solo(x):\n    return x * 2\n")
    engine = build([only])
    edited = doc_with("solo.py", "def solo(x):\n    return x * 3\n\n\ndef duo():\n    return 2\n")
    engine.update_documents([edited])
    check(engine, [edited], "single-file repository edit", ["update solo.py"])


def test_unicode_heavy_identifiers_and_content():
    text = FILES["i18n/übersetzung.py"] + "\n\ndef übergröße_prüfen(größe):\n    return größe in ('XL', 'XXL', '特大')\n"
    new = doc_with("i18n/übersetzung.py", text)
    assert "übergröße_prüfen" in new.symbols
    engine = build(BASE_DOCS)
    engine.update_documents([new])
    unicode_queries = [q for q in ALL_QUERIES if q["category"] == "unicode"]
    check(engine, replace(BASE_DOCS, new), "Unicode edit", ["update i18n/übersetzung.py"], queries=unicode_queries)


def test_large_document_within_the_file_size_limit(tmp_path):
    from equivalence_fixture import _large_module

    big = _large_module(2600)
    assert 300_000 < len(big.encode("utf-8")) < 500_000
    files = {**FILES, "shop/rules_catalogue.py": big}
    root = write_files(tmp_path / "repo", files)
    engine = RepoNeedleEngine.from_directory(str(root))
    assert any(d.path == "shop/rules_catalogue.py" for d in engine.docs)
    edited = big.replace("def rule_1300(", "def rule_1300_renamed(")
    (root / "shop" / "rules_catalogue.py").write_text(edited, encoding="utf-8", newline="\n")
    reference = RepoNeedleEngine.from_directory(str(root))
    engine.update_documents([reference.path_to_doc["shop/rules_catalogue.py"]])
    # Index state in full; retrieval and packing on a small sample (packing a 15,000-line file is slow).
    assert_equivalent(engine, reference, label="large document edit (directory)", queries=ALL_QUERIES[::75],
                      mutations=["edit shop/rules_catalogue.py on disk", "update_documents"], packing_queries=None)


def test_directory_modification_matches_a_fresh_scan(tmp_path):
    root = write_files(tmp_path / "repo", FILES)
    engine = RepoNeedleEngine.from_directory(str(root))
    (root / "shop" / "cart.py").write_text(FILES["shop/cart.py"] + "\n\ndef empty_cart():\n    return Cart()\n",
                                           encoding="utf-8", newline="\n")
    reference = RepoNeedleEngine.from_directory(str(root))
    engine.update_documents([reference.path_to_doc["shop/cart.py"]])
    assert_equivalent(engine, reference, label="directory edit", queries=SAMPLE, packing_queries=5,
                      mutations=["edit shop/cart.py on disk", "update_documents"])


# ---------------------------------------------------------------------------------------------------------------
# Seeded mutation sequences
# ---------------------------------------------------------------------------------------------------------------

def _random_step(rng, model, counter):
    """One random lifecycle step; returns (description, apply(engine)) and updates ``model`` (expected order)."""
    op = rng.choice(["modify", "remove", "add"] if len(model) > 3 else ["modify", "add"])
    if op == "modify":
        target = rng.choice(model)
        new = doc_with(target.path, target.content + f"\n# edit {counter}\n" + (
            f"\ndef generated_{counter}():\n    return {counter}\n" if target.path.endswith(".py") else ""))
        model[:] = replace(model, new)
        return f"modify {target.path}", lambda e: e.update_documents([new])
    if op == "remove":
        target = rng.choice(model)
        model[:] = [d for d in model if d.path != target.path]
        return f"remove {target.path}", lambda e: e.remove_documents([target.path])
    new = doc_with(f"gen/mod_{counter}.py",
                   f"from shop.pricing import apply_discount\n\n\ndef gen_{counter}(x):\n    return apply_discount(x, {counter % 50 + 1})\n")
    model.append(new)
    return f"add {new.path}", lambda e: e.update_documents([new])


@pytest.mark.parametrize("seed", [11, 23, 42])
def test_seeded_mutation_sequences(seed):
    rng = random.Random(seed)
    model = list(BASE_DOCS)
    engine = build(model)
    applied = []
    for step in range(6):
        description, apply = _random_step(rng, model, step)
        apply(engine)
        applied.append(description)
        check(engine, model, f"seed {seed}, step {step}", applied, queries=ALL_QUERIES[seed % 7::45],
              packing_queries=None)
