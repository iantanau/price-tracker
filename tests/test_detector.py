"""Tests for parser auto-detection."""

from models.product import Product
from models.site import Site
from parsers.detector import detect_parser_type


def _make_product(**overrides) -> Product:
    """Create a product with sensible detector-test defaults."""
    defaults = {
        "id": "detector-product",
        "name": "Detector Product",
        "site": Site(name="Detector Store"),
        "url": "https://detector-store.example/products/001",
        "price_selector": ".price",
        "currency": "AUD",
    }
    defaults.update(overrides)
    return Product(**defaults)


def test_detects_json_ld_when_price_present() -> None:
    """Chooses json_ld when a JSON-LD Product/Offer has a price."""
    content = (
        '<script type="application/ld+json">'
        '{"@type":"Product","offers":{"@type":"Offer","price":"499.00",'
        '"priceCurrency":"AUD"}}'
        "</script>"
    )

    assert detect_parser_type(content, _make_product(), {"json_ld", "css"}) == "json_ld"


def test_detects_embedded_json_when_no_json_ld() -> None:
    """Chooses embedded_json when the product variable is present."""
    content = "<script>window.__PRELOADED_STATE__ = {\"x\": 1}</script>"
    product = _make_product(json_variable="window.__PRELOADED_STATE__")

    assert (
        detect_parser_type(content, product, {"embedded_json", "css"})
        == "embedded_json"
    )


def test_falls_back_to_css() -> None:
    """Chooses css when no other signal matches."""
    content = "<html><body>no price signal</body></html>"

    assert detect_parser_type(content, _make_product(), {"css"}) == "css"


def test_json_ld_wins_over_css() -> None:
    """Prioritises JSON-LD over a CSS-rendered price."""
    content = (
        '<script type="application/ld+json">'
        '{"@type":"Product","offers":{"@type":"Offer","price":"499.00",'
        '"priceCurrency":"AUD"}}'
        "</script>"
        '<div class="price">$499</div>'
    )

    assert detect_parser_type(content, _make_product(), {"json_ld", "css"}) == "json_ld"


def test_ignores_json_ld_without_price() -> None:
    """Falls through when JSON-LD exists but has no product price."""
    content = (
        '<script type="application/ld+json">'
        '{"@type":"BreadcrumbList","itemListElement":[]}'
        "</script>"
    )

    assert detect_parser_type(content, _make_product(), {"json_ld", "css"}) == "css"


def test_skips_json_ld_when_not_registered() -> None:
    """Does not select json_ld when it is not an available parser."""
    content = (
        '<script type="application/ld+json">'
        '{"@type":"Product","offers":{"@type":"Offer","price":"499.00",'
        '"priceCurrency":"AUD"}}'
        "</script>"
    )

    assert detect_parser_type(content, _make_product(), {"css"}) == "css"
