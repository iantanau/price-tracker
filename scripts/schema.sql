CREATE TABLE IF NOT EXISTS products (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    brand         TEXT,
    category      TEXT,
    currency      TEXT NOT NULL DEFAULT 'AUD',
    enabled       BOOLEAN NOT NULL DEFAULT TRUE,
    target_price  NUMERIC,
    availability  TEXT,
    listings      JSONB NOT NULL DEFAULT '[]',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS price_history (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    listing_id   TEXT NOT NULL,
    value        NUMERIC NOT NULL,
    currency     TEXT NOT NULL,
    raw_text     TEXT,
    observed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_price_history_listing_observed
    ON price_history (listing_id, observed_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_price_history_listing_value
    ON price_history (listing_id, value);
