-- Product catalog table (replaces large inline JSON product arrays in company profiles)
-- Fresh installs: applied via SQLAlchemy create_all on startup.

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(64) NOT NULL,
    name VARCHAR(160) NOT NULL,
    description TEXT,
    price INTEGER,
    stock_status VARCHAR(32) DEFAULT 'in_stock',
    category VARCHAR(64),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_products_company_id ON products (company_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON products (company_id, category);
CREATE INDEX IF NOT EXISTS idx_products_active ON products (company_id, is_active);
