import time
import feedparser
from loguru import logger
from shared.redis_client import is_duplicate, push_to_stream
from services.collector.sources import SOURCES


def collect():
    logger.info("Starting collection...")
    total = 0

    for src in SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:15]:
                url   = entry.get("link", "")
                title = entry.get("title", "")[:300]

                if not url or is_duplicate(url):
                    continue

                push_to_stream({
                    "title":      title,
                    "source_url": url,
                    "source":     src["source"],
                    "content":    entry.get("summary", "")[:2000],
                })
                total += 1
                logger.debug(f"Queued: {title[:60]}")

            logger.info(f"[{src['source']}] done")
            time.sleep(1)

        except Exception as e:
            logger.error(f"[{src['source']}] failed: {e}")

    logger.success(f"Collection complete — {total} new articles queued")


if __name__ == "__main__":
    collect()