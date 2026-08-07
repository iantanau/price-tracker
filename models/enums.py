"""Domain enumerations used across the price tracker."""

from enum import Enum


class Availability(Enum):
    """Stock availability of a product.

    Phase 1 does not scrape availability, but the enum is defined so future
    parsers can populate it without changing the Product model contract.
    """

    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    UNKNOWN = "unknown"
