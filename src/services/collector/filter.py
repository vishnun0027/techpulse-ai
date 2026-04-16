from loguru import logger
from shared.db import get_filter_config
from functools import lru_cache
import time

# Cache the config for 5 minutes during a run
_config_cache = {"data": None, "expiry": 0}

def get_cached_config():
    now = time.time()
    if _config_cache["data"] is None or now > _config_cache["expiry"]:
        _config_cache["data"] = get_filter_config()
        _config_cache["expiry"] = now + 300 # 5 min
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