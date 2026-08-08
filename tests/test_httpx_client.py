"""Tests for HttpxClient using respx to mock HTTP responses."""

import httpx
import pytest
import respx

from clients.base import HttpClientError
from clients.http_client import HttpxClient
from config.settings import Settings


class TestHttpxClient:
    """Tests for the httpx-backed HTTP client."""

    def _settings(self, **overrides) -> Settings:
        """Create settings with sensible defaults for tests."""
        defaults = {
            "http_timeout": 5,
            "http_retries": 2,
            "http_user_agent": "PriceTracker-Test/1.0",
            "http_headers": {},
        }
        defaults.update(overrides)
        return Settings(**defaults)

    @respx.mock
    def test_returns_http_response_on_success(self) -> None:
        """Returns a normalised HttpResponse for a successful request."""
        respx.get("https://api.example/data").mock(
            return_value=httpx.Response(
                status_code=200,
                text="<html>OK</html>",
                headers={"content-type": "text/html"},
            )
        )

        client = HttpxClient(self._settings())
        response = client.get("https://api.example/data")
        client.close()

        assert response.status_code == 200
        assert response.content == "<html>OK</html>"
        assert response.headers["content-type"] == "text/html"

    @respx.mock
    def test_retries_on_server_error(self) -> None:
        """Retries transient 5xx errors and eventually succeeds."""
        route = respx.get("https://api.example/data").mock(
            side_effect=[
                httpx.Response(status_code=500, text="Server Error"),
                httpx.Response(status_code=200, text="<html>OK</html>"),
            ]
        )

        client = HttpxClient(self._settings(http_retries=1))
        response = client.get("https://api.example/data")
        client.close()

        assert response.status_code == 200
        assert route.call_count == 2

    @respx.mock
    def test_does_not_retry_client_error(self) -> None:
        """Raises HttpClientError immediately for 4xx errors without retrying."""
        route = respx.get("https://api.example/data").mock(
            return_value=httpx.Response(status_code=404, text="Not Found")
        )

        client = HttpxClient(self._settings(http_retries=2))

        with pytest.raises(HttpClientError, match="HTTP 404"):
            client.get("https://api.example/data")

        client.close()
        assert route.call_count == 1

    @respx.mock
    def test_raises_after_retries_exhausted(self) -> None:
        """Raises HttpClientError when all retries are exhausted."""
        route = respx.get("https://api.example/data").mock(
            side_effect=httpx.ConnectError("connection refused")
        )

        client = HttpxClient(self._settings(http_retries=2))

        with pytest.raises(HttpClientError, match="Failed to fetch"):
            client.get("https://api.example/data")

        client.close()
        assert route.call_count == 3

    @respx.mock
    def test_sends_configured_headers(self) -> None:
        """Sends the configured User-Agent and custom headers."""
        respx.get("https://api.example/data").mock(
            return_value=httpx.Response(status_code=200, text="OK")
        )

        client = HttpxClient(
            self._settings(
                http_user_agent="Custom-Agent/2.0",
                http_headers={"X-Custom": "value"},
            )
        )
        client.get("https://api.example/data")
        client.close()

        request = respx.calls.last.request
        assert request.headers["user-agent"] == "Custom-Agent/2.0"
        assert request.headers["x-custom"] == "value"
