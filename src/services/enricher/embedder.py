from sentence_transformers import SentenceTransformer
from loguru import logger
import os

# Load model once on import
# all-mpnet-base-v2 provides 768-dimensional embeddings to match the DB schema
MODEL_NAME = "all-mpnet-base-v2"
_model = None

def get_model():
    """Initializes and returns the local embedding model singleton."""
    global _model
    if _model is None:
        logger.info(f"Loading local embedding model: {MODEL_NAME}...")
        try:
            _model = SentenceTransformer(MODEL_NAME)
            logger.success(f"Model {MODEL_NAME} loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    return _model

def embed_text(text: str, api_key: str = None) -> list[float]:
    """
    Returns a 768-dim embedding via local sentence-transformers.
    
    The api_key argument is preserved for compatibility with the V2 blueprint 
    but is not used for local embeddings.
    """
    model = get_model()
    truncated = text[:4000]  # Respect typical model limits
    try:
        # Generate embedding locally
        embedding = model.encode(truncated)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Local embedding failed: {e}")
        raise
