"""Seed the Supabase product catalog from ``data/products.py``.

This is a one-time, idempotent operation. Running it repeatedly is safe
because each product is written with an upsert.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import get_settings
from data.products import PRODUCTS
from storage.postgres import PostgresProductStore, ensure_schema


def main() -> None:
    """Connect to Supabase and upsert every seed product."""
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
        store = PostgresProductStore(connection)
        for product in PRODUCTS:
            store.save(product)

    print(f"Seeded {len(PRODUCTS)} product(s)")


if __name__ == "__main__":
    main()
