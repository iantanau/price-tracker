"""Tests for RuleEngine and TargetPriceRule."""

from decimal import Decimal

import pytest

from models.parsed_result import ParsedResult
from models.price import Price
from models.product import Product
from models.site import Site
from services.rule_engine import RuleEngine, TargetPriceRule


class TestTargetPriceRule:
    """Tests for the target price notification rule."""

    def setup_method(self) -> None:
        """Create a fresh rule and product for each test."""
        self.rule = TargetPriceRule()
        self.product = Product(
            id="rule-product-001",
            name="Rule Test Product",
            site=Site(name="Rule Store"),
            url="https://rule-store.example/products/001",
            price_selector=".price",
            target_price=Decimal("100.00"),
        )

    def _result(self, value: str) -> ParsedResult:
        """Build a parsed result with the given AUD price."""
        return ParsedResult(price=Price(value=Decimal(value), currency="AUD"))

    def test_notifies_when_price_below_target(self) -> None:
        """Notifies when current price is strictly below the target."""
        result = ParsedResult(price=Price(value=Decimal("99.99"), currency="AUD"))

        assert self.rule.should_notify(self.product, result) is True

    def test_notifies_when_price_equals_target(self) -> None:
        """Notifies when current price is exactly at the target."""
        result = ParsedResult(price=Price(value=Decimal("100.00"), currency="AUD"))

        assert self.rule.should_notify(self.product, result) is True

    def test_does_not_notify_when_price_above_target(self) -> None:
        """Does not notify when current price is above the target."""
        result = ParsedResult(price=Price(value=Decimal("100.01"), currency="AUD"))

        assert self.rule.should_notify(self.product, result) is False

    def test_does_not_notify_when_no_target_price(self) -> None:
        """Does not notify when the product has no target price configured."""
        self.product.target_price = None
        result = ParsedResult(price=Price(value=Decimal("50.00"), currency="AUD"))

        assert self.rule.should_notify(self.product, result) is False

    def test_does_not_notify_when_no_price_parsed(self) -> None:
        """Does not notify when the parser could not extract a price."""
        result = ParsedResult(price=None)

        assert self.rule.should_notify(self.product, result) is False

    def test_notifies_when_no_previous_history(self) -> None:
        """Notifies when there is no prior price history."""
        result = self._result("99.99")

        assert self.rule.should_notify(self.product, result, None, None) is True

    def test_does_not_notify_when_price_stays_below_target(self) -> None:
        """Does not repeat an alert while the price stays below target."""
        previous = Price(value=Decimal("90.00"), currency="AUD")
        lowest = Price(value=Decimal("90.00"), currency="AUD")
        result = self._result("90.00")

        assert self.rule.should_notify(self.product, result, previous, lowest) is False

    def test_notifies_when_crossing_from_above_target(self) -> None:
        """Notifies when the price crosses from above into the target range."""
        previous = Price(value=Decimal("110.00"), currency="AUD")
        lowest = Price(value=Decimal("110.00"), currency="AUD")
        result = self._result("99.99")

        assert self.rule.should_notify(self.product, result, previous, lowest) is True

    def test_notifies_on_new_low_below_target(self) -> None:
        """Notifies on a new all-time low while already below target."""
        previous = Price(value=Decimal("90.00"), currency="AUD")
        lowest = Price(value=Decimal("90.00"), currency="AUD")
        result = self._result("85.00")

        assert self.rule.should_notify(self.product, result, previous, lowest) is True

    def test_does_not_notify_on_recovery_to_seen_price(self) -> None:
        """Does not notify when the price recovers to an already-seen value."""
        previous = Price(value=Decimal("92.00"), currency="AUD")
        lowest = Price(value=Decimal("85.00"), currency="AUD")
        result = self._result("90.00")

        assert self.rule.should_notify(self.product, result, previous, lowest) is False


class TestRuleEngine:
    """Tests for the RuleEngine composite."""

    def test_notifies_when_any_rule_matches(self) -> None:
        """Notifies when at least one rule says to notify."""
        product = Product(
            id="engine-product-001",
            name="Engine Test Product",
            site=Site(name="Engine Store"),
            url="https://engine-store.example/products/001",
            price_selector=".price",
            target_price=Decimal("100.00"),
        )
        result = ParsedResult(price=Price(value=Decimal("90.00"), currency="AUD"))

        engine = RuleEngine(rules=[TargetPriceRule()])

        assert engine.should_notify(product, result) is True

    def test_does_not_notify_when_no_rules_match(self) -> None:
        """Does not notify when no rules match."""
        product = Product(
            id="engine-product-001",
            name="Engine Test Product",
            site=Site(name="Engine Store"),
            url="https://engine-store.example/products/001",
            price_selector=".price",
            target_price=Decimal("100.00"),
        )
        result = ParsedResult(price=Price(value=Decimal("150.00"), currency="AUD"))

        engine = RuleEngine(rules=[TargetPriceRule()])

        assert engine.should_notify(product, result) is False

    def test_does_not_notify_with_empty_rules(self) -> None:
        """Does not notify when no rules are configured."""
        product = Product(
            id="engine-product-001",
            name="Engine Test Product",
            site=Site(name="Engine Store"),
            url="https://engine-store.example/products/001",
            price_selector=".price",
            target_price=Decimal("100.00"),
        )
        result = ParsedResult(price=Price(value=Decimal("90.00"), currency="AUD"))

        engine = RuleEngine(rules=[])

        assert engine.should_notify(product, result) is False
