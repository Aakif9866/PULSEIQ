"""Dev-only provider that stores files on the backend's own filesystem,
rooted at settings.LOCAL_STORAGE_ROOT.

Whether this filesystem survives a restart or redeploy depends entirely on
the hosting platform — see docs/STORAGE.md.
"""
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from app.storage.base import StorageProvider


class LocalStorageProvider(StorageProvider):
    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve()

    def _path_for(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if path != self._root and self._root not in path.parents:
            raise ValueError(f"Storage key escapes storage root: {key!r}")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to a sibling temp file and rename into place atomically, so
        # a crash or a full disk mid-write never leaves a truncated file
        # sitting at the real key — readers only ever see a complete file.
        tmp_path = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
        try:
            tmp_path.write_bytes(data)
            os.replace(tmp_path, path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

    def open(self, key: str) -> BinaryIO:
        return self._path_for(key).open("rb")

    def exists(self, key: str) -> bool:
        return self._path_for(key).is_file()

    def delete(self, key: str) -> None:
        self._path_for(key).unlink(missing_ok=True)

    @contextmanager
    def local_path(self, key: str) -> Iterator[Path]:
        # Already a real path on disk — nothing to copy.
        yield self._path_for(key)
