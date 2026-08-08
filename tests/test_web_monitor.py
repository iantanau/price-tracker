"""Tests for WebMonitor coordination."""

from decimal import Decimal
from unittest.mock import Mock

import pytest

from clients.base import HttpClientError
from models.http_response import HttpResponse
from models.parsed_result import ParsedResult
from models.price import Price
from monitors.base import MonitorError
from monitors.web_monitor import WebMonitor
from parsers.base import ParseError


class TestWebMonitor:
    """Tests for WebMonitor's coordination of HTTP client and parser."""

    def test_returns_parsed_result_from_parser(self, base_product) -> None:
        """Fetches content, delegates to the parser, and returns its result."""
        http_client = Mock()
        parser = Mock()
        parser.parse.return_value = ParsedResult(
            price=Price(value=Decimal("99.95"), currency="AUD")
        )
        http_client.get.return_value = HttpResponse(
            content="<html><body>$99.95</body></html>",
            status_code=200,
            headers={},
        )

        monitor = WebMonitor(client=http_client, parser=parser)
        result = monitor.fetch(base_product)

        http_client.get.assert_called_once_with(base_product.url)
        parser.parse.assert_called_once_with(
            "<html><body>$99.95</body></html>", base_product
        )
        assert result.price is not None
        assert result.price.value == Decimal("99.95")

    def test_wraps_http_client_error_in_monitor_error(self, base_product) -> None:
        """Raises MonitorError when the HTTP client fails."""
        http_client = Mock()
        parser = Mock()
        http_client.get.side_effect = HttpClientError("connection failed")

        monitor = WebMonitor(client=http_client, parser=parser)

        with pytest.raises(MonitorError, match="Failed to fetch product"):
            monitor.fetch(base_product)

    def test_wraps_parse_error_in_monitor_error(self, base_product) -> None:
        """Raises MonitorError when the parser fails."""
        http_client = Mock()
        parser = Mock()
        parser.parse.side_effect = ParseError("no price found")
        http_client.get.return_value = HttpResponse(
            content="<html><body>No price</body></html>",
            status_code=200,
            headers={},
        )

        monitor = WebMonitor(client=http_client, parser=parser)

        with pytest.raises(MonitorError, match="Failed to parse product"):
            monitor.fetch(base_product)
