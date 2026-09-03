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

-- Migration
-- ---------------------------------------------------------------------------
-- Older databases predate the ``listings`` JSONB column and keyed price
-- history by ``product_id`` instead of ``listing_id``. ``CREATE TABLE IF NOT
-- EXISTS`` leaves those existing tables untouched, so upgrade them in place
-- before the indexes below are created.

DO $$
DECLARE
    fk_name text;
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'price_history'
          AND column_name = 'product_id'
    ) THEN
        ALTER TABLE price_history ADD COLUMN IF NOT EXISTS listing_id TEXT;

        UPDATE price_history ph
           SET listing_id = lower(p.site_name)
          FROM products p
         WHERE p.id = ph.product_id
           AND ph.listing_id IS NULL;

        UPDATE price_history
           SET listing_id = product_id
         WHERE listing_id IS NULL;

        ALTER TABLE price_history ALTER COLUMN listing_id SET NOT NULL;

        SELECT conname
          INTO fk_name
          FROM pg_constraint
         WHERE conrelid = to_regclass('price_history')
           AND contype = 'f'
           AND conname LIKE '%product_id%'
         LIMIT 1;

        IF fk_name IS NOT NULL THEN
            EXECUTE format('ALTER TABLE price_history DROP CONSTRAINT %I', fk_name);
        END IF;

        ALTER TABLE price_history DROP COLUMN IF EXISTS product_id;
        DROP INDEX IF EXISTS idx_price_history_product_observed;
        DROP INDEX IF EXISTS idx_price_history_product_value;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'products'
          AND column_name = 'url'
    ) THEN
        ALTER TABLE products ADD COLUMN IF NOT EXISTS listings JSONB NOT NULL DEFAULT '[]';

        UPDATE products
           SET listings = jsonb_build_array(
               jsonb_build_object(
                   'id', lower(site_name),
                   'site_name', site_name,
                   'site_base_url', site_base_url,
                   'site_default_headers', site_default_headers,
                   'url', url,
                   'price_selector', price_selector,
                   'parser_type', parser_type,
                   'json_variable', json_variable,
                   'price_path', price_path,
                   'currency_path', currency_path,
                   'currency', currency
               )
           )
         WHERE listings = '[]'::jsonb;

        ALTER TABLE products DROP COLUMN IF EXISTS site_name;
        ALTER TABLE products DROP COLUMN IF EXISTS site_base_url;
        ALTER TABLE products DROP COLUMN IF EXISTS site_default_headers;
        ALTER TABLE products DROP COLUMN IF EXISTS url;
        ALTER TABLE products DROP COLUMN IF EXISTS price_selector;
        ALTER TABLE products DROP COLUMN IF EXISTS parser_type;
        ALTER TABLE products DROP COLUMN IF EXISTS json_variable;
        ALTER TABLE products DROP COLUMN IF EXISTS price_path;
        ALTER TABLE products DROP COLUMN IF EXISTS currency_path;
    END IF;
END $$;

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