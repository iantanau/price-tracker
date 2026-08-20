# Product Price Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let one logical product own multiple retailer listings, compare their current prices, and notify when the product's best price first reaches target or a new all-time low.

**Architecture:** Introduce `ProductListing` as the per-URL/parser unit, make `Product` the logical product owning `listings`, key price history by listing, and replace `MonitorService` with a comparison service that derives a product-level best price and reuses the existing edge-triggered `TargetPriceRule`.

**Tech Stack:** Python, pytest, BeautifulSoup, httpx, psycopg.

---

### Task 1: Domain model (`ProductListing` + `Product`)

**Files:**
- Create: `models/listing.py`
- Modify: `models/product.py`
- Modify: `tests/conftest.py`

`ProductListing`:

```python
@dataclass(frozen=True)
class ProductListing:
    id: str
    site: Site
    url: str
    price_selector: str = ""
    parser_type: str = "auto"
    json_variable: str | None = None
    price_path: str | None = None
    currency_path: str | None = None
    currency: str = "AUD"
```

`Product` keeps `id`, `name`, `brand`, `category`, `currency`, `enabled`,
`target_price`, `availability`, and future fields; replaces `site`, `url`,
`price_selector`, `parser_type`, `json_variable`, `price_path`, and
`currency_path` with `listings: list[ProductListing]`.

Update `base_product` in `tests/conftest.py` to return a product with one CSS
listing.

### Task 2: Parsers operate on listings

**Files:** `parsers/base.py`, `parsers/css_price_parser.py`,
`parsers/embedded_json_price_parser.py`, `parsers/json_ld_price_parser.py`,
`parsers/detector.py`, `parsers/dispatching_product_parser.py`, plus their tests.

Change `ProductParser.parse(content, product)` to
`parse(content, listing: ProductListing)` and read config from the listing.
`detect_parser_type(content, listing, available)` and
`DispatchingProductParser.parse(content, listing)` follow.

### Task 3: Monitor fetches listings

**Files:** `monitors/base.py`, `monitors/web_monitor.py`, `tests/test_web_monitor.py`.

Replace `fetch(product)` with `fetch_listing(listing: ProductListing)`; fetch
`listing.url` and parse `listing`.

### Task 4: Comparison service

**Files:** create `services/comparison_service.py`, `services/rule_engine.py`
(unchanged), `models/notification_payload.py`, tests.

For each enabled product:

1. Fetch every listing; collect successful listing prices.
2. Compute `current_best` = minimum listing price.
3. Read previous best and all-time low from listing history.
4. `rule_engine.should_notify(product, ParsedResult(price=current_best), previous_best, all_time_low)`.
5. On match, build a comparison item and send once at the end of the run.

Extend the notification payload to carry listing prices per product.

### Task 5: Per-listing price history + product store with listings

**Files:** `storage/base.py`, `storage/in_memory.py`, `storage/postgres.py`,
`scripts/schema.sql`, `scripts/seed_products.py`, `data/products.py`,
`tests/test_postgres.py`.

- Store `listings` as JSONB on `products`; drop per-URL columns.
- Key `price_history` by `listing_id` (keep `product_id` for grouping).
- `PriceHistoryStore` methods use `listing_id`.

### Task 6: Email comparison rendering

**Files:** `notifiers/email_notifier.py`, `tests/test_email_notifier.py`.

Render each product as a retailer list with current prices, mark the cheapest,
and show target/new-low context.

### Task 7: Composition

**Files:** `app.py`.

Wire `ComparisonService`, the product store with listings, and the email
notifier.

### Task 8: Full suite green

Run `pytest -q`; fix regressions until all tests pass.
