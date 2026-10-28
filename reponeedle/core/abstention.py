"""
Calibrated selective abstention engine for no-gold and out-of-repository queries.
Addresses the selective retrieval calibration gap identified in Agent Retrieval Bench.
"""

from typing import List, Dict, Set, Tuple
import numpy as np

from reponeedle.models import FileDoc
from reponeedle.core.tokenizer import CodeTokenizer


class SelectiveAbstainer:
    """
    Evaluates whether a query genuinely corresponds to evidence in the repository,
    or whether the retriever should abstain to avoid polluting the agent context window.
    """

    def __init__(self, confidence_threshold: float = 0.38):
        self.confidence_threshold = confidence_threshold
        self.tokenizer = CodeTokenizer()
        self.repo_vocabulary: Set[str] = set()

    def fit(self, docs: List[FileDoc]) -> "SelectiveAbstainer":
        """
        Builds repository vocabulary from paths, symbols, and contents.
        """
        self.repo_vocabulary = set()
        for doc in docs:
            # Add path tokens
            for t in self.tokenizer.tokenize_path(doc.path):
                self.repo_vocabulary.add(t.lower())
            # Add symbol tokens
            for s in doc.symbols:
                for t in self.tokenizer.tokenize_text(s):
                    self.repo_vocabulary.add(t.lower())
            # Add content identifiers if doc.content is present
            if doc.content:
                for t in self.tokenizer.tokenize_text(doc.content[:3000]):
                    if len(t) > 2:
                        self.repo_vocabulary.add(t.lower())

        return self

    def evaluate_abstention(
        self,
        query: str,
        fused_scores: np.ndarray,
    ) -> Tuple[bool, float, str]:
        """
        Evaluates abstention criteria.
        Returns:
            abstained (bool): True if system should abstain.
            confidence (float): Calibrated confidence score in [0, 1].
            reason (str): Diagnostic explanation.
        """
        if len(fused_scores) == 0:
            return True, 0.0, "Empty repository candidate set."

        q_tokens = self.tokenizer.tokenize_text(query)
        if not q_tokens:
            return True, 0.0, "Empty or stop-word only query."

        # 1. Lexical Overlap Ratio against repository symbol vocabulary
        meaningful_tokens = [t for t in q_tokens if len(t) > 2]
        if not meaningful_tokens:
            overlap_ratio = 0.5
        else:
            in_repo_count = sum(1 for t in meaningful_tokens if t in self.repo_vocabulary)
            overlap_ratio = in_repo_count / len(meaningful_tokens)

        # 2. Peak-to-Noise Ratio (Z-score of top-1 file)
        mean_score = float(np.mean(fused_scores))
        std_score = float(np.std(fused_scores))
        max_score = float(np.max(fused_scores))

        if std_score > 1e-6:
            z_score = (max_score - mean_score) / std_score
        else:
            z_score = 0.0

        # Normalized Z-score component: z_score of 3.0 or higher maps to ~1.0
        z_component = min(1.0, max(0.0, z_score / 3.0))

        # 3. Score margin between top-1 and 50th percentile
        median_score = float(np.median(fused_scores))
        margin = max(0.0, max_score - median_score)

        # Calibrated composite confidence score
        confidence = (
            0.30 * z_component +
            0.45 * overlap_ratio +
            0.25 * margin
        )
        confidence = float(np.clip(confidence, 0.0, 1.0))

        # Decision
        if overlap_ratio <= 0.10:
            return True, confidence, f"Negligible query symbol overlap with repository vocabulary (overlap: {overlap_ratio:.2f}, z: {z_score:.2f})."

        if confidence < self.confidence_threshold:
            return True, confidence, f"Confidence {confidence:.3f} below threshold {self.confidence_threshold:.3f} (z: {z_score:.2f}, overlap: {overlap_ratio:.2f})."

        return False, confidence, f"Confident repository match (confidence: {confidence:.3f}, z: {z_score:.2f}, overlap: {overlap_ratio:.2f})."
