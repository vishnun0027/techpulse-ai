-- migrations/v2_005_rpc_functions.sql

-- Semantic similarity search scoped per user
CREATE OR REPLACE FUNCTION match_articles(
  query_embedding  vector(768),
  match_threshold  float,
  match_count      int,
  p_user_id        uuid
)
RETURNS TABLE (
  id              uuid,
  title           text,
  summary         text,
  why_it_matters  text,
  published_at    timestamptz,
  similarity      float
)
LANGUAGE sql STABLE AS $$
  SELECT
    id, title, summary, why_it_matters, published_at,
    1 - (embedding <=> query_embedding) AS similarity
  FROM articles
  WHERE user_id       = p_user_id
    AND embedding     IS NOT NULL
    AND 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;

-- Near-duplicate check: returns true if a very similar article exists
CREATE OR REPLACE FUNCTION is_near_duplicate(
  query_embedding  vector(768),
  dup_threshold    float,
  p_user_id        uuid
)
RETURNS boolean
LANGUAGE sql STABLE AS $$
  SELECT EXISTS (
    SELECT 1 FROM articles
    WHERE user_id = p_user_id
      AND embedding IS NOT NULL
      AND 1 - (embedding <=> query_embedding) >= dup_threshold
  );
$$;

-- Recency-weighted similarity (fuses content similarity with freshness)
-- novelty = similarity_score * exp(-decay_rate * days_since_publication)
CREATE OR REPLACE FUNCTION match_articles_recency(
  query_embedding  vector(768),
  match_count      int,
  p_user_id        uuid,
  decay_rate       float DEFAULT 0.1
)
RETURNS TABLE (id uuid, title text, summary text, recency_score float)
LANGUAGE sql STABLE AS $$
  SELECT
    id, title, summary,
    (1 - (embedding <=> query_embedding))
      * exp(-decay_rate * EXTRACT(EPOCH FROM (now() - COALESCE(published_at, created_at))) / 86400)
    AS recency_score
  FROM articles
  WHERE user_id = p_user_id
    AND embedding IS NOT NULL
  ORDER BY recency_score DESC
  LIMIT match_count;
$$;

-- Match events by centroid similarity
CREATE OR REPLACE FUNCTION match_events_by_centroid(
  query_embedding  vector(768),
  threshold        float,
  p_user_id        uuid
)
RETURNS TABLE (id uuid, article_count int, similarity float)
LANGUAGE sql STABLE AS $$
  SELECT
    id, article_count,
    1 - (centroid_embedding <=> query_embedding) AS similarity
  FROM article_events
  WHERE user_id = p_user_id
    AND centroid_embedding IS NOT NULL
    AND 1 - (centroid_embedding <=> query_embedding) >= threshold
  ORDER BY similarity DESC
  LIMIT 5;
$$;
