from supabase import Client
from loguru import logger

NEAR_DUPLICATE_THRESHOLD = 0.92  # cosine similarity above this = same story

def is_near_duplicate(
    supabase: Client,
    embedding: list[float],
    user_id: str
) -> bool:
    """Returns True if a semantically near-identical article already exists."""
    try:
        result = supabase.rpc("is_near_duplicate", {
            "query_embedding": embedding,
            "dup_threshold": NEAR_DUPLICATE_THRESHOLD,
            "p_user_id": user_id
        }).execute()
        return result.data
    except Exception as e:
        logger.error(f"Deduplication check failed: {e}")
        return False
