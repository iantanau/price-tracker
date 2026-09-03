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
from parsers.auto_discovery_price_parser import AutoDiscoveryPriceParser
from parsers.css_price_parser import CssPriceParser
from parsers.dispatching_product_parser import DispatchingProductParser
from parsers.embedded_json_price_parser import EmbeddedJsonPriceParser
from parsers.json_ld_price_parser import JsonLdPriceParser
from services.catalog_sync import sync_catalog
from services.comparison_service import ComparisonService
from services.rule_engine import RuleEngine, TargetPriceRule
from storage.in_memory import InMemoryProductStore
from storage.postgres import (
    PostgresPriceHistoryStore,
    PostgresProductStore,
    ensure_schema,
)
from utils.logging import configure_logging


def main() -> None:
    """Wire dependencies and run the monitor service."""
    settings = get_settings()
    configure_logging(settings.log_level)

    connection = None
    http_client = None
    try:
        if settings.supabase_database_url:
            import psycopg
            from psycopg.rows import dict_row

            connection = psycopg.connect(
                settings.supabase_database_url,
                autocommit=True,
                prepare_threshold=None,
                row_factory=dict_row,
            )
            ensure_schema(connection)
            product_store = PostgresProductStore(connection)
            price_history_store = PostgresPriceHistoryStore(connection)
            sync_catalog(PRODUCTS, product_store, price_history_store)
        else:
            product_store = InMemoryProductStore(PRODUCTS)
            price_history_store = None

        http_client = HttpxClient(settings)
        parser = DispatchingProductParser(
            parsers={
                "css": CssPriceParser(),
                "embedded_json": EmbeddedJsonPriceParser(),
                "json_ld": JsonLdPriceParser(),
                "auto": AutoDiscoveryPriceParser(),
            }
        )
        monitor = WebMonitor(client=http_client, parser=parser)

        rule_engine = RuleEngine(rules=[TargetPriceRule()])
        notifier = EmailNotifier(settings)

        service = ComparisonService(
            product_store=product_store,
            monitor=monitor,
            rule_engine=rule_engine,
            notifier=notifier,
            price_history_store=price_history_store,
        )

        service.run()
    finally:
        if http_client is not None:
            http_client.close()
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    main()
