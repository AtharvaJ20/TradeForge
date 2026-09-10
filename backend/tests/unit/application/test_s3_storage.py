"""Unit tests for S3Storage using moto S3 mock (S20-2).

All tests run against moto's in-process S3 mock — no real AWS calls are made.
Uses mock_aws() as a context manager (not decorator) to preserve async test functions.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws


def _make_settings(bucket: str = "test-bucket", region: str = "us-east-1") -> MagicMock:
    s = MagicMock()
    s.s3_bucket = bucket
    s.s3_access_key = "test-access"
    s.s3_secret_key = "test-secret"
    s.s3_region = region
    s.s3_endpoint = ""
    return s


def _s3_client(region: str = "us-east-1"):
    return boto3.client(
        "s3",
        region_name=region,
        aws_access_key_id="test-access",
        aws_secret_access_key="test-secret",
    )


def _create_bucket(bucket: str = "test-bucket", region: str = "us-east-1") -> None:
    client = _s3_client(region)
    if region == "us-east-1":
        client.create_bucket(Bucket=bucket)
    else:
        client.create_bucket(
            Bucket=bucket,
            CreateBucketConfiguration={"LocationConstraint": region},
        )


def _put_object(key: str, body: bytes = b"hello", bucket: str = "test-bucket") -> None:
    _s3_client().put_object(Bucket=bucket, Key=key, Body=body)


# ---------------------------------------------------------------------------
# presign_put
# ---------------------------------------------------------------------------


async def test_presign_put_returns_https_url():
    from tradeforge.application.journal.storage import S3Storage

    with mock_aws():
        _create_bucket()
        storage = S3Storage(_make_settings())
        url = await storage.presign_put("user/trade/att.png", "image/png", 1024, 3600)

    assert url.startswith("https://")


async def test_presign_put_url_contains_key():
    from tradeforge.application.journal.storage import S3Storage

    with mock_aws():
        _create_bucket()
        storage = S3Storage(_make_settings())
        url = await storage.presign_put("some/key.pdf", "application/pdf", 512, 300)

    assert "some/key.pdf" in url or "some%2Fkey.pdf" in url


async def test_presign_put_url_contains_bucket():
    from tradeforge.application.journal.storage import S3Storage

    with mock_aws():
        _create_bucket()
        storage = S3Storage(_make_settings())
        url = await storage.presign_put("file.png", "image/png", 100, 3600)

    assert "test-bucket" in url


# ---------------------------------------------------------------------------
# presign_get
# ---------------------------------------------------------------------------


async def test_presign_get_returns_https_url():
    from tradeforge.application.journal.storage import S3Storage

    with mock_aws():
        _create_bucket()
        _put_object("doc.pdf")
        storage = S3Storage(_make_settings())
        url = await storage.presign_get("doc.pdf", "document.pdf", "application/pdf", 3600)

    assert url.startswith("https://")


async def test_presign_get_url_contains_bucket():
    from tradeforge.application.journal.storage import S3Storage

    with mock_aws():
        _create_bucket()
        _put_object("image.png")
        storage = S3Storage(_make_settings())
        url = await storage.presign_get("image.png", "my chart.png", "image/png", 3600)

    assert "test-bucket" in url


# ---------------------------------------------------------------------------
# head_object
# ---------------------------------------------------------------------------


async def test_head_object_returns_metadata_for_existing_key():
    from tradeforge.application.journal.storage import S3Storage

    with mock_aws():
        _create_bucket()
        _put_object("file.txt", body=b"hello world")
        storage = S3Storage(_make_settings())
        meta = await storage.head_object("file.txt")

    assert meta is not None
    assert meta["ContentLength"] == 11


async def test_head_object_returns_none_for_missing_key():
    from tradeforge.application.journal.storage import S3Storage

    with mock_aws():
        _create_bucket()
        storage = S3Storage(_make_settings())
        meta = await storage.head_object("does-not-exist.png")

    assert meta is None


# ---------------------------------------------------------------------------
# delete_object
# ---------------------------------------------------------------------------


async def test_delete_object_removes_existing_key():
    from tradeforge.application.journal.storage import S3Storage

    with mock_aws():
        _create_bucket()
        _put_object("to-delete.png")
        storage = S3Storage(_make_settings())

        meta_before = await storage.head_object("to-delete.png")
        assert meta_before is not None

        await storage.delete_object("to-delete.png")

        meta_after = await storage.head_object("to-delete.png")
        assert meta_after is None


async def test_delete_object_is_noop_for_missing_key():
    """S3 delete of a non-existent key must not raise (S3 semantics)."""
    from tradeforge.application.journal.storage import S3Storage

    with mock_aws():
        _create_bucket()
        storage = S3Storage(_make_settings())
        await storage.delete_object("never-existed.png")  # must not raise


# ---------------------------------------------------------------------------
# StoragePort Protocol conformance
# ---------------------------------------------------------------------------


def test_s3_storage_implements_storage_port():
    """S3Storage must satisfy the StoragePort runtime-checkable Protocol."""
    from tradeforge.application.journal.storage import S3Storage, StoragePort

    assert issubclass(S3Storage, StoragePort)


def test_stub_storage_implements_storage_port():
    """StubStorage must satisfy the StoragePort Protocol (delete_object now present)."""
    from tradeforge.application.journal.storage import StoragePort, StubStorage

    assert issubclass(StubStorage, StoragePort)
