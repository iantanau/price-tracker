"""Synchronize the persisted product catalog with a source-of-truth list."""

from models.product import Product
from storage.base import PriceHistoryStore, ProductStore
from utils.logging import get_logger


logger = get_logger("services.catalog_sync")


def sync_catalog(
    desired_products: list[Product],
    product_store: ProductStore,
    price_history_store: PriceHistoryStore | None = None,
) -> None:
    """Reconcile the store with ``desired_products``.

    ``desired_products`` is the authoritative catalog: every entry is upserted,
    and any stored product missing from that list is removed together with its
    listing price history.
    """
    desired_ids = {product.id for product in desired_products}

    for product in desired_products:
        product_store.save(product)

    for existing in product_store.list_all():
        if existing.id in desired_ids:
            continue

        if price_history_store is not None:
            for listing in existing.listings:
                try:
                    price_history_store.delete_history(listing.id)
                except Exception:
                    logger.exception(
                        "Failed to delete price history for listing %s",
                        listing.id,
                    )

        product_store.delete(existing.id)
