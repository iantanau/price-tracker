"""Parser for prices embedded inside JavaScript variables in HTML.

Many single-page applications ship product data in a global JavaScript
variable (for example ``window.__PRELOADED_STATE__``) rather than rendering
the price directly into the DOM. This parser extracts that embedded JSON and
reads the configured path, without requiring JavaScript execution.
"""

import json
from decimal import Decimal, InvalidOperation

from models.parsed_result import ParsedResult
from models.price import Price
from models.product import Product
from parsers.base import ParseError, ProductParser


class EmbeddedJsonPriceParser(ProductParser):
    """Extract a price from JSON embedded in a JavaScript variable."""

    def parse(self, content: str, product: Product) -> ParsedResult:
        """Extract the price from embedded JSON using the product's paths.

        Args:
            content: Raw HTML content.
            product: Product configured with ``json_variable``, ``price_path``,
                and optionally ``currency_path``.

        Returns:
            ParsedResult containing the extracted price.

        Raises:
            ParseError: If the variable is missing, the JSON is invalid, the
                path does not exist, or the value is not a valid number.
        """
        if not product.json_variable:
            raise ParseError(f"Product {product.id} has no json_variable configured")
        if not product.price_path:
            raise ParseError(f"Product {product.id} has no price_path configured")

        json_text = self._extract_json_assignment(content, product.json_variable, product.id)
        data = self._parse_json(json_text, product.json_variable, product.id)

        price_value = self._get_first_existing(data, product.price_path, product.id)
        price = self._coerce_price(price_value, product, data)

        currency = self._get_currency(data, product)
        return ParsedResult(price=Price(value=price, currency=currency, raw_text=str(price_value)))

    def _extract_json_assignment(self, content: str, variable: str, product_id: str) -> str:
        """Extract the JSON object assigned to a JavaScript variable.

        The extractor scans character by character so it can handle nested
        objects and JSON strings containing braces without requiring a full
        JavaScript parser.

        Args:
            content: Raw HTML content.
            variable: Variable name to locate, e.g. ``window.__PRELOADED_STATE__``.
            product_id: Product identifier used in error messages.

        Returns:
            The JSON object as a string.

        Raises:
            ParseError: If the variable or its JSON object cannot be found.
        """
        marker = f"{variable} ="
        index = content.find(marker)
        if index == -1:
            raise ParseError(
                f"JavaScript variable '{variable}' not found in HTML for product {product_id}"
            )

        start = content.find("{", index)
        if start == -1:
            raise ParseError(
                f"No JSON object found after variable '{variable}' for product {product_id}"
            )

        depth = 0
        in_string = False
        escaped = False

        for i in range(start, len(content)):
            char = content[i]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = not in_string
            elif not in_string:
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        return content[start : i + 1]

        raise ParseError(
            f"Could not extract complete JSON object for variable '{variable}' "
            f"for product {product_id}"
        )

    def _parse_json(self, json_text: str, variable: str, product_id: str) -> dict:
        """Parse a JSON string into a dictionary.

        Args:
            json_text: JSON object as text.
            variable: Variable name used in error messages.
            product_id: Product identifier used in error messages.

        Returns:
            Parsed JSON object.

        Raises:
            ParseError: If the text is not valid JSON or is not an object.
        """
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise ParseError(
                f"Invalid JSON in variable '{variable}' for product {product_id}: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise ParseError(
                f"Variable '{variable}' does not contain a JSON object for product {product_id}"
            )

        return data

    def _get_path(self, data: dict, path: str, product_id: str) -> object:
        """Traverse a dot-separated path inside a dictionary.

        Args:
            data: Parsed JSON object.
            path: Dot-separated path, e.g. ``entity.pdpEntity.001.product.prices.value``.
            product_id: Product identifier used in error messages.

        Returns:
            The value at the configured path.

        Raises:
            ParseError: If the path does not exist.
        """
        current = data
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                raise ParseError(
                    f"Path '{path}' does not exist for product {product_id}; "
                    f"missing segment '{part}'"
                )
            current = current[part]
        return current

    def _get_first_existing(self, data: dict, path_spec: str, product_id: str) -> object:
        """Return the first non-null value from a ``|``-separated path list.

        Each segment is tried in order. Missing paths and JSON ``null`` values
        are skipped so, for example, a sale price can fall back to the regular
        price when the promotional price is absent.

        Args:
            data: Parsed JSON object.
            path_spec: One or more dot-separated paths, separated by ``|``.
            product_id: Product identifier used in error messages.

        Returns:
            The first non-null value found at one of the paths.

        Raises:
            ParseError: If none of the paths resolve to a non-null value.
        """
        last_error = None
        for path in path_spec.split("|"):
            path = path.strip()
            if not path:
                continue
            try:
                value = self._get_path(data, path, product_id)
            except ParseError as exc:
                last_error = exc
                continue
            if value is None:
                continue
            return value

        if last_error is not None:
            raise last_error
        raise ParseError(
            f"No value found at any path '{path_spec}' for product {product_id}"
        )

    def _coerce_price(self, value: object, product: Product, data: dict) -> Decimal:
        """Convert a raw JSON value into a Decimal price.

        Args:
            value: Raw value extracted from the JSON path.
            product: Product being parsed.
            data: Full parsed JSON object (unused, kept for future context).

        Returns:
            Normalised price value.

        Raises:
            ParseError: If the value cannot be converted to a number.
        """
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ParseError(
                f"Value at path '{product.price_path}' is not a valid number for "
                f"product {product.id}: {value!r}"
            )

        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise ParseError(
                f"Value at path '{product.price_path}' is not a valid number for "
                f"product {product.id}: {value!r}"
            ) from exc

    def _get_currency(self, data: dict, product: Product) -> str:
        """Return the currency code for the product.

        Uses ``product.currency_path`` when provided; otherwise falls back to
        the product's default ``currency`` field.

        Args:
            data: Parsed JSON object.
            product: Product being parsed.

        Returns:
            ISO 4217 currency code.

        Raises:
            ParseError: If the currency path is configured but missing.
        """
        if product.currency_path:
            currency = self._get_first_existing(data, product.currency_path, product.id)
            if not isinstance(currency, str):
                raise ParseError(
                    f"Currency path '{product.currency_path}' does not contain a string "
                    f"for product {product.id}: {currency!r}"
                )
            return currency
        return product.currency
