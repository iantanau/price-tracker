"""Shared pytest fixtures for the price tracker test suite."""

from decimal import Decimal
from pathlib import Path

import pytest

from models.listing import ProductListing
from models.product import Product
from models.site import Site


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def css_html() -> str:
    """Static HTML page used by CSS parser tests."""
    return (FIXTURES_DIR / "css_price_page.html").read_text(encoding="utf-8")


@pytest.fixture
def embedded_json_html() -> str:
    """Static HTML page with embedded JSON used by embedded JSON parser tests."""
    return (FIXTURES_DIR / "embedded_json_page.html").read_text(encoding="utf-8")


@pytest.fixture
def base_listing() -> ProductListing:
    """A minimally configured listing for parser tests."""
    return ProductListing(
        id="test-listing-001",
        site=Site(name="Test Store"),
        url="https://test-store.example/products/001",
        price_selector=".product-price",
        currency="AUD",
    )


@pytest.fixture
def base_product(base_listing: ProductListing) -> Product:
    """A minimally configured product wrapping one listing."""
    return Product(
        id="test-product-001",
        name="Test Product",
        listings=[base_listing],
        currency="AUD",
    )
