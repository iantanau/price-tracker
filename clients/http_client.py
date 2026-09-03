"""httpx-based HTTP client implementation."""

import time

import httpx

from clients.base import HttpClient, HttpClientError
from config.settings import Settings
from models.http_response import HttpResponse


class HttpxClient(HttpClient):
    """HTTP client backed by ``httpx``.

    The client is configured from :class:`Settings` and supports:
    - custom User-Agent
    - additional headers
    - request timeout
    - simple retry loop for transient failures

    Attributes:
        _settings: Application settings.
        _client: Reusable httpx client.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialise the client with application settings.

        Args:
            settings: Configuration for timeouts, retries, headers, etc.
        """
        self._settings = settings
        headers = self._build_headers(settings)
        self._client = httpx.Client(
            headers=headers,
            timeout=settings.http_timeout,
            follow_redirects=True,
        )

    def _build_headers(self, settings: Settings) -> dict[str, str]:
        """Combine default headers with the configured User-Agent and extras."""
        headers: dict[str, str] = {
            "User-Agent": settings.http_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-AU,en;q=0.9",
        }
        if settings.http_headers:
            headers.update(settings.http_headers)
        return headers

    def get(self, url: str) -> HttpResponse:
        """Fetch ``url`` with retries.

        Args:
            url: URL to fetch.

        Returns:
            Normalised response object.

        Raises:
            HttpClientError: If all retries are exhausted.
        """
        last_exception: Exception | None = None
        attempts = max(1, self._settings.http_retries + 1)

        for attempt in range(1, attempts + 1):
            try:
                response = self._client.get(url)
                response.raise_for_status()
                return HttpResponse(
                    content=response.text,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                )
            except httpx.HTTPStatusError as exc:
                # Do not retry client errors (4xx); retry server errors (5xx).
                if exc.response.status_code < 500:
                    raise HttpClientError(
                        f"HTTP {exc.response.status_code} for URL {url}"
                    ) from exc
                last_exception = exc
            except httpx.RequestError as exc:
                last_exception = exc

            if attempt < attempts:
                time.sleep(attempt)  # Simple exponential back-off.

        raise HttpClientError(f"Failed to fetch {url} after {attempts} attempts") from last_exception

    def close(self) -> None:
        """Close the underlying httpx client."""
        self._client.close()
