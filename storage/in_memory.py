"""In-memory product store backed by a list of products.

This adapter satisfies the ``ProductStore`` contract for the Phase 1 MVP
until a persistent storage implementation is added.
"""

from models.product import Product
from storage.base import ProductStore


class InMemoryProductStore(ProductStore):
    """Product store that keeps products in memory."""

    def __init__(self, products: list[Product]) -> None:
        """Initialize the store with a product catalog.

        Args:
            products: Products to hold in memory.
        """
        self._products = products

    def get(self, product_id: str) -> Product | None:
        """Return the product with the given id, if present."""
        for product in self._products:
            if product.id == product_id:
                return product
        return None

    def list_all(self) -> list[Product]:
        """Return all products."""
        return list(self._products)

    def list_enabled(self) -> list[Product]:
        """Return products whose ``enabled`` flag is ``True``."""
        return [product for product in self._products if product.enabled]

    def save(self, product: Product) -> None:
        """Not supported by the in-memory store."""
        raise NotImplementedError("In-memory store does not support writes")

    def delete(self, product_id: str) -> None:
        """Not supported by the in-memory store."""
        raise NotImplementedError("In-memory store does not support writes")
