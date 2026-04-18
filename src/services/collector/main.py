import time
from datetime import datetime, timedelta, timezone
import feedparser
from loguru import logger
from shared.config import settings
from shared.redis_client import check_seen, mark_seen, check_title_seen, mark_title_seen, push_to_stream
from shared.db import log_telemetry, get_rss_sources
from services.collector.filter import is_relevant


def collect():
    logger.info("Starting collection...")
    total   = 0
    skipped = 0
    sources = get_rss_sources()
    
    # Calculate cutoff for freshness
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.collection_interval_days)

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
                src["_success"] = False
                continue
                
            for entry in feed.entries[:15]:
                url     = entry.get("link", "")
                title   = entry.get("title", "")[:300]
                content = entry.get("summary", "")[:2000]
                
                # 1. Freshness Check (e.g. 14 days)
                pub_date = entry.get("published_parsed")
                if pub_date:
                    dt = datetime.fromtimestamp(time.mktime(pub_date), tz=timezone.utc)
                    if dt < cutoff:
                        logger.debug(f"Skipped (stale): {title[:40]}...")
                        continue

                # 2. Deduplication Check
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
            src["_success"] = False

    logger.success(
        f"Collection complete — {total} queued, {skipped} skipped"
    )
    
    # Calculate source health metrics for dashboard
    total_sources = len(sources)
    error_count   = sum(1 for src in sources if not src.get("_success", True))
    
    # Calculate noise_ratio (skipped vs total valid found)
    found = total + skipped
    noise_ratio = round((skipped / found * 100) if found > 0 else 0, 1)

    # Record telemetry
    log_telemetry("collector", {
        "total_sources": total_sources,
        "error_count":   error_count,
        "noise_ratio":   noise_ratio
    })


if __name__ == "__main__":
    collect()