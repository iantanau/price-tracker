# Product Price Comparison Design

**Date:** 2026-08-20
**Status:** Draft for review

## Goal

Compare the same product across several retailer pages the user provides,
without automatic product matching. The program fetches each listing's price
and alerts when the product's best price drops to or below target, or reaches a
new all-time low.

## Problem

`Product` currently represents a single URL on a single site. There is no way
to associate several listings (URLs) with one logical product and compare them.

## Design

### Domain model

Introduce a `ProductListing` value object:

```python
@dataclass(frozen=True)
class ProductListing:
    site: Site
    url: str
    price_selector: str = ""
    parser_type: str = "auto"
    json_variable: str | None = None
    price_path: str | None = None
    currency_path: str | None = None
```

`Product` becomes the logical product:

- keeps `id`, `name`, `brand`, `category`, `currency`, `enabled`, `target_price`
- replaces its single-URL/parser fields with `listings: list[ProductListing]`

Each existing single-listing product migrates to one `ProductListing`. This
keeps the per-URL parser configuration intact while allowing multiple listings.

### Data flow

1. A comparison service loads enabled products.
2. For each product, it fetches and parses every listing, reusing `WebMonitor`
   and `DispatchingProductParser` (whose parser config now comes from the
   listing rather than the product).
3. Each successful listing price is recorded in history keyed by
   `(product_id, listing_key)`, where `listing_key` is derived from the site
   and URL.
4. Product-level values are derived:
   - `current_best` = minimum current price across listings
   - `previous_best` = minimum previous-run price across listings
   - `all_time_low` = minimum price across all listing histories
5. The alert rule below is evaluated on `current_best`.
6. When it fires, one comparison report is rendered and sent via the notifier.

### Alert rule (edge-triggered, product level)

Notify when:

- `current_best <= target_price` **and** (`previous_best is None` **or**
  `previous_best > target_price`) — the first crossing into target; or
- `current_best < all_time_low` — a new all-time low for the product.

This generalises the existing `TargetPriceRule` deduplication semantics to the
product's best price. "All-time low" is product-wide across listings, not
per-site.

### Output

- Email: one comparison per fired product, listing every retailer with its
  current price, marking the cheapest, and showing target/new-low context.
- Later: a standalone on-demand `python compare.py` for a plain-text comparison
  of all products.

## Error handling

- A listing that fails to fetch or parse is skipped and logged; the product's
  comparison still runs for the remaining listings.
- History reads remain best-effort and fail toward notifying when unavailable,
  matching the existing deduplication behavior.

## Scope

- Domain refactor: `Product` + new `ProductListing`.
- Comparison service and product-level alert rule.
- Per-listing price history in storage.
- Email comparison rendering.
- Composition in `app.py`.
- Tests for new and changed components.

## Out of scope

- Automatic cross-site product matching (the user supplies URLs).
- Multi-currency conversion (one currency per product assumed).
- Dashboard / web UI.
