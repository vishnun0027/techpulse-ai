-- TechPulse V2 Master Migration
-- Consolidates all necessary schema changes for V2

-- 1. Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Update articles table
ALTER TABLE articles
  ADD COLUMN IF NOT EXISTS embedding vector(768),
  ADD COLUMN IF NOT EXISTS novelty_score    float   DEFAULT 1.0,
  ADD COLUMN IF NOT EXISTS event_id         uuid,
  ADD COLUMN IF NOT EXISTS why_it_matters   text,
  ADD COLUMN IF NOT EXISTS source_quality   float   DEFAULT 0.5,
  ADD COLUMN IF NOT EXISTS v2_processed     boolean DEFAULT false;

CREATE INDEX IF NOT EXISTS articles_embedding_hnsw
  ON articles
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- 3. Create article_events table
CREATE TABLE IF NOT EXISTS article_events (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  title       text NOT NULL,
  theme       text,
  first_seen  timestamptz NOT NULL DEFAULT now(),
  last_updated timestamptz NOT NULL DEFAULT now(),
  article_count int DEFAULT 1,
  centroid_embedding vector(768)
);

ALTER TABLE article_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "user_events" ON article_events FOR ALL USING (auth.uid() = user_id);

ALTER TABLE articles ADD CONSTRAINT fk_event FOREIGN KEY (event_id) REFERENCES article_events(id) ON DELETE SET NULL;

-- 4. Create user_feedback table
CREATE TABLE IF NOT EXISTS user_feedback (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  article_id  uuid NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  signal      text NOT NULL CHECK (signal IN ('clicked','saved','dismissed','more_like_this','less_like_this')),
  created_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE user_feedback ENABLE ROW LEVEL SECURITY;
CREATE POLICY "user_feedback_policy" ON user_feedback FOR ALL USING (auth.uid() = user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_user_signal ON user_feedback(user_id, signal);

-- 5. Create source_health table
CREATE TABLE IF NOT EXISTS source_health (
  source_id         bigint NOT NULL REFERENCES rss_sources(id) ON DELETE CASCADE,
  user_id           uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  articles_ingested int  DEFAULT 0,
  articles_delivered int DEFAULT 0,
  articles_clicked  int  DEFAULT 0,
  duplicate_rate    float DEFAULT 0.0,
  quality_score     float DEFAULT 0.5,
  last_updated      timestamptz DEFAULT now(),
  PRIMARY KEY (source_id, user_id)
);

-- 6. RPC Functions
CREATE OR REPLACE FUNCTION match_articles(query_embedding vector(768), match_threshold float, match_count int, p_user_id uuid)
RETURNS TABLE (id uuid, title text, summary text, why_it_matters text, published_at timestamptz, similarity float)
LANGUAGE sql STABLE AS $$
  SELECT id, title, summary, why_it_matters, published_at, 1 - (embedding <=> query_embedding) AS similarity
  FROM articles
  WHERE user_id = p_user_id AND embedding IS NOT NULL AND 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY embedding <=> query_embedding LIMIT match_count;
$$;

CREATE OR REPLACE FUNCTION is_near_duplicate(query_embedding vector(768), dup_threshold float, p_user_id uuid)
RETURNS boolean LANGUAGE sql STABLE AS $$
  SELECT EXISTS (SELECT 1 FROM articles WHERE user_id = p_user_id AND embedding IS NOT NULL AND 1 - (embedding <=> query_embedding) >= dup_threshold);
$$;

CREATE OR REPLACE FUNCTION match_articles_recency(query_embedding vector(768), match_count int, p_user_id uuid, decay_rate float DEFAULT 0.1)
RETURNS TABLE (id uuid, title text, summary text, recency_score float) LANGUAGE sql STABLE AS $$
  SELECT id, title, summary, (1 - (embedding <=> query_embedding)) * exp(-decay_rate * EXTRACT(EPOCH FROM (now() - COALESCE(published_at, created_at))) / 86400) AS recency_score
  FROM articles WHERE user_id = p_user_id AND embedding IS NOT NULL
  ORDER BY recency_score DESC LIMIT match_count;
$$;

CREATE OR REPLACE FUNCTION match_events_by_centroid(query_embedding vector(768), threshold float, p_user_id uuid)
RETURNS TABLE (id uuid, article_count int, similarity float) LANGUAGE sql STABLE AS $$
  SELECT id, article_count, 1 - (centroid_embedding <=> query_embedding) AS similarity
  FROM article_events WHERE user_id = p_user_id AND centroid_embedding IS NOT NULL AND 1 - (centroid_embedding <=> query_embedding) >= threshold
  ORDER BY similarity DESC LIMIT 5;
$$;
