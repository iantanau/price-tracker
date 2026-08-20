"""Central Product domain object."""

from dataclasses import dataclass, field
from decimal import Decimal

from models.enums import Availability
from models.listing import ProductListing


@dataclass
class Product:
    """The core domain object of the price tracker.

    Required fields identify the product and how to fetch its price.
    Optional fields are future-ready: they default to ``None`` so adding
    more later is backward compatible for consumers that do not use them.

    Attributes:
        id: Stable unique identifier for the product.
        name: Product name.
        listings: One or more retailer listings to compare.
        brand: Optional product brand.
        category: Optional product category.
        currency: ISO 4217 currency code. Defaults to AUD for Australian retailers.
        enabled: Whether the product should be monitored.
        target_price: Optional threshold; notifications fire when the product's
            best price is at or below this value.
        availability: Optional stock status.
        cpu: Optional laptop CPU specification (future use).
        gpu: Optional laptop GPU specification (future use).
        ram: Optional RAM specification (future use).
        ssd: Optional SSD specification (future use).
        cashback: Optional cashback value (future use).
        coupon: Optional coupon code (future use).
        shipping: Optional shipping cost (future use).
    """

    id: str
    name: str
    listings: list[ProductListing] = field(default_factory=list)
    brand: str | None = None
    category: str | None = None
    currency: str = "AUD"
    enabled: bool = True

    # Comparison-level notification rule.
    target_price: Decimal | None = None

    # Future-ready fields; the current comparison logic ignores them.
    availability: Availability | None = None
    cpu: str | None = None
    gpu: str | None = None
    ram: str | None = None
    ssd: str | None = None
    cashback: Decimal | None = None
    coupon: str | None = None
    shipping: Decimal | None = None
