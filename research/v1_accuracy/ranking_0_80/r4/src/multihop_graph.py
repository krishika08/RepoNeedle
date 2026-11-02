"""
Multi-Hop Structural Retrieval Engine for RepoNeedle Phase R4.
Implements:
1. One-Hop and Two-Hop Directed Call-Graph Traversal.
2. Edge Confidence and Distance Attenuation (gamma = 0.5).
3. Hub Detection and Dampening (inversely proportional to node degree).
4. Intent-Conditioned Traversal (Reference, Implementation, Test).
5. Cycle prevention and topological distance bounding.
"""
import math
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict, deque
import networkx as nx

from reponeedle.core.function_graph import FunctionGraphEngine, FunctionGraphEdge


class MultiHopGraphEngine:
    """
    Evaluates multi-hop structural call-graph propagation with hub dampening.
    """

    def __init__(
        self,
        function_graph: FunctionGraphEngine,
        hop_decay: float = 0.5,
        hub_degree_threshold: int = 10,
        min_confidence: float = 0.60,
    ):
        self.fg = function_graph
        self.hop_decay = hop_decay
        self.hub_threshold = hub_degree_threshold
        self.min_confidence = min_confidence

    def _get_hub_damping(self, node: str) -> float:
        """Computes penalty factor if node is a high-degree hub."""
        if not self.fg.graph.has_node(node):
            return 1.0
        degree = self.fg.graph.degree(node)
        if degree > self.hub_threshold:
            return 1.0 / math.sqrt(degree)
        return 1.0

    def expand_multihop(
        self,
        seed_scores: Dict[str, float],
        max_hops: int = 2,
        intent: str = "reference_seeking",
    ) -> Dict[str, float]:
        """
        Propagates scores across call-graph edges up to max_hops.
        Returns:
            expanded_scores: Dict of {path: structural_score}.
        """
        if not seed_scores or max_hops < 1:
            return {}

        expanded: Dict[str, float] = defaultdict(float)
        # Queue stores: (current_node, current_score, current_hop, path_history)
        queue = deque()
        visited_distances: Dict[str, int] = {}

        for seed_path, score in seed_scores.items():
            if score > 0:
                queue.append((seed_path, score, 0, (seed_path,)))
                visited_distances[seed_path] = 0

        while queue:
            curr_node, curr_score, curr_hop, history = queue.popleft()

            if curr_hop >= max_hops:
                continue

            # Hub dampening factor on outgoing propagation
            hub_factor = self._get_hub_damping(curr_node)

            # Determine traversal neighbors based on intent
            neighbors: List[Tuple[str, float, str]] = []  # (target_node, confidence, edge_direction)

            # Direction 1: Forward callees (functions called by curr_node)
            if intent in ("reference_seeking", "general_search"):
                for callee, conf in self.fg.callees_map.get(curr_node, {}).items():
                    if conf >= self.min_confidence:
                        neighbors.append((callee, conf, "forward_callee"))

            # Direction 2: Reverse callers (functions that call curr_node)
            if intent in ("implementation_seeking", "reference_seeking", "general_search"):
                for caller, conf in self.fg.callers_map.get(curr_node, {}).items():
                    if conf >= self.min_confidence:
                        neighbors.append((caller, conf, "reverse_caller"))

            # Direction 3: Test-seeking edges
            if intent == "test_seeking":
                # Prioritize edges connecting code to test files
                for neighbor in list(self.fg.callees_map.get(curr_node, {}).keys()) + list(self.fg.callers_map.get(curr_node, {}).keys()):
                    is_test = "test" in neighbor.lower()
                    if is_test:
                        neighbors.append((neighbor, 1.0, "test_link"))

            for target_node, conf, edge_type in neighbors:
                # Cycle prevention: do not traverse already visited path in current lineage
                if target_node in history:
                    continue

                next_hop = curr_hop + 1
                decay = self.hop_decay ** next_hop
                edge_score = curr_score * conf * decay * hub_factor

                # Check if this achieves a higher score at this or smaller distance
                if edge_score > expanded[target_node]:
                    expanded[target_node] = edge_score

                if target_node not in visited_distances or next_hop < visited_distances[target_node]:
                    visited_distances[target_node] = next_hop
                    queue.append((target_node, edge_score, next_hop, history + (target_node,)))

        return dict(expanded)

