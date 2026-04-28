import time
import calendar
from datetime import datetime, timedelta, timezone
import feedparser
from loguru import logger
from shared.config import settings
from shared.redis_client import (
    check_seen,
    mark_seen,
    check_title_seen,
    mark_title_seen,
    push_to_stream,
)
from shared.db import log_telemetry, get_rss_sources, update_source_ingestion
from services.collector.filter import is_relevant


def collect() -> None:
    """
    Executes the multi-tenant collection pipeline.

    1. Fetches all active RSS sources from Supabase.
    2. Parses each feed for new entries.
    3. Filters entries based on:
       - Publication date (14-day freshness limit).
       - Deduplication (seen URL or title).
       - User-defined topic relevance.
    4. Queues relevant articles into the Redis stream for summarization.
    5. Records operational telemetry (noise ratio, source health).
    """
    logger.info("Starting collection...")
    total_queued: int = 0
    total_skipped: int = 0
    sources = get_rss_sources()

    # Calculate cutoff for freshness based on settings
    cutoff = datetime.now(timezone.utc) - timedelta(
        days=settings.collection_interval_days
    )

    # In a multi-tenant world, sources are associated with specific user_ids
    for src in sources:
        user_id = src.get("user_id")
        if not user_id:
            logger.debug(f"Source {src.get('name')} has no user_id, skipping.")
            continue

        try:
            feed = feedparser.parse(src["url"])
            if not hasattr(feed, "entries") or not feed.entries:
                logger.warning(
                    f"No entries found or failed to parse feed: {src['url']}"
                )
                src["_success"] = False
                continue

            # We only check the top 15 entries per source to keep runs fast
            for entry in feed.entries[:15]:
                url = entry.get("link", "")
                title = entry.get("title", "")[:300]
                content = entry.get("summary", "")[:2000]

                # 1. Freshness Check
                pub_date = entry.get("published_parsed")
                if pub_date:
                    # calendar.timegm() treats struct_time as UTC (unlike time.mktime
                    # which uses local time and would be wrong on non-UTC servers).
                    dt = datetime.fromtimestamp(
                        calendar.timegm(pub_date), tz=timezone.utc
                    )
                    if dt < cutoff:
                        logger.debug(f"Skipped (stale): {title[:40]}...")
                        continue

                # 2. Deduplication Check
                if (
                    not url
                    or check_seen(url, user_id)
                    or check_title_seen(title, user_id)
                ):
                    continue

                # 3. Topic Relevance Check
                if not is_relevant(title, content, user_id):
                    total_skipped += 1
                    logger.debug(f"Skipped (irrelevant): {title[:60]}")
                    continue

                # 4. Queue for Summarization
                try:
                    from shared.utils import normalize_url

                    n_url = normalize_url(url)
                    push_to_stream(
                        {
                            "user_id": user_id,
                            "title": title,
                            "source_url": n_url,
                            "source": src.get("name", "Unknown"),
                            "source_id": src.get("id"),
                            "content": content,
                        }
                    )
                    mark_seen(n_url, user_id)
                    mark_title_seen(title, user_id)
                    update_source_ingestion(src.get("id"), user_id)
                    total_queued += 1
                    logger.debug(f"Queued: {title[:60]}")

                except Exception as e:
                    logger.error(f"Failed to push {url} to stream: {e}")

            logger.info(f"[{src.get('name', 'Unknown')}] done for user {user_id}")
            time.sleep(1)  # Polite pause between sources

        except Exception as e:
            logger.error(f"[{src.get('name', 'Unknown')}] failed: {e}")
            src["_success"] = False

    logger.success(
        f"Collection complete - {total_queued} queued, {total_skipped} skipped"
    )

    # Calculate health metrics
    total_sources = len(sources)
    error_count = sum(1 for src in sources if not src.get("_success", True))

    # Calculate noise_ratio (skipped vs total valid candidates found)
    processed_count = total_queued + total_skipped
    noise_ratio = round(
        (total_skipped / processed_count * 100) if processed_count > 0 else 0, 1
    )

    # Record telemetry for the dashboard
    log_telemetry(
        "collector",
        {
            "total_sources": total_sources,
            "error_count": error_count,
            "noise_ratio": noise_ratio,
        },
    )


if __name__ == "__main__":
    collect()
