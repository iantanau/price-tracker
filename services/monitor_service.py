"""Monitor service that orchestrates the price-checking workflow.

The service loads enabled products, fetches their current state, asks the
rule engine whether a notification is warranted, and delegates delivery to
a notifier. It contains no business rules itself.
"""

from models.notification_payload import NotificationPayload
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

        notified = 0
        failed = 0

        for product in products:
            try:
                if self._check_product(product):
                    notified += 1
            except Exception:
                failed += 1
                logger.exception("Error monitoring product %s", product.id)

        logger.info(
            "Monitoring pass complete: %d notification(s), %d failure(s)",
            notified,
            failed,
        )

    def _check_product(self, product: Product) -> bool:
        """Check a single product and send a notification if rules match.

        Args:
            product: Product to check.

        Returns:
            ``True`` if a notification was sent, otherwise ``False``.
        """
        logger.info("Fetching product %s - %s", product.id, product.name)

        result = self.monitor.fetch(product)
        self._record_price(product, result)

        if not self.rule_engine.should_notify(product, result):
            logger.info("No notification needed for product %s", product.id)
            return False

        payload = self._build_payload(product, result)
        self.notifier.send(payload)

        logger.info("Notification sent for product %s", product.id)
        return True

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

    def _build_payload(self, product: Product, result) -> NotificationPayload:
        """Build a notification payload for a product that matched a rule.

        Args:
            product: Product that triggered the notification.
            result: Parsed observation for the product.

        Returns:
            A populated notification payload.
        """
        price = result.price
        price_text = (
            f"{price.value} {price.currency}" if price else "unknown price"
        )

        subject = f"Price alert: {product.name}"
        body = (
            f"The price for {product.name} is now {price_text}.\n"
            f"Product URL: {product.url}"
        )

        if product.target_price is not None:
            body += f"\nTarget price: {product.target_price}"

        return NotificationPayload(subject=subject, body=body)
