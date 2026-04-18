-- Migration: 008 Add Full Name to Profiles
-- Description: Stores the user's preferred name for personalizing digests.

ALTER TABLE tenant_profiles 
ADD COLUMN IF NOT EXISTS full_name TEXT;

-- Note: In a production Supabase app, a trigger should sync this from auth.users.raw_user_meta_data
