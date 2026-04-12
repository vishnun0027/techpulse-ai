import time
import feedparser
from loguru import logger
from shared.redis_client import check_seen, mark_seen, check_title_seen, mark_title_seen, push_to_stream
from services.collector.sources import SOURCES
from services.collector.filter import is_relevant


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

                if not url or check_seen(url) or check_title_seen(title):
                    continue

                if not is_relevant(title, content):
                    skipped += 1
                    logger.debug(f"Skipped (irrelevant): {title[:60]}")
                    continue

                try:
                    push_to_stream({
                        "title":      title,
                        "source_url": url,
                        "source":     src["source"],
                        "content":    content,
                    })
                    mark_seen(url)
                    mark_title_seen(title)  # Also mark title as seen
                    total += 1
                    logger.debug(f"Queued: {title[:60]}")

                except Exception as e:
                    logger.error(f"Failed to push {url} to stream: {e}")

            logger.info(f"[{src['source']}] done")
            time.sleep(1)

        except Exception as e:
            logger.error(f"[{src['source']}] failed: {e}")

    logger.success(
        f"Collection complete — {total} queued, {skipped} skipped"
    )


if __name__ == "__main__":
    collect()