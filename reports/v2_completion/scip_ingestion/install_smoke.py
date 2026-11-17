"""
Installation smoke test for the optional SCIP extra, run against an *installed* RepoNeedle.

    python install_smoke.py absent <repo-checkout>    # pip install reponeedle-<ver>.whl
    python install_smoke.py present <repo-checkout>   # pip install "reponeedle-<ver>.whl[scip]"

The checkout supplies the real scip-typescript fixture (tests/fixtures/scip/real/typescript).
"""

import importlib.util
import sys
from pathlib import Path

import reponeedle
from reponeedle import RepoNeedleEngine, ScipConfig
from reponeedle.core.scip_ingestion import ScipIngestionError, protobuf_status


def main(expect: str, checkout: str) -> int:
    real = Path(checkout) / "tests" / "fixtures" / "scip" / "real" / "typescript"
    config = ScipConfig(index_path=str(real / "index.scip"), allow_project_root_mismatch=True)
    print(f"reponeedle {reponeedle.__version__} from {reponeedle.__file__}")
    try:
        installed = importlib.util.find_spec("google.protobuf") is not None
    except ModuleNotFoundError:  # no `google` namespace at all
        installed = False
    print("protobuf installed:", installed)
    status = protobuf_status()
    print("status:", status)
    if expect == "absent":
        assert not status["available"]
        try:
            RepoNeedleEngine.from_directory(str(real), scip_config=config)
        except ScipIngestionError as exc:
            assert 'pip install -e ".[scip]"' in str(exc), exc
        else:
            raise AssertionError("SCIP ingestion should fail without the extra")
        skipped = RepoNeedleEngine.from_directory(str(real), scip_config=config.model_copy(update={"on_error": "skip"}))
        assert skipped.scip_diagnostics["status"] == "skipped"
        assert RepoNeedleEngine.from_directory(str(real)).scip_diagnostics is None
    else:
        assert status["available"], status
        engine = RepoNeedleEngine.from_directory(str(real), scip_config=config)
        d = engine.scip_diagnostics
        print("documents:", d["documents"]["matched"], "references:", d["references"]["total"],
              "edges added:", d["edges"]["added_to_graph"])
        assert d["status"] == "ingested" and d["documents"]["matched"] == 7
        assert d["edges"]["added_to_graph"] >= 1
        assert any(e.edge_type == "scip_reference" for e in engine.function_graph.edges)
    print(f"OK ({expect})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
