"""Web-based product monitor."""

from clients.base import HttpClient, HttpClientError
from models.parsed_result import ParsedResult
from models.listing import ProductListing
from monitors.base import Monitor, MonitorError
from parsers.base import ParseError, ProductParser


class WebMonitor(Monitor):
    """Monitor a product by fetching its web page and parsing the content.

    The monitor delegates communication to an :class:`HttpClient` and
    extraction to a :class:`ProductParser`. This separation lets either
    layer be replaced (requests, Playwright, JSON API, etc.) without
    changing the monitor or business logic.

    Attributes:
        _client: HTTP client used to fetch pages.
        _parser: Parser used to extract structured data from raw content.
    """

    def __init__(self, client: HttpClient, parser: ProductParser) -> None:
        """Initialise the monitor with its dependencies.

        Args:
            client: HTTP client implementation.
            parser: Parser implementation.
        """
        self._client = client
        self._parser = parser

    def fetch_listing(self, listing: ProductListing) -> ParsedResult:
        """Fetch the listing page and parse it.

        Args:
            listing: Listing to monitor.

        Returns:
            Structured extraction result.

        Raises:
            MonitorError: If the request or parse step fails.
        """

        try:
            response = self._client.get(listing.url)
        except HttpClientError as exc:
            raise MonitorError(f"Failed to fetch listing {listing.id}: {exc}") from exc

        try:
            return self._parser.parse(response.content, listing)
        except ParseError as exc:
            raise MonitorError(f"Failed to parse listing {listing.id}: {exc}") from exc
