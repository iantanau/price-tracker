"""Tests for catalog synchronization."""

from decimal import Decimal

from models.listing import ProductListing
from models.price import Price
from models.product import Product
from models.site import Site
from services.catalog_sync import sync_catalog


class FakeProductStore:
    """Records product store calls and returns the supplied catalog."""

    def __init__(self, products: list[Product]) -> None:
        self._products = products
        self.saved: list[Product] = []
        self.deleted: list[str] = []

    def list_all(self) -> list[Product]:
        return list(self._products)

    def save(self, product: Product) -> None:
        self.saved.append(product)

    def delete(self, product_id: str) -> None:
        self.deleted.append(product_id)


class FakePriceHistoryStore:
    """Records price-history deletions."""

    def __init__(self) -> None:
        self.deleted_listings: list[str] = []

    def delete_history(self, listing_id: str) -> None:
        self.deleted_listings.append(listing_id)


def listing(listing_id: str) -> ProductListing:
    return ProductListing(
        id=listing_id,
        site=Site(name="Test Store"),
        url=f"https://example.com/{listing_id}",
    )


def product(product_id: str, *listing_ids: str) -> Product:
    return Product(
        id=product_id,
        name=product_id,
        listings=[listing(listing_id) for listing_id in listing_ids],
    )


def test_sync_upserts_desired_products() -> None:
    """Desired products are saved even if they already exist."""
    desired = [product("p-001", "l-001")]
    store = FakeProductStore([product("p-001", "l-001")])

    sync_catalog(desired, store)

    assert [p.id for p in store.saved] == ["p-001"]
    assert store.deleted == []


def test_sync_deletes_removed_products_and_history() -> None:
    """Products absent from the desired list are removed with their history."""
    desired = [product("p-001", "l-001")]
    store = FakeProductStore([
        product("p-001", "l-001"),
        product("p-002", "l-002", "l-003"),
    ])
    history = FakePriceHistoryStore()

    sync_catalog(desired, store, history)

    assert store.deleted == ["p-002"]
    assert sorted(history.deleted_listings) == ["l-002", "l-003"]


def test_sync_without_history_store_still_deletes_products() -> None:
    """Sync works when price history is unavailable."""
    desired = [product("p-001", "l-001")]
    store = FakeProductStore([product("p-002", "l-002")])

    sync_catalog(desired, store)

    assert store.deleted == ["p-002"]


def test_sync_keeps_product_when_it_is_in_desired_list() -> None:
    """A product present in both lists is left alone."""
    desired = [product("p-001", "l-001")]
    store = FakeProductStore([product("p-001", "l-001"), product("p-002", "l-002")])
    history = FakePriceHistoryStore()

    sync_catalog(desired, store, history)

    assert store.deleted == ["p-002"]
    assert history.deleted_listings == ["l-002"]
