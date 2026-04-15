from supabase import create_client
from loguru import logger
from shared.config import settings

supabase = create_client(settings.supabase_url, settings.supabase_key)


def save_article(article: dict) -> bool:
    try:
        supabase.table("articles") \
            .upsert(article, on_conflict="source_url") \
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
        .select("title, summary, source_url, source, score, topics")  # ← added topics
        .gte("created_at", since)
        .eq("is_delivered", False)                                    # ← added delivered filter
        .not_.is_("summary", "null")
        .gte("score", 3.0)                                            # ← Higher quality bar (3.0)
        .order("score", desc=True)
        .limit(50)                                                    # ← Larger pool for smart grouping
        .execute()
    )
    return resp.data or []


def mark_as_delivered(source_urls: list[str]):
    """Mark articles as delivered in the database."""
    if not source_urls:
        return
    try:
        supabase.table("articles") \
            .update({"is_delivered": True}) \
            .in_("source_url", source_urls) \
            .execute()
    except Exception as e:
        logger.error(f"DB update error (mark_delivered): {e}")


def log_telemetry(service: str, metrics: dict, success: bool = True):
    try:
        supabase.table("telemetry").insert({
            "service": service,
            "metrics": metrics,
            "success": success
        }).execute()
    except Exception as e:
        print(f"Failed to log telemetry: {e}")

# ── DYNAMIC CONFIGURATION ─────────────────────────────────────────────────────

def get_rss_sources():
    """Fetches active RSS sources from the database."""
    try:
        res = supabase.table("rss_sources").select("*").eq("is_active", True).execute()
        return res.data or []
    except Exception as e:
        print(f"Error fetching RSS sources: {e}")
        return []

def get_filter_config():
    """Fetches allowed, blocked, and priority topics from the app_config table."""
    try:
        res = supabase.table("app_config").select("value").eq("key", "topics").execute()
        if res.data:
            return res.data[0]["value"]
    except Exception as e:
        print(f"Error fetching filter config: {e}")
    
    return {"allowed": [], "blocked": [], "priority": []}