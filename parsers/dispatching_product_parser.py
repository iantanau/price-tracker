"""Parser that delegates to the appropriate implementation per product.

This composite parser keeps the monitor and service layers unchanged while
allowing different products to use different extraction strategies. Products
choose their parser via the ``parser_type`` field; unknown types fall back
to CSS parsing to preserve existing behaviour.
"""

from models.parsed_result import ParsedResult
from models.product import Product
from parsers.base import ParseError, ProductParser


class DispatchingProductParser(ProductParser):
    """Dispatch parsing to a named parser implementation.

    Attributes:
        _parsers: Mapping of ``parser_type`` to parser implementation.
    """

    def __init__(self, parsers: dict[str, ProductParser]) -> None:
        """Initialise the dispatcher with available parsers.

        Args:
            parsers: Mapping of parser type names to parser instances.
        """
        self._parsers = parsers

    def parse(self, content: str, product: Product) -> ParsedResult:
        """Route parsing to the parser configured on the product.

        Args:
            content: Raw content returned by an HTTP client.
            product: Product whose ``parser_type`` selects the parser.

        Returns:
            Structured result extracted from the raw content.

        Raises:
            ParseError: If the configured parser type is not registered or
                the underlying parser fails.
        """
        parser_type = product.parser_type or "css"
        parser = self._parsers.get(parser_type)

        if parser is None:
            available = ", ".join(sorted(self._parsers))
            raise ParseError(
                f"Unknown parser type '{parser_type}' for product {product.id}. "
                f"Available parsers: {available}"
            )

        return parser.parse(content, product)
