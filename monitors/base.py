"""Monitor abstraction."""

from abc import ABC, abstractmethod

from models.parsed_result import ParsedResult
from models.product import Product


class Monitor(ABC):
    """Abstract monitor that retrieves current information for a product.

    A monitor is responsible only for obtaining raw content and delegating
    parsing to a :class:`ProductParser`. It must not send notifications,
    store data, compare prices, or contain business rules.
    """

    @abstractmethod
    def fetch(self, product: Product) -> ParsedResult:
        """Retrieve and parse the current state of ``product``.

        Args:
            product: Product to monitor.

        Returns:
            Structured result extracted from the product page.

        Raises:
            MonitorError: If the product cannot be monitored.
        """
        raise NotImplementedError


class MonitorError(Exception):
    """Raised when a monitor fails to retrieve product information."""

    pass
