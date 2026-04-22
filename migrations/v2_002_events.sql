-- migrations/v2_002_events.sql

CREATE TABLE IF NOT EXISTS article_events (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  title       text NOT NULL,             -- LLM-generated event title
  theme       text,                      -- e.g. "Generative AI", "Regulation"
  first_seen  timestamptz NOT NULL DEFAULT now(),
  last_updated timestamptz NOT NULL DEFAULT now(),
  article_count int DEFAULT 1,
  centroid_embedding vector(768),        -- mean of all member article embeddings
  CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES auth.users(id)
);

-- RLS: users only see their own events
ALTER TABLE article_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "user_events" ON article_events
  FOR ALL USING (auth.uid() = user_id);

-- Link articles to events
ALTER TABLE articles
  ADD CONSTRAINT fk_event
  FOREIGN KEY (event_id) REFERENCES article_events(id) ON DELETE SET NULL;
