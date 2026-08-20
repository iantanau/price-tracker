"""Content-based selection of the appropriate price parser."""

from models.product import Product
from parsers.json_ld_price_parser import JsonLdPriceParser


def detect_parser_type(content: str, product: Product, available: set[str]) -> str:
    """Choose a registered parser for ``content``.

    Detection priority is:

    1. ``json_ld`` when the content contains a JSON-LD Product/Offer price.
    2. ``embedded_json`` when the product has a configured variable present.
    3. ``css`` as the fallback.

    Args:
        content: Raw HTML content returned by the HTTP client.
        product: Product being parsed.
        available: Names of parsers currently registered in the dispatcher.

    Returns:
        A parser name from ``available``.
    """
    if "json_ld" in available and JsonLdPriceParser.find_price(
        content, product.currency
    ) is not None:
        return "json_ld"

    if "embedded_json" in available and product.json_variable:
        if f"{product.json_variable} =" in content:
            return "embedded_json"

    return "css"
