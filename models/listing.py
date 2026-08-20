"""A single retailer listing for a logical product."""

from dataclasses import dataclass

from models.site import Site


@dataclass(frozen=True)
class ProductListing:
    """One URL/site entry that belongs to a logical product.

    Attributes:
        id: Stable unique identifier for this listing, e.g. ``amazon-au``.
        site: Retailer or site the listing belongs to.
        url: Direct product page URL.
        price_selector: CSS selector used by the CSS parser.
        parser_type: Parser name (``css``, ``embedded_json``, ``json_ld``,
            or ``auto``).
        json_variable: JavaScript variable for the embedded JSON parser.
        price_path: Dot-separated path(s) to the price inside embedded JSON.
        currency_path: Dot-separated path(s) to the currency inside embedded JSON.
        currency: ISO 4217 currency code.
    """

    id: str
    site: Site
    url: str
    price_selector: str = ""
    parser_type: str = "auto"
    json_variable: str | None = None
    price_path: str | None = None
    currency_path: str | None = None
    currency: str = "AUD"
