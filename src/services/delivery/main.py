import httpx
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from collections import defaultdict
from loguru import logger
from shared.db import supabase, mark_as_delivered, log_telemetry, get_tenant_profiles
from shared.redis_client import redis, STREAM_RAW

# Theme Configuration is now handled dynamically by the AI in the Summarizer stage.


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
        # The AI now puts the primary theme/category as the FIRST topic in the list
        topics = a.get("topics", [])
        theme = topics[0] if topics else "🌐 General Tech"
        
        if theme not in grouped:
            grouped[theme] = []
        
        if len(grouped[theme]) < 10:
            grouped[theme].append(a)
    return grouped


# ── Payload Builders ──────────────────────────────────────────────────────────

def slack_payload(grouped_articles: Dict[str, List[Dict[str, Any]]], intro: Optional[str] = None) -> Dict[str, Any]:
    """
    Generates a Slack Block Kit payload for the digest.
    
    Args:
        grouped_articles: Dictionary of themed articles.
        intro: Optional LLM-generated narrative introduction.
        
    Returns:
        Dict[str, Any]: Slack-compliant JSON payload.
    """
    blocks = [{
        "type": "header",
        "text": {"type": "plain_text", "text": "🚀 TechPulse Smart Digest"}
    }]

    if intro:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"_{intro}_"}
        })
    
    blocks.append({"type": "divider"})

    total_count = sum(len(v) for v in grouped_articles.values())

    for theme, articles in grouped_articles.items():
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{theme}*"}
        })
        for a in articles:
            # Build the narrative text: Summary + Insight
            narrative = f"_{a['summary']}_"
            if a.get("why_it_matters"):
                narrative += f"\n> *Insight:* {a['why_it_matters']}"
                
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn",
                         "text": (f"• <{a['source_url']}|{a['title']}>\n"
                                   f"  {narrative}")},
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


def discord_payload_chunks(grouped_articles: Dict[str, List[Dict[str, Any]]], intro: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Generates Discord Markdown payloads, split into chunks to stay under character limits.
    
    Args:
        grouped_articles: Dictionary of themed articles.
        intro: Optional LLM-generated narrative introduction.
        
    Returns:
        List[Dict[str, Any]]: List of Discord message payloads.
    """
    chunks = []
    current = "# 🚀 TechPulse Smart Digest\n\n"
    if intro:
        current += f"*{intro}*\n\n---\n"
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
            insight = f"\n> **Insight:** {a['why_it_matters']}" if a.get("why_it_matters") else ""
            entry = (
                f"**{i}. [{a['title']}](<{a['source_url']}>)** (Score: {a['score']})\n"
                f"> {a['summary']}{insight}\n\n"
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

def deliver(target_user_id: Optional[str] = None, digest: Optional[Dict[str, Any]] = None) -> None:
    """
    Main delivery entry point.
    
    If digest is provided, it uses the pre-built narrative structure.
    Otherwise, it fetches pending articles and groups them automatically.
    """
    if digest:
        # V2 Path: Use pre-built digest
        articles_by_user = {digest["user_id"]: digest}
    else:
        # V1/Legacy Path: Fetch all pending
        all_articles = (
            supabase.table("articles")
            .select("user_id, title, summary, why_it_matters, source_url, source, score, topics")
            .gte("created_at", (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat())
            .eq("is_delivered", False)
            .gte("score", 3.0)
            .execute()
        ).data or []
        
        if target_user_id:
            all_articles = [a for a in all_articles if a["user_id"] == target_user_id]
            
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

    for user_id, content in articles_by_user.items():
        profile = tenant_profiles.get(user_id)
        if not profile:
            logger.warning(f"User {user_id} has articles but no profile, skipping.")
            continue

        user_name = profile.get("full_name") or "Tech Explorer"
        
        if digest:
            grouped = digest["sections"]
            intro = digest.get("intro")
        else:
            grouped = group_by_themes(content)
            intro = None
            
        total_to_send = sum(len(v) for v in grouped.values())
        
        logger.info(f"Delivering {total_to_send} articles to {user_name} ({user_id})...")

        slack_url = profile.get("slack_webhook_url")
        discord_url = profile.get("discord_webhook_url")

        if not slack_url and not discord_url:
            logger.info(f"User {user_id} has no webhooks configured.")
            continue

        # 1. Deliver to Slack
        if slack_url:
            payload = slack_payload(grouped, intro=intro)
            payload["blocks"][0]["text"]["text"] = f"🚀 Hi {user_name}, here is your TechPulse Digest"
            try:
                r = httpx.post(slack_url, json=payload, timeout=10)
                r.raise_for_status()
                logger.success(f"Slack ✅ (User {user_id})")
            except Exception as e:
                logger.error(f"Slack failed for {user_id}: {e}")

        # 2. Deliver to Discord
        if discord_url:
            chunks = discord_payload_chunks(grouped, intro=intro)
            if chunks:
                chunks[0]["content"] = chunks[0]["content"].replace("Smart Digest", f"Digest for {user_name}")
            
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