# Supabase/PostgreSQL Storage Design

**Date:** 2026-08-17
**Status:** Approved (specification)

## Goal

Replace the in-memory, hardcoded product catalog with a Supabase-hosted
PostgreSQL backend for both the product catalog and price history, while
preserving the existing Clean Architecture storage abstractions.

## Scope

This phase implements Postgres adapters for the existing `ProductStore` and
`PriceHistoryStore` interfaces. It does not implement notification
deduplication, migrations, or the cache store.

## Schema

```sql
CREATE TABLE IF NOT EXISTS products (
    id                   TEXT PRIMARY KEY,
    name                 TEXT NOT NULL,
    site_name            TEXT NOT NULL,
    site_base_url        TEXT,
    site_default_headers JSONB,
    url                  TEXT NOT NULL,
    price_selector       TEXT,
    brand                TEXT,
    category             TEXT,
    currency             TEXT NOT NULL DEFAULT 'AUD',
    enabled              BOOLEAN NOT NULL DEFAULT TRUE,
    target_price         NUMERIC,
    parser_type          TEXT NOT NULL DEFAULT 'css',
    json_variable        TEXT,
    price_path           TEXT,
    currency_path        TEXT,
    availability         TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS price_history (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id  TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    value       NUMERIC NOT NULL,
    currency    TEXT NOT NULL,
    raw_text    TEXT,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_price_history_product_observed
    ON price_history (product_id, observed_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_price_history_product_value
    ON price_history (product_id, value);
```

`price_selector` is nullable because products using `parser_type="embedded_json"`
do not require a CSS selector. The `json_variable`, `price_path`, and
`currency_path` columns support the embedded-JSON parser, including the current
Uniqlo product.

## Storage architecture

- `storage/base.py` keeps the existing `ProductStore` and `PriceHistoryStore`
  interfaces unchanged.
- `storage/postgres.py` adds `PostgresProductStore` and
  `PostgresPriceHistoryStore`.
- `ensure_schema(connection)` reads `scripts/schema.sql` as the single source
  of truth and executes it idempotently; it does not duplicate DDL.
- `scripts/seed_products.py` performs a one-time, idempotent upsert of the
  catalog from `data/products.py`.
- A future `NotificationStateStore` is additive and requires no changes to
  `products` or `price_history`.

## Supabase / GitHub Actions connection

GitHub-hosted runners are IPv4-only, so the app connects through the Supabase
Supavisor transaction-mode pooler rather than the IPv6-only direct endpoint:

```text
postgres://postgres.<project-ref>:<password>@aws-<region>.pooler.supabase.com:6543/postgres?sslmode=require
```

The full connection string is read from the `SUPABASE_DATABASE_URL` environment
variable. No Supabase hostname, username, password, or connection string is
hard-coded.

## psycopg connection requirements

- Dependency: `psycopg[binary]>=3.2`.
- `psycopg.connect(dsn, autocommit=True, prepare_threshold=None)`.
- `prepare_threshold=None` disables prepared statements, which transaction-mode
  pooling does not support.
- `autocommit=True` makes each single-statement write atomic and committed.
- `sslmode=require` is present in the DSN.
- The connection is single, sequential, and closed in `finally`.

## Security

`site_default_headers` may contain only non-sensitive HTTP headers. It must
never store `Authorization` headers, cookies, API keys, access tokens,
passwords, credentials, or session tokens. Sensitive request credentials come
from environment variables or GitHub Secrets and are injected at runtime.

The connection string lives only in the gitignored `.env` locally and in a
GitHub secret for Actions. It is never committed or logged.

## In scope

- Revised `scripts/schema.sql`.
- `storage/postgres.py` with both store adapters, mapping helpers, and
  `ensure_schema()`.
- `scripts/seed_products.py`.
- `SUPABASE_DATABASE_URL` configuration in `config/settings.py`.
- `psycopg[binary]>=3.2` in `pyproject.toml`.
- `app.py` wiring and `MonitorService` price-history recording.
- `.env.example` documentation.
- Unit tests for mapping, store methods, and history recording.

## Deferred

- Notification deduplication and `NotificationStateStore`.
- Alembic or other migration tooling.
- `CacheStore` usage.
- Dedicated period-low index.
- Database-level currency trigger.
- Dedicated pooler and Supabase network restrictions.
