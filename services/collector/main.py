import time, feedparser
from loguru import logger
from shared.redis_client import is_duplicate, push_to_stream
from services.collector.sources import SOURCES

def score(title: str) -> float:
    s = 1.0
    if len(title) > 40: s += 0.3
    if any(w in title.lower() for w in ["gpt","llm","ai","model","agent"]): s += 0.5
    return round(s, 2)

def collect():
    logger.info("Starting collection...")
    total = 0
    for src in SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:15]:
                url = entry.get("link", "")
                if not url or is_duplicate(url):
                    continue
                push_to_stream({
                    "title":      entry.get("title", "")[:300],
                    "source_url": url,
                    "source":     src["source"],
                    "content":    entry.get("summary", "")[:2000],
                    "score":      score(entry.get("title", "")),
                })
                total += 1
            logger.info(f"[{src['source']}] done")
            time.sleep(1)
        except Exception as e:
            logger.error(f"[{src['source']}] error: {e}")
    logger.success(f"Collection complete — {total} new items queued")

if __name__ == "__main__":
    collect()