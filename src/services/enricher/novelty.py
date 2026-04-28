from supabase import Client
from loguru import logger


def compute_novelty_score(
    supabase: Client, embedding: list[float], user_id: str, match_count: int = 5
) -> float:
    """
    Novelty score 0.0–1.0.
    High novelty = few similar articles in recent history.
    Low novelty  = many highly similar articles already seen.
    """
    try:
        result = supabase.rpc(
            "match_articles_recency",
            {
                "query_embedding": embedding,
                "match_count": match_count,
                "p_user_id": user_id,
                "decay_rate": 0.15,
            },
        ).execute()

        similar_items = result.data or []
        if not similar_items:
            return 1.0  # nothing similar found - fully novel

        # Average recency-weighted similarity of top matches (filter out NULLs)
        valid_scores = [
            r["recency_score"] for r in similar_items if r["recency_score"] is not None
        ]
        if not valid_scores:
            return 1.0  # Nothing valid to compare against - treat as novel

        avg_similarity = sum(valid_scores) / len(valid_scores)

        # Invert: high similarity → low novelty
        novelty = max(0.0, 1.0 - avg_similarity)
        return round(novelty, 4)
    except Exception as e:
        logger.error(f"Novelty computation failed: {e}")
        return 0.5  # Neutral fallback
