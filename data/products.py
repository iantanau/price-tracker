"""Seed product catalog for Phase 1."""

from decimal import Decimal

from models.listing import ProductListing
from models.product import Product
from models.site import Site


PRODUCTS: list[Product] = [
    Product(
        id="uniqlo-heattech-ultra-warm-t-shirt",
        name="Uniqlo HEATTECH ULTRA WARM Crew Neck Long Sleeve T-Shirt",
        brand="Uniqlo",
        category="Clothes",
        currency="AUD",
        enabled=True,
        target_price=Decimal("39.99"),
        listings=[
            ProductListing(
                id="uniqlo",
                site=Site(name="Uniqlo"),
                url="https://www.uniqlo.com/au/en/products/E479525-000/00?colorDisplayCode=08",
                parser_type="embedded_json",
                json_variable="window.__PRELOADED_STATE__",
                price_path=(
                    "entity.pdpEntity.E479525-000-00.product.prices.promo.value"
                    "|entity.pdpEntity.E479525-000-00.product.prices.base.value"
                ),
                currency_path=(
                    "entity.pdpEntity.E479525-000-00.product.prices.promo.currency.code"
                    "|entity.pdpEntity.E479525-000-00.product.prices.base.currency.code"
                ),
            )
        ],
    ),
]
