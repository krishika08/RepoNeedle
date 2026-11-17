"""
A deterministic LRU cache bounded by entry count *and* by an estimate of the bytes its entries retain.

Callers supply the estimate for each entry (see ``CodeSpanExtractor`` for the accounting it uses). The estimate is
an approximation of the Python objects kept alive by the cache; it is not a measurement of process memory (RSS),
which also depends on allocator behaviour, fragmentation and objects shared with the rest of the program.

Policy:

* ``get`` refreshes recency; ``put`` inserts as most recent.
* After every insert, least-recently-used entries are evicted (oldest first, deterministic) until both the entry
  limit and the byte budget hold. Evicted values are dropped from the cache, so nothing in the cache keeps them alive.
* An entry whose estimate exceeds ``max_entry_fraction`` of the byte budget is not cached at all (it is counted
  in ``rejected_oversized``); one huge file can therefore never flush the whole cache.
"""

from collections import OrderedDict
from typing import Any, Dict, Hashable, Tuple

_MISSING = object()


class ByteBudgetLRU:
    MISSING = _MISSING

    def __init__(self, max_entries: int, max_bytes: int, max_entry_fraction: float = 0.125):
        if max_entries < 1 or max_bytes < 1 or not 0 < max_entry_fraction <= 1:
            raise ValueError("max_entries and max_bytes must be positive; 0 < max_entry_fraction <= 1")
        self.max_entries = int(max_entries)
        self.max_bytes = int(max_bytes)
        self.max_entry_bytes = int(max_bytes * max_entry_fraction)
        self._data: "OrderedDict[Hashable, Tuple[Any, int]]" = OrderedDict()
        self._bytes = 0
        self.hits = self.misses = self.evictions = self.rejected_oversized = 0

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: Hashable) -> bool:
        return key in self._data

    @property
    def estimated_bytes(self) -> int:
        return self._bytes

    def get(self, key: Hashable) -> Any:
        """The cached value (refreshing its recency), or ``ByteBudgetLRU.MISSING``."""
        item = self._data.get(key)
        if item is None:
            self.misses += 1
            return _MISSING
        self._data.move_to_end(key)
        self.hits += 1
        return item[0]

    def put(self, key: Hashable, value: Any, estimated_bytes: int) -> bool:
        """Caches ``value``; returns False (and caches nothing) if the entry is too large for the budget."""
        old = self._data.pop(key, None)
        if old is not None:
            self._bytes -= old[1]
        if estimated_bytes > self.max_entry_bytes:
            self.rejected_oversized += 1
            return False
        self._data[key] = (value, estimated_bytes)
        self._bytes += estimated_bytes
        while len(self._data) > self.max_entries or self._bytes > self.max_bytes:
            _, (_, size) = self._data.popitem(last=False)
            self._bytes -= size
            self.evictions += 1
        return True

    def clear(self) -> None:
        self._data.clear()
        self._bytes = 0

    def stats(self) -> Dict[str, int]:
        return {
            "entries": len(self._data), "max_entries": self.max_entries,
            "estimated_bytes": self._bytes, "max_bytes": self.max_bytes, "max_entry_bytes": self.max_entry_bytes,
            "hits": self.hits, "misses": self.misses, "evictions": self.evictions,
            "rejected_oversized": self.rejected_oversized,
        }
