# Price Tracker

Price Tracker is an extensible, modular price intelligence platform written in Python. It monitors product prices on the web and sends alerts when prices meet your criteria.

This project is intentionally built as a framework, not a one-off script. Its layered architecture, dependency injection, and abstract component interfaces make it straightforward to add new parsers, notification channels, storage backends, and monitoring strategies without rewriting core logic.

> **Current scope:** Phase 1 MVP. The architecture is already designed to support future features such as historical price tracking, SQLite persistence, cashback and coupon handling, laptop specification filtering, ranking engines, and AI product matching.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Adding a Product](#adding-a-product)
- [Running Locally](#running-locally)
- [GitHub Actions](#github-actions)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [Design Philosophy](#design-philosophy)
- [License](#license)

## Features

### Implemented in Phase 1

- **Monitor product prices from websites** — run scheduled or on-demand checks against live product pages.
- **CSS selector based extraction** — extract prices from HTML using per-product CSS selectors.
- **Configurable target prices** — only notify when the current price drops to or below a threshold.
- **Email notifications** — send alerts via SMTP with support for SSL, STARTTLS, and unencrypted transports.
- **GitHub Actions compatible** — run the monitor on a schedule or on demand from GitHub Actions without changing application code.
- **Clean Architecture** — clear boundaries between domain, application, and infrastructure concerns.
- **SOLID principles** — small, focused components with single responsibilities.
- **Dependency Injection** — components are wired together in `app.py`, not hidden inside modules.
- **Extensible parser architecture** — add JSON, XPath, or regex parsers without touching the monitor.
- **Extensible notifier architecture** — add Telegram, Discord, Slack, ServerChan, or other channels without touching business logic.
- **Future-ready domain model** — the `Product` model supports future fields such as CPU, GPU, RAM, SSD, cashback, coupon, and shipping.

## Architecture

The project follows Clean Architecture and the SOLID principles. Domain models live at the center; infrastructure concerns such as HTTP clients, email delivery, and storage are pushed to the edges behind abstract interfaces. This makes the system easy to test, extend, and maintain.

### Runtime Data Flow

```
ProductStore
    ↓
Product
    ↓
Monitor.fetch(Product)
    ↓
HttpClient.get(Product.url)
    ↓
Parser.parse(HttpResponse.content, Product)
    ↓
ParsedResult
    ↓
RuleEngine.should_notify(Product, ParsedResult)
    ↓
Notifier.send(NotificationPayload)
```

### Responsibility of Each Layer

| Layer | Responsibility |
|-------|----------------|
| `Product` | Domain object that describes what to monitor and how. Contains the URL, CSS selector, currency, target price, and future catalog fields. |
| `ProductStore` | Loads and persists products. Phase 1 uses an in-memory store seeded from `data/products.py`; future phases will support SQLite and other backends. |
| `Monitor` | Retrieves current information for a product. It coordinates the HTTP client and parser but contains no business rules. |
| `HttpClient` | Fetches raw content from the web. The current implementation uses `httpx`; it can be replaced with `requests`, Playwright, or a test double. |
| `Parser` | Extracts structured data from raw content. Phase 1 implements CSS selector parsing; future parsers can handle JSON, XPath, or regex. |
| `RuleEngine` | Decides whether a notification should fire. Phase 1 includes a target-price rule; additional rules can be added without changing the service. |
| `Notifier` | Delivers messages through a specific channel. Phase 1 implements email; additional channels can be added behind the same interface. |

### Composition Root

All concrete implementations are wired together in `app.py`, the composition root. Changing a database, HTTP library, or notification provider requires editing only `app.py`, not the business logic.

```python
# app.py
http_client = HttpxClient(settings)
parser = CssPriceParser()
monitor = WebMonitor(client=http_client, parser=parser)
rule_engine = RuleEngine(rules=[TargetPriceRule()])
notifier = EmailNotifier(settings)

service = MonitorService(
    product_store=product_store,
    monitor=monitor,
    rule_engine=rule_engine,
    notifier=notifier,
)
```

## Project Structure

- `app.py` — Application entry point and composition root.
- `clients/` — HTTP client abstraction and implementations.
- `config/` — Centralised settings loaded from environment variables.
- `data/` — Seed product catalog.
- `models/` — Domain models and value objects.
- `monitors/` — Product monitor abstraction.
- `notifiers/` — Notification channel abstraction.
- `parsers/` — Content extraction abstraction.
- `services/` — Application services and notification rules.
- `storage/` — Storage abstraction for products, price history, and caching.
- `tests/` — Test suite location.
- `utils/` — Shared utilities such as structured logging.

## Installation

Requires Python 3.11 or newer.

```bash
# Clone the repository
git clone https://github.com/yourusername/price-tracker.git
cd price-tracker

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate

# Install the package and its dependencies
pip install -e .

# Or install with development dependencies (pytest, coverage, etc.)
pip install -e ".[dev]"
```

## Configuration

Copy the example environment file and fill in your own values:

```bash
cp .env.example .env
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SMTP_HOST` | Yes* | — | SMTP server hostname, e.g. `smtp.gmail.com`. |
| `SMTP_PORT` | No | `587` | SMTP server port. Common values: `25` (none), `587` (STARTTLS), `465` (SSL). |
| `SMTP_SECURITY` | No | `STARTTLS` | Transport security. Allowed values: `SSL`, `STARTTLS`, `NONE`. |
| `SMTP_USERNAME` | Yes* | — | SMTP authentication username. Often your full email address. |
| `SMTP_PASSWORD` | Yes* | — | SMTP authentication password or app-specific token. |
| `SMTP_FROM` | Yes* | — | From email address used in outgoing alerts. |
| `SMTP_TO` | Yes* | — | Comma-separated list of recipient email addresses. |
| `HTTP_TIMEOUT` | No | `30` | Request timeout in seconds. |
| `HTTP_RETRIES` | No | `3` | Number of retries for failed HTTP requests. |
| `HTTP_USER_AGENT` | No | `PriceTracker/0.1.0` | User-Agent header sent with every request. |
| `HTTP_HEADERS` | No | `{}` | Additional HTTP headers as a JSON object. |
| `LOG_LEVEL` | No | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. |

\* Required only if you want email notifications. The application will run without SMTP settings, but no alerts will be delivered.

Products are defined in `data/products.py`. Each product specifies its URL, CSS selector, currency, target price, and whether it is enabled.

## Adding a Product

Products are defined as Python objects in `data/products.py`. This gives you IDE autocomplete, type checking, and version control over your catalog.

Open `data/products.py` and add a new `Product` entry:

```python
from decimal import Decimal
from models.listing import ProductListing
from models.product import Product
from models.site import Site

PRODUCTS: list[Product] = [
    Product(
        id="dell-xps-15-001",
        name="Dell XPS 15",
        brand="Dell",
        category="laptops",
        currency="AUD",
        enabled=True,
        target_price=Decimal("2499.00"),
        listings=[
            ProductListing(
                id="dell-au",
                site=Site(name="Dell Australia"),
                url="https://www.dell.com/en-au/shop/laptops/xps-15/spd/xps-15-9530-laptop",
                price_selector=".ps-dell-price",
                currency="AUD",
            ),
        ],
    ),
]
```

### Product Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Stable unique identifier for the product. |
| `name` | Yes | Human-readable product name. |
| `listings` | Yes | One or more `ProductListing` objects, each with a `site`, `url`, and parser config. |
| `brand` | No | Product brand, e.g. `Dell`, `Apple`. |
| `category` | No | Product category, e.g. `laptops`, `monitors`. |
| `currency` | No | ISO 4217 currency code. Defaults to `AUD`. |
| `enabled` | No | Whether the product should be monitored. Defaults to `True`. |
| `target_price` | No | Notification fires when the best listing price is less than or equal to this value. |

### Why Manual CSS Selectors?

CSS selectors are configured manually per product for maximum reliability. Automatic selectors are fragile: a site redesign, A/B test, or JavaScript framework change can break generic extraction. Manual selectors let you choose the exact element that represents the current price and are easy to update when a site changes.

To find a selector in your browser:

1. Open the product page.
2. Right-click the price and choose **Inspect**.
3. Right-click the element in the DevTools panel and choose **Copy → Copy selector**.
4. Paste the selector into `price_selector`.

## Running Locally

Run a single monitoring pass:

```bash
python app.py
```

The application will:

1. Load enabled products from the product store.
2. Fetch each product page using the configured HTTP client.
3. Extract the current price using the product's CSS selector.
4. Evaluate notification rules against the observed price.
5. Send email alerts for products that match the rules.

If one product fails, the application logs the error and continues monitoring the rest.

Example output:

```text
2024-01-15 09:00:00 - price_tracker.services.monitor_service - INFO - Starting monitoring pass
2024-01-15 09:00:01 - price_tracker.services.monitor_service - INFO - Loaded 2 enabled product(s)
2024-01-15 09:00:02 - price_tracker.services.monitor_service - INFO - Notification sent for product dell-xps-15-001
2024-01-15 09:00:03 - price_tracker.services.monitor_service - INFO - Monitoring pass complete: 1 notification(s), 0 failure(s)
```

## GitHub Actions

No application code depends on GitHub Actions. The application is executed simply by running:

```bash
python app.py
```

A GitHub Actions workflow can run this command on demand or on a schedule.

### Workflow Dispatch

Use `workflow_dispatch` to trigger a manual run from the GitHub UI:

```yaml
on:
  workflow_dispatch:
```

### Scheduled Runs

Use `schedule` with cron syntax to run the monitor periodically:

```yaml
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
```

### Required GitHub Secrets

Add the following secrets in **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `SMTP_HOST` | SMTP server hostname. |
| `SMTP_USERNAME` | SMTP authentication username. |
| `SMTP_PASSWORD` | SMTP authentication password or app token. |
| `SMTP_FROM` | From email address. |
| `SMTP_TO` | Comma-separated list of recipient addresses. |

Optional secrets such as `SMTP_PORT`, `SMTP_SECURITY`, `HTTP_USER_AGENT`, `HTTP_TIMEOUT`, `HTTP_RETRIES`, and `LOG_LEVEL` can be exposed as repository variables if needed.

### Example Monitor Workflow

```yaml
name: Monitor Prices

on:
  workflow_dispatch:
  schedule:
    - cron: '0 */6 * * *'

jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e .
      - run: python app.py
        env:
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_USERNAME: ${{ secrets.SMTP_USERNAME }}
          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
          SMTP_FROM: ${{ secrets.SMTP_FROM }}
          SMTP_TO: ${{ secrets.SMTP_TO }}
          SMTP_SECURITY: ${{ vars.SMTP_SECURITY }}
          LOG_LEVEL: ${{ vars.LOG_LEVEL }}
```

A CI workflow for tests is already included under `.github/workflows/ci.yml`.

## Testing

Run the test suite with pytest:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov
```

The project is structured so that every component can be unit tested in isolation by injecting test doubles for HTTP clients, parsers, notifiers, and stores.

## Roadmap

### Phase 1 — Implemented

- CSS selector parser.
- Email notifications via SMTP.
- Clean Architecture with abstract component interfaces.
- In-memory product store.
- Target price notification rule.
- GitHub Actions compatibility.

### Phase 2 — Planned

- SQLite storage backend.
- Price history tracking and retrieval.
- JSON parser for API-driven product pages.
- XPath parser for pages where CSS selectors are insufficient.
- Playwright-backed HTTP client for JavaScript-rendered pages.
- Telegram notifications.
- ServerChan notifications.
- WeChat notifications.

### Phase 3 — Future Goals

- Cashback and coupon integration.
- OzBargain deal aggregation and matching.
- AI product matching across retailers.
- Laptop specification comparison (CPU, GPU, RAM, SSD).
- Automatic lowest-price ranking engine.
- Dashboard for visualising price history.
- Web UI for managing products and settings.

## Design Philosophy

This project uses established software design patterns to stay maintainable as it grows.

### SOLID

Each module has a single responsibility. Monitors fetch prices, parsers extract data, notifiers deliver messages, and services coordinate workflow. Interfaces are small and focused, and dependencies point toward abstractions.

### Dependency Injection

Concrete implementations are supplied to components from the outside rather than created inside them. For example, `WebMonitor` receives an `HttpClient` and a `ProductParser` through its constructor. This makes components easy to test and swap.

### Composition Root

`app.py` is the single place where the application is assembled. Changing the database, HTTP library, parser, or notifier requires editing only the composition root, not the business logic.

### Strategy Pattern

Parsers, notifiers, HTTP clients, and storage backends are interchangeable strategies. You can add a `TelegramNotifier` or `JsonPriceParser` by implementing the relevant interface and selecting it in `app.py`.

### Repository Pattern

`ProductStore` and `PriceHistoryStore` abstract persistence. The rest of the application does not know whether products are stored in memory, JSON files, SQLite, or a remote database.

### Rule Engine

Notification decisions are delegated to a `RuleEngine` composed of individual rules. Adding a "notify on restock" rule or a "notify on percentage drop" rule does not require changes to the monitor service.

These patterns together mean that new features can be added by introducing new implementations of existing interfaces, not by refactoring the core.

## License

This project is open source and available under the [MIT License](LICENSE).
