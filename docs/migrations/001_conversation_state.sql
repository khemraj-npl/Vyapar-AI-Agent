-- Phase 3 P0: conversation_state table
-- Applied automatically via SQLAlchemy create_all on startup (init_db).
-- Run manually on existing Postgres deployments if create_all already ran before this model existed.

CREATE TABLE IF NOT EXISTS conversation_state (
    user_id VARCHAR(64) NOT NULL,
    company_id VARCHAR(64) NOT NULL,
    language VARCHAR(16),
    name VARCHAR(120),
    phone VARCHAR(32),
    location VARCHAR(160),
    package_interest VARCHAR(160),
    lead_stage VARCHAR(32),
    pitch_count INTEGER DEFAULT 0,
    phone_collected BOOLEAN DEFAULT FALSE,
    escalation_requested BOOLEAN DEFAULT FALSE,
    last_assistant_reply TEXT,
    turn_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, company_id)
);

CREATE INDEX IF NOT EXISTS idx_conversation_state_company
    ON conversation_state (company_id);
