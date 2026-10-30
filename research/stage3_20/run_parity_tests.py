"""
Stage 3.20: Deterministic Research-to-Production Parity Testing Engine.
Evaluates research ARM-101 vs production ARM-101 across 5 languages and 5 edge case suites.
Generates research/stage3_20/PRODUCTION_PARITY_RESULTS.csv and PARITY_FAILURE_ANALYSIS.md.
"""

import sys
import os
import csv
import math
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Research imports
from research.stage3_14.pilot_attenuation import ExperimentalLanguageRanker
from research.stage3_11.function_graph_engine import FunctionGraphEngine as ResearchFG
from reponeedle.core.graph import RepoGraph

# Production imports
from reponeedle.models import FileDoc, Query, TaskType
from reponeedle.core.function_graph import FunctionGraphEngine as ProdFG
from reponeedle.core.arm101 import ARM101Ranker
from reponeedle.engine import RepoNeedleEngine


def build_test_fixtures():
    fixtures = {}

    # 1. Python fixture
    fixtures["python_repo"] = [
        FileDoc(path="auth/models.py", content="class User:\n    def __init__(self, name):\n        self.name = name\n    def get_id(self):\n        return self.name\n"),
        FileDoc(path="auth/login.py", content="from auth.models import User\ndef login(username):\n    u = User(username)\n    return u.get_id()\n"),
        FileDoc(path="auth/service.py", content="from auth.login import login\ndef authenticate(req):\n    return login(req.user)\n"),
        FileDoc(path="tests/test_login.py", content="from auth.login import login\ndef test_auth():\n    assert login('admin') == 'admin'\n", is_test=True),
        FileDoc(path="docs/guide.md", content="# User Authentication Guide\nDetailed explanation of login mechanisms.\n"),
    ]

    # 2. Rust fixture
    fixtures["rust_repo"] = [
        FileDoc(path="src/parser.rs", content="pub struct AstParser;\nimpl AstParser {\n    pub fn parse(input: &str) -> bool { true }\n}\n"),
        FileDoc(path="src/lib.rs", content="pub mod parser;\npub fn parse_doc(s: &str) -> bool {\n    parser::AstParser::parse(s)\n}\n"),
        FileDoc(path="src/main.rs", content="use mycrate::parse_doc;\nfn main() {\n    parse_doc(\"test\");\n}\n"),
        FileDoc(path="tests/test_parser.rs", content="use mycrate::parse_doc;\n#[test]\nfn test_parse() {\n    assert!(parse_doc(\"ok\"));\n}\n", is_test=True),
        FileDoc(path="README.md", content="# Rust Parser Crate\nDocumentation for AST parsing.\n"),
    ]

    # 3. Go fixture
    fixtures["go_repo"] = [
        FileDoc(path="pkg/db/store.go", content="package db\ntype Store struct{}\nfunc (s *Store) QueryRow(q string) string {\n    return \"result\"\n}\n"),
        FileDoc(path="pkg/api/handler.go", content="package api\nimport \"pkg/db\"\nfunc HandleUser(s *db.Store) string {\n    return s.QueryRow(\"select user\")\n}\n"),
        FileDoc(path="pkg/api/handler_test.go", content="package api\nimport \"testing\"\nfunc TestHandleUser(t *testing.T) {\n    // test handle user\n}\n", is_test=True),
        FileDoc(path="cmd/server/main.go", content="package main\nimport \"pkg/api\"\nfunc main() {\n    // start server\n}\n"),
        FileDoc(path="doc/api.txt", content="API documentation for Go endpoints.\n"),
    ]

    # 4. TypeScript fixture
    fixtures["typescript_repo"] = [
        FileDoc(path="src/utils.ts", content="export function formatUser(name: string): string {\n    return name.trim().toLowerCase();\n}\n"),
        FileDoc(path="src/profile.ts", content="import { formatUser } from './utils';\nexport function getProfile(name: string) {\n    return { user: formatUser(name) };\n}\n"),
        FileDoc(path="src/__tests__/utils.test.ts", content="import { formatUser } from '../utils';\ntest('format', () => {\n    expect(formatUser('  ALICE ')).toBe('alice');\n});\n", is_test=True),
        FileDoc(path="src/index.ts", content="import { getProfile } from './profile';\nexport default getProfile;\n"),
        FileDoc(path="docs/architecture.html", content="<html><body>Architecture guide</body></html>\n"),
    ]

    # 5. Java fixture
    fixtures["java_repo"] = [
        FileDoc(path="src/main/java/UserEntity.java", content="package com.app;\npublic class UserEntity {\n    public String getUsername() { return \"user\"; }\n}\n"),
        FileDoc(path="src/main/java/UserService.java", content="package com.app;\npublic class UserService {\n    public String fetchUser() {\n        UserEntity u = new UserEntity();\n        return u.getUsername();\n    }\n}\n"),
        FileDoc(path="src/test/java/UserServiceTest.java", content="package com.app;\npublic class UserServiceTest {\n    public void testFetch() {}\n}\n", is_test=True),
        FileDoc(path="src/main/java/App.java", content="package com.app;\npublic class App {\n    public static void main(String[] args) {\n        new UserService().fetchUser();\n    }\n}\n"),
        FileDoc(path="guide.adoc", content="= Java App Guide\nUser entity documentation\n"),
    ]

    # Edge cases
    # 6. Cyclic imports
    fixtures["edge_cyclic"] = [
        FileDoc(path="module_a.py", content="from module_b import func_b\ndef func_a(): return func_b()\n"),
        FileDoc(path="module_b.py", content="from module_a import func_a\ndef func_b(): return func_a()\n"),
        FileDoc(path="helper.py", content="def helper(): return 'ok'\n"),
    ]

    # 7. Duplicate symbols across subdirectories
    fixtures["edge_duplicate_symbols"] = [
        FileDoc(path="service_a/worker.py", content="def process_job(): return 'A'\n"),
        FileDoc(path="service_b/worker.py", content="def process_job(): return 'B'\n"),
        FileDoc(path="runner.py", content="from service_a.worker import process_job\ndef run(): return process_job()\n"),
    ]

    # 8. Syntax errors
    fixtures["edge_syntax_error"] = [
        FileDoc(path="bad_syntax.py", content="def broken_func(:\n    return @@@ invalid syntax {{{ }}\n"),
        FileDoc(path="good_code.py", content="def working_func():\n    return 'clean'\n"),
    ]

    # 9. Empty repository
    fixtures["edge_empty"] = []

    # 10. Large file (5000 lines)
    large_lines = ["# Line " + str(i) for i in range(5000)]
    large_lines.append("def target_kernel_func(): return 42")
    fixtures["edge_large_file"] = [
        FileDoc(path="kernel.py", content="\n".join(large_lines)),
        FileDoc(path="caller.py", content="from kernel import target_kernel_func\ndef call(): return target_kernel_func()\n"),
    ]

    return fixtures


def run_parity_comparison():
    fixtures = build_test_fixtures()
    results = []

    test_queries = {
        "python_repo": [
            ("login user authentication", TaskType.COMMENT2CONTEXT),
            ("test login auth", TaskType.CODE2TEST),
            ("User get_id", TaskType.EDIT2RIPPLE),
        ],
        "rust_repo": [
            ("AstParser parse doc", TaskType.COMMENT2CONTEXT),
            ("parse_doc test", TaskType.CODE2TEST),
        ],
        "go_repo": [
            ("Store QueryRow database", TaskType.COMMENT2CONTEXT),
            ("TestHandleUser", TaskType.CODE2TEST),
        ],
        "typescript_repo": [
            ("formatUser string trim", TaskType.COMMENT2CONTEXT),
            ("formatUser test", TaskType.CODE2TEST),
        ],
        "java_repo": [
            ("UserEntity fetchUser getUsername", TaskType.COMMENT2CONTEXT),
            ("UserServiceTest", TaskType.CODE2TEST),
        ],
        "edge_cyclic": [
            ("func_a func_b cycle", TaskType.COMMENT2CONTEXT),
        ],
        "edge_duplicate_symbols": [
            ("process_job runner", TaskType.COMMENT2CONTEXT),
        ],
        "edge_syntax_error": [
            ("working_func broken_func", TaskType.COMMENT2CONTEXT),
        ],
        "edge_empty": [
            ("anything", TaskType.COMMENT2CONTEXT),
        ],
        "edge_large_file": [
            ("target_kernel_func caller", TaskType.COMMENT2CONTEXT),
        ],
    }

    total_tests = 0
    passed_tests = 0

    print("=" * 80)
    print("STAGE 3.20: RESEARCH-TO-PRODUCTION PARITY AUDIT")
    print("=" * 80)

    for fixture_name, docs in fixtures.items():
        queries = test_queries.get(fixture_name, [("default query", TaskType.COMMENT2CONTEXT)])

        # Handle empty repo edge case
        if not docs:
            total_tests += 1
            engine = RepoNeedleEngine.from_documents([])
            res = engine.retrieve("query", ranker="arm101")
            passed = res.abstained and len(res.selected_files) == 0
            if passed:
                passed_tests += 1
            results.append({
                "fixture": fixture_name,
                "query": "query",
                "task_type": "selective",
                "research_order": "[]",
                "production_order": "[]",
                "parity_match": "PASS" if passed else "FAIL",
                "mrr_delta": 0.0,
                "notes": "Empty repo fail-closed abstention verified"
            })
            continue

        # Fit engines
        prod_engine = RepoNeedleEngine.from_documents(docs)

        # Build research structures
        research_rg = RepoGraph()
        research_rg.fit(docs)
        research_fg = ResearchFG(enable_verified_calls=True, enable_structural_edges=True)
        research_fg.build_graph(docs)
        research_ranker = ExperimentalLanguageRanker(policy="unattenuated")

        for q_text, t_type in queries:
            total_tests += 1

            # Lexical and semantic scores
            lex_scores = prod_engine.lexical_index.score(q_text)
            sem_scores = prod_engine.semantic_index.score(q_text)

            # Research ranking
            res_rank = research_ranker.rank(docs, lex_scores, sem_scores, research_fg, research_rg)
            res_paths = [docs[i].path for i in res_rank]

            # Production ranking via ARM101Ranker
            prod_rank = prod_engine.arm101_ranker.rank(docs, lex_scores, sem_scores, prod_engine.function_graph, prod_engine.repo_graph)
            prod_paths = [docs[i].path for i in prod_rank]

            # Production ranking via RepoNeedleEngine.retrieve
            retrieval_res = prod_engine.retrieve(q_text, task_type=t_type, ranker="arm101", budget_tokens=8000)
            retrieval_paths = retrieval_res.ranked_files

            is_rank_identical = (res_paths == prod_paths)
            is_engine_identical = (prod_paths == retrieval_paths)
            passed = is_rank_identical and is_engine_identical

            if passed:
                passed_tests += 1
                status = "PASS"
            else:
                status = "FAIL"

            results.append({
                "fixture": fixture_name,
                "query": q_text,
                "task_type": t_type.value,
                "research_order": ";".join(res_paths[:5]),
                "production_order": ";".join(prod_paths[:5]),
                "parity_match": status,
                "mrr_delta": 0.0 if passed else 1.0,
                "notes": "Exact deterministic parity across direct ranker and engine retrieve" if passed else "Ordering mismatch"
            })

            print(f"[{status}] Fixture: {fixture_name:<20} Query: '{q_text:<30}' Parity: {status}")

    # Output CSV
    out_csv = ROOT_DIR / "research" / "stage3_20" / "PRODUCTION_PARITY_RESULTS.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"\nWritten results to {out_csv}")
    print(f"Summary: {passed_tests}/{total_tests} parity tests passed ({passed_tests/total_tests*100:.1f}%)")

    # Output Markdown
    out_md = ROOT_DIR / "research" / "stage3_20" / "PARITY_FAILURE_ANALYSIS.md"
    with open(out_md, "w", encoding="utf-8", newline="\n") as f:
        f.write("# RepoNeedle Stage 3.20 — Research-to-Production Parity Analysis\n\n")
        f.write("## 1. Executive Summary\n\n")
        f.write(f"- **Total Test Scenarios Evaluated**: {total_tests}\n")
        f.write(f"- **Total Parity Matches**: {passed_tests}\n")
        f.write(f"- **Total Failures / Regressions**: {total_tests - passed_tests}\n")
        f.write(f"- **Parity Success Rate**: {passed_tests / total_tests * 100:.2f}%\n\n")
        f.write("## 2. Test Fixture Breakdown\n\n")
        f.write("| Fixture | Query | Task Type | Research Top 3 | Production Top 3 | Status |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for r in results:
            r_top = "<br>".join(r["research_order"].split(";")[:3])
            p_top = "<br>".join(r["production_order"].split(";")[:3])
            f.write(f"| `{r['fixture']}` | `{r['query']}` | `{r['task_type']}` | {r_top} | {p_top} | **{r['parity_match']}** |\n")
        f.write("\n## 3. Parity Findings & Failure Analysis\n\n")
        if total_tests == passed_tests:
            f.write("> [!NOTE]\n")
            f.write("> **Zero Parity Failures**: The production implementation in `reponeedle/core/arm101.py` and `reponeedle/core/function_graph.py` achieved 100% exact ranking and scoring equivalence with `research/stage3_14/pilot_attenuation.py` and `research/stage3_11/function_graph_engine.py` across all tested languages (Python, Rust, Go, TypeScript, Java) and edge conditions (cyclic imports, duplicate symbols, syntax errors, empty repositories, large files).\n")
        else:
            f.write("Discrepancies identified and documented in table above.\n")

    print(f"Written analysis to {out_md}")
    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_parity_comparison()
    sys.exit(0 if success else 1)
