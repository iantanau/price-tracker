"""Notification payload value objects."""

from dataclasses import dataclass
from decimal import Decimal

from models.price import Price


@dataclass(frozen=True)
class ListingPrice:
    """One retailer's current price for a product."""

    listing_id: str
    site_name: str
    url: str
    price: Price | None = None


@dataclass(frozen=True)
class NotificationItem:
    """One product comparison alert inside a notification.

    Carries structured data rather than rendered text so each notifier can
    format it for its own channel (email HTML, Telegram Markdown, WeChat text).

    Attributes:
        product_id: Stable product identifier.
        name: Product name.
        listings: Current price for every retailer listing.
        best_price: Cheapest price across the listings.
        target_price: Optional threshold that triggered the alert.
        brand: Optional product brand.
        category: Optional product category.
        trigger: Why the alert fired (``target`` or ``new_low``).
    """

    product_id: str
    name: str
    listings: tuple[ListingPrice, ...] = ()
    best_price: Price | None = None
    target_price: Decimal | None = None
    brand: str | None = None
    category: str | None = None
    trigger: str | None = None


@dataclass(frozen=True)
class NotificationPayload:
    """Data-only batch delivered by a notifier.

    This object contains no sending logic; notifiers decide how to format
    and deliver the payload through their specific channel.

    Attributes:
        subject: Short summary line.
        items: Structured alert items for the products in this notification.
        recipient: Optional override recipient; notifiers fall back to settings.
    """

    subject: str
    items: tuple[NotificationItem, ...] = ()
    recipient: str | None = None
