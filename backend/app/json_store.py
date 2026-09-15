"""Small, safe JSON persistence helpers for the current single-node store.

This is an interim hardening layer while PostgreSQL migration is prepared. Writes
are serialized per file and committed atomically so a crash cannot leave a partial
JSON document on disk.
"""
from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

_locks: dict[str, RLock] = {}
_locks_guard = RLock()


def _lock_for(path: Path) -> RLock:
    key = str(path.resolve())
    with _locks_guard:
        return _locks.setdefault(key, RLock())


@contextmanager
def file_lock(path: Path):
    """Serialize access within a backend process."""
    lock = _lock_for(path)
    with lock:
        yield


def atomic_write_json(path: Path, data: object, *, ensure_ascii: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=ensure_ascii, indent=2)
    with file_lock(path):
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
