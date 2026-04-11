import httpx
from loguru import logger
from shared.config import settings
from shared.db import get_top_articles

def slack_payload(articles: list) -> dict:
    blocks = [{
        "type": "header",
        "text": {"type": "plain_text", "text": "🤖 TechPulse — Daily Digest"}
    }, {"type": "divider"}]

    for i, a in enumerate(articles, 1):
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn",
                     "text": (f"*{i}. <{a['source_url']}|{a['title']}>*\n"
                              f"_{a['source']}_ — Score: {a['score']}\n"
                              f"{a['summary']}")}
        })
        blocks.append({"type": "divider"})
    return {"blocks": blocks}

def discord_payload_chunks(articles: list) -> list[dict]:
    """Split articles into multiple Discord messages if needed."""
    chunks = []
    current = "# 🤖 TechPulse Daily Digest\n\n"

    for i, a in enumerate(articles, 1):
        entry = (
            f"**{i}. [{a['title']}](<{a['source_url']}>)**\n"
            f"> {a['summary']}\n"
            f"*{a['source']}*\n\n"
        )
        # If adding this entry exceeds Discord limit, start new chunk
        if len(current) + len(entry) > 1900:
            chunks.append({"content": current})
            current = entry  # start fresh chunk
        else:
            current += entry

    if current.strip():
        chunks.append({"content": current})

    return chunks


def deliver():
    articles = get_top_articles(n=settings.top_n_articles)
    if not articles:
        logger.warning("No articles ready to send")
        return

    logger.info(f"Delivering {len(articles)} articles...")

    # Slack — single message, Block Kit handles long content fine
    if settings.slack_webhook_url:
        try:
            r = httpx.post(settings.slack_webhook_url,
                           json=slack_payload(articles), timeout=10)
            r.raise_for_status()
            logger.success("Slack ✅")
        except Exception as e:
            logger.error(f"Slack failed: {e}")

    # Discord — split into chunks to respect 2000 char limit
    if settings.discord_webhook_url:
        chunks = discord_payload_chunks(articles)
        for i, chunk in enumerate(chunks):
            try:
                r = httpx.post(settings.discord_webhook_url,
                               json=chunk, timeout=10)
                r.raise_for_status()
                logger.success(f"Discord chunk {i+1}/{len(chunks)} ✅")
            except Exception as e:
                logger.error(f"Discord chunk {i+1} failed: {e}")

if __name__ == "__main__":
    deliver()