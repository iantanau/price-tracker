"""Tests for CssPriceParser."""

from decimal import Decimal

import pytest

from models.parsed_result import ParsedResult
from parsers.base import ParseError
from parsers.css_price_parser import CssPriceParser


class TestCssPriceParser:
    """Behaviour tests for the CSS selector price parser."""

    def setup_method(self) -> None:
        """Create a fresh parser for each test."""
        self.parser = CssPriceParser()

    def test_parses_simple_price(self, css_html: str, base_product) -> None:
        """Extracts a plain price from a matching element."""
        result = self.parser.parse(css_html, base_product)

        assert isinstance(result, ParsedResult)
        assert result.price is not None
        assert result.price.value == Decimal("1999.00")
        assert result.price.currency == "AUD"
        assert result.price.raw_text == "$1,999.00"

    def test_parses_price_with_prefix(self, css_html: str, base_product) -> None:
        """Extracts the numeric price when text contains a prefix."""
        base_product.price_selector = ".sale-price"
        result = self.parser.parse(css_html, base_product)

        assert result.price is not None
        assert result.price.value == Decimal("1499")

    def test_parses_price_with_qualifier(self, css_html: str, base_product) -> None:
        """Ignores qualifiers such as 'inc. GST'."""
        base_product.price_selector = ".price-with-qualifier"
        result = self.parser.parse(css_html, base_product)

        assert result.price is not None
        assert result.price.value == Decimal("1499")

    def test_parses_last_price_when_savings_present(
        self, css_html: str, base_product
    ) -> None:
        """Uses the last number as the current price when savings are shown."""
        base_product.price_selector = ".price-with-savings"
        result = self.parser.parse(css_html, base_product)

        assert result.price is not None
        assert result.price.value == Decimal("1499")

    def test_raises_when_selector_matches_nothing(
        self, css_html: str, base_product
    ) -> None:
        """Raises ParseError when the selector matches no elements."""
        base_product.price_selector = ".missing-price"

        with pytest.raises(ParseError, match="matched no elements"):
            self.parser.parse(css_html, base_product)

    def test_raises_when_element_has_no_price(
        self, css_html: str, base_product
    ) -> None:
        """Raises ParseError when the element contains no numeric text."""
        base_product.price_selector = ".product-title"

        with pytest.raises(ParseError, match="Unable to parse price"):
            self.parser.parse(css_html, base_product)
