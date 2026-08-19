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
