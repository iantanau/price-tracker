"""HTTP client abstraction."""

from abc import ABC, abstractmethod

from models.http_response import HttpResponse


class HttpClient(ABC):
    """Abstract HTTP client.

    Implementations hide the underlying library (httpx, requests, Playwright,
    etc.) and return a normalised :class:`HttpResponse`. Business logic never
    calls a concrete HTTP library directly.
    """

    @abstractmethod
    def get(self, url: str) -> HttpResponse:
        """Fetch the given URL and return a normalised response.

        Args:
            url: URL to fetch.

        Returns:
            Normalised HTTP response.

        Raises:
            HttpClientError: If the request fails after retries.
        """
        raise NotImplementedError


class HttpClientError(Exception):
    """Raised when an HTTP request fails."""

    pass
