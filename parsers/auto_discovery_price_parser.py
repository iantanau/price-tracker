"""Fallback parser that discovers price and currency without listing hints.

This parser is intended for ``parser_type="auto"`` listings that provide only a
URL. It tries the structured sources first (JSON-LD), then scans embedded
JavaScript JSON objects, and finally falls back to visible HTML text.
"""

import json
import re
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from models.listing import ProductListing
from models.parsed_result import ParsedResult
from models.price import Price
from parsers.base import ParseError, ProductParser
from parsers.json_ld_price_parser import JsonLdPriceParser


class AutoDiscoveryPriceParser(ProductParser):
    """Discover a price from content without relying on listing hints."""

    _ASSIGNMENT_PATTERN = re.compile(
        r"(?m)([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*=\s*\{"
    )
    _ISO_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
    _PRICE_AMOUNT_PATTERN = re.compile(
        r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?"
    )
    _MAX_PRICE = Decimal("1000000")
    _BLOCK_MARKERS = (
        "incapsula",
        "request unsuccessful",
        "incident id",
        "captcha",
        "access denied",
        "are you a human",
    )

    def parse(self, content: str, listing: ProductListing) -> ParsedResult:
        """Extract a price from ``content`` without requiring parser hints.

        Args:
            content: Raw HTML content.
            listing: Listing being parsed; used for fallback currency and id.

        Returns:
            ParsedResult containing the discovered price.

        Raises:
            ParseError: If no price can be discovered.
        """
        if self._is_block_page(content):
            raise ParseError(
                f"Blocked or challenge page detected for listing {listing.id}"
            )

        price = (
            JsonLdPriceParser.find_price(content, listing.currency)
            or self._discover_embedded_price(content, listing)
            or self._discover_html_price(content, listing)
        )
        if price is None:
            raise ParseError(f"Could not discover a price for listing {listing.id}")
        return ParsedResult(price=price)

    def _is_block_page(self, content: str) -> bool:
        """Return ``True`` when the page looks like an anti-bot challenge."""
        lowered = content.lower()
        return any(marker in lowered for marker in self._BLOCK_MARKERS)

    def _discover_embedded_price(
        self, content: str, listing: ProductListing
    ) -> Price | None:
        """Return the best price found inside embedded JavaScript JSON."""
        candidates: list[tuple[int, Price]] = []
        for data in self._iter_embedded_json(content):
            self._walk_json(data, [], [], candidates, listing.currency)

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def _iter_embedded_json(self, content: str):
        """Yield parsed JSON objects from JavaScript variable assignments."""
        for match in self._ASSIGNMENT_PATTERN.finditer(content):
            start = match.end() - 1
            json_text = self._extract_json_object(content, start)
            if json_text is None:
                continue
            try:
                data = json.loads(json_text)
            except json.JSONDecodeError:
                continue
            yield data

    def _extract_json_object(self, content: str, start: int) -> str | None:
        """Extract a balanced JSON object beginning at ``start``."""
        depth = 0
        in_string = False
        escaped = False

        for index in range(start, len(content)):
            char = content[index]
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
                        return content[start : index + 1]
        return None

    def _walk_json(
        self,
        node: object,
        path: list[str],
        ancestors: list[dict],
        candidates: list[tuple[int, Price]],
        fallback_currency: str,
    ) -> None:
        """Recursively score price-like values inside a JSON tree."""
        if isinstance(node, dict):
            for key, value in node.items():
                child_path = [*path, key]
                if isinstance(value, (dict, list)):
                    self._walk_json(
                        value,
                        child_path,
                        [*ancestors, node],
                        candidates,
                        fallback_currency,
                    )
                    continue

                score = self._price_score(key, child_path)
                if score <= 0:
                    continue

                value_decimal = self._coerce_number(value)
                if value_decimal is None:
                    continue

                currency = self._find_currency(
                    [*ancestors, node], fallback_currency
                )
                candidates.append(
                    (
                        score,
                        Price(
                            value=value_decimal,
                            currency=currency,
                            raw_text=str(value),
                        ),
                    )
                )
        elif isinstance(node, list):
            for item in node:
                self._walk_json(
                    item, path, ancestors, candidates, fallback_currency
                )

    def _price_score(self, key: str, path: list[str]) -> int:
        """Score a scalar key by how much it looks like a price."""
        lowered = key.lower()
        if any(
            token in lowered
            for token in ("currency", "code", "rating", "quantity", "count")
        ):
            return 0

        score = 0
        if "price" in lowered or lowered == "amount":
            score = 100
        elif lowered in {"value", "current", "sale", "promo", "base", "selling"}:
            score = 70
        elif any(
            token in lowered
            for token in ("amount", "value", "price", "sale", "promo")
        ):
            score = 50
        else:
            score = 1

        context = " ".join(part.lower() for part in path)
        if (
            "promo" in context
            or "sale" in context
            or "current" in context
        ):
            score += 20
        elif "base" in context or "regular" in context:
            score += 5

        return score

    def _coerce_number(self, value: object) -> Decimal | None:
        """Convert a JSON scalar to Decimal when it looks like a price."""
        if isinstance(value, bool):
            return None
        if not isinstance(value, (int, float, str)):
            return None
        try:
            decimal = Decimal(str(value))
        except InvalidOperation:
            return None
        if not decimal.is_finite() or decimal < 0:
            return None
        if decimal > self._MAX_PRICE:
            return None
        return decimal

    def _find_currency(
        self, objects: list[dict], fallback_currency: str
    ) -> str:
        """Find the nearest ISO currency code in the JSON context."""
        for obj in reversed(objects):
            for key, value in obj.items():
                lowered = key.lower()
                if not any(
                    token in lowered
                    for token in ("currency", "pricecurrency")
                ):
                    continue
                code = self._currency_from_value(value)
                if code is not None:
                    return code
        return fallback_currency

    def _currency_from_value(self, value: object) -> str | None:
        """Return an ISO currency code from a JSON value, if present."""
        if isinstance(value, str):
            candidate = value.strip().upper()
            if self._ISO_CURRENCY_PATTERN.fullmatch(candidate):
                return candidate
        if isinstance(value, dict):
            for nested in value.values():
                code = self._currency_from_value(nested)
                if code is not None:
                    return code
        return None

    def _discover_html_price(
        self, content: str, listing: ProductListing
    ) -> Price | None:
        """Return the best price-like value from visible HTML text."""
        soup = BeautifulSoup(content, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        candidates: list[tuple[int, int, Price]] = []
        for element in soup.find_all(True):
            text = element.get_text(" ", strip=True)
            if not text:
                continue
            price = self._price_from_text(text, listing.currency)
            if price is None:
                continue
            score = self._html_element_score(element, text)
            candidates.append((score, -len(text), price))

        if not candidates:
            return None

        symbol_candidates = [
            candidate
            for candidate in candidates
            if self._has_currency_symbol(candidate[2].raw_text or "")
        ]
        if symbol_candidates:
            candidates = symbol_candidates

        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return candidates[0][2]

    def _html_element_score(self, element, text: str) -> int:
        """Score an HTML element by how likely it contains a price."""
        score = 0
        identifier = " ".join(
            [
                element.name or "",
                " ".join(element.get("class", [])),
                element.get("id", ""),
            ]
        ).lower()
        if element.get("itemprop") in {"price", "lowPrice", "highPrice"}:
            score += 120
        if any(
            token in identifier
            for token in ("price", "amount", "current", "sale", "offer")
        ):
            score += 100
        if any(symbol in text for symbol in ("$", "€", "£", "AUD", "USD")):
            score += 30
        if len(text) <= 80:
            score += 10
        return score

    def _has_currency_symbol(self, text: str) -> bool:
        """Return ``True`` when the text contains a common currency marker."""
        return any(
            symbol in text for symbol in ("$", "€", "£", "AUD", "USD", "¥")
        )

    def _price_from_text(self, text: str, fallback_currency: str) -> Price | None:
        """Extract the last plausible price amount from text."""
        matches = self._PRICE_AMOUNT_PATTERN.findall(text)
        if not matches:
            return None
        raw = matches[-1]
        normalized = raw.replace(",", "")
        try:
            value = Decimal(normalized)
        except InvalidOperation:
            return None
        if value > self._MAX_PRICE:
            return None

        currency = fallback_currency
        for code in re.findall(r"\b[A-Z]{3}\b", text.upper()):
            if self._ISO_CURRENCY_PATTERN.fullmatch(code):
                currency = code
                break
        return Price(value=value, currency=currency, raw_text=text)
