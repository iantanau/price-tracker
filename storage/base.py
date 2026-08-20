"""Storage abstraction layer.

Stores hide persistence details (JSON files, SQLite, Redis, etc.) from the
rest of the application. Consumers interact only with these abstract
interfaces.
"""

from abc import ABC, abstractmethod

from models.price import Price
from models.product import Product


class ProductStore(ABC):
    """Abstract store for product catalog operations."""

    @abstractmethod
    def get(self, product_id: str) -> Product | None:
        """Fetch a product by its unique identifier.

        Args:
            product_id: Stable unique identifier for the product.

        Returns:
            The matching product, or ``None`` if not found.

        Raises:
            StorageError: If the lookup fails.
        """
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[Product]:
        """Return all known products.

        Returns:
            A list of every product in the store.

        Raises:
            StorageError: If the read fails.
        """
        raise NotImplementedError

    @abstractmethod
    def list_enabled(self) -> list[Product]:
        """Return products that should be monitored.

        Returns:
            A list of products whose ``enabled`` flag is ``True``.

        Raises:
            StorageError: If the read fails.
        """
        raise NotImplementedError

    @abstractmethod
    def save(self, product: Product) -> None:
        """Persist a product, creating or updating as needed.

        Args:
            product: Product to persist.

        Raises:
            StorageError: If the write fails.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, product_id: str) -> None:
        """Remove a product from the store.

        Args:
            product_id: Unique identifier of the product to remove.

        Raises:
            StorageError: If the deletion fails.
        """
        raise NotImplementedError


class PriceHistoryStore(ABC):
    """Abstract store for historical price records."""

    @abstractmethod
    def record(self, listing_id: str, price: Price) -> None:
        """Store a price observation for a listing.

        Args:
            listing_id: Listing the price belongs to.
            price: Normalised price value observed.

        Raises:
            StorageError: If the write fails.
        """
        raise NotImplementedError

    @abstractmethod
    def get_latest(self, listing_id: str) -> Price | None:
        """Return the most recent recorded price for a listing, if any.

        Args:
            listing_id: Listing to look up.

        Returns:
            The latest price observation, or ``None`` if no history exists.

        Raises:
            StorageError: If the lookup fails.
        """
        raise NotImplementedError

    @abstractmethod
    def get_history(self, listing_id: str) -> list[Price]:
        """Return all recorded prices for a listing, newest first.

        Args:
            listing_id: Listing to look up.

        Returns:
            A list of recorded prices ordered from most to least recent.

        Raises:
            StorageError: If the lookup fails.
        """
        raise NotImplementedError

    @abstractmethod
    def get_lowest(self, listing_id: str) -> Price | None:
        """Return the lowest recorded price for a listing, if any.

        Args:
            listing_id: Listing to look up.

        Returns:
            The lowest price observation, or ``None`` if no history exists.

        Raises:
            StorageError: If the lookup fails.
        """
        raise NotImplementedError


class CacheStore(ABC):
    """Abstract cache for transient data."""

    @abstractmethod
    def get(self, key: str) -> str | None:
        """Return the cached value for ``key``, or ``None`` if missing/expired.

        Args:
            key: Cache entry key.

        Returns:
            The cached value, or ``None`` if not found or expired.

        Raises:
            StorageError: If the lookup fails.
        """
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """Cache ``value`` under ``key`` with an optional time-to-live.

        Args:
            key: Cache entry key.
            value: Value to cache.
            ttl_seconds: Optional expiry time in seconds.

        Raises:
            StorageError: If the write fails.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove a key from the cache.

        Args:
            key: Cache entry key to remove.

        Raises:
            StorageError: If the deletion fails.
        """
        raise NotImplementedError


class StorageError(Exception):
    """Raised when a store operation fails."""

    pass
