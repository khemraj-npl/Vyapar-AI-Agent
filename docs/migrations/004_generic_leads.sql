-- Generic lead columns (ecommerce / services — replaces ISP-specific coverage/speed fields)
-- Fresh installs: applied via SQLAlchemy create_all on startup.
-- Existing Postgres: run this migration manually.

ALTER TABLE leads RENAME COLUMN requested_speed TO requested_item_or_service;
ALTER TABLE leads ALTER COLUMN requested_item_or_service TYPE VARCHAR(160);

ALTER TABLE leads RENAME COLUMN coverage_area TO delivery_or_service_location;
ALTER TABLE leads RENAME COLUMN coverage_status TO delivery_or_service_status;
ALTER TABLE leads RENAME COLUMN coverage_check_needed TO delivery_check_needed;

ALTER TABLE leads ADD COLUMN IF NOT EXISTS custom_signals TEXT;
