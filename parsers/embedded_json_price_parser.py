"""Parser for prices embedded inside JavaScript variables in HTML.

Many single-page applications ship product data in a global JavaScript
variable (for example ``window.__PRELOADED_STATE__``) rather than rendering
the price directly into the DOM. This parser extracts that embedded JSON and
reads the configured path, without requiring JavaScript execution.
"""

import json
import re
from decimal import Decimal, InvalidOperation

from models.listing import ProductListing
from models.parsed_result import ParsedResult
from models.price import Price
from parsers.base import ParseError, ProductParser


class EmbeddedJsonPriceParser(ProductParser):
    """Extract a price from JSON embedded in a JavaScript variable."""

    def parse(self, content: str, listing: ProductListing) -> ParsedResult:
        """Extract the price from embedded JSON using the listing's paths.

        Args:
            content: Raw HTML content.
            listing: Listing configured with ``price_path`` and optionally
                ``currency_path``. If ``json_variable`` is not configured, the
                parser locates a JavaScript variable whose JSON object contains
                ``price_path``.

        Returns:
            ParsedResult containing the extracted price.

        Raises:
            ParseError: If the variable is missing, the JSON is invalid, the
                path does not exist, or the value is not a valid number.
        """
        if not listing.price_path:
            raise ParseError(f"Listing {listing.id} has no price_path configured")

        if listing.json_variable:
            if f"{listing.json_variable} =" not in content:
                raise ParseError(
                    f"JavaScript variable '{listing.json_variable}' not found in HTML "
                    f"for listing {listing.id}"
                )
            variable = listing.json_variable
        else:
            variable = self._detect_variable(content, listing)
            if variable is None:
                raise ParseError(
                    f"Could not locate an embedded JSON variable containing "
                    f"'{listing.price_path}' for listing {listing.id}"
                )

        json_text = self._extract_json_assignment(content, variable, listing.id)
        data = self._parse_json(json_text, variable, listing.id)

        price_value = self._get_first_existing(data, listing.price_path, listing.id)
        price = self._coerce_price(price_value, listing, data)

        currency = self._get_currency(data, listing)
        return ParsedResult(
            price=Price(value=price, currency=currency, raw_text=str(price_value))
        )

    def find_variable(self, content: str, listing: ProductListing) -> str | None:
        """Return the variable name to parse for ``listing``.

        Explicit ``json_variable`` configuration is preferred. When it is not
        configured, this method scans JavaScript object assignments and returns
        the first variable whose object contains ``listing.price_path``.
        """
        if listing.json_variable:
            if f"{listing.json_variable} =" in content:
                return listing.json_variable
            return None
        return self._detect_variable(content, listing)

    def _detect_variable(
        self, content: str, listing: ProductListing
    ) -> str | None:
        """Find a JavaScript variable assignment containing ``price_path``."""
        if not listing.price_path:
            return None

        assignment_pattern = re.compile(
            r"(?m)([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*=\s*\{"
        )
        for match in assignment_pattern.finditer(content):
            variable = match.group(1)
            try:
                json_text = self._extract_json_assignment(
                    content, variable, listing.id
                )
                data = self._parse_json(json_text, variable, listing.id)
                self._get_first_existing(data, listing.price_path, listing.id)
            except ParseError:
                continue
            return variable
        return None

    def _extract_json_assignment(
        self, content: str, variable: str, listing_id: str
    ) -> str:
        """Extract the JSON object assigned to a JavaScript variable.

        The extractor scans character by character so it can handle nested
        objects and JSON strings containing braces without requiring a full
        JavaScript parser.

        Args:
            content: Raw HTML content.
            variable: Variable name to locate, e.g. ``window.__PRELOADED_STATE__``.
            listing_id: Listing identifier used in error messages.

        Returns:
            The JSON object as a string.

        Raises:
            ParseError: If the variable or its JSON object cannot be found.
        """
        marker = f"{variable} ="
        index = content.find(marker)
        if index == -1:
            raise ParseError(
                f"JavaScript variable '{variable}' not found in HTML "
                f"for listing {listing_id}"
            )

        start = content.find("{", index)
        if start == -1:
            raise ParseError(
                f"No JSON object found after variable '{variable}' "
                f"for listing {listing_id}"
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
            f"for listing {listing_id}"
        )

    def _parse_json(self, json_text: str, variable: str, listing_id: str) -> dict:
        """Parse a JSON string into a dictionary.

        Args:
            json_text: JSON object as text.
            variable: Variable name used in error messages.
            listing_id: Listing identifier used in error messages.

        Returns:
            Parsed JSON object.

        Raises:
            ParseError: If the text is not valid JSON or is not an object.
        """
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise ParseError(
                f"Invalid JSON in variable '{variable}' for listing {listing_id}: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise ParseError(
                f"Variable '{variable}' does not contain a JSON object "
                f"for listing {listing_id}"
            )

        return data

    def _get_path(self, data: dict, path: str, listing_id: str) -> object:
        """Traverse a dot-separated path inside a dictionary.

        Args:
            data: Parsed JSON object.
            path: Dot-separated path, e.g. ``entity.pdpEntity.001.product.prices.value``.
            listing_id: Listing identifier used in error messages.

        Returns:
            The value at the configured path.

        Raises:
            ParseError: If the path does not exist.
        """
        current = data
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                raise ParseError(
                    f"Path '{path}' does not exist for listing {listing_id}; "
                    f"missing segment '{part}'"
                )
            current = current[part]
        return current

    def _get_first_existing(
        self, data: dict, path_spec: str, listing_id: str
    ) -> object:
        """Return the first non-null value from a ``|``-separated path list.

        Each segment is tried in order. Missing paths and JSON ``null`` values
        are skipped so, for example, a sale price can fall back to the regular
        price when the promotional price is absent.

        Args:
            data: Parsed JSON object.
            path_spec: One or more dot-separated paths, separated by ``|``.
            listing_id: Listing identifier used in error messages.

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
                value = self._get_path(data, path, listing_id)
            except ParseError as exc:
                last_error = exc
                continue
            if value is None:
                continue
            return value

        if last_error is not None:
            raise last_error
        raise ParseError(
            f"No value found at any path '{path_spec}' for listing {listing_id}"
        )

    def _coerce_price(
        self, value: object, listing: ProductListing, data: dict
    ) -> Decimal:
        """Convert a raw JSON value into a Decimal price.

        Args:
            value: Raw value extracted from the JSON path.
            listing: Listing being parsed.
            data: Full parsed JSON object (unused, kept for future context).

        Returns:
            Normalised price value.

        Raises:
            ParseError: If the value cannot be converted to a number.
        """
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ParseError(
                f"Value at path '{listing.price_path}' is not a valid number for "
                f"listing {listing.id}: {value!r}"
            )

        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise ParseError(
                f"Value at path '{listing.price_path}' is not a valid number for "
                f"listing {listing.id}: {value!r}"
            ) from exc

    def _get_currency(self, data: dict, listing: ProductListing) -> str:
        """Return the currency code for the listing.

        Uses ``listing.currency_path`` when provided; otherwise falls back to
        the listing's default ``currency`` field.

        Args:
            data: Parsed JSON object.
            listing: Listing being parsed.

        Returns:
            ISO 4217 currency code.

        Raises:
            ParseError: If the currency path is configured but missing.
        """
        if listing.currency_path:
            currency = self._get_first_existing(
                data, listing.currency_path, listing.id
            )
            if not isinstance(currency, str):
                raise ParseError(
                    f"Currency path '{listing.currency_path}' does not contain a string "
                    f"for listing {listing.id}: {currency!r}"
                )
            return currency
        return listing.currency
