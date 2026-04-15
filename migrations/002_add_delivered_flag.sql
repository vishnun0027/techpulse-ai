-- Add is_delivered column to track delivery status
ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_delivered BOOLEAN DEFAULT FALSE;

-- Index for efficient querying of non-delivered articles
CREATE INDEX IF NOT EXISTS idx_articles_is_delivered ON articles(is_delivered) WHERE is_delivered = FALSE;
