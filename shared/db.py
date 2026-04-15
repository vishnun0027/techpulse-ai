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
    from datetime import datetime, timedelta
    since = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    resp = (
        supabase.table("articles")
        .select("title, summary, source_url, source, score, topics")  # ← added topics
        .gte("created_at", since)
        .eq("is_delivered", False)                                    # ← added delivered filter
        .not_.is_("summary", "null")
        .gte("score", 2.5)                                            # ← only quality articles
        .order("score", desc=True)
        .limit(n)
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
    """Log run metrics to the telemetry table."""
    try:
        supabase.table("telemetry").insert({
            "service": service,
            "metrics": metrics,
            "success": success
        }).execute()
    except Exception as e:
        logger.error(f"Telemetry log error ({service}): {e}")