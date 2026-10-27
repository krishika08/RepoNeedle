"""
Tests for SelectiveAbstainer.
"""

import pytest
import numpy as np
from reponeedle.models import FileDoc
from reponeedle.core.abstention import SelectiveAbstainer


def test_abstention_on_counterfactual():
    docs = [
        FileDoc(path="app.py", content="class FlaskApp: pass\n", symbols=["FlaskApp"]),
        FileDoc(path="routes.py", content="def index(): pass\n", symbols=["index"]),
    ]
    abstainer = SelectiveAbstainer(confidence_threshold=0.35).fit(docs)
    # Query with 0 repository symbols (e.g. rust cargo serde)
    zero_scores = np.array([0.05, 0.04], dtype=np.float32)
    abstained, conf, reason = abstainer.evaluate_abstention("Cargo.toml serde_json rust compilation", zero_scores)
    assert abstained is True
    assert conf < 0.35


def test_no_abstention_on_confident_match():
    docs = [
        FileDoc(path="app.py", content="class FlaskApp: pass\n", symbols=["FlaskApp"]),
        FileDoc(path="routes.py", content="def index(): pass\n", symbols=["index"]),
    ]
    abstainer = SelectiveAbstainer(confidence_threshold=0.35).fit(docs)
    # Query matching FlaskApp with high peak-to-noise ratio
    scores = np.array([0.95, 0.05], dtype=np.float32)
    abstained, conf, reason = abstainer.evaluate_abstention("FlaskApp index", scores)
    assert abstained is False
    assert conf >= 0.35

