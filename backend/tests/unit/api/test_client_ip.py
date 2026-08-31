"""Unit tests for get_client_ip — trusted-proxy-aware IP extraction (BLOCKER-2)."""

from unittest.mock import MagicMock

import pytest

from tradeforge.api.v1.deps import get_client_ip


def _make_request(
    *,
    client_host: str | None = "1.2.3.4",
    x_forwarded_for: str | None = None,
    trusted_proxies: str = "",
) -> MagicMock:
    """Build a minimal mock Request that get_client_ip will interrogate."""
    request = MagicMock()
    if client_host is not None:
        request.client = MagicMock()
        request.client.host = client_host
    else:
        request.client = None

    headers: dict[str, str] = {}
    if x_forwarded_for is not None:
        headers["X-Forwarded-For"] = x_forwarded_for
    request.headers.get = lambda key, default="": headers.get(key, default)

    # Patch settings so trusted_proxies comes from our argument, not the real .env
    import tradeforge.api.v1.deps as deps_module
    from unittest.mock import patch

    request._trusted_proxies_patch = patch.object(
        deps_module,
        "_parse_trusted_proxies",
        side_effect=lambda raw: deps_module._parse_trusted_proxies(trusted_proxies),
    )

    return request


# ------------------------------------------------------------------
# Helper that patches settings inside get_client_ip
# ------------------------------------------------------------------

from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def _trusted(trusted_proxies: str):
    """Context manager: make get_settings().trusted_proxies return the given value."""
    from tradeforge.settings import Settings

    fake_settings = MagicMock(spec=Settings)
    fake_settings.trusted_proxies = trusted_proxies
    with patch("tradeforge.api.v1.deps.get_settings", return_value=fake_settings):
        yield


def _request(
    *,
    client_host: str | None = "1.2.3.4",
    x_forwarded_for: str | None = None,
) -> MagicMock:
    req = MagicMock()
    if client_host is not None:
        req.client = MagicMock()
        req.client.host = client_host
    else:
        req.client = None
    headers: dict[str, str] = {}
    if x_forwarded_for is not None:
        headers["X-Forwarded-For"] = x_forwarded_for
    req.headers.get = lambda key, default="": headers.get(key, default)
    return req


# ------------------------------------------------------------------
# No trusted proxies (default) — always use direct peer
# ------------------------------------------------------------------


def test_no_trusted_proxies_uses_direct_peer() -> None:
    """Without trusted proxies, direct peer IP is returned regardless of XFF."""
    with _trusted(""):
        assert get_client_ip(_request(client_host="5.6.7.8")) == "5.6.7.8"


def test_no_trusted_proxies_ignores_xff() -> None:
    """A spoofed XFF header must be ignored when no proxies are trusted."""
    with _trusted(""):
        ip = get_client_ip(_request(client_host="5.6.7.8", x_forwarded_for="1.1.1.1"))
        assert ip == "5.6.7.8"


def test_no_client_returns_loopback() -> None:
    """Missing request.client (ASGI transport) falls back to 127.0.0.1."""
    with _trusted(""):
        assert get_client_ip(_request(client_host=None)) == "127.0.0.1"


# ------------------------------------------------------------------
# With trusted proxies — XFF is used
# ------------------------------------------------------------------


def test_trusted_proxy_reads_xff_leftmost_client() -> None:
    """When the direct peer is a trusted proxy, the leftmost non-trusted XFF IP is the client."""
    with _trusted("10.0.0.1"):
        ip = get_client_ip(
            _request(client_host="10.0.0.1", x_forwarded_for="203.0.113.5, 10.0.0.1")
        )
        assert ip == "203.0.113.5"


def test_trusted_proxy_skips_intermediate_trusted_hops() -> None:
    """A chain of trusted proxies is walked right-to-left; first non-trusted IP is returned."""
    with _trusted("10.0.0.1, 10.0.0.2"):
        ip = get_client_ip(
            _request(client_host="10.0.0.2", x_forwarded_for="198.51.100.7, 10.0.0.1, 10.0.0.2")
        )
        assert ip == "198.51.100.7"


def test_trusted_proxy_cidr_range_is_matched() -> None:
    """CIDR notation in TRUSTED_PROXIES is resolved correctly."""
    with _trusted("10.0.0.0/8"):
        ip = get_client_ip(
            _request(client_host="10.99.99.99", x_forwarded_for="203.0.113.42, 10.99.99.99")
        )
        assert ip == "203.0.113.42"


def test_untrusted_peer_with_xff_is_not_trusted() -> None:
    """A peer NOT in the trusted list cannot override the IP via XFF."""
    with _trusted("10.0.0.1"):
        # Peer is 5.6.7.8 which is not trusted → XFF must be ignored.
        ip = get_client_ip(
            _request(client_host="5.6.7.8", x_forwarded_for="1.1.1.1")
        )
        assert ip == "5.6.7.8"


def test_all_xff_trusted_falls_back_to_direct_peer() -> None:
    """If every XFF IP is itself a trusted proxy, fall back to the direct peer."""
    with _trusted("10.0.0.1, 10.0.0.2"):
        ip = get_client_ip(
            _request(client_host="10.0.0.2", x_forwarded_for="10.0.0.1")
        )
        assert ip == "10.0.0.2"


def test_malformed_trusted_proxy_entry_is_ignored() -> None:
    """A malformed TRUSTED_PROXIES entry does not crash; direct peer is used."""
    with _trusted("not-an-ip, 10.0.0.1"):
        ip = get_client_ip(_request(client_host="5.6.7.8"))
        assert ip == "5.6.7.8"
