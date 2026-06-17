-- Phase 3 P0 patch: language lock + coverage mention tracking
ALTER TABLE conversation_state ADD COLUMN IF NOT EXISTS language_locked BOOLEAN DEFAULT FALSE;
ALTER TABLE conversation_state ADD COLUMN IF NOT EXISTS coverage_mention_count INTEGER DEFAULT 0;
