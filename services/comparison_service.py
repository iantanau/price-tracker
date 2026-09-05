"""Comparison service that compares listings for each product.

The service loads enabled products, fetches every listing, derives the
product's best current price, asks the rule engine whether an alert is
warranted, and delegates a single aggregated notification to a notifier.
It contains no business rules itself.
"""

from models.notification_payload import ListingPrice, NotificationItem, NotificationPayload
from models.parsed_result import ParsedResult
from models.price import Price
from models.product import Product
from monitors.base import Monitor
from notifiers.base import Notifier
from services.rule_engine import RuleEngine
from storage.base import PriceHistoryStore, ProductStore
from utils.logging import get_logger

logger = get_logger("services.comparison_service")


class ComparisonService:
    """Orchestrates cross-listing price comparison across enabled products."""

    def __init__(
        self,
        product_store: ProductStore,
        monitor: Monitor,
        rule_engine: RuleEngine,
        notifier: Notifier,
        price_history_store: PriceHistoryStore | None = None,
    ) -> None:
        """Initialize the service with its collaborators.

        Args:
            product_store: Source of enabled products and their listings.
            monitor: Fetches and parses a single listing.
            rule_engine: Decides whether a notification should fire.
            notifier: Delivers notification payloads.
            price_history_store: Optional sink/source for listing price history.
        """
        self.product_store = product_store
        self.monitor = monitor
        self.rule_engine = rule_engine
        self.notifier = notifier
        self.price_history_store = price_history_store

    def run(self) -> None:
        """Run one comparison pass over all enabled products."""
        logger.info("Starting comparison pass")

        try:
            products = self.product_store.list_enabled()
        except Exception:
            logger.exception("Failed to load enabled products")
            return

        logger.info("Loaded %d enabled product(s)", len(products))

        items: list[NotificationItem] = []
        product_failures = 0
        listing_failures = 0

        for product in products:
            try:
                item, failed_listings = self._compare_product(product)
                listing_failures += failed_listings
                if item is not None:
                    items.append(item)
            except Exception:
                product_failures += 1
                logger.exception("Error comparing product %s", product.id)

        if items:
            self.notifier.send(
                NotificationPayload(
                    subject=self._build_subject(items),
                    items=tuple(items),
                )
            )

        logger.info(
            "Comparison pass complete: %d alert(s), %d product failure(s), "
            "%d listing failure(s)",
            len(items),
            product_failures,
            listing_failures,
        )

    def _compare_product(
        self, product: Product
    ) -> tuple[NotificationItem | None, int]:
        """Compare a product's listings and return an alert item and failures.

        Args:
            product: Product whose listings should be compared.

        Returns:
            A tuple of ``(notification_item, failed_listing_count)``. The item
            is ``None`` when no rule matched or no listing produced a price.
        """
        listing_prices: list[ListingPrice] = []
        current_prices: list[Price] = []
        previous_prices: list[Price] = []
        lowest_prices: list[Price] = []
        failed_listings = 0

        for listing in product.listings:
            try:
                result = self.monitor.fetch_listing(listing)
            except Exception:
                failed_listings += 1
                logger.exception("Failed to fetch listing %s", listing.id)
                listing_prices.append(
                    ListingPrice(
                        listing_id=listing.id,
                        site_name=listing.site.name,
                        url=listing.url,
                    )
                )
                continue

            price = result.price
            listing_prices.append(
                ListingPrice(
                    listing_id=listing.id,
                    site_name=listing.site.name,
                    url=listing.url,
                    price=price,
                )
            )

            if price is None:
                continue

            previous = self._get_previous_price(listing.id)
            lowest = self._get_lowest_price(listing.id)

            current_prices.append(price)
            if previous is not None:
                previous_prices.append(previous)
            if lowest is not None:
                lowest_prices.append(lowest)

            self._record_price(product.id, listing.id, price)

        if not current_prices:
            return None, failed_listings

        best_price = min(current_prices, key=lambda price: price.value)
        previous_best = self._min_or_none(previous_prices)
        all_time_low = self._min_or_none(lowest_prices)

        if not self.rule_engine.should_notify(
            product,
            ParsedResult(price=best_price),
            previous_best,
            all_time_low,
        ):
            return None, failed_listings

        return (
            NotificationItem(
                product_id=product.id,
                name=product.name,
                listings=tuple(listing_prices),
                best_price=best_price,
                target_price=product.target_price,
                brand=product.brand,
                category=product.category,
                trigger=self._determine_trigger(
                    product, best_price, previous_best, all_time_low
                ),
            ),
            failed_listings,
        )

    def _get_previous_price(self, listing_id: str) -> Price | None:
        """Return the most recent recorded price for a listing, if available."""
        if self.price_history_store is None:
            return None
        try:
            return self.price_history_store.get_latest(listing_id)
        except Exception:
            logger.exception("Failed to read previous price for listing %s", listing_id)
            return None

    def _get_lowest_price(self, listing_id: str) -> Price | None:
        """Return the lowest recorded price for a listing, if available."""
        if self.price_history_store is None:
            return None
        try:
            return self.price_history_store.get_lowest(listing_id)
        except Exception:
            logger.exception("Failed to read lowest price for listing %s", listing_id)
            return None

    def _record_price(
        self, product_id: str, listing_id: str, price: Price
    ) -> None:
        """Record a listing price observation in history, best-effort."""
        if self.price_history_store is None:
            return
        try:
            self.price_history_store.record(listing_id, price, product_id)
        except Exception:
            logger.exception("Failed to record price for listing %s", listing_id)

    @staticmethod
    def _min_or_none(prices: list[Price]) -> Price | None:
        """Return the lowest price in ``prices``, or ``None`` when empty."""
        return min(prices, key=lambda price: price.value) if prices else None

    @staticmethod
    def _determine_trigger(
        product: Product,
        best_price: Price,
        previous_best: Price | None,
        all_time_low: Price | None,
    ) -> str | None:
        """Classify the alert as a target hit or a new all-time low."""
        target = product.target_price
        if target is not None and best_price.value <= target:
            if previous_best is None or previous_best.value > target:
                return "target"
        if all_time_low is None or best_price.value < all_time_low.value:
            return "new_low"
        return None

    def _build_subject(self, items: list[NotificationItem]) -> str:
        """Build a short subject line for a batch of alerts."""
        if len(items) == 1:
            return f"Price alert: {items[0].name}"
        return f"Price alert: {len(items)} products"
