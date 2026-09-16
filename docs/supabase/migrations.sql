-- Run these in Supabase SQL editor (once, in order)

-- 1. Read tracking (which chapters a user has read per manga)
CREATE TABLE IF NOT EXISTS read_tracking (
  user_id     VARCHAR NOT NULL,
  provider    VARCHAR NOT NULL,
  manga_id    VARCHAR NOT NULL,
  chapter_ids JSONB NOT NULL DEFAULT '[]',
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, provider, manga_id)
);
ALTER TABLE read_tracking ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users own read_tracking" ON read_tracking
  USING (auth.uid()::text = user_id)
  WITH CHECK (auth.uid()::text = user_id);

-- 2. Category assignments (custom categories + per-manga assignments)
CREATE TABLE IF NOT EXISTS user_categories (
  user_id            VARCHAR NOT NULL PRIMARY KEY,
  custom_categories  JSONB NOT NULL DEFAULT '[]',
  manga_assignments  JSONB NOT NULL DEFAULT '{}',
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE user_categories ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users own user_categories" ON user_categories
  USING (auth.uid()::text = user_id)
  WITH CHECK (auth.uid()::text = user_id);

-- 3. Manga notes and ratings
CREATE TABLE IF NOT EXISTS manga_notes (
  user_id    VARCHAR NOT NULL,
  provider   VARCHAR NOT NULL,
  manga_id   VARCHAR NOT NULL,
  note       TEXT NOT NULL DEFAULT '',
  rating     INTEGER NOT NULL DEFAULT 0 CHECK (rating >= 0 AND rating <= 5),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, provider, manga_id)
);
ALTER TABLE manga_notes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users own manga_notes" ON manga_notes
  USING (auth.uid()::text = user_id)
  WITH CHECK (auth.uid()::text = user_id);

-- 4. Manga metadata overrides
CREATE TABLE IF NOT EXISTS manga_overrides (
  user_id     VARCHAR NOT NULL,
  provider    VARCHAR NOT NULL,
  manga_id    VARCHAR NOT NULL,
  title       VARCHAR,
  cover_url   VARCHAR,
  description TEXT,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, provider, manga_id)
);
ALTER TABLE manga_overrides ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users own manga_overrides" ON manga_overrides
  USING (auth.uid()::text = user_id)
  WITH CHECK (auth.uid()::text = user_id);

