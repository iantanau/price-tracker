"""Tests for EmbeddedJsonPriceParser."""

from dataclasses import replace
from decimal import Decimal

import pytest

from models.listing import ProductListing
from models.parsed_result import ParsedResult
from models.site import Site
from parsers.base import ParseError
from parsers.embedded_json_price_parser import EmbeddedJsonPriceParser


class TestEmbeddedJsonPriceParser:
    """Behaviour tests for the embedded JSON price parser."""

    def setup_method(self) -> None:
        """Create a fresh parser and listing for each test."""
        self.parser = EmbeddedJsonPriceParser()
        self.listing = ProductListing(
            id="json-listing-001",
            site=Site(name="JSON Store"),
            url="https://json-store.example/products/001",
            currency="AUD",
            parser_type="embedded_json",
            json_variable="window.__PRELOADED_STATE__",
            price_path="entity.products.SKU-12345.prices.promo.value",
            currency_path="entity.products.SKU-12345.prices.promo.currency.code",
        )

    def test_parses_promotional_price(self, embedded_json_html: str) -> None:
        """Extracts the promotional price and currency from embedded JSON."""
        result = self.parser.parse(embedded_json_html, self.listing)

        assert isinstance(result, ParsedResult)
        assert result.price is not None
        assert result.price.value == Decimal("79.95")
        assert result.price.currency == "AUD"
        assert result.price.raw_text == "79.95"

    def test_parses_base_price(self, embedded_json_html: str) -> None:
        """Extracts the regular/base price when configured."""
        listing = replace(
            self.listing,
            price_path="entity.products.SKU-12345.prices.base.value",
            currency_path="entity.products.SKU-12345.prices.base.currency.code",
        )

        result = self.parser.parse(embedded_json_html, listing)

        assert result.price is not None
        assert result.price.value == Decimal("99.95")
        assert result.price.currency == "AUD"

    def test_prefers_promo_when_both_paths_present(self, embedded_json_html: str) -> None:
        """Prefers the promotional price when both promo and base paths resolve."""
        listing = replace(
            self.listing,
            price_path=(
                "entity.products.SKU-12345.prices.promo.value"
                "|entity.products.SKU-12345.prices.base.value"
            ),
            currency_path=(
                "entity.products.SKU-12345.prices.promo.currency.code"
                "|entity.products.SKU-12345.prices.base.currency.code"
            ),
        )

        result = self.parser.parse(embedded_json_html, listing)

        assert result.price is not None
        assert result.price.value == Decimal("79.95")
        assert result.price.currency == "AUD"

    def test_falls_back_to_base_when_promo_is_null(self) -> None:
        """Falls back to the base price when the promo path is JSON null."""
        html = (
            "<script>window.__PRELOADED_STATE__ = {"
            '"entity": {"products": {"SKU-12345": {'
            '"prices": {'
            '"base": {"currency": {"code": "AUD"}, "value": 99.95},'
            '"promo": null'
            "}}}}};</script>"
        )
        listing = replace(
            self.listing,
            price_path=(
                "entity.products.SKU-12345.prices.promo.value"
                "|entity.products.SKU-12345.prices.base.value"
            ),
            currency_path=(
                "entity.products.SKU-12345.prices.promo.currency.code"
                "|entity.products.SKU-12345.prices.base.currency.code"
            ),
        )

        result = self.parser.parse(html, listing)

        assert result.price is not None
        assert result.price.value == Decimal("99.95")
        assert result.price.currency == "AUD"

    def test_uses_listing_currency_when_currency_path_missing(
        self, embedded_json_html: str
    ) -> None:
        """Falls back to the listing currency when no currency path is set."""
        listing = replace(self.listing, currency_path=None)

        result = self.parser.parse(embedded_json_html, listing)

        assert result.price is not None
        assert result.price.currency == "AUD"

    def test_raises_when_variable_missing(self, embedded_json_html: str) -> None:
        """Raises ParseError when the JavaScript variable is not found."""
        listing = replace(self.listing, json_variable="window.__MISSING_STATE__")

        with pytest.raises(ParseError, match="not found in HTML"):
            self.parser.parse(embedded_json_html, listing)

    def test_raises_when_json_invalid(self, embedded_json_html: str) -> None:
        """Raises ParseError when the variable contains invalid JSON."""
        html = embedded_json_html.replace(
            '"value": 79.95', '"value": 79.95 invalid'
        )

        with pytest.raises(ParseError, match="Invalid JSON"):
            self.parser.parse(html, self.listing)

    def test_raises_when_path_missing(self, embedded_json_html: str) -> None:
        """Raises ParseError when the configured path does not exist."""
        listing = replace(
            self.listing,
            price_path="entity.products.MISSING.prices.promo.value",
        )

        with pytest.raises(ParseError, match="missing segment 'MISSING'"):
            self.parser.parse(embedded_json_html, listing)

    def test_raises_when_value_not_numeric(self, embedded_json_html: str) -> None:
        """Raises ParseError when the extracted value is not a number."""
        listing = replace(
            self.listing,
            price_path="entity.products.SKU-12345.name",
        )

        with pytest.raises(ParseError, match="not a valid number"):
            self.parser.parse(embedded_json_html, listing)

    def test_raises_when_currency_not_string(self, embedded_json_html: str) -> None:
        """Raises ParseError when the currency path points to a non-string."""
        listing = replace(
            self.listing,
            currency_path="entity.products.SKU-12345.prices.promo",
        )

        with pytest.raises(ParseError, match="does not contain a string"):
            self.parser.parse(embedded_json_html, listing)
