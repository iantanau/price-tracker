"""Central Product domain object."""

from dataclasses import dataclass, field
from decimal import Decimal

from models.enums import Availability
from models.site import Site


@dataclass
class Product:
    """The core domain object of the price tracker.

    Required fields identify the product and how to fetch its price.
    Optional fields are future-ready: they default to ``None`` so adding
    more later is backward compatible for consumers that do not use them.

    Attributes:
        id: Stable unique identifier for the product.
        name: Product name.
        site: Site where the product is sold.
        url: Direct URL to the product page.
        price_selector: CSS selector that locates the price element.
        brand: Optional product brand.
        category: Optional product category.
        currency: ISO 4217 currency code. Defaults to AUD for Australian retailers.
        enabled: Whether the product should be monitored.
        target_price: Optional threshold; notifications fire when current price is lower.
        parser_type: Which parser to use for this product (``css`` or ``embedded_json``).
        json_variable: JavaScript variable containing embedded JSON (embedded JSON parser only).
        price_path: Dot-separated path to the price value inside the JSON (embedded JSON parser only).
        currency_path: Dot-separated path to the currency code inside the JSON (embedded JSON parser only).
        availability: Optional stock status.
        cpu: Optional laptop CPU specification (future use).
        gpu: Optional laptop GPU specification (future use).
        ram: Optional RAM specification (future use).
        ssd: Optional SSD specification (future use).
        cashback: Optional cashback value (future use).
        coupon: Optional coupon code (future use).
        shipping: Optional shipping cost (future use).
    """

    # Required fields
    id: str
    name: str
    site: Site
    url: str
    price_selector: str

    # Optional catalog fields
    brand: str | None = None
    category: str | None = None
    currency: str = "AUD"
    enabled: bool = True

    # Phase 1 notification rule
    target_price: Decimal | None = None

    # Parser selection and embedded JSON extraction configuration.
    parser_type: str = "css"
    json_variable: str | None = None
    price_path: str | None = None
    currency_path: str | None = None

    # Future-ready fields; Phase 1 logic ignores them.
    availability: Availability | None = None
    cpu: str | None = None
    gpu: str | None = None
    ram: str | None = None
    ssd: str | None = None
    cashback: Decimal | None = None
    coupon: str | None = None
    shipping: Decimal | None = None
