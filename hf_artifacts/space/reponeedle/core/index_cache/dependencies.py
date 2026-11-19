"""
Dependency invalidation for per-file graph contributions (design sections 9.1, 9.2 and 9.4).

Each graph resolver (``FunctionGraphEngine._resolve_file`` and ``RepoGraph._resolve_doc_edges``) reads structures
built from OTHER files only through a lookup object that records a typed key for every read, and returns exactly the
key's value (``key_value``). A file's resolved edges are therefore a function of its own inputs plus the values of
the keys it consumed. Two mechanisms use that:

* **Dependency index** (design section 9.1): every persisted file stores its typed *provider events* (``provides``
  artifact: the keys it contributes, in emission order, with the contributed value) and its *consumed keys* (in its
  resolution artifact). For each key the concatenation of all files' events in discovery order is its *ordered
  provider list*. A key changed when that list differs between the previous generation and the current scan
  (additions, deletions, a different winner or uniqueness count, or a different order). The affected files are the
  files whose own inputs changed plus every consumer of a changed key; only they are re-resolved.
* **Dependency context** (artifact identity, section 16 of the Stage 2 brief): a resolution artifact's key binds the
  SHA-256 of the consumed keys' CURRENT values (``ContextDigests``). Before an unaffected file's stored edges are
  replayed, that digest is recomputed from the current build and the key must match; otherwise the file is
  re-resolved, and the miss is counted (it would mean the dependency index missed a change; tests assert zero).

Neither mechanism can make the result differ from a full resolution: re-resolving a file is always allowed, and a
file is reused only when every value its previous resolution read is unchanged.
"""

import hashlib
import json
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from reponeedle.core.index_cache.schema import framed

CONTEXT_VERSION = b"reponeedle-dependency-context-v1"
RESOLUTION_INPUT_VERSION = b"reponeedle-resolution-input-v1"


def key_value_digest(key: str, value: Any) -> bytes:
    """SHA-256 binding a typed key to its value (canonical JSON), so a context digest binds keys and values."""
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(framed(key.encode("utf-8", "surrogatepass"), raw.encode("utf-8", "surrogatepass"))).digest()


class ContextDigests:
    """Memoised digests of key values in one build, and per-file dependency contexts over them."""

    def __init__(self, key_value: Callable[[str], Any]):
        self.key_value = key_value
        self._memo: Dict[str, bytes] = {}
        self.keys_evaluated = 0

    def key(self, key: str) -> bytes:
        d = self._memo.get(key)
        if d is None:
            d = key_value_digest(key, self.key_value(key))
            self._memo[key] = d
            self.keys_evaluated += 1
        return d

    def context(self, consumed: Sequence[str]) -> bytes:
        """Digest of the (sorted, unique) consumed keys with their current values (fixed-size per-key digests)."""
        key = self.key
        return hashlib.sha256(CONTEXT_VERSION + b"".join([key(k) for k in consumed])).digest()


def resolution_input_sig(own: bytes, context: bytes) -> bytes:
    """``input_sig`` of a resolution artifact: the file's own extraction identity plus its dependency context."""
    return hashlib.sha256(framed(RESOLUTION_INPUT_VERSION, own, context)).digest()


def provider_lists(per_file_events: Iterable[Sequence[Tuple[str, str]]],
                   only: Optional[Set[str]] = None) -> Dict[str, List[str]]:
    """
    Ordered provider list of every key (or of the keys in ``only``): the files' events concatenated in the given
    (discovery) order.
    """
    out: Dict[str, List[str]] = {}
    for events in per_file_events:
        for key, value in events:
            if only is not None and key not in only:
                continue
            lst = out.get(key)
            if lst is None:
                out[key] = [value]
            else:
                lst.append(value)
    return out


def changed_provider_keys(old_order: Sequence[str], old_events: Dict[str, Sequence[Tuple[str, str]]],
                          new_order: Sequence[str], new_events: Dict[str, Sequence[Tuple[str, str]]],
                          unchanged: Set[str]) -> Tuple[Set[str], Dict[str, Any]]:
    """
    Keys whose ordered provider list differs between two generations. ``unchanged``: files whose provider events are
    identical in both (same verified artifact).

    When the files of ``unchanged`` keep their relative order, a key provided only by them has the same list in both
    generations, so only the keys provided (before or after) by the other files are candidates and only their lists
    are compared: the work is proportional to the change, and an unchanged repository compares nothing. Otherwise
    (a discovery-order change) every list is compared.
    """
    old_seq = [p for p in old_order if p in unchanged]
    new_seq = [p for p in new_order if p in unchanged]
    if old_seq == new_seq:
        changed_files = [p for p in old_order if p not in unchanged] + [p for p in new_order if p not in unchanged]
        candidates: Set[str] = set()
        for p in changed_files:
            for events in (old_events.get(p), new_events.get(p)):
                if events:
                    candidates.update(k for k, _v in events)
        if not candidates:
            return set(), {"order_preserved": True, "candidate_keys": 0}
        changed = changed_keys(provider_lists((old_events[p] for p in old_order), candidates),
                               provider_lists((new_events[p] for p in new_order), candidates))
        return changed, {"order_preserved": True, "candidate_keys": len(candidates)}
    changed = changed_keys(provider_lists(old_events[p] for p in old_order),
                           provider_lists(new_events[p] for p in new_order))
    return changed, {"order_preserved": False, "candidate_keys": None}


def changed_keys(old: Dict[str, List[str]], new: Dict[str, List[str]]) -> Set[str]:
    """Keys whose ordered provider list differs (including keys that appeared or disappeared)."""
    changed = {k for k, v in new.items() if old.get(k) != v}
    changed.update(k for k in old if k not in new)
    return changed


def consumer_index(consumed_by_path: Dict[str, Sequence[str]]) -> Dict[str, List[str]]:
    """key -> files that consumed it."""
    out: Dict[str, List[str]] = {}
    for path, keys in consumed_by_path.items():
        for k in keys:
            out.setdefault(k, []).append(path)
    return out


def affected_files(own_changed: Set[str], changed: Set[str], consumers: Dict[str, List[str]]) -> Set[str]:
    """Design section 9.1: the files whose own inputs changed, plus every consumer of a changed key."""
    affected = set(own_changed)
    for k in changed:
        affected.update(consumers.get(k, ()))
    return affected


class GraphPlan:
    """
    Reuse decisions for one graph in one build. ``stored`` maps a path to (stored artifact key, stored resolution)
    for files whose stored resolution may be reused (own inputs unchanged); ``affected`` must be re-resolved.
    ``expected_key(path, context)`` recomputes the artifact key the stored one must equal.
    """

    def __init__(self, name: str, stored: Dict[str, Tuple[bytes, Any]], affected: Set[str],
                 expected_key: Callable[[str, bytes], bytes]):
        self.name = name
        self.stored = stored
        self.affected = affected
        self.expected_key = expected_key
        self.digests: Optional[ContextDigests] = None
        self.reused: Set[str] = set()
        self.context_mismatch: List[str] = []       # unaffected by the index, yet the context changed

    def __call__(self, graph, doc):
        """The ``reuse`` hook of ``RepoGraph.fit`` / ``FunctionGraphEngine.build_graph``."""
        if self.digests is None:
            self.digests = ContextDigests(graph.key_value)
        entry = self.stored.get(doc.path)
        if entry is None or doc.path in self.affected:
            return None
        key, resolution = entry
        if self.expected_key(doc.path, self.digests.context(resolution.consumed)) != key:
            self.context_mismatch.append(doc.path)
            return None
        self.reused.add(doc.path)
        return resolution
