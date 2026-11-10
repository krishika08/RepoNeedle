"""
Tests for RepoNeedle CLI anchor file support (--anchors) and Change-Impact integration.
"""

import os
import sys
import json
import pytest
from pathlib import Path

from reponeedle.cli import main, build_parser, resolve_and_validate_anchors
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import TaskType, Query


@pytest.fixture
def change_impact_repo(tmp_path: Path) -> Path:
    """Creates a temporary project graph specifically designed to test change propagation."""
    repo = tmp_path / "impact_repo"
    repo.mkdir()

    src = repo / "src"
    src.mkdir()

    # 1. Seed file: payment.py
    (src / "payment.py").write_text(
        "class PaymentGateway:\n"
        "    def process_charge(self, amount: int) -> bool:\n"
        "        return amount > 0\n",
        encoding="utf-8"
    )

    # 2. Dependent file importing payment.py
    (src / "checkout.py").write_text(
        "from src.payment import PaymentGateway\n\n"
        "class CheckoutService:\n"
        "    def __init__(self):\n"
        "        self.gateway = PaymentGateway()\n"
        "    def checkout(self, amount: int):\n"
        "        return self.gateway.process_charge(amount)\n",
        encoding="utf-8"
    )

    # 3. Independent sibling
    (src / "inventory.py").write_text(
        "class InventoryManager:\n"
        "    def check_stock(self, item_id: str) -> int:\n"
        "        return 100\n",
        encoding="utf-8"
    )

    tests = repo / "tests"
    tests.mkdir()

    # 4. Test file matching payment stem
    (tests / "test_payment.py").write_text(
        "from src.payment import PaymentGateway\n\n"
        "def test_charge():\n"
        "    gw = PaymentGateway()\n"
        "    assert gw.process_charge(50) is True\n",
        encoding="utf-8"
    )
    return repo


class TestCLIAnchorSupport:
    """Test suite for anchor resolution and Change-Impact CLI integration."""

    def test_parser_accepts_single_and_multiple_anchors(self):
        parser = build_parser()
        args = parser.parse_args(["query", "--anchors", "src/payment.py"])
        assert args.anchors == ["src/payment.py"]

        args_multi = parser.parse_args(["query", "--anchors", "src/payment.py", "src/checkout.py"])
        assert args_multi.anchors == ["src/payment.py", "src/checkout.py"]

    def test_resolve_and_validate_anchors_normalization(self, change_impact_repo: Path):
        # Empty/None check
        assert resolve_and_validate_anchors(str(change_impact_repo), None) == []
        assert resolve_and_validate_anchors(str(change_impact_repo), []) == []

        # Relative to repo
        res = resolve_and_validate_anchors(str(change_impact_repo), ["src/payment.py"])
        assert res == ["src/payment.py"]

        # Backslash normalization
        res_bs = resolve_and_validate_anchors(str(change_impact_repo), ["src\\payment.py"])
        assert res_bs == ["src/payment.py"]

        # Absolute path resolution
        abs_p = str(change_impact_repo / "src" / "payment.py")
        res_abs = resolve_and_validate_anchors(str(change_impact_repo), [abs_p])
        assert res_abs == ["src/payment.py"]

        # Multiple anchors deduplicated in order
        res_multi = resolve_and_validate_anchors(
            str(change_impact_repo),
            ["src/payment.py", "src/checkout.py", "src/payment.py"]
        )
        assert res_multi == ["src/payment.py", "src/checkout.py"]

    def test_resolve_and_validate_anchors_invalid_path(self, change_impact_repo: Path):
        with pytest.raises(ValueError, match="does not exist or is not a regular file"):
            resolve_and_validate_anchors(str(change_impact_repo), ["src/nonexistent.py"])

    def test_resolve_and_validate_anchors_outside_repo(self, change_impact_repo: Path, tmp_path: Path):
        outside_file = tmp_path / "outside.py"
        outside_file.write_text("print('outside')", encoding="utf-8")

        with pytest.raises(ValueError, match="resolves outside repository root"):
            resolve_and_validate_anchors(str(change_impact_repo), [str(outside_file)])

    def test_cli_change_impact_single_anchor(self, change_impact_repo: Path, capsys: pytest.CaptureFixture):
        exit_code = main([
            "Fix payment gateway timeout",
            "--repo", str(change_impact_repo),
            "--ranker", "change_impact",
            "--anchors", "src/payment.py",
            "--json"
        ])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)

        assert data["status"] == "success"
        assert data["ranker"] == "change_impact"

        selected = data["selected_files"]
        paths = [s["path"] for s in selected]

        # checkout.py imports payment.py -> should be prioritized
        assert "src/checkout.py" in paths
        # test_payment.py matches payment stem -> should be prioritized
        assert "tests/test_payment.py" in paths

        # Verify Seed File Suppression (SFS): the seed file payment.py
        # must have explanation mentioning suppression or lower score than its dependents
        for item in selected:
            if item["path"] == "src/payment.py":
                assert "Suppressed query seed" in item["explanation"]

    def test_cli_change_impact_multiple_anchors(self, change_impact_repo: Path, capsys: pytest.CaptureFixture):
        exit_code = main([
            "Refactor payment and checkout pipeline",
            "--repo", str(change_impact_repo),
            "--ranker", "change_impact",
            "--anchors", "src/payment.py", "src/checkout.py",
            "--json"
        ])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)

        assert data["status"] == "success"
        # Both payment.py and checkout.py are seeds, both should be marked suppressed
        for item in data["selected_files"]:
            if item["path"] in ("src/payment.py", "src/checkout.py"):
                assert "Suppressed query seed" in item["explanation"]

    def test_cli_invalid_anchor_returns_exit_1_and_stderr(self, change_impact_repo: Path, capsys: pytest.CaptureFixture):
        exit_code = main([
            "Fix payment gateway",
            "--repo", str(change_impact_repo),
            "--ranker", "change_impact",
            "--anchors", "src/ghost.py",
            "--json"
        ])
        assert exit_code == 1
        captured = capsys.readouterr()

        # Stdout must not produce JSON on fatal argument error
        assert captured.out == ""
        assert "Error:" in captured.err
        assert "src/ghost.py" in captured.err

    def test_cli_legacy_ranker_with_anchors_routes_to_edit2ripple(self, change_impact_repo: Path, capsys: pytest.CaptureFixture):
        exit_code = main([
            "Evaluate payment changes",
            "--repo", str(change_impact_repo),
            "--ranker", "legacy",
            "--anchors", "src/payment.py",
            "--json"
        ])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)

        assert data["status"] == "success"
        # WorkflowRouter automatically classifies queries with anchors as edit2ripple
        assert data["task_type"] == "edit2ripple"

    def test_python_api_direct_anchor_files_argument(self, change_impact_repo: Path):
        engine = RepoNeedleEngine.from_directory(str(change_impact_repo))

        # Test retrieve() with anchor_files as List[str]
        result = engine.retrieve(
            query="Fix payment gateway timeout",
            anchor_files=["src/payment.py"],
            ranker="change_impact"
        )
        assert result.abstained is False
        assert result.ranker == "change_impact"
        paths = [sf.path for sf in result.selected_files]
        assert "src/checkout.py" in paths

        # Test query() alias with anchor_files
        result_alias = engine.query(
            "Fix payment gateway timeout",
            anchor_files=["src/payment.py"],
            ranker="change_impact"
        )
        assert result_alias.abstained is False
        assert result_alias.ranker == "change_impact"
