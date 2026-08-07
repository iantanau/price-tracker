"""Notification rule engine.

Rules decide whether a price observation should trigger a notification.
The engine itself contains no delivery logic; it only evaluates rules
against a product and its parsed result.
"""

from abc import ABC, abstractmethod

from models.parsed_result import ParsedResult
from models.product import Product


class NotificationRule(ABC):
    """Abstract base class for notification decision rules."""

    @abstractmethod
    def should_notify(self, product: Product, result: ParsedResult) -> bool:
        """Return ``True`` if this rule says a notification should fire.

        Args:
            product: Product being monitored.
            result: Parsed observation for the product.

        Returns:
            Whether the rule matches.
        """
        raise NotImplementedError


class TargetPriceRule(NotificationRule):
    """Notify when the current price is at or below the product's target."""

    def should_notify(self, product: Product, result: ParsedResult) -> bool:
        """Return ``True`` if ``result.price`` is <= ``product.target_price``.

        The rule only matches when a target price is configured and a price
        was successfully parsed.
        """
        if product.target_price is None:
            return False
        if result.price is None:
            return False
        return result.price.value <= product.target_price


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

    def should_notify(self, product: Product, result: ParsedResult) -> bool:
        """Return ``True`` if any rule matches the observation.

        Args:
            product: Product being monitored.
            result: Parsed observation for the product.

        Returns:
            ``True`` when at least one rule says a notification should fire.
        """
        return any(rule.should_notify(product, result) for rule in self.rules)
