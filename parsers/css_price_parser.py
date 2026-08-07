"""CSS-selector based price parser."""

import re
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from models.parsed_result import ParsedResult
from models.price import Price
from models.product import Product
from parsers.base import ParseError, ProductParser


class CssPriceParser(ProductParser):
    """Parse a price from HTML using a CSS selector stored on the product."""

    # Matches numbers commonly found in e-commerce price text:
    #   - grouped thousands: 1,999.00
    #   - plain integer: 1999
    #   - decimal: 1999.00, 0.99
    # Thousand separators are validated (groups of exactly three digits).
    _PRICE_PATTERN = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?|\d+\.\d+")

    def parse(self, content: str, product: Product) -> ParsedResult:
        """Extract the price from ``content`` using ``product.price_selector``.

        Args:
            content: HTML content.
            product: Product whose ``price_selector`` points to the price element.

        Returns:
            ParsedResult containing the extracted price.

        Raises:
            ParseError: If the selector matches nothing or the price is invalid.
        """
        soup = BeautifulSoup(content, "html.parser")
        elements = soup.select(product.price_selector)

        if not elements:
            raise ParseError(
                f"Selector '{product.price_selector}' matched no elements "
                f"for product {product.id}"
            )

        raw_text = elements[0].get_text(strip=True)
        price = self._parse_price(raw_text, product.currency)
        return ParsedResult(price=price)

    def _parse_price(self, raw_text: str, currency: str) -> Price:
        """Convert raw price text into a normalised :class:`Price`.

        The parser extracts every numeric token from the text and treats the
        last one as the current/final price. This handles common patterns such
        as ``"Now $1,999"``, ``"$1,999 inc. GST"``, and
        ``"Save $300 — $1,999"``. Thousand separators (commas) are removed
        before conversion to ``Decimal``.

        Args:
            raw_text: Text extracted from the price element.
            currency: ISO 4217 currency code to attach to the price.

        Returns:
            Normalised price value.

        Raises:
            ParseError: If the text cannot be parsed as a price.
        """
        matches = self._PRICE_PATTERN.findall(raw_text)
        if not matches:
            raise ParseError(f"Unable to parse price from text: {raw_text!r}")

        # The final numeric token is usually the current price; earlier tokens
        # are often crossed-out prices, savings amounts, or qualifiers.
        price_text = matches[-1]
        normalized = price_text.replace(",", "")

        try:
            value = Decimal(normalized)
        except InvalidOperation as exc:
            raise ParseError(f"Unable to parse price from text: {raw_text!r}") from exc

        return Price(value=value, currency=currency, raw_text=raw_text)
