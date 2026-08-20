"""Monitor abstraction."""

from abc import ABC, abstractmethod

from models.parsed_result import ParsedResult
from models.listing import ProductListing


class Monitor(ABC):
    """Abstract monitor that retrieves current information for a product.

    A monitor is responsible only for obtaining raw content and delegating
    parsing to a :class:`ProductParser`. It must not send notifications,
    store data, compare prices, or contain business rules.
    """

    @abstractmethod
    def fetch_listing(self, listing: ProductListing) -> ParsedResult:
        """Retrieve and parse the current state of ``listing``.

        Args:
            listing: Listing to monitor.

        Returns:
            Structured result extracted from the listing page.

        Raises:
            MonitorError: If the listing cannot be monitored.
        """
        raise NotImplementedError


class MonitorError(Exception):
    """Raised when a monitor fails to retrieve product information."""

    pass
