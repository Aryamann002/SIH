-- Additive migration: preserves existing sessions, evaluations, OTPs and audits.
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS token_hash TEXT;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS generation UUID;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS latest_evaluation_id UUID;
ALTER TABLE risk_evaluations ALTER COLUMN score DROP NOT NULL;
ALTER TABLE risk_evaluations ADD COLUMN IF NOT EXISTS model_version TEXT NOT NULL DEFAULT 'unavailable';
ALTER TABLE risk_evaluations ADD COLUMN IF NOT EXISTS threshold_profile TEXT NOT NULL DEFAULT 'prototype-uncalibrated-v1';

CREATE TABLE IF NOT EXISTS protected_actions (
    action_id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions(session_id),
    action_type TEXT NOT NULL CHECK (action_type = 'fund_transfer'),
    payload JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'VERIFIED', 'COMPLETED', 'BLOCKED', 'EXPIRED')),
    risk_state TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    completed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS verification_challenges (
    challenge_id UUID PRIMARY KEY,
    action_id UUID NOT NULL UNIQUE REFERENCES protected_actions(action_id),
    code_hash TEXT NOT NULL,
    attempts INT NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'VERIFIED', 'EXPIRED', 'LOCKED')),
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS approval_tokens (
    action_id UUID PRIMARY KEY REFERENCES protected_actions(action_id),
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ
);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS action_id UUID REFERENCES protected_actions(action_id);
CREATE INDEX IF NOT EXISTS idx_actions_session ON protected_actions(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action_id);
