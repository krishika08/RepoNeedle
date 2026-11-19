"""Index-cache exceptions."""


class IndexCacheError(RuntimeError):
    """
    Raised when the persistent index cache cannot be used and ``IndexCacheConfig.rebuild_policy="never"`` forbids
    falling back (a rebuild or an uncached build). Messages contain reasons and paths, never file contents.
    """


class CacheUnusable(Exception):
    """
    Internal: the database exists but must not be used (corrupt, foreign, incompatible or unpublished).
    ``migratable`` is True when it has an older minor schema version that a writer migrates in place.
    """

    def __init__(self, reason: str, migratable: bool = False):
        super().__init__(reason)
        self.reason = reason
        self.migratable = migratable


class PersistenceUnavailable(Exception):
    """
    Internal: persistence cannot be used in this environment (settings, filesystem, permissions, locks).
    ``corrupt`` is True only when SQLite reported that the existing file is not a usable database.
    """

    def __init__(self, reason: str, corrupt: bool = False):
        super().__init__(reason)
        self.reason = reason
        self.corrupt = corrupt
