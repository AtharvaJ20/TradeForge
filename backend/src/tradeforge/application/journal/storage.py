"""StoragePort — pluggable object-store abstraction for journal attachments.

The StubStorage implementation is used in development and test. Nakula supplies
a real implementation backed by AWS S3 (or compatible) for production.

Security requirements implemented at this layer (SR-ATT-007, SR-ATT-008):
  - Upload URL: Content-Type condition + content-length-range condition
  - Download URL: Content-Disposition: attachment header; 1-hour TTL
  - All URLs are HTTPS-only

Nakula action required before production:
  - Replace StubStorage with a real boto3/aioboto3 implementation
  - Set S3_BUCKET, AWS_REGION in environment
  - Configure S3 bucket: Block Public Access, SSE-KMS, server access logging (SR-ATT-004)
  - Add lifecycle rule: delete PENDING-tagged objects older than 1 hour (SR-ATT-010)
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StoragePort(Protocol):
    async def presign_put(
        self,
        key: str,
        content_type: str,
        byte_size: int,
        ttl_seconds: int,
    ) -> str:
        """Return a pre-signed PUT URL.

        Must include Content-Type + content-length-range conditions.
        """
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


class StubStorage:
    """Stub implementation for local development and unit tests.

    Returns recognisable placeholder URLs and always reports a successful HeadObject.
    Replace with a real S3 implementation before production deployment.
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
