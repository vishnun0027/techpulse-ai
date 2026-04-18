from loguru import logger
from shared.db import get_filter_config
import time

# Cache the config for 5 minutes during a run per user
_config_cache = {}

def get_cached_config(user_id: str):
    now = time.time()
    if not user_id:
        return {"allowed": [], "blocked": [], "priority": []}
    
    if user_id not in _config_cache or now > _config_cache[user_id]["expiry"]:
        raw = get_filter_config(user_id)
        
        # Robustness: strip any internal quotes and backslashes added by mistake
        raw["allowed"] = [t.replace('\\"', '').strip('"').strip("'").strip() for t in raw.get("allowed", [])]
        raw["blocked"] = [t.replace('\\"', '').strip('"').strip("'").strip() for t in raw.get("blocked", [])]
        raw["priority"] = [t.replace('\\"', '').strip('"').strip("'").strip() for t in raw.get("priority", [])]

        _config_cache[user_id] = {"data": raw, "expiry": now + 300}
        
    return _config_cache[user_id]["data"]

def is_relevant(title: str, content: str = "", user_id: str | None = None) -> bool:
    config = get_cached_config(user_id)
    allowed = config.get("allowed", [])
    blocked = config.get("blocked", [])

    text = (title + " " + content[:300]).lower()

    # Block irrelevant content first
    if any(b.lower() in text for b in blocked):
        return False

    # Must match at least one allowed topic
    return any(t.lower() in text for t in allowed)