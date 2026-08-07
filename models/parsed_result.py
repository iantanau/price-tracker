"""Structured extraction result returned by parsers."""

from dataclasses import dataclass

from models.enums import Availability
from models.price import Price


@dataclass
class ParsedResult:
    """Structured information extracted from raw content.

    Phase 1 only populates ``price``. Additional fields are included so
    future parsers can return product names, availability, coupons, etc.
    without requiring interface changes.

    Attributes:
        price: Normalised price, if found.
        name: Parsed product name, if found.
        availability: Parsed stock status, if found.
        coupon: Parsed coupon code, if found.
        cashback: Parsed cashback amount, if found.
    """

    price: Price | None = None
    name: str | None = None
    availability: Availability | None = None
    coupon: str | None = None
    cashback: float | None = None
