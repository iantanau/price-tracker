"""Tests for DispatchingProductParser."""

from dataclasses import replace
from decimal import Decimal

import pytest

from models.listing import ProductListing
from models.parsed_result import ParsedResult
from models.site import Site
from parsers.base import ParseError
from parsers.css_price_parser import CssPriceParser
from parsers.dispatching_product_parser import DispatchingProductParser
from parsers.embedded_json_price_parser import EmbeddedJsonPriceParser
from parsers.json_ld_price_parser import JsonLdPriceParser


class TestDispatchingProductParser:
    """Tests for parser selection by listing type."""

    def setup_method(self) -> None:
        """Create a dispatcher with both parsers registered."""
        self.dispatcher = DispatchingProductParser(
            parsers={
                "css": CssPriceParser(),
                "embedded_json": EmbeddedJsonPriceParser(),
            }
        )

    def test_dispatches_to_css_parser(self, css_html: str, base_listing) -> None:
        """Routes to CssPriceParser when parser_type is css."""
        listing = replace(base_listing, parser_type="css")

        result = self.dispatcher.parse(css_html, listing)

        assert isinstance(result, ParsedResult)
        assert result.price is not None
        assert result.price.value == Decimal("1999.00")

    def test_dispatches_to_embedded_json_parser(
        self, embedded_json_html: str
    ) -> None:
        """Routes to EmbeddedJsonPriceParser when parser_type is embedded_json."""
        listing = ProductListing(
            id="json-listing-001",
            site=Site(name="JSON Store"),
            url="https://json-store.example/products/001",
            currency="AUD",
            parser_type="embedded_json",
            json_variable="window.__PRELOADED_STATE__",
            price_path="entity.products.SKU-12345.prices.promo.value",
            currency_path="entity.products.SKU-12345.prices.promo.currency.code",
        )

        result = self.dispatcher.parse(embedded_json_html, listing)

        assert isinstance(result, ParsedResult)
        assert result.price is not None
        assert result.price.value == Decimal("79.95")

    def test_raises_for_unknown_parser_type(self, css_html: str, base_listing) -> None:
        """Raises ParseError when parser_type is not registered."""
        listing = replace(base_listing, parser_type="unknown")

        with pytest.raises(ParseError, match="Unknown parser type"):
            self.dispatcher.parse(css_html, listing)

    def test_defaults_to_css_when_parser_type_is_empty(
        self, css_html: str, base_listing
    ) -> None:
        """Defaults to CSS parsing when parser_type is empty or unset."""
        listing = replace(base_listing, parser_type="")

        result = self.dispatcher.parse(css_html, listing)

        assert result.price is not None
        assert result.price.value == Decimal("1999.00")

    def _dispatcher_with_json_ld(self) -> DispatchingProductParser:
        """Return a dispatcher with all three parsers registered."""
        return DispatchingProductParser(
            parsers={
                "css": CssPriceParser(),
                "embedded_json": EmbeddedJsonPriceParser(),
                "json_ld": JsonLdPriceParser(),
            }
        )

    def test_auto_dispatches_to_json_ld(self) -> None:
        """Routes auto to JSON-LD when structured product price exists."""
        dispatcher = self._dispatcher_with_json_ld()
        listing = ProductListing(
            id="auto-json-ld",
            site=Site(name="Auto Store"),
            url="https://auto-store.example/products/001",
            currency="AUD",
            parser_type="auto",
        )
        html = (
            '<script type="application/ld+json">'
            '{"@type":"Product","offers":{"@type":"Offer","price":"499.00",'
            '"priceCurrency":"AUD"}}'
            "</script>"
        )

        result = dispatcher.parse(html, listing)

        assert result.price is not None
        assert result.price.value == Decimal("499.00")

    def test_auto_dispatches_to_embedded_json(
        self, embedded_json_html: str
    ) -> None:
        """Routes auto to embedded JSON when its variable is present."""
        dispatcher = self._dispatcher_with_json_ld()
        listing = ProductListing(
            id="auto-json-listing",
            site=Site(name="Auto Store"),
            url="https://auto-store.example/products/001",
            currency="AUD",
            parser_type="auto",
            json_variable="window.__PRELOADED_STATE__",
            price_path="entity.products.SKU-12345.prices.promo.value",
            currency_path="entity.products.SKU-12345.prices.promo.currency.code",
        )

        result = dispatcher.parse(embedded_json_html, listing)

        assert result.price is not None
        assert result.price.value == Decimal("79.95")

    def test_auto_falls_back_to_css(self, css_html: str, base_listing) -> None:
        """Routes auto to CSS when no JSON-LD or embedded JSON signal exists."""
        dispatcher = self._dispatcher_with_json_ld()
        listing = replace(base_listing, parser_type="auto")

        result = dispatcher.parse(css_html, listing)

        assert result.price is not None
        assert result.price.value == Decimal("1999.00")
