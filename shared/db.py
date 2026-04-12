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
        .not_.is_("summary", "null")
        .gte("score", 2.5)                                            # ← only quality articles
        .order("score", desc=True)
        .limit(n)
        .execute()
    )
    return resp.data or []