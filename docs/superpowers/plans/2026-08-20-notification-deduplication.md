# Notification Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make target-price alerts edge-triggered so a product only notifies on the first crossing into the target range and on subsequent new all-time lows, not on every run while it stays below target.

**Architecture:** Extend the notification rule interface to receive the previous and lowest recorded prices, have `MonitorService` read them from `PriceHistoryStore` before recording the current observation, and keep the existing single aggregated `notifier.send()`.

**Tech Stack:** Python, pytest, `unittest.mock`.

---

### Task 1: Edge-triggered `TargetPriceRule`

**Files:**
- Modify: `services/rule_engine.py`
- Test: `tests/test_rule_engine.py`

- [ ] **Step 1: Write the failing tests**

Add to `TestTargetPriceRule` in `tests/test_rule_engine.py`:

```python
    def _result(self, value: str) -> ParsedResult:
        return ParsedResult(price=Price(value=Decimal(value), currency="AUD"))

    def test_notifies_when_no_previous_history(self) -> None:
        result = self._result("99.99")

        assert self.rule.should_notify(self.product, result, None, None) is True

    def test_does_not_notify_when_price_stays_below_target(self) -> None:
        previous = Price(value=Decimal("90.00"), currency="AUD")
        lowest = Price(value=Decimal("90.00"), currency="AUD")
        result = self._result("90.00")

        assert self.rule.should_notify(self.product, result, previous, lowest) is False

    def test_notifies_when_crossing_from_above_target(self) -> None:
        previous = Price(value=Decimal("110.00"), currency="AUD")
        lowest = Price(value=Decimal("110.00"), currency="AUD")
        result = self._result("99.99")

        assert self.rule.should_notify(self.product, result, previous, lowest) is True

    def test_notifies_on_new_low_below_target(self) -> None:
        previous = Price(value=Decimal("90.00"), currency="AUD")
        lowest = Price(value=Decimal("90.00"), currency="AUD")
        result = self._result("85.00")

        assert self.rule.should_notify(self.product, result, previous, lowest) is True

    def test_does_not_notify_on_recovery_to_seen_price(self) -> None:
        previous = Price(value=Decimal("92.00"), currency="AUD")
        lowest = Price(value=Decimal("85.00"), currency="AUD")
        result = self._result("90.00")

        assert self.rule.should_notify(self.product, result, previous, lowest) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_rule_engine.py -v`
Expected: the new `should_notify` calls fail because the current signature takes only two positional arguments.

- [ ] **Step 3: Write minimal implementation**

Update `services/rule_engine.py`:

```python
from models.price import Price


class NotificationRule(ABC):
    @abstractmethod
    def should_notify(
        self,
        product: Product,
        result: ParsedResult,
        previous_price: Price | None = None,
        lowest_price: Price | None = None,
    ) -> bool:
        raise NotImplementedError


class TargetPriceRule(NotificationRule):
    def should_notify(
        self,
        product: Product,
        result: ParsedResult,
        previous_price: Price | None = None,
        lowest_price: Price | None = None,
    ) -> bool:
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
    def should_notify(
        self,
        product: Product,
        result: ParsedResult,
        previous_price: Price | None = None,
        lowest_price: Price | None = None,
    ) -> bool:
        return any(
            rule.should_notify(product, result, previous_price, lowest_price)
            for rule in self.rules
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_rule_engine.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/rule_engine.py tests/test_rule_engine.py
git commit -m "feat: make target price rule edge-triggered"
```

### Task 2: Wire price history into `MonitorService`

**Files:**
- Modify: `services/monitor_service.py`
- Test: `tests/test_monitor_service.py`

- [ ] **Step 1: Write the failing tests**

Add to `TestMonitorService` in `tests/test_monitor_service.py`:

```python
    def test_passes_previous_and_lowest_prices_to_rule_engine(self) -> None:
        product = self._make_product("p001")
        self.product_store.list_enabled.return_value = [product]
        result = ParsedResult(price=Price(value=Decimal("90.00"), currency="AUD"))
        self.monitor.fetch.return_value = result
        self.rule_engine.should_notify.return_value = True
        previous = Price(value=Decimal("110.00"), currency="AUD")
        lowest = Price(value=Decimal("110.00"), currency="AUD")
        history_store = Mock()
        history_store.get_latest.return_value = previous
        history_store.get_lowest.return_value = lowest
        service = self._service_with_history_store(history_store)

        service.run()

        self.rule_engine.should_notify.assert_called_once_with(
            product, result, previous, lowest
        )

    def test_history_read_failure_treated_as_no_history(self) -> None:
        product = self._make_product("p001")
        self.product_store.list_enabled.return_value = [product]
        result = ParsedResult(price=Price(value=Decimal("90.00"), currency="AUD"))
        self.monitor.fetch.return_value = result
        self.rule_engine.should_notify.return_value = True
        history_store = Mock()
        history_store.get_latest.side_effect = Exception("read failed")
        history_store.get_lowest.side_effect = Exception("read failed")
        service = self._service_with_history_store(history_store)

        service.run()

        self.rule_engine.should_notify.assert_called_once_with(
            product, result, None, None
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_monitor_service.py -v`
Expected: the new assertions fail because `should_notify` is currently called with only two arguments.

- [ ] **Step 3: Write minimal implementation**

Add `from models.price import Price` to `services/monitor_service.py` and update
`_check_product` plus add two read helpers:

```python
        result = self.monitor.fetch(product)
        previous_price = self._get_previous_price(product.id)
        lowest_price = self._get_lowest_price(product.id)
        self._record_price(product, result)

        if not self.rule_engine.should_notify(
            product, result, previous_price, lowest_price
        ):
            logger.info("No notification needed for product %s", product.id)
            return None
```

```python
    def _get_previous_price(self, product_id: str) -> Price | None:
        if self.price_history_store is None:
            return None
        try:
            return self.price_history_store.get_latest(product_id)
        except Exception:
            logger.exception("Failed to read previous price for product %s", product_id)
            return None

    def _get_lowest_price(self, product_id: str) -> Price | None:
        if self.price_history_store is None:
            return None
        try:
            return self.price_history_store.get_lowest(product_id)
        except Exception:
            logger.exception("Failed to read lowest price for product %s", product_id)
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_monitor_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/monitor_service.py tests/test_monitor_service.py
git commit -m "feat: dedupe alerts using price history"
```

### Task 3: Full suite verification

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: PASS with no regressions.
