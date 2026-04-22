-- migrations/v2_006_telemetry_rpc.sql

-- Atomic increment for source ingestion counts
CREATE OR REPLACE FUNCTION increment_source_ingestion(p_source_id bigint, p_user_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    INSERT INTO source_health (source_id, user_id, articles_ingested)
    VALUES (p_source_id, p_user_id, 1)
    ON CONFLICT (source_id, user_id)
    DO UPDATE SET 
        articles_ingested = source_health.articles_ingested + 1,
        last_ingested_at = now();
END;
$$;
