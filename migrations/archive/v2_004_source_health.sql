-- migrations/v2_004_source_health.sql

CREATE TABLE IF NOT EXISTS source_health (
  source_id         bigint NOT NULL REFERENCES rss_sources(id) ON DELETE CASCADE,
  user_id           uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  articles_ingested int  DEFAULT 0,
  articles_delivered int DEFAULT 0,
  articles_clicked  int  DEFAULT 0,
  duplicate_rate    float DEFAULT 0.0,   -- fraction of near-duplicates produced
  quality_score     float DEFAULT 0.5,   -- derived: clicked / delivered
  last_updated      timestamptz DEFAULT now(),
  PRIMARY KEY (source_id, user_id)
);
