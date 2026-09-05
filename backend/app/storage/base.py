"""Storage provider interface.

Callers deal only in opaque storage keys — never filesystem paths or bucket
names — so the backing provider can be swapped via STORAGE_PROVIDER without
touching calling code. The analytics layer (app/analytics) is written
entirely against this interface and has no idea whether a dataset lives on
local disk or in Cloudflare R2.
"""
from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from pathlib import Path
from typing import BinaryIO


class StorageProvider(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes) -> None:
        """Persist data under key, creating/overwriting as needed.

        Must not leave a partially-written object behind if it fails or is
        interrupted partway through — implementations write to a temporary
        location and move it into place atomically once complete.
        """

    @abstractmethod
    def open(self, key: str) -> BinaryIO:
        """Return a readable binary stream for a previously-saved key."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Whether an object is currently stored under key."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove the object at key. No-op if it doesn't exist."""

    @abstractmethod
    def local_path(self, key: str) -> AbstractContextManager[Path]:
        """Yield a real filesystem path to the object at key, for tools that
        need an actual path rather than a stream (e.g. a future DuckDB
        `read_csv`). Local: yields the real path directly, no copy. Remote
        providers: download to a temp file for the duration of the `with`
        block and remove it on exit — callers never need to know which."""
