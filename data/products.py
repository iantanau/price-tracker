"""Seed product catalog for Phase 1.

This module contains the initial set of products to monitor. Replace the
example entries below with real products, URLs, and CSS selectors before
running the monitor in production.
"""

from decimal import Decimal

from models.product import Product
from models.site import Site


# Example placeholder products. Copy and adjust these entries for the actual
# products you want to track.
PRODUCTS: list[Product] = [
    Product(
        id="uniqlo-heattech-ultra-warm-t-shirt",
        name="Uniqlo HEATTECH ULTRA WARM Crew Neck Long Sleeve T-Shirt",
        site=Site(name="Uniqlo"),
        url="https://www.uniqlo.com/au/en/products/E479525-000/00?colorDisplayCode=08&sizeDisplayCode=004",
        price_selector="",  # not used by embedded_json parser
        brand="Uniqlo",
        category="Clothes",
        currency="AUD",
        enabled=True,
        target_price=Decimal("39.99"),
        parser_type="embedded_json",
        json_variable="window.__PRELOADED_STATE__",
        price_path="entity.pdpEntity.E479525-000-00.product.prices.promo.value",
        currency_path="entity.pdpEntity.E479525-000-00.product.prices.promo.currency.code",
    ),
    # Product(
    #     id="example-monitor-1",
    #     name="Example 27 inch Monitor",
    #     site=Site(name="Example Retailer"),
    #     url="https://example.com/products/example-27-monitor",
    #     price_selector="span.product-price",
    #     brand="ExampleBrand",
    #     category="monitors",
    #     currency="AUD",
    #     enabled=True,
    #     target_price=Decimal("499.00"),
    # ),
    # Product(
    #     id="example-mouse-1",
    #     name="Example Wireless Mouse",
    #     site=Site(name="Another Retailer"),
    #     url="https://another-example.com/example-wireless-mouse",
    #     price_selector=".current-price",
    #     brand="ExampleBrand",
    #     category="peripherals",
    #     currency="AUD",
    #     enabled=False,
    #     target_price=Decimal("79.00"),
    # ),
]
