"""Tests for DispatchingProductParser."""

from decimal import Decimal

import pytest

from models.parsed_result import ParsedResult
from models.product import Product
from models.site import Site
from parsers.base import ParseError
from parsers.css_price_parser import CssPriceParser
from parsers.dispatching_product_parser import DispatchingProductParser
from parsers.embedded_json_price_parser import EmbeddedJsonPriceParser


class TestDispatchingProductParser:
    """Tests for parser selection by product type."""

    def setup_method(self) -> None:
        """Create a dispatcher with both parsers registered."""
        self.dispatcher = DispatchingProductParser(
            parsers={
                "css": CssPriceParser(),
                "embedded_json": EmbeddedJsonPriceParser(),
            }
        )

    def test_dispatches_to_css_parser(self, css_html: str, base_product) -> None:
        """Routes to CssPriceParser when parser_type is css."""
        base_product.parser_type = "css"

        result = self.dispatcher.parse(css_html, base_product)

        assert isinstance(result, ParsedResult)
        assert result.price is not None
        assert result.price.value == Decimal("1999.00")

    def test_dispatches_to_embedded_json_parser(
        self, embedded_json_html: str
    ) -> None:
        """Routes to EmbeddedJsonPriceParser when parser_type is embedded_json."""
        product = Product(
            id="json-product-001",
            name="Embedded JSON Product",
            site=Site(name="JSON Store"),
            url="https://json-store.example/products/001",
            price_selector="",
            currency="AUD",
            parser_type="embedded_json",
            json_variable="window.__PRELOADED_STATE__",
            price_path="entity.products.SKU-12345.prices.promo.value",
            currency_path="entity.products.SKU-12345.prices.promo.currency.code",
        )

        result = self.dispatcher.parse(embedded_json_html, product)

        assert isinstance(result, ParsedResult)
        assert result.price is not None
        assert result.price.value == Decimal("79.95")

    def test_raises_for_unknown_parser_type(self, css_html: str, base_product) -> None:
        """Raises ParseError when parser_type is not registered."""
        base_product.parser_type = "unknown"

        with pytest.raises(ParseError, match="Unknown parser type"):
            self.dispatcher.parse(css_html, base_product)

    def test_defaults_to_css_when_parser_type_is_empty(
        self, css_html: str, base_product
    ) -> None:
        """Defaults to CSS parsing when parser_type is empty or unset."""
        base_product.parser_type = ""

        result = self.dispatcher.parse(css_html, base_product)

        assert result.price is not None
        assert result.price.value == Decimal("1999.00")
