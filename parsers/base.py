"""Parser abstraction."""

from abc import ABC, abstractmethod

from models.parsed_result import ParsedResult
from models.product import Product


class ProductParser(ABC):
    """Abstract parser that extracts structured data from raw content.

    Phase 1 implementations extract price. Future implementations can add
    product names, availability, coupons, cashback, etc. without changing
    the monitor or service logic.
    """

    @abstractmethod
    def parse(self, content: str, product: Product) -> ParsedResult:
        """Extract structured information from raw content.

        Args:
            content: Raw content returned by an HTTP client (e.g. HTML).
            product: Product being parsed; contains selector hints.

        Returns:
            A :class:`ParsedResult` with any extracted fields.

        Raises:
            ParseError: If the content cannot be parsed as expected.
        """
        raise NotImplementedError


class ParseError(Exception):
    """Raised when a parser fails to extract expected data."""

    pass
