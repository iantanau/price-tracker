# Notification Deduplication Design

**Date:** 2026-08-20
**Status:** Approved

## Goal

Stop duplicate price alerts that fire on every monitoring pass while a product
stays below its target price, and combine the deduplication with the existing
multi-product aggregation so one email is sent per run.

## Problem

`TargetPriceRule` is level-triggered: it matches whenever the current price is
at or below the target. Because the monitor runs every six hours, a product
that remains below target produces a new alert on every pass.

## Design

Make `TargetPriceRule` edge-triggered using the persisted price history:

- `previous_price` = `PriceHistoryStore.get_latest(product_id)`, read before the
  current observation is recorded.
- `lowest_price` = `PriceHistoryStore.get_lowest(product_id)`, read before the
  current observation is recorded.

The rule notifies when the current price is at or below the target and at least
one of these holds:

1. no previous history exists (`previous_price is None`);
2. the previous price was above the target (a fresh crossing);
3. the current price is below the all-time lowest recorded price (a new low
   while already below target).

This keeps the rule silent while the price simply stays below target without
dropping to a new low, and while it rises within the below-target range.

`MonitorService` keeps its existing aggregation: it collects matching items and
calls `notifier.send()` once at the end, so deduplication only controls which
products appear in that single batch.

## Error handling

History reads are best-effort. If the store is unavailable or a read fails,
previous and lowest prices are treated as `None`, which errs toward notifying
rather than dropping a genuine alert. The local in-memory fallback has no
persistent history, so cross-run deduplication only applies when the
Postgres/Supabase history store is wired in.

## Scope

- `services/rule_engine.py` — extend `NotificationRule`, `TargetPriceRule`, and
  `RuleEngine` with `previous_price` and `lowest_price`.
- `services/monitor_service.py` — read previous/lowest before recording and pass
  them to the rule engine.
- Update `tests/test_rule_engine.py` and `tests/test_monitor_service.py`.

## Out of scope

- Time-based cooldowns or per-product suppression state beyond price history.
- Changing the multi-product aggregation mechanics.
