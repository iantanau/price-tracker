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

-- Security
-- ---------------------------------------------------------------------------
-- The application connects directly with the Supabase service credential
-- (the ``postgres`` role), which bypasses row level security. The Supabase
-- REST API, on the other hand, uses the ``anon`` and ``authenticated`` roles,
-- which must never be able to read or modify these tables.
--
-- Enabling RLS without granting those roles a policy denies them by default,
-- and the explicit ``service_role`` policies below keep the intent
-- self-documenting (and satisfy Supabase's "RLS enabled, no policy" lint).

ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "products: service_role full access" ON products;
CREATE POLICY "products: service_role full access"
    ON products
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS "price_history: service_role full access" ON price_history;
CREATE POLICY "price_history: service_role full access"
    ON price_history
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
