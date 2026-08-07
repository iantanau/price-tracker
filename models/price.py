"""Price value object."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Price:
    """A normalized price value.

    ``raw_text`` preserves the original scraped string for debugging and
    audit purposes, while ``value`` is a Decimal for reliable comparisons.

    Attributes:
        value: Numeric price amount.
        currency: ISO 4217 currency code, e.g. ``AUD``.
        raw_text: Original text found in the page, if any.
    """

    value: Decimal
    currency: str
    raw_text: str | None = None
