"""Application entry point.

Composes all dependencies and runs one pass of the monitoring service.
No business logic lives here; this file only wires concrete
implementations to their abstract collaborators.
"""

from clients.http_client import HttpxClient
from config.settings import get_settings
from data.products import PRODUCTS
from monitors.web_monitor import WebMonitor
from notifiers.email_notifier import EmailNotifier
from parsers.css_price_parser import CssPriceParser
from parsers.dispatching_product_parser import DispatchingProductParser
from parsers.embedded_json_price_parser import EmbeddedJsonPriceParser
from services.monitor_service import MonitorService
from services.rule_engine import RuleEngine, TargetPriceRule
from storage.in_memory import InMemoryProductStore
from utils.logging import configure_logging


def main() -> None:
    """Wire dependencies and run the monitor service."""
    settings = get_settings()
    configure_logging(settings.log_level)

    product_store = InMemoryProductStore(PRODUCTS)

    http_client = HttpxClient(settings)
    parser = DispatchingProductParser(
        parsers={
            "css": CssPriceParser(),
            "embedded_json": EmbeddedJsonPriceParser(),
        }
    )
    monitor = WebMonitor(client=http_client, parser=parser)

    rule_engine = RuleEngine(rules=[TargetPriceRule()])
    notifier = EmailNotifier(settings)

    service = MonitorService(
        product_store=product_store,
        monitor=monitor,
        rule_engine=rule_engine,
        notifier=notifier,
    )

    try:
        service.run()
    finally:
        http_client.close()


if __name__ == "__main__":
    main()
