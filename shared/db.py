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
    since = (datetime.utcnow() - timedelta(hours=8)).isoformat()  # ← change 24 to 8
    resp = (
        supabase.table("articles")
        .select("title, summary, source_url, source, score")
        .gte("created_at", since)
        .not_.is_("summary", "null")
        .order("score", desc=True)
        .limit(n)
        .execute()
    )
    return resp.data or []