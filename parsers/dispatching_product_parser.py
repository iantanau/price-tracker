"""Parser that delegates to the appropriate implementation per product.

This composite parser keeps the monitor and service layers unchanged while
allowing different products to use different extraction strategies. Products
choose their parser via the ``parser_type`` field; ``"auto"`` selects a parser
from the raw content, while explicit types are dispatched directly.
"""

from models.parsed_result import ParsedResult
from models.listing import ProductListing
from parsers.base import ParseError, ProductParser
from parsers.detector import detect_parser_type


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

    def parse(self, content: str, listing: ProductListing) -> ParsedResult:
        """Route parsing to the parser configured on the listing.

        Args:
            content: Raw content returned by an HTTP client.
            listing: Listing whose ``parser_type`` selects the parser.

        Returns:
            Structured result extracted from the raw content.

        Raises:
            ParseError: If the configured parser type is not registered or
                the underlying parser fails.
        """
        parser_type = listing.parser_type or "css"
        if parser_type == "auto":
            parser_type = detect_parser_type(content, listing, set(self._parsers))

        parser = self._parsers.get(parser_type)

        if parser is None:
            available = ", ".join(sorted(self._parsers))
            raise ParseError(
                f"Unknown parser type '{parser_type}' for listing {listing.id}. "
                f"Available parsers: {available}"
            )

        return parser.parse(content, listing)
