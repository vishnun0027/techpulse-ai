-- Add theme column for AI-driven categorization
ALTER TABLE articles ADD COLUMN IF NOT EXISTS theme TEXT;

-- Index for delivery grouping optimization
CREATE INDEX IF NOT EXISTS idx_articles_theme ON articles(theme);
