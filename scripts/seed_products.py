"""Reconcile the Supabase product catalog with ``data/products.py``.

The seed catalog is the source of truth: products present there are upserted,
and products absent from it are removed together with their price history.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import get_settings
from data.products import PRODUCTS
from services.catalog_sync import sync_catalog
from storage.postgres import (
    PostgresPriceHistoryStore,
    PostgresProductStore,
    ensure_schema,
)


def main() -> None:
    """Connect to Supabase and reconcile the catalog with the seed list."""
    settings = get_settings()
    if not settings.supabase_database_url:
        raise SystemExit("SUPABASE_DATABASE_URL is not set; nothing to seed")

    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(
        settings.supabase_database_url,
        autocommit=True,
        prepare_threshold=None,
        row_factory=dict_row,
    ) as connection:
        ensure_schema(connection)
        product_store = PostgresProductStore(connection)
        price_history_store = PostgresPriceHistoryStore(connection)
        sync_catalog(PRODUCTS, product_store, price_history_store)

    print(f"Synced {len(PRODUCTS)} product(s)")


if __name__ == "__main__":
    main()
