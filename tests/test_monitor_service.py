"""Tests for MonitorService orchestration."""

from decimal import Decimal
from unittest.mock import Mock

import pytest

from models.notification_payload import NotificationItem, NotificationPayload
from models.parsed_result import ParsedResult
from models.price import Price
from models.product import Product
from models.site import Site
from services.monitor_service import MonitorService


class TestMonitorService:
    """Tests for the monitoring workflow service."""

    def setup_method(self) -> None:
        """Create mocked dependencies and a service for each test."""
        self.product_store = Mock()
        self.monitor = Mock()
        self.rule_engine = Mock()
        self.notifier = Mock()

        self.service = MonitorService(
            product_store=self.product_store,
            monitor=self.monitor,
            rule_engine=self.rule_engine,
            notifier=self.notifier,
        )

    def _make_product(self, product_id: str, enabled: bool = True) -> Product:
        """Create a test product."""
        return Product(
            id=product_id,
            name=f"Product {product_id}",
            site=Site(name="Test Store"),
            url=f"https://test-store.example/products/{product_id}",
            price_selector=".price",
            enabled=enabled,
            target_price=Decimal("100.00"),
        )

    def test_sends_notification_when_rule_matches(self) -> None:
        """Sends a notification when the rule engine says to notify."""
        product = self._make_product("p001")
        self.product_store.list_enabled.return_value = [product]
        self.monitor.fetch.return_value = ParsedResult(
            price=Price(value=Decimal("90.00"), currency="AUD")
        )
        self.rule_engine.should_notify.return_value = True

        self.service.run()

        self.product_store.list_enabled.assert_called_once()
        self.monitor.fetch.assert_called_once_with(product)
        self.rule_engine.should_notify.assert_called_once()
        self.notifier.send.assert_called_once()

        payload = self.notifier.send.call_args[0][0]
        assert isinstance(payload, NotificationPayload)
        assert payload.subject == "Price alert: Product p001"
        assert len(payload.items) == 1
        item = payload.items[0]
        assert item.product_id == "p001"
        assert item.name == "Product p001"
        assert item.price == Price(value=Decimal("90.00"), currency="AUD")
        assert item.target_price == Decimal("100.00")
        assert item.url == product.url

    def test_sends_single_notification_for_multiple_matches(self) -> None:
        """Aggregates all matching products into one notification."""
        first = self._make_product("p001")
        second = self._make_product("p002")
        self.product_store.list_enabled.return_value = [first, second]
        self.monitor.fetch.side_effect = [
            ParsedResult(price=Price(value=Decimal("90.00"), currency="AUD")),
            ParsedResult(price=Price(value=Decimal("80.00"), currency="AUD")),
        ]
        self.rule_engine.should_notify.return_value = True

        self.service.run()

        self.notifier.send.assert_called_once()
        payload = self.notifier.send.call_args[0][0]
        assert isinstance(payload, NotificationPayload)
        assert payload.subject == "Price alert: 2 products"
        assert [item.product_id for item in payload.items] == ["p001", "p002"]
        assert [item.price.value for item in payload.items] == [
            Decimal("90.00"),
            Decimal("80.00"),
        ]

    def test_does_not_send_notification_when_rule_does_not_match(self) -> None:
        """Does not send a notification when the rule engine says not to."""
        product = self._make_product("p001")
        self.product_store.list_enabled.return_value = [product]
        self.monitor.fetch.return_value = ParsedResult(
            price=Price(value=Decimal("150.00"), currency="AUD")
        )
        self.rule_engine.should_notify.return_value = False

        self.service.run()

        self.monitor.fetch.assert_called_once()
        self.notifier.send.assert_not_called()

    def test_continues_processing_after_one_product_fails(self) -> None:
        """One product failure does not prevent other products from running."""
        failing = self._make_product("p001")
        succeeding = self._make_product("p002")

        self.product_store.list_enabled.return_value = [failing, succeeding]
        self.monitor.fetch.side_effect = [
            Exception("fetch failed"),
            ParsedResult(price=Price(value=Decimal("90.00"), currency="AUD")),
        ]
        self.rule_engine.should_notify.return_value = True

        self.service.run()

        assert self.monitor.fetch.call_count == 2
        self.notifier.send.assert_called_once()
        payload = self.notifier.send.call_args[0][0]
        assert [item.product_id for item in payload.items] == ["p002"]

    def test_handles_empty_product_list(self) -> None:
        """Handles an empty enabled product list gracefully."""
        self.product_store.list_enabled.return_value = []

        self.service.run()

        self.monitor.fetch.assert_not_called()
        self.notifier.send.assert_not_called()

    def test_stops_cleanly_when_store_fails(self) -> None:
        """Stops without crashing when the product store fails to load."""
        self.product_store.list_enabled.side_effect = Exception("store unavailable")

        self.service.run()

        self.monitor.fetch.assert_not_called()
        self.notifier.send.assert_not_called()

    def _service_with_history_store(self, history_store: Mock) -> MonitorService:
        """Return a service wired with a price history store."""
        return MonitorService(
            product_store=self.product_store,
            monitor=self.monitor,
            rule_engine=self.rule_engine,
            notifier=self.notifier,
            price_history_store=history_store,
        )

    def test_records_price_after_fetching(self) -> None:
        """A parsed price is recorded in the price history store."""
        product = self._make_product("p001")
        self.product_store.list_enabled.return_value = [product]
        price = Price(value=Decimal("90.00"), currency="AUD")
        self.monitor.fetch.return_value = ParsedResult(price=price)
        self.rule_engine.should_notify.return_value = False
        history_store = Mock()
        service = self._service_with_history_store(history_store)

        service.run()

        history_store.record.assert_called_once_with("p001", price)

    def test_does_not_record_when_price_missing(self) -> None:
        """A fetch without a price does not write history."""
        product = self._make_product("p001")
        self.product_store.list_enabled.return_value = [product]
        self.monitor.fetch.return_value = ParsedResult(price=None)
        self.rule_engine.should_notify.return_value = False
        history_store = Mock()
        service = self._service_with_history_store(history_store)

        service.run()

        history_store.record.assert_not_called()

    def test_recording_failure_does_not_prevent_notification(self) -> None:
        """History write failures are isolated from alert delivery."""
        product = self._make_product("p001")
        self.product_store.list_enabled.return_value = [product]
        self.monitor.fetch.return_value = ParsedResult(
            price=Price(value=Decimal("90.00"), currency="AUD")
        )
        self.rule_engine.should_notify.return_value = True
        history_store = Mock()
        history_store.record.side_effect = Exception("history unavailable")
        service = self._service_with_history_store(history_store)

        service.run()

        self.notifier.send.assert_called_once()
