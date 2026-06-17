-- Multi-tenant channel credentials (Telegram + Facebook Messenger)
-- Applied automatically via SQLAlchemy create_all on startup.
-- Run manually on existing Postgres deployments if create_all already ran before this model existed.

CREATE TABLE IF NOT EXISTS tenants (
    company_id VARCHAR(64) NOT NULL PRIMARY KEY,
    telegram_bot_token VARCHAR(255),
    telegram_bot_username VARCHAR(64),
    telegram_webhook_secret VARCHAR(128),
    fb_page_id VARCHAR(64),
    fb_access_token VARCHAR(512),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tenants_fb_page_id
    ON tenants (fb_page_id)
    WHERE fb_page_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_tenants_telegram_bot_username
    ON tenants (telegram_bot_username)
    WHERE telegram_bot_username IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_tenants_telegram_webhook_secret
    ON tenants (telegram_webhook_secret)
    WHERE telegram_webhook_secret IS NOT NULL;
