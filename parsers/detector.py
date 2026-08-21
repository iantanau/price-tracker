"""Content-based selection of the appropriate price parser."""

from models.listing import ProductListing
from parsers.embedded_json_price_parser import EmbeddedJsonPriceParser
from parsers.json_ld_price_parser import JsonLdPriceParser


def detect_parser_type(
    content: str, listing: ProductListing, available: set[str]
) -> str:
    """Choose a registered parser for ``content``.

    Detection priority is:

    1. ``json_ld`` when the content contains a JSON-LD Product/Offer price.
    2. ``embedded_json`` when the content contains a JavaScript variable whose
       JSON object contains the listing's configured price path.
    3. ``css`` as the fallback.

    Args:
        content: Raw HTML content returned by the HTTP client.
        listing: Listing being parsed.
        available: Names of parsers currently registered in the dispatcher.

    Returns:
        A parser name from ``available``.
    """
    if "json_ld" in available and JsonLdPriceParser.find_price(
        content, listing.currency
    ) is not None:
        return "json_ld"

    if "embedded_json" in available:
        if EmbeddedJsonPriceParser().find_variable(content, listing):
            return "embedded_json"

    return "css"
