from loguru import logger
from shared.db import get_filter_config
import time

# Hardcoded fallback defaults — used if DB config is empty or unreachable
_DEFAULT_ALLOWED = [
    "ai", "llm", "gpt", "claude", "gemini", "openai", "anthropic",
    "mistral", "llama", "agent", "rag", "embedding", "chatbot",
    "transformer", "diffusion", "multimodal", "fine-tun",
    "machine learning", "deep learning", "neural", "pytorch",
    "tensorflow", "dataset", "model", "training", "inference",
    "benchmark", "computer vision", "nlp", "reinforcement",
    "python", "rust", "golang", "typescript", "open source",
    "api", "framework", "library", "cli", "tool", "github",
    "docker", "kubernetes", "fastapi", "database",
    "startup", "research", "paper", "released", "launched",
    "security", "vulnerability", "breach", "programming",
]
_DEFAULT_BLOCKED = [
    "hiring", "job posting", "salary", "cryptocurrency",
    "bitcoin", "nft", "forex", "trading signals",
    "weight loss", "casino", "betting",
]

# Cache the config for 5 minutes during a run
_config_cache = {"data": None, "expiry": 0}

def get_cached_config():
    now = time.time()
    if _config_cache["data"] is None or now > _config_cache["expiry"]:
        raw = get_filter_config()
        # Fallback to hardcoded defaults if DB returns empty lists
        if not raw.get("allowed"):
            logger.warning("Filter config not found in DB, using hardcoded defaults.")
            raw["allowed"] = _DEFAULT_ALLOWED
        if not raw.get("blocked"):
            raw["blocked"] = _DEFAULT_BLOCKED
        _config_cache["data"] = raw
        _config_cache["expiry"] = now + 300  # 5 min cache
    return _config_cache["data"]

def is_relevant(title: str, content: str = "") -> bool:
    config = get_cached_config()
    allowed = config.get("allowed", [])
    blocked = config.get("blocked", [])

    text = (title + " " + content[:300]).lower()

    # Block irrelevant content first
    if any(b.lower() in text for b in blocked):
        return False

    # Must match at least one allowed topic
    return any(t.lower() in text for t in allowed)