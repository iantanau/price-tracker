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
            )
        ],
    ),
    Product(
        id="shark-carpetxpert-hairpro-pet-ex300anz",
        name="Shark CarpetXpert HairPro Pet with StainStriker EX300ANZ",
        brand="Shark",
        category="Carpet Cleaners",
        currency="AUD",
        enabled=True,
        listings=[
            ProductListing(
                id="everyday",
                site=Site(name="Everyday"),
                url="https://www.everyday.com.au/shop/product/shark-carpetxpert-hairpro-pet-with-stainstriker-ex300anz-14378469/14378469-1",
            ),
            ProductListing(
                id="appliances-online",
                site=Site(name="Appliances Online"),
                url="https://www.appliancesonline.com.au/product/shark-carpetxpert-hairpro-pet-upright-cleaner-with-stainstriker-ex300/",
            ),
            ProductListing(
                id="the-good-guys",
                site=Site(name="The Good Guys"),
                url="https://www.thegoodguys.com.au/shark-carpetxpert-hairpro-pet-with-stainstriker-ex300anz",
            ),
            ProductListing(
                id="harvey-norman",
                site=Site(name="Harvey Norman"),
                url="https://www.harveynorman.com.au/shark-carpetxpert-hairpro-pet-with-stainstriker-dark-silver.html",
            ),
        ],
    ),
    Product(
        id="klevv-fit-v-32gb-ddr5-6000-cl28",
        name="KLEVV FIT V 32GB (2x 16GB) DDR5 6000MHz CL28 Desktop Memory",
        brand="KLEVV",
        category="Memory",
        currency="AUD",
        enabled=True,
        listings=[
            ProductListing(
                id="mwave",
                site=Site(name="Mwave"),
                url="https://www.mwave.com.au/products/klevv-fit-v-32gb-2x-16gb-ddr5-6000mhz-cl28-desktop-memory-black-ac87786",
            ),
            ProductListing(
                id="pccasegear",
                site=Site(name="PC Case Gear"),
                url="https://www.pccasegear.com/products/71545/klevv-fit-v-32gb-2x16gb-6000mhz-cl28-ddr5-white",
            ),
            ProductListing(
                id="centrecom",
                site=Site(name="Centre Com"),
                url="https://www.centrecom.com.au/klevv-fit-v-32gb-2-x-16gb-ddr5-6000mhz-cl28-desktop-ram-black",
            ),
            ProductListing(
                id="amazon-au",
                site=Site(name="Amazon Australia"),
                url="https://www.amazon.com.au/KLEVV-Performance-Overclocking-28-36-36-76-Ultra-Low/dp/B0FF5CQ4GN",
            ),
        ],
    ),
    Product(
        id="apple-iphone-17-pro-max-512gb",
        name="Apple iPhone 17 Pro Max 512GB",
        brand="Apple",
        category="Mobile Phones",
        currency="AUD",
        enabled=True,
        listings=[
            ProductListing(
                id="officeworks",
                site=Site(name="Officeworks"),
                url="https://www.officeworks.com.au/shop/officeworks/p/iphone-17-pro-max-512gb-cosmic-orange-ip17px51og",
            ),
            ProductListing(
                id="costco-au",
                site=Site(name="Costco Australia"),
                url="https://www.costco.com.au/Electronics/Mobile-Phones/iPhones/iPhone-17-Pro-Max/Apple-iPhone-17-Pro-Max-512GB/p/240980",
            ),
        ],
    ),
]
