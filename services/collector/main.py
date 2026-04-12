import time
import feedparser
from loguru import logger
from shared.redis_client import is_duplicate, push_to_stream
from services.collector.sources import SOURCES
from services.collector.filter import is_relevant          # ← add this


def collect():
    logger.info("Starting collection...")
    total   = 0
    skipped = 0

    for src in SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:15]:
                url     = entry.get("link", "")
                title   = entry.get("title", "")[:300]
                content = entry.get("summary", "")[:2000]

                if not url or is_duplicate(url):
                    continue

                if not is_relevant(title, content):        # ← filter here
                    skipped += 1
                    logger.debug(f"Skipped (irrelevant): {title[:60]}")
                    continue

                push_to_stream({
                    "title":      title,
                    "source_url": url,
                    "source":     src["source"],
                    "content":    content,
                })
                total += 1
                logger.debug(f"Queued: {title[:60]}")

            logger.info(f"[{src['source']}] done")
            time.sleep(1)

        except Exception as e:
            logger.error(f"[{src['source']}] failed: {e}")

    logger.success(
        f"Collection complete — {total} queued, {skipped} skipped"
    )


if __name__ == "__main__":
    collect()