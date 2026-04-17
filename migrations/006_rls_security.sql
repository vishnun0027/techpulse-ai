-- Migration: 006 Row Level Security (RLS)
-- Description: Locks down all tables so the browser-based client can safely query data.

-- 1. Enable RLS on all tenant-facing tables
ALTER TABLE tenant_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE rss_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry ENABLE ROW LEVEL SECURITY;

-- 2. tenant_profiles Policies
CREATE POLICY "Users can view own profile" 
ON tenant_profiles FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own profile" 
ON tenant_profiles FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own profile" 
ON tenant_profiles FOR UPDATE USING (auth.uid() = user_id);

-- 3. app_config Policies
CREATE POLICY "Users can view own config" 
ON app_config FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own config" 
ON app_config FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own config" 
ON app_config FOR UPDATE USING (auth.uid() = user_id);

-- 4. rss_sources Policies
CREATE POLICY "Users can view own sources" 
ON rss_sources FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own sources" 
ON rss_sources FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own sources" 
ON rss_sources FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own sources" 
ON rss_sources FOR DELETE USING (auth.uid() = user_id);

-- 5. articles Policies
-- Users only need to SELECT articles on the frontend
CREATE POLICY "Users can view own articles" 
ON articles FOR SELECT USING (auth.uid() = user_id);

-- 6. telemetry Policies
-- Users only need to SELECT their telemetry on the frontend
CREATE POLICY "Users can view own telemetry" 
ON telemetry FOR SELECT USING (auth.uid() = user_id);

-- Note: The Python backend services bypass RLS because they use the SUPABASE_KEY (Service Role Key)
-- which naturally overrides Row Level Security.
