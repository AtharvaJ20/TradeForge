"""StoragePort — pluggable object-store abstraction for journal attachments.

The StubStorage implementation is used in development and test. S3Storage
provides a production-ready implementation backed by AWS S3 or Cloudflare R2.

Security requirements implemented at this layer (SR-ATT-007, SR-ATT-008):
  - Upload URL: Content-Type is included in the signature; size enforcement is
    the application layer's responsibility (post-upload ContentLength check).
  - Download URL: Content-Disposition: attachment header; 1-hour TTL
  - All URLs are HTTPS-only

Deployment checklist (before production):
  - Set S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY in environment
  - Configure S3 bucket: Block Public Access, SSE-KMS, server access logging (SR-ATT-004)
  - Add lifecycle rule: delete PENDING-tagged objects older than 1 hour (SR-ATT-010)
  - For Cloudflare R2: set S3_ENDPOINT to the R2 endpoint; S3_REGION stays "auto"
"""

from __future__ import annotations

import asyncio
import urllib.parse
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

import boto3
import botocore.exceptions

if TYPE_CHECKING:
    from tradeforge.settings import Settings


@runtime_checkable
class StoragePort(Protocol):
    async def presign_put(
        self,
        key: str,
        content_type: str,
        byte_size: int,
        ttl_seconds: int,
    ) -> str:
        """Return a pre-signed PUT URL. Content-Type is enforced by the signature."""
        ...

    async def presign_get(
        self,
        key: str,
        filename: str,
        content_type: str,
        ttl_seconds: int,
    ) -> str:
        """Return a pre-signed GET URL. Must enforce Content-Disposition: attachment."""
        ...

    async def head_object(self, key: str) -> dict[str, Any] | None:
        """Return S3 object metadata dict, or None if the object does not exist."""
        ...

    async def delete_object(self, key: str) -> None:
        """Permanently delete the object at key. No-op if object does not exist."""
        ...


class StubStorage:
    """Stub implementation for local development and unit tests.

    Returns recognisable placeholder URLs and always reports a successful HeadObject.
    Replace with S3Storage (via environment variables) before production deployment.
    """

    STUB_BASE = "https://stub-s3.local"

    async def presign_put(
        self,
        key: str,
        content_type: str,
        byte_size: int,
        ttl_seconds: int,
    ) -> str:
        params = urllib.parse.urlencode(
            {"action": "put", "content_type": content_type, "ttl": ttl_seconds}
        )
        return f"{self.STUB_BASE}/{key}?{params}"

    async def presign_get(
        self,
        key: str,
        filename: str,
        content_type: str,
        ttl_seconds: int,
    ) -> str:
        params = urllib.parse.urlencode(
            {
                "action": "get",
                "response-content-disposition": f"attachment; filename={filename}",
                "response-content-type": content_type,
                "ttl": ttl_seconds,
            }
        )
        return f"{self.STUB_BASE}/{key}?{params}"

    async def head_object(self, key: str) -> dict[str, Any] | None:
        # Stub always reports the object exists (upload succeeded)
        return {"ETag": '"stub"', "ContentLength": 0}

    async def delete_object(self, key: str) -> None:
        # No-op — stub never stores real objects
        pass


class S3Storage:
    """Production S3-compatible storage. Wraps synchronous boto3 in run_in_executor.

    Compatible with AWS S3 and Cloudflare R2. Set s3_endpoint to the R2 endpoint
    URL and leave s3_region as "auto" for R2 deployments.
    """

    def __init__(self, settings: Settings) -> None:
        kwargs: dict[str, Any] = {
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
            "region_name": settings.s3_region,
        }
        if settings.s3_endpoint:
            kwargs["endpoint_url"] = settings.s3_endpoint
        self._client = boto3.client("s3", **kwargs)
        self._bucket = settings.s3_bucket

    async def presign_put(
        self,
        key: str,
        content_type: str,
        byte_size: int,
        ttl_seconds: int,
    ) -> str:
        loop = asyncio.get_running_loop()
        client = self._client
        bucket = self._bucket
        return await loop.run_in_executor(
            None,
            lambda: client.generate_presigned_url(
                "put_object",
                Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=ttl_seconds,
            ),
        )

    async def presign_get(
        self,
        key: str,
        filename: str,
        content_type: str,
        ttl_seconds: int,
    ) -> str:
        loop = asyncio.get_running_loop()
        client = self._client
        bucket = self._bucket
        return await loop.run_in_executor(
            None,
            lambda: client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": bucket,
                    "Key": key,
                    "ResponseContentDisposition": f'attachment; filename="{filename}"',
                    "ResponseContentType": content_type,
                },
                ExpiresIn=ttl_seconds,
            ),
        )

    async def head_object(self, key: str) -> dict[str, Any] | None:
        loop = asyncio.get_running_loop()
        client = self._client
        bucket = self._bucket

        def _head() -> dict[str, Any]:
            return cast(dict[str, Any], client.head_object(Bucket=bucket, Key=key))

        try:
            return await loop.run_in_executor(None, _head)
        except botocore.exceptions.ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return None
            raise

    async def delete_object(self, key: str) -> None:
        loop = asyncio.get_running_loop()
        client = self._client
        bucket = self._bucket
        await loop.run_in_executor(
            None,
            lambda: client.delete_object(Bucket=bucket, Key=key),
        )
