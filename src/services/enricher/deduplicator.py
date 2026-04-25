from supabase import Client
from loguru import logger
from shared.config import settings


def is_near_duplicate(
    supabase: Client,
    embedding: list[float],
    user_id: str
) -> bool:
    """Returns True if a semantically near-identical article already exists."""
    try:
        result = supabase.rpc("is_near_duplicate", {
            "query_embedding": embedding,
            "dup_threshold": settings.near_duplicate_threshold,
            "p_user_id": user_id
        }).execute()
        return result.data
    except Exception as e:
        logger.error(f"Deduplication check failed: {e}")
        return False
