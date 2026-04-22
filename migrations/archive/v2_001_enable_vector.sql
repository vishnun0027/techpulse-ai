-- migrations/v2_001_enable_vector.sql

CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to articles table
ALTER TABLE articles
  ADD COLUMN IF NOT EXISTS embedding vector(768),
  ADD COLUMN IF NOT EXISTS novelty_score    float   DEFAULT 1.0,
  ADD COLUMN IF NOT EXISTS event_id         uuid,
  ADD COLUMN IF NOT EXISTS why_it_matters   text,
  ADD COLUMN IF NOT EXISTS source_quality   float   DEFAULT 0.5,
  ADD COLUMN IF NOT EXISTS v2_processed     boolean DEFAULT false;

-- HNSW index: faster lookup, supports live updates without rebuild
CREATE INDEX IF NOT EXISTS articles_embedding_hnsw
  ON articles
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
