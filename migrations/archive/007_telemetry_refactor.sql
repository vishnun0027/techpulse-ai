-- Migration: 007 Telemetry Refactor
-- Description: Adds flat columns for metric names and values to support UI 2.0 spec.

-- 1. Add new columns
ALTER TABLE telemetry 
ADD COLUMN IF NOT EXISTS metric_name TEXT,
ADD COLUMN IF NOT EXISTS value FLOAT8;

-- 2. Create index for faster visualization queries
CREATE INDEX IF NOT EXISTS idx_telemetry_metric_name ON telemetry(metric_name);

-- Note: We keep the original 'metrics' JSONB column for backward compatibility 
-- with older telemetry logs not yet migrated to the flat structure.
