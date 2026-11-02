"""
R2.2 — Test Intent Prior (TIP) Module.
Classifies query intent (test-seeking vs implementation-seeking) without oracle labels,
identifies candidate test roles, and applies an asymmetric prior.
"""
import json
import re
from typing import Dict, List, Optional, Set, Tuple

# Universal test directory and file affix patterns across languages
TEST_DIR_PATTERNS = [
    re.compile(r'(^|/)(tests?|__tests__|testsuite|spec|testing|src/test)(/|$)', re.IGNORECASE),
]

TEST_FILE_PATTERNS = [
    re.compile(r'(^|/)test_[^\s/]+\.py$', re.IGNORECASE),
    re.compile(r'_test\.(py|go|rs|cpp|cc|cxx|c|js|ts|jsx|tsx)$', re.IGNORECASE),
    re.compile(r'\.(test|spec)\.(js|ts|jsx|tsx)$', re.IGNORECASE),
    re.compile(r'(^|/)[^\s/]+Test(s|Case)?\.java$', re.IGNORECASE),
    re.compile(r'(^|/)tests?\.rs$', re.IGNORECASE),
]

# Query text triggers for test intent
TEST_KEYWORD_REGEX = re.compile(
    r'\b(test|tests|testsuite|unittest|spec|assert|assertion|coverage|reproduce|regression|fixture|mock)\b',
    re.IGNORECASE
)

TEST_ACTION_REGEX = re.compile(
    r'\b(find|locate|write|add|run|execute|verify|check)\b.*?\b(tests?|specs?|coverage)\b',
    re.IGNORECASE
)

TEST_COMMAND_REGEX = re.compile(
    r'\b(go\s+test|pytest|cargo\s+test|npm\s+test|jest|mvn\s+test|gradle\s+test)\b',
    re.IGNORECASE
)

CODE2TEST_STRUCTURE_KEYS = [
    "changed_file",
    "implementation_files",
    "changed_file_summary",
]

def is_test_candidate(path: str) -> bool:
    """
    Language-aware, repository-independent detector of test files.
    Returns True if the file path is a test file or located within a test folder.
    """
    if not path:
        return False
    norm = path.replace("\\", "/").strip()
    
    # Check directory patterns
    for pat in TEST_DIR_PATTERNS:
        if pat.search(norm):
            return True
            
    # Check filename patterns
    for pat in TEST_FILE_PATTERNS:
        if pat.search(norm):
            return True
            
    return False


class TestIntentClassifier:
    """
    Zero-oracle query intent classifier.
    Infers whether the user query is seeking test artifacts vs implementation artifacts.
    """
    __test__ = False

    @classmethod
    def predict_score(cls, query_text: str) -> float:
        """
        Calculates a continuous test intent score in [0.0, 1.0].
        Uses only runtime query text and metadata.
        """
        if not query_text:
            return 0.0

        score = 0.0
        text_lower = query_text.lower()

        # Check JSON structure
        try:
            d = json.loads(query_text)
            
            # Structural signal 1: changed implementation files provided
            if any(k in d for k in CODE2TEST_STRUCTURE_KEYS):
                score += 0.55
                
            # Structural signal 2: PR title/body mentions testing
            pr_title = str(d.get("pr_title", ""))
            pr_body = str(d.get("pr_body", ""))
            pr_text = f"{pr_title} {pr_body}".lower()
            
            if TEST_ACTION_REGEX.search(pr_text):
                score += 0.35
            elif TEST_KEYWORD_REGEX.search(pr_text):
                score += 0.20
                
            # Structural signal 3: command execution
            cmd = str(d.get("command", ""))
            if TEST_COMMAND_REGEX.search(cmd):
                # Distinguish: is the query looking for the test itself or the bug site?
                # If source_type is local_test_reproduction, it might be seeking code
                source_type = str(d.get("source_type", ""))
                if "local_test_reproduction" in source_type:
                    # In trace2code, the developer ran tests but is looking for the application bug
                    # Therefore, trace2code seeks CODE, not tests!
                    score += 0.05
                else:
                    score += 0.15
                    
            # Structural signal 4: review comment on code asking for test
            rev_comment = str(d.get("review_comment", ""))
            if rev_comment:
                if TEST_KEYWORD_REGEX.search(rev_comment):
                    score += 0.40
                else:
                    score -= 0.10

            # Structural signal 5: anchor_diff (ripple usually seeks code)
            if "anchor_diff" in d:
                score -= 0.20

        except Exception:
            # Fallback for plain text queries
            if TEST_ACTION_REGEX.search(text_lower):
                score += 0.60
            elif TEST_KEYWORD_REGEX.search(text_lower):
                score += 0.30

        # Bound score to [0.0, 1.0]
        return max(0.0, min(1.0, score))

    @classmethod
    def classify(cls, query_text: str, threshold: float = 0.5) -> bool:
        """Binary decision: True if query intent is test-seeking."""
        return cls.predict_score(query_text) >= threshold


class TestIntentPrior:
    """Applies asymmetric test-intent boosting to candidate scores."""
    __test__ = False

    def __init__(
        self,
        boost_weight: float = 1.5,
        threshold: float = 0.5,
        enabled: bool = True
    ):
        """
        Args:
            boost_weight: Multiplier applied to test candidates when test intent is active (e.g. 1.5 -> score * 2.5).
            threshold: Probability threshold for activating test intent.
            enabled: Toggle prior on/off.
        """
        self.boost_weight = boost_weight
        self.threshold = threshold
        self.enabled = enabled

    def apply(
        self,
        candidates: List[dict],
        query_text: str,
        boost_weight: Optional[float] = None
    ) -> Tuple[List[dict], Dict[str, any]]:
        """
        Apply asymmetric test intent prior.
        Returns:
            reordered_candidates: Candidate list with updated ranks and scores.
            telemetry: Diagnostic information (intent score, decision, boosted count).
        """
        weight = boost_weight if boost_weight is not None else self.boost_weight
        intent_prob = TestIntentClassifier.predict_score(query_text)
        is_test_intent = intent_prob >= self.threshold

        telemetry = {
            "intent_prob": intent_prob,
            "is_test_intent": is_test_intent,
            "boosted_candidates": [],
            "enabled": self.enabled,
            "boost_weight": weight,
        }

        if not self.enabled or not is_test_intent:
            # Return original candidates without alteration
            return list(candidates), telemetry

        modified_cands = []
        for c in candidates:
            cand_copy = dict(c)
            path = cand_copy.get("path", "")
            
            # Check current score
            current_score = cand_copy.get("current_score", cand_copy.get("m1_score", 0.0))
            
            if is_test_candidate(path):
                # Asymmetric boost: test files boosted by (1.0 + weight * intent_prob)
                multiplier = 1.0 + (weight * intent_prob)
                cand_copy["tip_boosted"] = True
                cand_copy["tip_multiplier"] = multiplier
                cand_copy["current_score"] = current_score * multiplier
                telemetry["boosted_candidates"].append(path)
            else:
                cand_copy["tip_boosted"] = False
                cand_copy["current_score"] = current_score
                
            modified_cands.append(cand_copy)

        # Stable sort by current_score descending, breaking ties with original m1_rank
        reordered = sorted(
            modified_cands,
            key=lambda x: (x.get("current_score", 0.0), -x.get("m1_rank", 9999)),
            reverse=True
        )

        # Update ranks
        for idx, c in enumerate(reordered, 1):
            c["rank"] = idx

        return reordered, telemetry

if __name__ == "__main__":
    from split import load_data
    train_data, val_data, _ = load_data()
    
    # Evaluate classifier on training set
    print("Evaluating TestIntentClassifier on Training Set (210 queries)...")
    y_true = []
    y_pred = []
    
    for q in train_data:
        # Ground truth task type (for evaluation metric only)
        # code2test is true test intent
        is_gold_test_task = (q["task_type"] == "code2test")
        pred = TestIntentClassifier.classify(q["query_text"])
        y_true.append(is_gold_test_task)
        y_pred.append(pred)
        
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt and yp)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if not yt and yp)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt and not yp)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if not yt and not yp)
    
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    acc = (tp + tn) / len(y_true)
    
    print(f"Classifier Metrics on Training Set:")
    print(f"  Accuracy:  {acc*100:.2f}% ({tp+tn}/{len(y_true)})")
    print(f"  Precision: {prec*100:.2f}% ({tp}/{tp+fp})")
    print(f"  Recall:    {rec*100:.2f}% ({tp}/{tp+fn})")
    print(f"  F1 Score:  {f1:.4f}")
    print(f"  Confusion Matrix: TP={tp}, FP={fp}, FN={fn}, TN={tn}")

