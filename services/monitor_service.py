"""Monitor service that orchestrates the price-checking workflow.

The service loads enabled products, fetches their current state, asks the
rule engine whether a notification is warranted, and delegates delivery to
a notifier. It contains no business rules itself.
"""

from models.notification_payload import NotificationItem, NotificationPayload
from models.parsed_result import ParsedResult
from models.product import Product
from monitors.base import Monitor
from notifiers.base import Notifier
from services.rule_engine import RuleEngine
from storage.base import PriceHistoryStore, ProductStore
from utils.logging import get_logger

logger = get_logger("services.monitor_service")


class MonitorService:
    """Orchestrates price monitoring across all enabled products."""

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
            product_store: Source of enabled products.
            monitor: Fetches and parses product state.
            rule_engine: Decides whether a notification should fire.
            notifier: Delivers notification payloads.
            price_history_store: Optional sink for observed price history.
        """
        self.product_store = product_store
        self.monitor = monitor
        self.rule_engine = rule_engine
        self.notifier = notifier
        self.price_history_store = price_history_store

    def run(self) -> None:
        """Run one monitoring pass over all enabled products.

        Errors are caught per product so that one failure does not abort the
        rest of the pass.
        """
        logger.info("Starting monitoring pass")

        try:
            products = self.product_store.list_enabled()
        except Exception:
            logger.exception("Failed to load enabled products")
            return

        logger.info("Loaded %d enabled product(s)", len(products))

        items: list[NotificationItem] = []
        failed = 0

        for product in products:
            try:
                item = self._check_product(product)
                if item is not None:
                    items.append(item)
            except Exception:
                failed += 1
                logger.exception("Error monitoring product %s", product.id)

        if items:
            self.notifier.send(
                NotificationPayload(
                    subject=self._build_subject(items),
                    items=tuple(items),
                )
            )

        logger.info(
            "Monitoring pass complete: %d notification(s), %d failure(s)",
            len(items),
            failed,
        )

    def _check_product(self, product: Product) -> NotificationItem | None:
        """Check a single product and return an alert item if rules match.

        Args:
            product: Product to check.

        Returns:
            A ``NotificationItem`` when a notification should fire, otherwise
            ``None``.
        """
        logger.info("Fetching product %s - %s", product.id, product.name)

        result = self.monitor.fetch(product)
        self._record_price(product, result)

        if not self.rule_engine.should_notify(product, result):
            logger.info("No notification needed for product %s", product.id)
            return None

        logger.info("Notification queued for product %s", product.id)
        return self._build_item(product, result)

    def _record_price(self, product: Product, result: ParsedResult) -> None:
        """Record an observed price in history when one is available.

        History recording is best-effort: a storage failure must not prevent
        the notification flow from continuing.

        Args:
            product: Product whose price was observed.
            result: Parsed observation for the product.
        """
        if self.price_history_store is None or result.price is None:
            return

        try:
            self.price_history_store.record(product.id, result.price)
        except Exception:
            logger.exception("Failed to record price for product %s", product.id)

    def _build_item(self, product: Product, result) -> NotificationItem:
        """Build a structured alert item for a matched product.

        Args:
            product: Product that triggered the notification.
            result: Parsed observation for the product.

        Returns:
            A populated notification item.
        """
        return NotificationItem(
            product_id=product.id,
            name=product.name,
            url=product.url,
            price=result.price,
            target_price=product.target_price,
            brand=product.brand,
            category=product.category,
        )

    def _build_subject(self, items: list[NotificationItem]) -> str:
        """Build a short subject line for a batch of alerts.

        Args:
            items: Alert items that will be sent in this notification.

        Returns:
            A subject summarising the batch.
        """
        if len(items) == 1:
            return f"Price alert: {items[0].name}"
        return f"Price alert: {len(items)} products"
