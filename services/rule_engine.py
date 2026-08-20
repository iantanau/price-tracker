"""Notification rule engine.

Rules decide whether a price observation should trigger a notification.
The engine itself contains no delivery logic; it only evaluates rules
against a product, its parsed result, and the previous/lowest recorded
prices.
"""

from abc import ABC, abstractmethod

from models.parsed_result import ParsedResult
from models.price import Price
from models.product import Product


class NotificationRule(ABC):
    """Abstract base class for notification decision rules."""

    @abstractmethod
    def should_notify(
        self,
        product: Product,
        result: ParsedResult,
        previous_price: Price | None = None,
        lowest_price: Price | None = None,
    ) -> bool:
        """Return ``True`` if this rule says a notification should fire.

        Args:
            product: Product being monitored.
            result: Parsed observation for the product.
            previous_price: Most recent recorded price before this observation.
            lowest_price: Lowest price ever recorded for the product.

        Returns:
            Whether the rule matches.
        """
        raise NotImplementedError


class TargetPriceRule(NotificationRule):
    """Notify when the current price first drops to or below the target.

    The rule is edge-triggered: it fires when the price crosses into the
    ``<= target`` state or reaches a new all-time low while already below
    target. It deliberately does not fire again on every run while the
    price simply remains below target.
    """

    def should_notify(
        self,
        product: Product,
        result: ParsedResult,
        previous_price: Price | None = None,
        lowest_price: Price | None = None,
    ) -> bool:
        """Return ``True`` when the target is first reached or a new low is set."""
        if product.target_price is None or result.price is None:
            return False

        current = result.price.value
        if current > product.target_price:
            return False

        if previous_price is None:
            return True

        if previous_price.value > product.target_price:
            return True

        baseline = (
            lowest_price.value if lowest_price is not None else previous_price.value
        )
        return current < baseline


class RuleEngine:
    """Evaluates a collection of notification rules.

    A notification should be sent if any configured rule matches.
    """

    def __init__(self, rules: list[NotificationRule]) -> None:
        """Initialize the engine with the given rules.

        Args:
            rules: Notification rules to evaluate.
        """
        self.rules = rules

    def should_notify(
        self,
        product: Product,
        result: ParsedResult,
        previous_price: Price | None = None,
        lowest_price: Price | None = None,
    ) -> bool:
        """Return ``True`` if any rule matches the observation.

        Args:
            product: Product being monitored.
            result: Parsed observation for the product.
            previous_price: Most recent recorded price before this observation.
            lowest_price: Lowest price ever recorded for the product.

        Returns:
            ``True`` when at least one rule says a notification should fire.
        """
        return any(
            rule.should_notify(product, result, previous_price, lowest_price)
            for rule in self.rules
        )
