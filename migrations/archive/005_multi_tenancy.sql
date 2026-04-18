-- Migration: 005 Multi-Tenancy and User Profiles
-- Description: Adapts tables for multi-tenant isolation and user-specific webhooks.

-- Wipe legacy single-user data to allow strict constraints (Primary keys / Not Null)
TRUNCATE TABLE app_config CASCADE;
TRUNCATE TABLE rss_sources CASCADE;
TRUNCATE TABLE articles CASCADE;
TRUNCATE TABLE telemetry CASCADE;

-- 1. Create tenant_profiles table (linked to auth.users)
CREATE TABLE IF NOT EXISTS tenant_profiles (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    slack_webhook_url TEXT,
    discord_webhook_url TEXT,
    api_token TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trigger to auto-update updated_at on tenant_profiles
CREATE TRIGGER update_tenant_profiles_updated_at
    BEFORE UPDATE ON tenant_profiles
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- 2. Modify rss_sources
ALTER TABLE rss_sources ADD COLUMN user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;
-- Drop the existing unique constraint on just 'url'
ALTER TABLE rss_sources DROP CONSTRAINT IF EXISTS rss_sources_url_key;
-- Make it unique per user instead
ALTER TABLE rss_sources ADD CONSTRAINT rss_sources_url_userid_key UNIQUE (url, user_id);

-- 3. Modify app_config
-- Note: Re-creating app_config primary key requires dropping the old one
ALTER TABLE app_config DROP CONSTRAINT IF EXISTS app_config_pkey;
ALTER TABLE app_config ADD COLUMN user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;
ALTER TABLE app_config ADD PRIMARY KEY (key, user_id);

-- 4. Modify articles
ALTER TABLE articles ADD COLUMN user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;
-- Original unique constraint was just on source_url. Now an article is unique per user + source_url
ALTER TABLE articles DROP CONSTRAINT IF EXISTS articles_source_url_key;
ALTER TABLE articles ADD CONSTRAINT articles_source_url_userid_key UNIQUE (source_url, user_id);
CREATE INDEX IF NOT EXISTS idx_articles_user_id ON articles(user_id);

-- 5. Modify telemetry
ALTER TABLE telemetry ADD COLUMN user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_telemetry_user_id ON telemetry(user_id);

-- 6. Enable Row Level Security (RLS) base policies for safety (Optional but recommended)
-- For a SaaS, you typically enable RLS so clients can only read their data:
-- ALTER TABLE rss_sources ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY \"Users can view own sources\" ON rss_sources FOR SELECT USING (auth.uid() = user_id);
-- ... (RLS can be fully activated later based on the App's API route strategy)
