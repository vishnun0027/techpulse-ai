import httpx
from loguru import logger
from shared.config import settings
from shared.db import get_top_articles, mark_as_delivered, log_telemetry
from shared.redis_client import redis, STREAM_RAW

THEMES = {
    "🧠 Generative AI": ["ai", "llm", "chatgpt", "gpt", "anthropic", "claude", "gemini", "rag", "agent"],
    "🤖 ML & Data": ["machine learning", "ml", "data science", "dataset", "analytics", "vision", "dataset"],
    "🛠️ Dev Tools": ["dev tools", "python", "rust", "github", "api", "framework", "cli", "library"],
    "🛡️ Security & Infra": ["security", "vulnerability", "breach", "cloud", "infra", "database", "postgres"],
    "🚀 Tech Trends": ["startup", "research", "paper", "launch", "release"]
}

def get_theme(topics: list) -> str:
    topics_lower = [t.lower() for t in topics]
    for theme, keywords in THEMES.items():
        if any(k in topics_lower for k in keywords):
            return theme
    return "🌐 General Tech"

def group_by_themes(articles: list) -> dict:
    grouped = {}
    for a in articles:
        theme = get_theme(a.get("topics", []))
        if theme not in grouped:
            grouped[theme] = []
        if len(grouped[theme]) < 4: # Max 4 per theme
            grouped[theme].append(a)
    return grouped

def slack_payload(grouped_articles: dict) -> dict:
    blocks = [{
        "type": "header",
        "text": {"type": "plain_text", "text": "🚀 TechPulse Smart Digest"}
    }, {"type": "divider"}]

    total_count = sum(len(v) for v in grouped_articles.values())  # fix: total across all themes

    for theme, articles in grouped_articles.items():
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{theme}*"}
        })
        for i, a in enumerate(articles, 1):
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn",
                         "text": (f"• <{a['source_url']}|{a['title']}>\n"
                                   f"  _{a['summary']}_")},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": f"⭐ {a['score']}"},
                    "url": a['source_url']
                }
            })
        blocks.append({"type": "divider"})
    
    # Add Health Stats Footer
    try:
        pending = redis.execute(command=["XLEN", STREAM_RAW]) or 0
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"📊 *System Health* — {total_count} delivered | {pending} pending in queue"
            }]
        })
    except Exception:
        pass

    return {"blocks": blocks}

def discord_payload_chunks(grouped_articles: dict) -> list[dict]:
    """Split articles into multiple Discord messages if needed."""
    chunks = []
    current = "# 🚀 TechPulse Smart Digest\n\n"
    total_count = sum(len(v) for v in grouped_articles.values())  # fix: total across all themes

    for theme, articles in grouped_articles.items():
        theme_header = f"## {theme}\n"
        if len(current) + len(theme_header) > 1900:
            chunks.append({"content": current})
            current = theme_header
        else:
            current += theme_header

        for i, a in enumerate(articles, 1):
            entry = (
                f"**{i}. [{a['title']}](<{a['source_url']}>)** (Score: {a['score']})\n"
                f"> {a['summary']}\n\n"
            )
            # If adding this entry exceeds Discord limit, start new chunk
            if len(current) + len(entry) > 1900:
                chunks.append({"content": current})
                current = entry  # start fresh chunk
            else:
                current += entry

    # Append the final remaining content
    if current:
        chunks.append({"content": current})

    # Add Health Stats Footer
    try:
        pending = redis.execute(command=["XLEN", STREAM_RAW]) or 0
        footer = f"\n---\n📊 **System Health**: {total_count} articles | {len(grouped_articles)} themes active | {pending} pending"
        
        # Add to last chunk if possible, or new chunk
        if len(chunks[-1]["content"]) + len(footer) < 1950:
            chunks[-1]["content"] += footer
        else:
            chunks.append({"content": footer})
    except Exception:
        pass

    return chunks


def deliver():
    articles = get_top_articles()
    if not articles:
        logger.warning("No articles ready to send")
        return

    grouped = group_by_themes(articles)
    total_to_send = sum(len(v) for v in grouped.values())
    
    logger.info(f"Delivering {total_to_send} articles across {len(grouped)} themes...")

    # Slack — single message, Block Kit handles long content fine
    if settings.slack_webhook_url:
        try:
            r = httpx.post(settings.slack_webhook_url,
                           json=slack_payload(grouped), timeout=10)
            r.raise_for_status()
            logger.success("Slack ✅")
        except Exception as e:
            logger.error(f"Slack failed: {e}")

    # Discord — split into chunks to respect 2000 char limit
    if settings.discord_webhook_url:
        chunks = discord_payload_chunks(grouped)
        for i, chunk in enumerate(chunks):
            try:
                r = httpx.post(settings.discord_webhook_url,
                               json=chunk, timeout=10)
                r.raise_for_status()
                logger.success(f"Discord chunk {i+1}/{len(chunks)} ✅")
            except Exception as e:
                logger.error(f"Discord chunk {i+1} failed: {e}")

    # Mark as delivered
    delivered_urls = [a["source_url"] for theme_list in grouped.values() for a in theme_list]
    mark_as_delivered(delivered_urls)

    # Record telemetry
    log_telemetry("delivery", {
        "count": len(delivered_urls),
        "themes": list(grouped.keys())
    })

if __name__ == "__main__":
    deliver()