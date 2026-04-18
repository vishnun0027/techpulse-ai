ALTER TABLE articles ADD COLUMN IF NOT EXISTS score  FLOAT  DEFAULT 0.0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS topics TEXT[] DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_articles_score      ON articles(score DESC);
CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at DESC);
