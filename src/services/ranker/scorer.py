from supabase import Client
from dataclasses import dataclass
from loguru import logger

@dataclass
class RankSignals:
    base_relevance:    float  # 0–5: LLM relevance score from current summarizer
    novelty_score:     float  # 0–1: from enricher/novelty.py
    source_quality:    float  # 0–1: from source_health table
    topic_match:       float  # 0–1: keyword profile match (existing logic)
    priority_boost:    float  # +1.0 if matches priority topics (existing logic)

# Default weights — can be stored per user in app_config
DEFAULT_WEIGHTS = {
    "base_relevance": 0.35,
    "novelty_score":  0.25,
    "source_quality": 0.20,
    "topic_match":    0.15,
    "priority_boost": 0.05,
}

# Article scoring thresholds
DELIVERY_THRESHOLD = 4.5   # articles below this are stored but not delivered
BREAKING_THRESHOLD = 8.0   # articles above this trigger an immediate alert

def compute_final_score(signals: RankSignals, weights: dict = DEFAULT_WEIGHTS) -> float:
    """
    Returns a final score 0.0–10.0.
    Articles scoring below DELIVERY_THRESHOLD are excluded from digests.
    """
    try:
        score = (
            signals.base_relevance   * weights["base_relevance"] * 2.0 +  # normalize 0–5 to 0–1
            signals.novelty_score    * weights["novelty_score"]  * 10.0 +
            signals.source_quality   * weights["source_quality"] * 10.0 +
            signals.topic_match      * weights["topic_match"]    * 10.0 +
            signals.priority_boost   * weights["priority_boost"] * 10.0
        )
        return round(min(score, 10.0), 4)
    except Exception as e:
        logger.error(f"Scoring failed: {e}")
        return 0.0
