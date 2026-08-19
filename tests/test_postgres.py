"""Tests for the PostgreSQL/Supabase storage adapters."""

from decimal import Decimal
from pathlib import Path

import pytest

from models.enums import Availability
from models.price import Price
from models.product import Product
from models.site import Site
from storage.base import StorageError
from storage.postgres import (
    PostgresPriceHistoryStore,
    PostgresProductStore,
    ensure_schema,
    product_to_row,
    row_to_price,
    row_to_product,
)


class FakeCursor:
    """Minimal cursor fake for exercising store fetch behaviour."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def fetchone(self) -> dict | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[dict]:
        return list(self._rows)


class FakeConnection:
    """Duck-typed psycopg connection used by the stores."""

    def __init__(self, rows: list[dict] | None = None) -> None:
        self._rows = rows or []
        self.executions: list[tuple[str, dict | None]] = []

    def execute(self, query: str, params: dict | None = None) -> FakeCursor:
        self.executions.append((query, params))
        return FakeCursor(self._rows)


class ExplodingConnection:
    """Connection that raises whenever a query is executed."""

    def execute(self, query: str, params: dict | None = None) -> FakeCursor:
        raise RuntimeError("database unavailable")


def make_product() -> Product:
    """Return a fully-populated product for mapping tests."""
    return Product(
        id="p-001",
        name="Test Product",
        site=Site(
            name="Test Store",
            base_url="https://test-store.example",
            default_headers={"Accept-Language": "en-AU"},
        ),
        url="https://test-store.example/products/001",
        price_selector="",
        brand="TestBrand",
        category="accessories",
        currency="AUD",
        enabled=False,
        target_price=Decimal("99.99"),
        parser_type="embedded_json",
        json_variable="window.__STATE__",
        price_path="product.price.value",
        currency_path="product.price.currency",
        availability=Availability.IN_STOCK,
    )


class TestMapping:
    """Tests for Product/Price <-> database row mapping helpers."""

    def test_product_to_row_maps_all_columns(self) -> None:
        """Product fields map to the database column names."""
        row = product_to_row(make_product())

        assert row == {
            "id": "p-001",
            "name": "Test Product",
            "site_name": "Test Store",
            "site_base_url": "https://test-store.example",
            "site_default_headers": '{"Accept-Language": "en-AU"}',
            "url": "https://test-store.example/products/001",
            "price_selector": None,
            "brand": "TestBrand",
            "category": "accessories",
            "currency": "AUD",
            "enabled": False,
            "target_price": Decimal("99.99"),
            "parser_type": "embedded_json",
            "json_variable": "window.__STATE__",
            "price_path": "product.price.value",
            "currency_path": "product.price.currency",
            "availability": "in_stock",
        }

    def test_empty_price_selector_is_mapped_to_null(self) -> None:
        """An empty CSS selector is stored as NULL for non-CSS parsers."""
        product = make_product()
        product.price_selector = ""

        assert product_to_row(product)["price_selector"] is None

    def test_row_to_product_round_trips_product(self) -> None:
        """A database row reconstructs the original product."""
        row = product_to_row(make_product())

        assert row_to_product(row) == make_product()

    def test_row_to_product_accepts_psycopg_jsonb_dict(self) -> None:
        """A JSONB value already decoded by psycopg is accepted."""
        row = product_to_row(make_product())
        row["site_default_headers"] = {"Accept-Language": "en-AU"}
        row["price_selector"] = None

        product = row_to_product(row)

        assert product.site.default_headers == {"Accept-Language": "en-AU"}
        assert product.price_selector == ""

    def test_row_to_product_handles_nulls(self) -> None:
        """Optional database columns come back as None/empty defaults."""
        row = {
            "id": "p-002",
            "name": "Minimal",
            "site_name": "Minimal Store",
            "site_base_url": None,
            "site_default_headers": None,
            "url": "https://example.com/p/2",
            "price_selector": ".price",
            "brand": None,
            "category": None,
            "currency": "AUD",
            "enabled": True,
            "target_price": None,
            "parser_type": "css",
            "json_variable": None,
            "price_path": None,
            "currency_path": None,
            "availability": None,
        }

        product = row_to_product(row)

        assert product.site.name == "Minimal Store"
        assert product.site.base_url is None
        assert product.site.default_headers is None
        assert product.brand is None
        assert product.target_price is None
        assert product.availability is None

    def test_row_to_price_maps_price_columns(self) -> None:
        """A price history row maps to a Price value object."""
        row = {
            "value": Decimal("49.95"),
            "currency": "AUD",
            "raw_text": "$49.95",
        }

        price = row_to_price(row)

        assert price == Price(
            value=Decimal("49.95"),
            currency="AUD",
            raw_text="$49.95",
        )


class TestEnsureSchema:
    """Tests for idempotent schema creation."""

    def test_executes_schema_file_as_single_source_of_truth(self) -> None:
        """ensure_schema runs scripts/schema.sql verbatim."""
        connection = FakeConnection()
        schema_path = Path(__file__).resolve().parents[1] / "scripts" / "schema.sql"
        expected = schema_path.read_text(encoding="utf-8")

        ensure_schema(connection)

        assert connection.executions == [(expected, None)]


class TestPostgresProductStore:
    """Tests for the product catalog store adapter."""

    def test_get_returns_product(self) -> None:
        """get maps a found row back to a Product."""
        row = product_to_row(make_product())
        connection = FakeConnection([row])
        store = PostgresProductStore(connection)

        product = store.get("p-001")

        assert product == make_product()
        query, params = connection.executions[0]
        assert "products" in query
        assert params == {"product_id": "p-001"}

    def test_get_returns_none_when_missing(self) -> None:
        """get returns None when the product does not exist."""
        store = PostgresProductStore(FakeConnection([]))

        assert store.get("missing") is None

    def test_list_all_returns_products(self) -> None:
        """list_all returns every stored product."""
        first = product_to_row(make_product())
        second = dict(first)
        second["id"] = "p-002"
        second["name"] = "Second"
        store = PostgresProductStore(FakeConnection([first, second]))

        products = store.list_all()

        assert [product.id for product in products] == ["p-001", "p-002"]

    def test_list_enabled_filters_enabled_products(self) -> None:
        """list_enabled delegates the enabled filter to SQL."""
        connection = FakeConnection([product_to_row(make_product())])
        store = PostgresProductStore(connection)

        store.list_enabled()

        query, _ = connection.executions[0]
        assert "enabled = TRUE" in query

    def test_save_executes_upsert(self) -> None:
        """save writes a mapped row using an idempotent upsert."""
        connection = FakeConnection()
        store = PostgresProductStore(connection)

        store.save(make_product())

        query, params = connection.executions[0]
        assert "ON CONFLICT (id) DO UPDATE" in query
        assert params["id"] == "p-001"
        assert params["site_default_headers"] == '{"Accept-Language": "en-AU"}'

    def test_delete_removes_product(self) -> None:
        """delete issues a delete for the given product id."""
        connection = FakeConnection()
        store = PostgresProductStore(connection)

        store.delete("p-001")

        query, params = connection.executions[0]
        assert "DELETE FROM products" in query
        assert params == {"product_id": "p-001"}

    @pytest.mark.parametrize("method_name, args", [
        ("get", ("p-001",)),
        ("list_all", ()),
        ("list_enabled", ()),
        ("save", (make_product(),)),
        ("delete", ("p-001",)),
    ])
    def test_store_methods_wrap_failures(self, method_name, args) -> None:
        """Store failures are surfaced as StorageError."""
        store = PostgresProductStore(ExplodingConnection())

        with pytest.raises(StorageError):
            getattr(store, method_name)(*args)


class TestPostgresPriceHistoryStore:
    """Tests for the price history store adapter."""

    def _row(self, value: str = "49.95") -> dict:
        return {
            "value": Decimal(value),
            "currency": "AUD",
            "raw_text": "$49.95",
        }

    def test_record_inserts_price(self) -> None:
        """record writes a price observation for a product."""
        connection = FakeConnection()
        store = PostgresPriceHistoryStore(connection)
        price = Price(value=Decimal("49.95"), currency="AUD", raw_text="$49.95")

        store.record("p-001", price)

        query, params = connection.executions[0]
        assert "INSERT INTO price_history" in query
        assert params == {
            "product_id": "p-001",
            "value": Decimal("49.95"),
            "currency": "AUD",
            "raw_text": "$49.95",
        }

    def test_get_latest_returns_price(self) -> None:
        """get_latest returns the most recent price observation."""
        store = PostgresPriceHistoryStore(FakeConnection([self._row()]))

        price = store.get_latest("p-001")

        assert price == Price(
            value=Decimal("49.95"),
            currency="AUD",
            raw_text="$49.95",
        )

    def test_get_latest_returns_none_when_empty(self) -> None:
        """get_latest returns None when there is no history."""
        store = PostgresPriceHistoryStore(FakeConnection([]))

        assert store.get_latest("p-001") is None

    def test_get_history_returns_prices(self) -> None:
        """get_history maps all returned rows to prices."""
        rows = [self._row("49.95"), self._row("59.95")]
        store = PostgresPriceHistoryStore(FakeConnection(rows))

        prices = store.get_history("p-001")

        assert [price.value for price in prices] == [
            Decimal("49.95"),
            Decimal("59.95"),
        ]

    def test_get_lowest_returns_lowest_price(self) -> None:
        """get_lowest maps the lowest-value row to a price."""
        store = PostgresPriceHistoryStore(FakeConnection([self._row("39.95")]))

        price = store.get_lowest("p-001")

        assert price.value == Decimal("39.95")

    @pytest.mark.parametrize("method_name, args", [
        ("record", ("p-001", Price(value=Decimal("1"), currency="AUD"))),
        ("get_latest", ("p-001",)),
        ("get_history", ("p-001",)),
        ("get_lowest", ("p-001",)),
    ])
    def test_history_methods_wrap_failures(self, method_name, args) -> None:
        """History store failures are surfaced as StorageError."""
        store = PostgresPriceHistoryStore(ExplodingConnection())

        with pytest.raises(StorageError):
            getattr(store, method_name)(*args)
