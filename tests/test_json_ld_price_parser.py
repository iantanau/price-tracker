"""Tests for JsonLdPriceParser."""

from decimal import Decimal

import pytest

from models.parsed_result import ParsedResult
from models.product import Product
from models.site import Site
from parsers.base import ParseError
from parsers.json_ld_price_parser import JsonLdPriceParser


class TestJsonLdPriceParser:
    """Behaviour tests for the JSON-LD price parser."""

    def setup_method(self) -> None:
        """Create a fresh parser and product for each test."""
        self.parser = JsonLdPriceParser()
        self.product = Product(
            id="json-ld-product",
            name="JSON-LD Product",
            site=Site(name="JSON-LD Store"),
            url="https://json-ld-store.example/products/001",
            price_selector="",
            currency="AUD",
        )

    def test_parses_product_offer_price(self) -> None:
        """Extracts price and currency from a Product's offers block."""
        html = (
            '<script type="application/ld+json">'
            '{"@type":"Product","offers":{"@type":"Offer","price":"499.00",'
            '"priceCurrency":"AUD"}}'
            "</script>"
        )

        result = self.parser.parse(html, self.product)

        assert isinstance(result, ParsedResult)
        assert result.price is not None
        assert result.price.value == Decimal("499.00")
        assert result.price.currency == "AUD"

    def test_parses_standalone_offer(self) -> None:
        """Extracts price from a top-level Offer block."""
        html = (
            '<script type="application/ld+json">'
            '{"@type":"Offer","price":"39.90","priceCurrency":"AUD"}'
            "</script>"
        )

        result = self.parser.parse(html, self.product)

        assert result.price is not None
        assert result.price.value == Decimal("39.90")
        assert result.price.currency == "AUD"

    def test_parses_offer_list(self) -> None:
        """Extracts price when Product.offers is a list."""
        html = (
            '<script type="application/ld+json">'
            '{"@type":"Product","offers":['
            '{"@type":"Offer","price":"100.00","priceCurrency":"AUD"}'
            "]}"
            "</script>"
        )

        result = self.parser.parse(html, self.product)

        assert result.price is not None
        assert result.price.value == Decimal("100.00")

    def test_uses_product_currency_as_fallback(self) -> None:
        """Falls back to the product currency when JSON-LD omits it."""
        html = (
            '<script type="application/ld+json">'
            '{"@type":"Offer","price":"50"}'
            "</script>"
        )

        result = self.parser.parse(html, self.product)

        assert result.price is not None
        assert result.price.currency == "AUD"

    def test_raises_when_no_price_found(self) -> None:
        """Raises ParseError when no JSON-LD product/offer price exists."""
        html = "<html><body>no structured data</body></html>"

        with pytest.raises(ParseError, match="No JSON-LD product price"):
            self.parser.parse(html, self.product)
