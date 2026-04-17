from supabase import create_client
from loguru import logger
from shared.config import settings

supabase = create_client(settings.supabase_url, settings.supabase_key)


def save_article(article: dict) -> bool:
    try:
        supabase.table("articles") \
            .upsert(article, on_conflict="source_url,user_id") \
            .execute()
        return True
    except Exception as e:
        logger.error(f"DB save error: {e}")
        return False


def get_top_articles(n: int = 10) -> list:
    from datetime import datetime, timedelta, timezone
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    resp = (
        supabase.table("articles")
        .select("user_id, title, summary, source_url, source, score, topics")  # ← added user_id
        .gte("created_at", since)
        .eq("is_delivered", False)
        .not_.is_("summary", "null")
        .gte("score", 3.0)
        .order("score", desc=True)
        .limit(500)  # increased limit since it covers all users now
        .execute()
    )
    return resp.data or []


def mark_as_delivered(source_urls: list[str], user_id: str):
    """Mark articles as delivered in the database for a specific user."""
    if not source_urls:
        return
    try:
        supabase.table("articles") \
            .update({"is_delivered": True}) \
            .eq("user_id", user_id) \
            .in_("source_url", source_urls) \
            .execute()
    except Exception as e:
        logger.error(f"DB update error (mark_delivered): {e}")


def log_telemetry(service: str, metrics: dict, user_id: str | None = None, success: bool = True):
    try:
        payload = {
            "service": service,
            "metrics": metrics,
            "success": success
        }
        if user_id:
            payload["user_id"] = user_id
        supabase.table("telemetry").insert(payload).execute()
    except Exception as e:
        print(f"Failed to log telemetry: {e}")

# ── DYNAMIC CONFIGURATION ─────────────────────────────────────────────────────

def get_rss_sources():
    """Fetches active RSS sources from the database, for all users."""
    try:
        res = supabase.table("rss_sources").select("*").eq("is_active", True).execute()
        return res.data or []
    except Exception as e:
        print(f"Error fetching RSS sources: {e}")
        return []

def get_filter_config(user_id: str | None = None):
    """Fetches allowed, blocked, and priority topics from the app_config table for a given user."""
    try:
        query = supabase.table("app_config").select("value").eq("key", "topics")
        if user_id:
            query = query.eq("user_id", user_id)
        
        res = query.execute()
        if res.data:
            return res.data[0]["value"]
    except Exception as e:
        print(f"Error fetching filter config: {e}")
    
    return {"allowed": [], "blocked": [], "priority": []}

def get_tenant_profiles():
    """Fetches all tenant profiles (webhooks etc)."""
    try:
        res = supabase.table("tenant_profiles").select("*").execute()
        return res.data or []
    except Exception as e:
        print(f"Error fetching tenant profiles: {e}")
        return []