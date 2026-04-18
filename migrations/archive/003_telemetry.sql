-- Create telemetry table to track system metrics
CREATE TABLE IF NOT EXISTS telemetry (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service     TEXT NOT NULL, -- 'collector', 'summarizer', 'delivery'
    timestamp   TIMESTAMPTZ DEFAULT NOW(),
    metrics     JSONB NOT NULL,
    success     BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_telemetry_service ON telemetry(service);
CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry(timestamp DESC);
