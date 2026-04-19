-- Migration 009: Add fingerprinting for Smart Refresh (ETags)
ALTER TABLE rss_sources 
ADD COLUMN IF NOT EXISTS etag TEXT,
ADD COLUMN IF NOT EXISTS last_modified TEXT;

-- Add comments for documentation
COMMENT ON COLUMN rss_sources.etag IS 'HTTP ETag of the last successful fetch';
COMMENT ON COLUMN rss_sources.last_modified IS 'HTTP Last-Modified header of the last successful fetch';
