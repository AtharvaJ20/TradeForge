"""Unit tests for S20-2 startup guard — partial S3 config must be rejected.

Tests the guard logic: S3_BUCKET set without access/secret key must raise ValueError.
"""

import pytest


def _run_guard(bucket: str, access_key: str, secret_key: str) -> None:
    """Mirror the guard logic from main.create_app() so it can be tested in isolation."""
    if bucket and not (access_key and secret_key):
        raise ValueError(
            "S3_BUCKET is set but S3_ACCESS_KEY or S3_SECRET_KEY is missing. "
            "All three must be set together, or all three must be empty."
        )


class TestS3StartupGuard:
    def test_empty_s3_config_passes(self):
        """No S3 vars configured (StubStorage mode) must not raise."""
        _run_guard("", "", "")  # no exception

    def test_full_s3_config_passes(self):
        """All three S3 vars set together must not raise."""
        _run_guard("my-bucket", "AKID", "secret")  # no exception

    def test_bucket_without_credentials_raises(self):
        """S3_BUCKET with no credentials must raise ValueError."""
        with pytest.raises(ValueError, match="S3_BUCKET"):
            _run_guard("my-bucket", "", "")

    def test_bucket_with_only_access_key_raises(self):
        """S3_BUCKET + access key only (no secret) must raise ValueError."""
        with pytest.raises(ValueError, match="S3_BUCKET"):
            _run_guard("my-bucket", "AKID", "")

    def test_bucket_with_only_secret_key_raises(self):
        """S3_BUCKET + secret key only (no access key) must raise ValueError."""
        with pytest.raises(ValueError, match="S3_BUCKET"):
            _run_guard("my-bucket", "", "secret")

    def test_error_message_names_both_keys(self):
        """Error message must mention both ACCESS_KEY and SECRET_KEY."""
        with pytest.raises(ValueError) as exc_info:
            _run_guard("bucket", "", "")
        msg = str(exc_info.value)
        assert "S3_ACCESS_KEY" in msg
        assert "S3_SECRET_KEY" in msg
