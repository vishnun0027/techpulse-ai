import httpx
from loguru import logger
from shared.db import get_top_articles, mark_as_delivered, log_telemetry, get_tenant_profiles
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

    total_count = sum(len(v) for v in grouped_articles.values())

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
    chunks = []
    current = "# 🚀 TechPulse Smart Digest\n\n"
    total_count = sum(len(v) for v in grouped_articles.values())

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
            if len(current) + len(entry) > 1900:
                chunks.append({"content": current})
                current = entry
            else:
                current += entry

    if current:
        chunks.append({"content": current})

    try:
        pending = redis.execute(command=["XLEN", STREAM_RAW]) or 0
        footer = f"\n---\n📊 **System Health**: {total_count} articles | {len(grouped_articles)} themes active | {pending} pending"
        
        if len(chunks[-1]["content"]) + len(footer) < 1950:
            chunks[-1]["content"] += footer
        else:
            chunks.append({"content": footer})
    except Exception:
        pass

    return chunks


def deliver():
    from collections import defaultdict
    
    all_articles = get_top_articles()
    if not all_articles:
        logger.warning("No articles ready to send")
        return

    articles_by_user = defaultdict(list)
    for a in all_articles:
        user_id = a.get("user_id")
        if user_id:
            articles_by_user[user_id].append(a)

    tenant_profiles = {p["user_id"]: p for p in get_tenant_profiles()}
    total_delivered = 0

    for user_id, articles in articles_by_user.items():
        profile = tenant_profiles.get(user_id)
        if not profile:
            logger.warning(f"User {user_id} has articles but no tenant profile, skipping.")
            continue

        grouped = group_by_themes(articles)
        total_to_send = sum(len(v) for v in grouped.values())
        
        logger.info(f"Delivering {total_to_send} articles across {len(grouped)} themes to user {user_id}...")

        slack_url = profile.get("slack_webhook_url")
        discord_url = profile.get("discord_webhook_url")

        if slack_url:
            try:
                r = httpx.post(slack_url, json=slack_payload(grouped), timeout=10)
                r.raise_for_status()
                logger.success(f"Slack ✅ (User {user_id})")
            except Exception as e:
                logger.error(f"Slack failed for {user_id}: {e}")

        if discord_url:
            chunks = discord_payload_chunks(grouped)
            for i, chunk in enumerate(chunks):
                try:
                    r = httpx.post(discord_url, json=chunk, timeout=10)
                    r.raise_for_status()
                    logger.success(f"Discord chunk {i+1}/{len(chunks)} ✅ (User {user_id})")
                except Exception as e:
                    logger.error(f"Discord chunk {i+1} failed for {user_id}: {e}")

        delivered_urls = [a["source_url"] for theme_list in grouped.values() for a in theme_list]
        mark_as_delivered(delivered_urls, user_id)
        total_delivered += len(delivered_urls)

    log_telemetry("delivery", {
        "count": total_delivered,
        "users": len(articles_by_user)
    })

if __name__ == "__main__":
    deliver()