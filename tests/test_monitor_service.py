"""Tests for MonitorService orchestration."""

from decimal import Decimal
from unittest.mock import Mock

import pytest

from models.notification_payload import NotificationPayload
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
        assert product.name in payload.subject
        assert "90.00" in payload.body
        assert product.url in payload.body

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
