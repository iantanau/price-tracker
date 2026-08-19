# Multi-Product Notification Design

**Date:** 2026-08-19
**Status:** Approved

## Goal

Send one aggregated notification per monitoring run instead of one email per
matching product, and make the payload channel-neutral so future Telegram and
WeChat notifiers can render the same data without coupling to email HTML.

## Problem

- `MonitorService.run()` calls `notifier.send()` once per matching product.
- `NotificationPayload` is a flat `subject` + `body` string, which is awkward
  to format well and does not translate cleanly across channels.

## Design

Introduce a structured alert item:

```python
@dataclass(frozen=True)
class NotificationItem:
    product_id: str
    name: str
    url: str
    price: Price | None = None
    target_price: Decimal | None = None
    brand: str | None = None
    category: str | None = None
```

Change `NotificationPayload` to carry a list of items:

```python
@dataclass(frozen=True)
class NotificationPayload:
    subject: str
    items: tuple[NotificationItem, ...] = ()
    recipient: str | None = None
```

`MonitorService` collects matching items during the pass and calls
`notifier.send()` once at the end (or not at all when nothing matched).

Subject rules:

- one item: `Price alert: {name}`
- multiple items: `Price alert: {N} products`

`EmailNotifier` renders from `items`:

- HTML body with a list/table of name, current price, target price, and URL.
- Plain-text fallback with the same information.
- `Notifier.send(payload)` interface stays unchanged.

Future `TelegramNotifier`/`WeChatNotifier` implement the same `Notifier`
interface and render Markdown/plain text from `items`; no email HTML leaks into
the service layer.

## Scope

- `models/notification_payload.py` — add `NotificationItem`, change payload.
- `services/monitor_service.py` — aggregate matches and send once.
- `notifiers/email_notifier.py` — HTML + plain-text rendering from items.
- Update `tests/test_monitor_service.py` and `tests/test_email_notifier.py`.

## Out of scope

- Implementing Telegram/WeChat notifiers.
- Notification deduplication across runs.
