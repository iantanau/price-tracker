"""Parser for schema.org JSON-LD product prices."""

import json
import re
from decimal import Decimal, InvalidOperation

from models.parsed_result import ParsedResult
from models.price import Price
from models.listing import ProductListing
from parsers.base import ParseError, ProductParser


_JSON_LD_PATTERN = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


class JsonLdPriceParser(ProductParser):
    """Extract a price from schema.org JSON-LD ``Product``/``Offer`` data."""

    def parse(self, content: str, listing: ProductListing) -> ParsedResult:
        """Extract the first JSON-LD price found in ``content``.

        Args:
            content: Raw HTML containing one or more ``application/ld+json``
                blocks.
            listing: Listing being parsed; its currency is used as fallback.

        Returns:
            ParsedResult containing the extracted price.

        Raises:
            ParseError: If no Product/Offer price can be found.
        """
        price = self.find_price(content, listing.currency)
        if price is None:
            raise ParseError(
                f"No JSON-LD product price found for listing {listing.id}"
            )
        return ParsedResult(price=price)

    @classmethod
    def find_price(cls, content: str, fallback_currency: str) -> Price | None:
        """Return the first price found in JSON-LD blocks, if any."""
        for block in _JSON_LD_PATTERN.findall(content):
            try:
                data = json.loads(block)
            except (json.JSONDecodeError, TypeError):
                continue
            price = cls._find_price_in_node(data, fallback_currency)
            if price is not None:
                return price
        return None

    @classmethod
    def _find_price_in_node(cls, node, fallback_currency: str) -> Price | None:
        """Recursively find a price in a JSON-LD node."""
        if isinstance(node, list):
            for item in node:
                price = cls._find_price_in_node(item, fallback_currency)
                if price is not None:
                    return price
            return None

        if not isinstance(node, dict):
            return None

        node_type = node.get("@type")
        if isinstance(node_type, list):
            node_type = node_type[0] if node_type else None

        if node_type == "Offer":
            price = cls._price_from_offer(node, fallback_currency)
            if price is not None:
                return price

        if node_type == "Product":
            offers = node.get("offers")
            if isinstance(offers, dict):
                price = cls._price_from_offer(offers, fallback_currency)
                if price is not None:
                    return price
            elif isinstance(offers, list):
                for offer in offers:
                    price = cls._price_from_offer(offer, fallback_currency)
                    if price is not None:
                        return price

        return None

    @classmethod
    def _price_from_offer(cls, offer, fallback_currency: str) -> Price | None:
        """Build a Price from an Offer-like dictionary, if possible."""
        if not isinstance(offer, dict):
            return None

        raw = offer.get("price")
        if raw is None or isinstance(raw, bool):
            return None

        try:
            value = Decimal(str(raw))
        except (InvalidOperation, ValueError):
            return None

        currency = offer.get("priceCurrency") or fallback_currency
        return Price(value=value, currency=currency, raw_text=str(raw))
