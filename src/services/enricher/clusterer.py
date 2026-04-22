from supabase import Client
from groq import Groq
from loguru import logger
import uuid

CLUSTER_THRESHOLD = 0.85  # articles above this similarity join same event

def find_or_create_event(
    supabase: Client,
    groq_client: Groq,
    embedding: list[float],
    article_title: str,
    user_id: str
) -> str:
    """
    Finds an existing article_event with a similar centroid,
    or creates a new one. Returns the event_id.
    """
    try:
        # Find existing event with similar centroid embedding
        result = supabase.rpc("match_events_by_centroid", {
            "query_embedding": embedding,
            "threshold": CLUSTER_THRESHOLD,
            "p_user_id": user_id
        }).execute()

        if result.data:
            event_id = result.data[0]["id"]
            # Update centroid and count
            supabase.table("article_events").update({
                "article_count": result.data[0]["article_count"] + 1,
                "last_updated": "now()"
            }).eq("id", event_id).execute()
            return event_id

        # Create new event — generate a clean event title via LLM
        prompt = f"In 8 words or fewer, name the tech story: '{article_title}'"
        title_response = groq_client.invoke(prompt)
        event_title = title_response.content.strip().strip('"')

        new_event = supabase.table("article_events").insert({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "title": event_title,
            "centroid_embedding": embedding,
            "article_count": 1
        }).execute()

        return new_event.data[0]["id"]
    except Exception as e:
        logger.error(f"Clustering failed: {e}")
        return None
