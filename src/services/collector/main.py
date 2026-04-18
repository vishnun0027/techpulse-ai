import time
import feedparser
from loguru import logger
from shared.redis_client import check_seen, mark_seen, check_title_seen, mark_title_seen, push_to_stream
from shared.db import log_telemetry, get_rss_sources
from services.collector.filter import is_relevant


def collect():
    logger.info("Starting collection...")
    total   = 0
    skipped = 0
    sources = get_rss_sources()

    # In a multi-tenant world, source urls might be requested by multiple users
    for src in sources:
        user_id = src.get("user_id")
        if not user_id:
            logger.debug(f"Source {src.get('name')} has no user_id, skipping.")
            continue
            
        try:
            feed = feedparser.parse(src["url"])
            if not hasattr(feed, "entries") or not feed.entries:
                logger.warning(f"No entries found or failed to parse feed: {src['url']}")
                continue
                
            for entry in feed.entries[:15]:
                url     = entry.get("link", "")
                title   = entry.get("title", "")[:300]
                content = entry.get("summary", "")[:2000]

                if not url or check_seen(url, user_id) or check_title_seen(title, user_id):
                    continue

                if not is_relevant(title, content, user_id):
                    skipped += 1
                    logger.debug(f"Skipped (irrelevant): {title[:60]}")
                    continue

                try:
                    push_to_stream({
                        "user_id":    user_id,
                        "title":      title,
                        "source_url": url,
                        "source":     src.get("name", "Unknown"),
                        "content":    content,
                    })
                    mark_seen(url, user_id)
                    mark_title_seen(title, user_id)
                    total += 1
                    logger.debug(f"Queued: {title[:60]}")

                except Exception as e:
                    logger.error(f"Failed to push {url} to stream: {e}")

            logger.info(f"[{src.get('name', 'Unknown')}] done for user {user_id}")
            time.sleep(1)

        except Exception as e:
            logger.error(f"[{src.get('name', 'Unknown')}] failed: {e}")

    logger.success(
        f"Collection complete — {total} queued, {skipped} skipped"
    )
    
    # Record telemetry
    log_telemetry("collector", {
        "found": total + skipped,
        "queued": total,
        "skipped": skipped
    })


if __name__ == "__main__":
    collect()