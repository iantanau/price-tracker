"""PostgreSQL/Supabase storage adapters.

This module implements the existing ``ProductStore`` and ``PriceHistoryStore``
interfaces against a Supabase-hosted PostgreSQL database. The adapters are
driver-agnostic: they receive a connection object produced by the composition
root and never construct one themselves.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from models.enums import Availability
from models.listing import ProductListing
from models.price import Price
from models.product import Product
from models.site import Site
from storage.base import PriceHistoryStore, ProductStore, StorageError


DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "scripts" / "schema.sql"


_SELECT_PRODUCT_BY_ID = """
SELECT id, name, brand, category, currency, enabled, target_price,
       availability, listings
FROM products
WHERE id = %(product_id)s
"""

_SELECT_PRODUCTS = """
SELECT id, name, brand, category, currency, enabled, target_price,
       availability, listings
FROM products
"""

_SELECT_ENABLED_PRODUCTS = _SELECT_PRODUCTS + "\nWHERE enabled = TRUE"

_UPSERT_PRODUCT = """
INSERT INTO products (
    id, name, brand, category, currency, enabled, target_price,
    availability, listings
) VALUES (
    %(id)s, %(name)s, %(brand)s, %(category)s, %(currency)s, %(enabled)s, %(target_price)s,
    %(availability)s, %(listings)s::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    brand = EXCLUDED.brand,
    category = EXCLUDED.category,
    currency = EXCLUDED.currency,
    enabled = EXCLUDED.enabled,
    target_price = EXCLUDED.target_price,
    availability = EXCLUDED.availability,
    listings = EXCLUDED.listings,
    updated_at = now()
"""

_DELETE_PRODUCT = "DELETE FROM products WHERE id = %(product_id)s"

_INSERT_PRICE_HISTORY = """
INSERT INTO price_history (listing_id, value, currency, raw_text)
VALUES (%(listing_id)s, %(value)s, %(currency)s, %(raw_text)s)
"""

_SELECT_LATEST_PRICE = """
SELECT value, currency, raw_text
FROM price_history
WHERE listing_id = %(listing_id)s
ORDER BY observed_at DESC, id DESC
LIMIT 1
"""

_SELECT_PRICE_HISTORY = """
SELECT value, currency, raw_text
FROM price_history
WHERE listing_id = %(listing_id)s
ORDER BY observed_at DESC, id DESC
"""

_SELECT_LOWEST_PRICE = """
SELECT value, currency, raw_text
FROM price_history
WHERE listing_id = %(listing_id)s
ORDER BY value ASC, id ASC
LIMIT 1
"""


def _decimal(value: object) -> Decimal:
    """Coerce a database numeric value to ``Decimal``."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _availability_to_db(value: Availability | None) -> str | None:
    """Map an Availability enum to its database text value."""
    return value.value if value is not None else None


def _availability_from_db(value: str | None) -> Availability | None:
    """Map database text back to an Availability enum, if valid."""
    if value is None:
        return None
    try:
        return Availability(value)
    except ValueError:
        return None


def _listing_to_dict(listing: ProductListing) -> dict[str, Any]:
    """Convert a ``ProductListing`` to a JSON-serialisable dictionary."""
    return {
        "id": listing.id,
        "site_name": listing.site.name,
        "site_base_url": listing.site.base_url,
        "site_default_headers": listing.site.default_headers,
        "url": listing.url,
        "price_selector": listing.price_selector,
        "parser_type": listing.parser_type,
        "json_variable": listing.json_variable,
        "price_path": listing.price_path,
        "currency_path": listing.currency_path,
        "currency": listing.currency,
    }


def _serialize_listings(listings: list[ProductListing]) -> str:
    """Serialize product listings to JSON text for the JSONB column."""
    return json.dumps([_listing_to_dict(listing) for listing in listings])


def _deserialize_listings(value: Any) -> list[ProductListing]:
    """Deserialize a JSONB listings column to ``ProductListing`` objects."""
    if value is None:
        return []
    if isinstance(value, str):
        value = json.loads(value)

    listings: list[ProductListing] = []
    for item in value:
        listings.append(
            ProductListing(
                id=item["id"],
                site=Site(
                    name=item["site_name"],
                    base_url=item.get("site_base_url"),
                    default_headers=item.get("site_default_headers"),
                ),
                url=item["url"],
                price_selector=item.get("price_selector", ""),
                parser_type=item.get("parser_type", "auto"),
                json_variable=item.get("json_variable"),
                price_path=item.get("price_path"),
                currency_path=item.get("currency_path"),
                currency=item.get("currency", "AUD"),
            )
        )
    return listings


def product_to_row(product: Product) -> dict[str, Any]:
    """Convert a domain ``Product`` to database column values."""
    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "currency": product.currency,
        "enabled": product.enabled,
        "target_price": product.target_price,
        "availability": _availability_to_db(product.availability),
        "listings": _serialize_listings(product.listings),
    }


def row_to_product(row: dict[str, Any]) -> Product:
    """Convert a database row to a domain ``Product``."""
    return Product(
        id=row["id"],
        name=row["name"],
        listings=_deserialize_listings(row.get("listings")),
        brand=row.get("brand"),
        category=row.get("category"),
        currency=row.get("currency") or "AUD",
        enabled=bool(row.get("enabled", True)),
        target_price=(
            _decimal(row["target_price"])
            if row.get("target_price") is not None
            else None
        ),
        availability=_availability_from_db(row.get("availability")),
    )


def row_to_price(row: dict[str, Any]) -> Price:
    """Convert a price history row to a domain ``Price``."""
    return Price(
        value=_decimal(row["value"]),
        currency=row["currency"],
        raw_text=row.get("raw_text"),
    )


def ensure_schema(connection, schema_path: Path | None = None) -> None:
    """Create the required tables and indexes idempotently.

    ``scripts/schema.sql`` is the single source of truth for schema changes.
    The optional ``schema_path`` argument exists for testing.
    """
    path = schema_path or DEFAULT_SCHEMA_PATH
    sql = path.read_text(encoding="utf-8")
    connection.execute(sql)


class PostgresProductStore(ProductStore):
    """Product catalog store backed by a PostgreSQL/Supabase database."""

    def __init__(self, connection) -> None:
        """Initialize the store with a psycopg connection."""
        self._connection = connection

    def get(self, product_id: str) -> Product | None:
        """Fetch a product by id, or ``None`` if it is not found."""
        try:
            row = self._connection.execute(
                _SELECT_PRODUCT_BY_ID, {"product_id": product_id}
            ).fetchone()
        except Exception as exc:
            raise StorageError(f"Failed to get product {product_id}") from exc
        return row_to_product(row) if row else None

    def list_all(self) -> list[Product]:
        """Return every product in the catalog."""
        try:
            rows = self._connection.execute(_SELECT_PRODUCTS).fetchall()
        except Exception as exc:
            raise StorageError("Failed to list products") from exc
        return [row_to_product(row) for row in rows]

    def list_enabled(self) -> list[Product]:
        """Return products whose ``enabled`` flag is true."""
        try:
            rows = self._connection.execute(_SELECT_ENABLED_PRODUCTS).fetchall()
        except Exception as exc:
            raise StorageError("Failed to list enabled products") from exc
        return [row_to_product(row) for row in rows]

    def save(self, product: Product) -> None:
        """Persist a product using an idempotent upsert."""
        try:
            self._connection.execute(_UPSERT_PRODUCT, product_to_row(product))
        except Exception as exc:
            raise StorageError(f"Failed to save product {product.id}") from exc

    def delete(self, product_id: str) -> None:
        """Remove a product from the catalog."""
        try:
            self._connection.execute(_DELETE_PRODUCT, {"product_id": product_id})
        except Exception as exc:
            raise StorageError(f"Failed to delete product {product_id}") from exc


class PostgresPriceHistoryStore(PriceHistoryStore):
    """Price history store backed by a PostgreSQL/Supabase database."""

    def __init__(self, connection) -> None:
        """Initialize the store with a psycopg connection."""
        self._connection = connection

    def record(self, listing_id: str, price: Price) -> None:
        """Store a price observation for a listing."""
        try:
            self._connection.execute(
                _INSERT_PRICE_HISTORY,
                {
                    "listing_id": listing_id,
                    "value": price.value,
                    "currency": price.currency,
                    "raw_text": price.raw_text,
                },
            )
        except Exception as exc:
            raise StorageError(
                f"Failed to record price for listing {listing_id}"
            ) from exc

    def get_latest(self, listing_id: str) -> Price | None:
        """Return the most recent price observation, if any."""
        try:
            row = self._connection.execute(
                _SELECT_LATEST_PRICE, {"listing_id": listing_id}
            ).fetchone()
        except Exception as exc:
            raise StorageError(
                f"Failed to get latest price for listing {listing_id}"
            ) from exc
        return row_to_price(row) if row else None

    def get_history(self, listing_id: str) -> list[Price]:
        """Return all recorded prices for a listing, newest first."""
        try:
            rows = self._connection.execute(
                _SELECT_PRICE_HISTORY, {"listing_id": listing_id}
            ).fetchall()
        except Exception as exc:
            raise StorageError(
                f"Failed to get price history for listing {listing_id}"
            ) from exc
        return [row_to_price(row) for row in rows]

    def get_lowest(self, listing_id: str) -> Price | None:
        """Return the lowest recorded price for a listing, if any."""
        try:
            row = self._connection.execute(
                _SELECT_LOWEST_PRICE, {"listing_id": listing_id}
            ).fetchone()
        except Exception as exc:
            raise StorageError(
                f"Failed to get lowest price for listing {listing_id}"
            ) from exc
        return row_to_price(row) if row else None
