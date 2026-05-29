-- ──────────────────────────────────────────────
--  Gmail AI Agent  –  Supabase SQL Schema
--  Paste and run this in Supabase SQL Editor
-- ──────────────────────────────────────────────

-- Users
CREATE TABLE IF NOT EXISTS users (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email            TEXT UNIQUE NOT NULL,
    name             TEXT,
    telegram_chat_id TEXT,
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now()
);

-- OAuth Tokens
CREATE TABLE IF NOT EXISTS oauth_tokens (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_email    TEXT UNIQUE REFERENCES users(email) ON DELETE CASCADE,
    access_token  TEXT,
    refresh_token TEXT,
    token_expiry  TIMESTAMPTZ,
    updated_at    TIMESTAMPTZ DEFAULT now()
);

-- Emails
CREATE TABLE IF NOT EXISTS emails (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id        TEXT UNIQUE NOT NULL,
    thread_id         TEXT,
    sender            TEXT,
    sender_name       TEXT,
    subject           TEXT,
    body_preview      TEXT,
    received_at       TIMESTAMPTZ,
    is_important      BOOLEAN DEFAULT FALSE,
    importance_score  INTEGER DEFAULT 0,
    urgency           TEXT,
    category          TEXT,
    summary           TEXT,
    action_required   BOOLEAN DEFAULT FALSE,
    reason            TEXT,
    deadline_detected BOOLEAN DEFAULT FALSE,
    deadline          TEXT,
    has_attachments   BOOLEAN DEFAULT FALSE,
    labels            TEXT[],
    created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS emails_received_at_idx  ON emails(received_at DESC);
CREATE INDEX IF NOT EXISTS emails_is_important_idx ON emails(is_important);
CREATE INDEX IF NOT EXISTS emails_message_id_idx   ON emails(message_id);

-- Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id          TEXT REFERENCES emails(message_id) ON DELETE CASCADE,
    telegram_chat_id    TEXT,
    telegram_message_id BIGINT,
    sent_at             TIMESTAMPTZ DEFAULT now()
);

-- Groups
CREATE TABLE IF NOT EXISTS groups (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Group Members
CREATE TABLE IF NOT EXISTS group_members (
    id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
    email    TEXT NOT NULL,
    name     TEXT,
    UNIQUE(group_id, email)
);
