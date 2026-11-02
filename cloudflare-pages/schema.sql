-- GSHER Podcast Studio / Cloudflare D1. Run against remote D1 before public use.
CREATE TABLE IF NOT EXISTS episodes (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, series TEXT DEFAULT 'GSHER Conversations',
  language TEXT DEFAULT 'en', episode_date TEXT, description TEXT DEFAULT '',
  transcript TEXT DEFAULT '', status TEXT DEFAULT 'draft', media_name TEXT,
  media_kind TEXT, cover_name TEXT, speakers TEXT DEFAULT '[]',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_episodes_status_date ON episodes(status,episode_date DESC);
CREATE TABLE IF NOT EXISTS upload_sessions (
  id TEXT PRIMARY KEY, episode_id TEXT NOT NULL, r2_key TEXT NOT NULL,
  r2_upload_id TEXT NOT NULL, size_bytes INTEGER NOT NULL, created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_uploads_episode ON upload_sessions(episode_id);
CREATE TABLE IF NOT EXISTS login_attempts (
  ip_hash TEXT PRIMARY KEY, count INTEGER NOT NULL, first_at INTEGER NOT NULL
);
