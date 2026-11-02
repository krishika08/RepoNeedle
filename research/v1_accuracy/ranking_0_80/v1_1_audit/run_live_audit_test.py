import tempfile
import os
import shutil
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import FileDoc, Query, RankerType
from reponeedle.core.change_impact import ChangeImpactConfig, ChangeImpactRanker

def run_audit():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "app"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "tests"), exist_ok=True)

        with open(os.path.join(tmpdir, "app", "auth.py"), "w", encoding="utf-8") as f:
            f.write("def login(username, password):\n    return True\n")
        with open(os.path.join(tmpdir, "app", "session.py"), "w", encoding="utf-8") as f:
            f.write("import app.auth\ndef create_session(user):\n    return app.auth.login(user, '')\n")
        with open(os.path.join(tmpdir, "tests", "test_auth.py"), "w", encoding="utf-8") as f:
            f.write("import app.auth\ndef test_login():\n    assert app.auth.login('admin', 'pass')\n")
        with open(os.path.join(tmpdir, "README.md"), "w", encoding="utf-8") as f:
            f.write("# WebApp Project\nDocumentation for auth and sessions.\n")

        # 1. Test from_directory with default
        engine_default = RepoNeedleEngine.from_directory(tmpdir)
        print("1. Default Engine Ranker:", engine_default.ranker)
        assert engine_default.ranker == RankerType.LEGACY

        # Query with default
        q = Query(text="modify auth to use jwt", anchor_files=["app/auth.py"], budget_tokens=2000)
        res_default = engine_default.retrieve(q)
        print("2. Default retrieve returned files:", [f.path for f in res_default.packed_files])

        # 2. Test query-level opt-in
        res_ci = engine_default.retrieve(q, ranking_engine="change_impact")
        print("3. Change-impact retrieve returned files:", [f.path for f in res_ci.packed_files])
        top_file = res_ci.packed_files[0]
        print("   Top file:", top_file.path)
        print("   Explanation:", top_file.explanation)
        assert top_file.explanation is not None

        # 3. Test graph disabled
        cfg_no_graph = ChangeImpactConfig(enable_graph=False)
        engine_no_graph = RepoNeedleEngine.from_directory(tmpdir, ranker="change_impact", change_impact_config=cfg_no_graph)
        res_no_graph = engine_no_graph.retrieve(q)
        print("4. Graph disabled top file:", res_no_graph.packed_files[0].path)

        # 4. Test strict token budget CUD-pack
        q_budget = Query(text="modify auth to use jwt", budget_tokens=40)
        res_budget = engine_default.retrieve(q_budget, ranking_engine="change_impact")
        print("5. Strict 40-token budget packed tokens:", res_budget.total_tokens)
        assert res_budget.total_tokens <= 40

        # 5. Test fallback on error
        class ExplodingGraphRanker(ChangeImpactRanker):
            def evaluate_candidate_impact(self, *args, **kwargs):
                raise RuntimeError("Simulated Graph Traversal Exception")

        engine_fallback = RepoNeedleEngine.from_directory(tmpdir, ranker="change_impact")
        engine_fallback.change_impact_ranker = ExplodingGraphRanker()
        res_fallback = engine_fallback.retrieve(q)
        print("6. Fallback on error succeeded, returned:", [f.path for f in res_fallback.packed_files])
        assert len(res_fallback.packed_files) > 0
        assert "Fallback to baseline" in res_fallback.packed_files[0].explanation

    print("ALL LIVE PRODUCTION INTEGRATION AUDIT TESTS PASSED!")

if __name__ == "__main__":
    run_audit()
