import unittest
import numpy as np
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "research" / "stage3_9" / "prototypes"))
from fragment_lexical_engine import FragmentClassifier, MultiFieldFragmentBM25, tokenize_code


class TestFragmentLexicalEngine(unittest.TestCase):
    def test_tokenization(self):
        tokens = tokenize_code("def get_user_profile(user_id: int):")
        self.assertIn("user", tokens)
        self.assertIn("profile", tokens)
        self.assertIn("get", tokens)

    def test_classification_complete(self):
        clf = FragmentClassifier(repo="pallets/click", base_commit="test_commit")
        candidate_files = {"src/click/core.py"}

        valid_chunk = {
            "path": "src/click/core.py",
            "start_line": 10,
            "end_line": 20,
            "text": """
            def format_help(ctx, formatter):
                \"\"\"Writes the help into the formatter if exists.\"\"\"
                return formatter.getvalue()
            """,
        }

        clf.ingest_chunk(valid_chunk, candidate_files)
        self.assertEqual(len(clf.complete_fragments), 1)
        frag = clf.complete_fragments[0]
        self.assertEqual(frag.name, "format_help")
        self.assertIn("ctx", frag.params)
        self.assertIn("formatter", frag.params)
        self.assertEqual(frag.docstring, "Writes the help into the formatter if exists.")
        self.assertEqual(clf.incomplete_headers_count, 0)
        self.assertEqual(clf.incomplete_bodies_count, 0)

    def test_classification_incomplete_header(self):
        clf = FragmentClassifier(repo="pallets/click", base_commit="test_commit")
        candidate_files = {"src/click/core.py"}

        # Incomplete header with unclosed paren
        bad_header_chunk = {
            "path": "src/click/core.py",
            "start_line": 10,
            "end_line": 20,
            "text": "def broken_func(arg1, arg2",
        }
        clf.ingest_chunk(bad_header_chunk, candidate_files)
        self.assertEqual(len(clf.complete_fragments), 0)
        self.assertEqual(clf.incomplete_headers_count, 1)

    def test_classification_incomplete_body(self):
        clf = FragmentClassifier(repo="pallets/click", base_commit="test_commit")
        candidate_files = {"src/click/core.py"}

        # Incomplete body with unterminated string
        bad_body_chunk = {
            "path": "src/click/core.py",
            "start_line": 10,
            "end_line": 20,
            "text": """
            def parse_args(args):
                s = "unterminated string at chunk cutoff...
            """,
        }
        clf.ingest_chunk(bad_body_chunk, candidate_files)
        self.assertEqual(len(clf.complete_fragments), 0)
        self.assertEqual(clf.incomplete_bodies_count, 1)

    def test_deduplication(self):
        clf = FragmentClassifier(repo="pallets/click", base_commit="test_commit")
        candidate_files = {"src/click/core.py"}

        chunk = {
            "path": "src/click/core.py",
            "start_line": 10,
            "end_line": 20,
            "text": "def my_func(): pass",
        }
        # Ingest twice
        clf.ingest_chunk(chunk, candidate_files)
        clf.ingest_chunk(chunk, candidate_files)
        self.assertEqual(len(clf.complete_fragments), 1)

    def test_multi_field_scoring(self):
        clf = FragmentClassifier(repo="pallets/click", base_commit="test_commit")
        candidate_files = {"src/click/core.py", "src/click/parser.py"}

        c1 = {
            "path": "src/click/core.py",
            "start_line": 10,
            "end_line": 20,
            "text": """
            def command_formatter(ctx, buffer):
                \"\"\"Formats the command line help.\"\"\"
                return buffer.render()
            """,
        }
        c2 = {
            "path": "src/click/parser.py",
            "start_line": 30,
            "end_line": 40,
            "text": """
            def split_arg_string(string):
                \"\"\"Splits an argument string.\"\"\"
                return string.split()
            """,
        }
        clf.ingest_chunk(c1, candidate_files)
        clf.ingest_chunk(c2, candidate_files)

        index = MultiFieldFragmentBM25(clf.complete_fragments)
        tot, fields = index.score_query_per_field("format command line help")
        self.assertEqual(len(tot), 2)
        # First fragment matches doc and name
        self.assertGreater(tot[0], tot[1])
        self.assertGreater(fields["doc"][0], 0.0)


if __name__ == "__main__":
    unittest.main()

