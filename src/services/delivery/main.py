import httpx
from typing import List, Dict, Any, Optional
from collections import defaultdict
from loguru import logger
from shared.db import get_top_articles, mark_as_delivered, log_telemetry, get_tenant_profiles
from shared.redis_client import redis, STREAM_RAW

# ── Theme Configuration ───────────────────────────────────────────────────────

THEMES = {
    "🧠 Generative AI": ["ai", "llm", "chatgpt", "gpt", "anthropic", "claude", "gemini", "rag", "agent"],
    "🤖 ML & Data": ["machine learning", "ml", "data science", "dataset", "analytics", "vision", "dataset"],
    "🛠️ Dev Tools": ["dev tools", "python", "rust", "github", "api", "framework", "cli", "library"],
    "🛡️ Security & Infra": ["security", "vulnerability", "breach", "cloud", "infra", "database", "postgres"],
    "🚀 Tech Trends": ["startup", "research", "paper", "launch", "release"]
}


def get_theme(topics: List[str]) -> str:
    """
    Categorizes an article into a theme based on its topics.
    
    Args:
        topics: List of topic tags from the AI analysis.
        
    Returns:
        str: The selected theme emoji and name.
    """
    if not topics:
        return "🌐 General Tech"
        
    topics_lower = [t.lower() for t in topics]
    for theme, keywords in THEMES.items():
        if any(k.lower() in topics_lower for k in keywords):
            return theme
            
    # Dynamic fallback: Use the first relevant topic as the category
    main_topic = topics[0].strip().title()
    return f"📌 {main_topic}"


def group_by_themes(articles: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Groups a list of articles by their calculated themes.
    
    Args:
        articles: List of article dictionaries.
        
    Returns:
        Dict[str, List[Dict[str, Any]]]: Grouped articles (max 4 per theme).
    """
    grouped = {}
    for a in articles:
        theme = get_theme(a.get("topics", []))
        if theme not in grouped:
            grouped[theme] = []
        if len(grouped[theme]) < 4:  # Capacity limit per theme
            grouped[theme].append(a)
    return grouped


# ── Payload Builders ──────────────────────────────────────────────────────────

def slack_payload(grouped_articles: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Generates a Slack Block Kit payload for the digest.
    
    Args:
        grouped_articles: Dictionary of themed articles.
        
    Returns:
        Dict[str, Any]: Slack-compliant JSON payload.
    """
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
        for a in articles:
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
    
    # Add System Health context footer
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


def discord_payload_chunks(grouped_articles: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Generates Discord Markdown payloads, split into chunks to stay under character limits.
    
    Args:
        grouped_articles: Dictionary of themed articles.
        
    Returns:
        List[Dict[str, Any]]: List of Discord message payloads.
    """
    chunks = []
    current = "# 🚀 TechPulse Smart Digest\n\n"
    total_count = sum(len(v) for v in grouped_articles.values())

    for theme, articles in grouped_articles.items():
        theme_header = f"## {theme}\n"
        # Check for Discord 2000 char limit
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

    # Add Stats Footer to the last chunk
    try:
        pending = redis.execute(command=["XLEN", STREAM_RAW]) or 0
        footer = f"\n---\n📊 **System Health**: {total_count} articles | {len(grouped_articles)} themes | {pending} pending"
        
        if len(chunks[-1]["content"]) + len(footer) < 1950:
            chunks[-1]["content"] += footer
        else:
            chunks.append({"content": footer})
    except Exception:
        pass

    return chunks


# ── Delivery Manager ──────────────────────────────────────────────────────────

def deliver() -> None:
    """
    Main delivery entry point.
    
    1. Fetches all top-scoring articles from the last 24h.
    2. Groups them by user.
    3. Fetches user profiles to get Slack/Discord webhooks.
    4. Personalizes and sends digests to each user.
    5. Marks articles as delivered to avoid duplication.
    """
    all_articles = get_top_articles()
    if not all_articles:
        logger.warning("No articles ready to send")
        return

    # Map articles to users for multi-tenant delivery
    articles_by_user = defaultdict(list)
    for a in all_articles:
        user_id = a.get("user_id")
        if user_id:
            articles_by_user[user_id].append(a)

    tenant_profiles = {p["user_id"]: p for p in get_tenant_profiles()}
    total_delivered_count = 0

    for user_id, articles in articles_by_user.items():
        profile = tenant_profiles.get(user_id)
        if not profile:
            logger.warning(f"User {user_id} has articles but no profile, skipping.")
            continue

        user_name = profile.get("full_name") or "Tech Explorer"
        grouped = group_by_themes(articles)
        total_to_send = sum(len(v) for v in grouped.values())
        
        logger.info(f"Delivering {total_to_send} articles to {user_name} ({user_id})...")

        slack_url = profile.get("slack_webhook_url")
        discord_url = profile.get("discord_webhook_url")

        if not slack_url and not discord_url:
            logger.info(f"User {user_id} has no webhooks configured.")
            continue

        # 1. Deliver to Slack
        if slack_url:
            payload = slack_payload(grouped)
            payload["blocks"][0]["text"]["text"] = f"🚀 Hi {user_name}, here is your TechPulse Digest"
            try:
                r = httpx.post(slack_url, json=payload, timeout=10)
                r.raise_for_status()
                logger.success(f"Slack ✅ (User {user_id})")
            except Exception as e:
                logger.error(f"Slack failed for {user_id}: {e}")

        # 2. Deliver to Discord
        if discord_url:
            chunks = discord_payload_chunks(grouped)
            if chunks:
                chunks[0]["content"] = f"# 🚀 Hi {user_name}, your TechPulse Digest\n\n" + \
                                       chunks[0]["content"].replace("# 🚀 TechPulse Smart Digest\n\n", "")
            
            for i, chunk in enumerate(chunks):
                try:
                    r = httpx.post(discord_url, json=chunk, timeout=10)
                    r.raise_for_status()
                    logger.success(f"Discord chunk {i+1}/{len(chunks)} ✅ (User {user_id})")
                except Exception as e:
                    logger.error(f"Discord chunk {i+1} failed for {user_id}: {e}")

        # 3. Mark batch as delivered
        delivered_urls = [a["source_url"] for theme_list in grouped.values() for a in theme_list]
        mark_as_delivered(delivered_urls, user_id)
        total_delivered_count += len(delivered_urls)

    # 4. Record run telemetry
    log_telemetry("delivery", {
        "count": total_delivered_count,
        "users_reached": len(articles_by_user)
    })


if __name__ == "__main__":
    deliver()