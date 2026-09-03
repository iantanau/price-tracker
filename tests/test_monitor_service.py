"""Tests for ComparisonService orchestration."""

from decimal import Decimal
from unittest.mock import Mock

from models.listing import ProductListing
from models.notification_payload import NotificationPayload
from models.parsed_result import ParsedResult
from models.price import Price
from models.product import Product
from models.site import Site
from services.comparison_service import ComparisonService


class TestComparisonService:
    """Tests for the comparison workflow service."""

    def setup_method(self) -> None:
        """Create mocked dependencies and a service for each test."""
        self.product_store = Mock()
        self.monitor = Mock()
        self.rule_engine = Mock()
        self.notifier = Mock()

        self.service = ComparisonService(
            product_store=self.product_store,
            monitor=self.monitor,
            rule_engine=self.rule_engine,
            notifier=self.notifier,
        )

    def _make_listing(self, listing_id: str) -> ProductListing:
        return ProductListing(
            id=listing_id,
            site=Site(name=f"Store {listing_id}"),
            url=f"https://test-store.example/products/{listing_id}",
            currency="AUD",
        )

    def _make_product(
        self, product_id: str, listing_ids: list[str] | None = None
    ) -> Product:
        listing_ids = listing_ids or [product_id]
        return Product(
            id=product_id,
            name=f"Product {product_id}",
            listings=[self._make_listing(listing_id) for listing_id in listing_ids],
            target_price=Decimal("100.00"),
        )

    def test_sends_notification_when_rule_matches(self) -> None:
        """Sends a notification when the rule engine says to notify."""
        product = self._make_product("p001")
        self.product_store.list_enabled.return_value = [product]
        price = Price(value=Decimal("90.00"), currency="AUD")
        self.monitor.fetch_listing.return_value = ParsedResult(price=price)
        self.rule_engine.should_notify.return_value = True

        self.service.run()

        self.notifier.send.assert_called_once()
        payload = self.notifier.send.call_args[0][0]
        assert isinstance(payload, NotificationPayload)
        assert payload.subject == "Price alert: Product p001"
        assert len(payload.items) == 1
        item = payload.items[0]
        assert item.product_id == "p001"
        assert item.best_price == price
        assert len(item.listings) == 1
        assert item.listings[0].price == price

    def test_sends_single_notification_for_multiple_products(self) -> None:
        """Aggregates all matching products into one notification."""
        first = self._make_product("p001")
        second = self._make_product("p002")
        self.product_store.list_enabled.return_value = [first, second]
        self.monitor.fetch_listing.side_effect = [
            ParsedResult(price=Price(value=Decimal("90.00"), currency="AUD")),
            ParsedResult(price=Price(value=Decimal("80.00"), currency="AUD")),
        ]
        self.rule_engine.should_notify.return_value = True

        self.service.run()

        self.notifier.send.assert_called_once()
        payload = self.notifier.send.call_args[0][0]
        assert payload.subject == "Price alert: 2 products"
        assert [item.product_id for item in payload.items] == ["p001", "p002"]

    def test_does_not_send_notification_when_rule_does_not_match(self) -> None:
        """Does not send a notification when the rule engine says not to."""
        product = self._make_product("p001")
        self.product_store.list_enabled.return_value = [product]
        self.monitor.fetch_listing.return_value = ParsedResult(
            price=Price(value=Decimal("150.00"), currency="AUD")
        )
        self.rule_engine.should_notify.return_value = False

        self.service.run()

        self.notifier.send.assert_not_called()

    def test_chooses_best_price_across_listings(self) -> None:
        """Uses the cheapest listing price for the rule decision."""
        product = self._make_product("p001", ["p001-a", "p001-b"])
        self.product_store.list_enabled.return_value = [product]
        self.monitor.fetch_listing.side_effect = [
            ParsedResult(price=Price(value=Decimal("95.00"), currency="AUD")),
            ParsedResult(price=Price(value=Decimal("85.00"), currency="AUD")),
        ]
        self.rule_engine.should_notify.return_value = True

        self.service.run()

        best = Price(value=Decimal("85.00"), currency="AUD")
        assert self.rule_engine.should_notify.call_args[0][1].price == best
        item = self.notifier.send.call_args[0][0].items[0]
        assert item.best_price == best

    def test_records_listing_prices(self) -> None:
        """Records each successful listing price in history."""
        product = self._make_product("p001", ["p001-a", "p001-b"])
        self.product_store.list_enabled.return_value = [product]
        price_a = Price(value=Decimal("95.00"), currency="AUD")
        price_b = Price(value=Decimal("85.00"), currency="AUD")
        self.monitor.fetch_listing.side_effect = [
            ParsedResult(price=price_a),
            ParsedResult(price=price_b),
        ]
        self.rule_engine.should_notify.return_value = False
        history_store = Mock()
        history_store.get_latest.return_value = None
        history_store.get_lowest.return_value = None
        service = ComparisonService(
            product_store=self.product_store,
            monitor=self.monitor,
            rule_engine=self.rule_engine,
            notifier=self.notifier,
            price_history_store=history_store,
        )

        service.run()

        assert history_store.record.call_args_list == [
            (("p001-a", price_a, "p001"),),
            (("p001-b", price_b, "p001"),),
        ]

    def test_passes_previous_and_lowest_best_to_rule_engine(self) -> None:
        """Derives previous best and all-time low across listings."""
        product = self._make_product("p001", ["p001-a", "p001-b"])
        self.product_store.list_enabled.return_value = [product]
        self.monitor.fetch_listing.side_effect = [
            ParsedResult(price=Price(value=Decimal("90.00"), currency="AUD")),
            ParsedResult(price=Price(value=Decimal("80.00"), currency="AUD")),
        ]
        self.rule_engine.should_notify.return_value = True
        history_store = Mock()
        history_store.get_latest.side_effect = [
            Price(value=Decimal("110.00"), currency="AUD"),
            Price(value=Decimal("120.00"), currency="AUD"),
        ]
        history_store.get_lowest.side_effect = [
            Price(value=Decimal("110.00"), currency="AUD"),
            Price(value=Decimal("120.00"), currency="AUD"),
        ]
        service = ComparisonService(
            product_store=self.product_store,
            monitor=self.monitor,
            rule_engine=self.rule_engine,
            notifier=self.notifier,
            price_history_store=history_store,
        )

        service.run()

        previous_best = Price(value=Decimal("110.00"), currency="AUD")
        all_time_low = Price(value=Decimal("110.00"), currency="AUD")
        assert self.rule_engine.should_notify.call_args[0][2] == previous_best
        assert self.rule_engine.should_notify.call_args[0][3] == all_time_low

    def test_skips_failed_listing(self) -> None:
        """Skips a failing listing and still compares the remaining one."""
        product = self._make_product("p001", ["p001-a", "p001-b"])
        self.product_store.list_enabled.return_value = [product]
        self.monitor.fetch_listing.side_effect = [
            Exception("fetch failed"),
            ParsedResult(price=Price(value=Decimal("85.00"), currency="AUD")),
        ]
        self.rule_engine.should_notify.return_value = True

        self.service.run()

        item = self.notifier.send.call_args[0][0].items[0]
        assert len(item.listings) == 2
        assert item.listings[0].price is None
        assert item.listings[1].price is not None
        assert item.best_price == Price(value=Decimal("85.00"), currency="AUD")

    def test_no_notification_when_no_listing_price(self) -> None:
        """Does not notify when no listing produced a price."""
        product = self._make_product("p001", ["p001-a"])
        self.product_store.list_enabled.return_value = [product]
        self.monitor.fetch_listing.return_value = ParsedResult(price=None)

        self.service.run()

        self.rule_engine.should_notify.assert_not_called()
        self.notifier.send.assert_not_called()
