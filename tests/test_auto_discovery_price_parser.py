"""Tests for the URL-only automatic price discovery parser."""

from decimal import Decimal

import pytest

from models.listing import ProductListing
from models.site import Site
from parsers.auto_discovery_price_parser import AutoDiscoveryPriceParser
from parsers.base import ParseError


def _make_listing() -> ProductListing:
    """Create a listing with only the fields the user wants to provide."""
    return ProductListing(
        id="auto-listing-001",
        site=Site(name="Auto Store"),
        url="https://auto-store.example/products/001",
        currency="AUD",
    )


class TestAutoDiscoveryPriceParser:
    """Tests for extracting price and currency from raw page content."""

    def setup_method(self) -> None:
        """Create a fresh parser for each test."""
        self.parser = AutoDiscoveryPriceParser()

    def test_finds_price_and_currency_from_embedded_json(self) -> None:
        """Discovers a price and currency inside a JavaScript JSON object."""
        html = (
            "<script>window.__STATE__ = {"
            '"product": {"price": {"value": 49.95, "currency": "AUD"}}'
            "};</script>"
        )

        result = self.parser.parse(html, _make_listing())

        assert result.price is not None
        assert result.price.value == Decimal("49.95")
        assert result.price.currency == "AUD"

    def test_finds_price_from_nested_currency_code(self) -> None:
        """Discovers a nested currency code near the price."""
        html = (
            "<script>window.__STATE__ = {"
            '"product": {"prices": {"promo": {'
            '"value": 79.95, "currency": {"code": "AUD"}'
            "}}}}</script>"
        )

        result = self.parser.parse(html, _make_listing())

        assert result.price is not None
        assert result.price.value == Decimal("79.95")
        assert result.price.currency == "AUD"

    def test_finds_price_from_visible_html_without_selector(self) -> None:
        """Discovers a price from HTML even when no CSS selector is configured."""
        html = (
            "<html><body>"
            '<span class="price">$1,999.00</span>'
            "</body></html>"
        )

        result = self.parser.parse(html, _make_listing())

        assert result.price is not None
        assert result.price.value == Decimal("1999.00")
        assert result.price.currency == "AUD"

    def test_prefers_promo_price_in_uniqlo_like_embedded_json(self) -> None:
        """Chooses the promo price from a Uniqlo-style preloaded state."""
        html = (
            "<script>window.__PRELOADED_STATE__ = {"
            '"entity": {"pdpEntity": {"E479525-000-00": {'
            '"product": {"prices": {'
            '"base": {"currency": {"code": "AUD"}, "value": 49.9},'
            '"promo": {"currency": {"code": "AUD"}, "value": 39.9}'
            "}}}}}}</script>"
        )

        result = self.parser.parse(html, _make_listing())

        assert result.price is not None
        assert result.price.value == Decimal("39.9")
        assert result.price.currency == "AUD"

    def test_raises_when_no_price_can_be_discovered(self) -> None:
        """Raises ParseError when no price-like value is present."""
        html = "<html><body><p>No price here</p></body></html>"

        with pytest.raises(ParseError, match="Could not discover"):
            self.parser.parse(html, _make_listing())
