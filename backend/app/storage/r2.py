"""Cloudflare R2 (S3-compatible) provider, for production use.

R2 requires no egress fees and speaks the S3 API, so this is a thin wrapper
around boto3's S3 client pointed at the account's R2 endpoint.

Not yet exercised against a real R2 bucket in this project — see
docs/STORAGE.md for exactly what's needed to turn this on.
"""
import io
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError

from app.storage.base import StorageProvider


class R2StorageProvider(StorageProvider):
    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        endpoint_url: str | None = None,
    ) -> None:
        self._bucket = bucket_name
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    def save(self, key: str, data: bytes) -> None:
        # A single put_object call is already atomic from the caller's
        # perspective — S3-compatible stores replace the object as one
        # unit, so there's no local-filesystem-style partial-write risk.
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    def open(self, key: str) -> BinaryIO:
        obj = self._client.get_object(Bucket=self._bucket, Key=key)
        return io.BytesIO(obj["Body"].read())

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404:
                return False
            raise

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    @contextmanager
    def local_path(self, key: str) -> Iterator[Path]:
        # No real path on R2 — download to a throwaway temp file for
        # whatever needs an actual filesystem path, then remove it.
        suffix = Path(key).suffix
        fd, tmp_name = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(fd, "wb") as tmp_file:
                obj = self._client.get_object(Bucket=self._bucket, Key=key)
                tmp_file.write(obj["Body"].read())
            yield Path(tmp_name)
        finally:
            os.unlink(tmp_name)
