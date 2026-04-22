"""
techpulse-ops — Operator CLI
Uses the service-role Supabase key from .env (bypasses RLS).
Intended for server admins, cron jobs, and deployment pipelines.
"""
from typing import Any, Dict
import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from loguru import logger
import os

from services.summarizer import main as summarizer_main
from services.delivery import main as delivery_main
from services.enricher import embedder, deduplicator, novelty, clusterer
from services.ranker import scorer
from services.agents.research_agent import build_research_agent
from services.agents.composer_agent import compose_digest
from shared.redis_client import read_from_group, acknowledge_message, ensure_group_exists
from shared.config import settings
from shared.db import get_tenant_profiles, log_telemetry, get_source_quality

app = typer.Typer(
    name="techpulse-ops",
    help="🛠️  TechPulse AI — Operator CLI (system-level access)",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

run_app = typer.Typer(help="Run pipeline services", no_args_is_help=True)
app.add_typer(run_app, name="run")

tenants_app = typer.Typer(help="Manage tenants", no_args_is_help=True)
app.add_typer(tenants_app, name="tenants")

console = Console()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_db() -> Any:
    """Returns the shared Supabase service-role client for administrative access."""
    from shared.db import supabase
    return supabase


def get_active_users() -> list[str]:
    """Fetches all registered user IDs from tenant profiles."""
    profiles = get_tenant_profiles()
    return [p["user_id"] for p in profiles]


def process_article_v2(db: Any, msg: Dict[str, Any], agent: Any, GROQ_API_KEY: str) -> bool:
    """
    Executes the full V2 pipeline for a single article message.
    Stages: 2 (Enrich), 3 (Rank), 4 (Research)
    """
    article = msg["data"]
    msg_id = msg["id"]
    user_id = article.get("user_id")
    title = article.get("title", "Untitled")

    try:
        # Stage 2: Enrich (Semantic)
        embedding = embedder.embed_text(article.get("content", title), GROQ_API_KEY)
        
        if deduplicator.is_near_duplicate(db, embedding, user_id):
            rprint(f"[dim]SKIP: Near-duplicate: {title[:50]}...[/dim]")
            acknowledge_message(summarizer_main.GROUP_NAME, msg_id)
            return False
        
        novelty_score = novelty.compute_novelty_score(db, embedding, user_id)
        event_id = clusterer.find_or_create_event(db, summarizer_main.llm, embedding, title, user_id)
        
        # Stage 3: Rank
        from services.summarizer.main import get_filter_config
        config = get_filter_config(user_id)
        quality = get_source_quality(article.get("source_id"), user_id)
        
        signals = scorer.RankSignals(
            base_relevance=3.0, # Neutral fallback
            novelty_score=novelty_score,
            source_quality=quality,
            topic_match=0.5,
            priority_boost=1.0 if any(t.lower() in [tc.lower() for tc in config.get("priority", [])] for t in article.get("topics", [])) else 0.0
        )
        final_score = scorer.compute_final_score(signals)
        
        # Stage 4: Research Agent (RAG Deep Dive)
        result = agent.invoke({
            "article_text":  article.get("content", ""),
            "article_title": title,
            "user_id":       user_id,
            "embedding":     embedding
        })
        
        # Stage 5: Save
        db.table("articles").upsert({
            "user_id":       user_id,
            "title":         title,
            "source_url":    article.get("source_url"),
            "source":        article.get("source"),
            "content":       article.get("content"),
            "embedding":     embedding,
            "novelty_score": novelty_score,
            "event_id":      event_id,
            "score":         final_score,
            "summary":       result["summary"],
            "why_it_matters": result["why_it_matters"],
            "topics":        result.get("topics", []),
            "v2_processed":  True
        }, on_conflict="source_url,user_id").execute()
        
        acknowledge_message(summarizer_main.GROUP_NAME, msg_id)
        rprint(f"[green]✓ Processed: {title[:50]}... [Score: {final_score}][/green]")
        return True

    except Exception as e:
        logger.error(f"Failed to process V2 pipeline for {title}: {e}")
        return False


# ── Run Sub-Commands ─────────────────────────────────────────────────────────

@run_app.command("collect")
def run_collect() -> None:
    """Scrape new articles from all active multi-tenant RSS sources into the Redis queue."""
    console.rule("[bold blue]Collector Service")
    from services.collector.main import collect
    collect()
    rprint("[green]✓ Collector finished.[/green]")


@run_app.command("summarize")
def run_summarize() -> None:
    """Analyze and summarize articles from the Redis queue using AI refinement."""
    console.rule("[bold blue]Summarizer Service (Legacy/Batch)")
    import asyncio
    from services.summarizer.main import summarize
    asyncio.run(summarize())
    rprint("[green]✓ Summarizer finished.[/green]")


@run_app.command("deliver")
def run_deliver() -> None:
    """Send personalized digests to all tenant webhooks (Slack/Discord)."""
    console.rule("[bold blue]Delivery Service")
    from services.delivery.main import deliver
    deliver()
    rprint("[green]✓ Delivery finished.[/green]")


@run_app.command("all")
def run_all() -> None:
    """Execute the complete end-to-end V2 pipeline: collect → enrich → rank → research → deliver."""
    console.rule("[bold cyan]TechPulse AI V2 Pipeline Orchestration")
    
    GROQ_API_KEY = settings.groq_api_key
    db = _get_db()
    
    # Stage 1: Collect
    ensure_group_exists(summarizer_main.GROUP_NAME)
    console.rule("[dim]Stage 1: Collect", align="left")
    run_collect()

    # Stage 2-5: Enrichment, Ranking, and Research
    console.rule("[dim]Stage 2-5: Personal Intelligence Enhancement", align="left")
    
    # Read articles from Redis Stream
    messages = read_from_group(summarizer_main.GROUP_NAME, summarizer_main.CONSUMER_NAME, count=50)
    if not messages:
        rprint("[yellow]No new articles to process.[/yellow]")
    else:
        rprint(f"[blue]Processing {len(messages)} articles...[/blue]")
        agent = build_research_agent(db, GROQ_API_KEY)
        for msg in messages:
            process_article_v2(db, msg, agent, GROQ_API_KEY)

    # Stage 6: Compose + Deliver
    console.rule("[dim]Stage 6: Multi-Channel Delivery", align="left")
    for user_id in get_active_users():
        digest = compose_digest(db, summarizer_main.llm, user_id)
        if not digest.get("empty"):
            from services.delivery.main import deliver
            deliver(digest=digest)
            rprint(f"[green]✓ Digest delivered to user {user_id}[/green]")
        else:
            rprint(f"[yellow]No items above delivery threshold for user {user_id}[/yellow]")

    rprint("\n[bold green]✓ Full TechPulse V2 pipeline sequence complete.[/bold green]")


# ── Monitor ───────────────────────────────────────────────────────────────────

@app.command("monitor")
def monitor(
    live: bool = typer.Option(True, "--live/--once", help="Enable auto-refreshing dashboard")
) -> None:
    """Launch the live system monitor to track queue depth and telemetry stats."""
    import subprocess
    import sys
    args = [sys.executable, "-m", "shared.monitor"]
    if live:
        args.append("--live")
    subprocess.run(args)


# ── Tenants Sub-Commands ──────────────────────────────────────────────────────

@tenants_app.command("list")
def tenants_list() -> None:
    """List all registered system tenants and their configured webhook status."""
    db = _get_db()
    res = db.table("tenant_profiles").select("user_id, slack_webhook_url, discord_webhook_url, created_at").execute()
    rows = res.data or []

    if not rows:
        rprint("[yellow]No tenants registered yet.[/yellow]")
        raise typer.Exit()

    table = Table(title="Registered TechPulse Tenants", show_lines=True)
    table.add_column("User ID", style="cyan", no_wrap=True)
    table.add_column("Slack", style="dim", justify="center")
    table.add_column("Discord", style="dim", justify="center")
    table.add_column("Created At", style="dim")

    for r in rows:
        table.add_row(
            r["user_id"],
            "✓" if r.get("slack_webhook_url") else "—",
            "✓" if r.get("discord_webhook_url") else "—",
            str(r.get("created_at", ""))[:19],
        )
    console.print(table)


@tenants_app.command("stats")
def tenants_stats() -> None:
    """View per-tenant usage statistics, including delivered and pending article counts."""
    db = _get_db()
    res = db.table("articles").select("user_id, is_delivered").execute()
    rows = res.data or []

    from collections import defaultdict
    counts = defaultdict(lambda: {"total": 0, "delivered": 0})
    for r in rows:
        uid = r["user_id"]
        counts[uid]["total"] += 1
        if r.get("is_delivered"):
            counts[uid]["delivered"] += 1

    table = Table(title="Per-Tenant Article Analytics", show_lines=True)
    table.add_column("User ID", style="cyan")
    table.add_column("Total Scored", justify="right")
    table.add_column("Delivered", justify="right", style="green")
    table.add_column("Pending", justify="right", style="yellow")

    for uid, c in sorted(counts.items()):
        pending = c["total"] - c["delivered"]
        table.add_row(uid, str(c["total"]), str(c["delivered"]), str(pending))

    console.print(table)


# ── System Maintenance ────────────────────────────────────────────────────────

@app.command("reset")
def reset(
    confirm: bool = typer.Option(False, "--confirm", help="Must be passed to verify destructive reset")
) -> None:
    """⚠️ Danger: Wipe ALL data including articles, telemetry, and the Redis stream."""
    if not confirm:
        rprint("[red]⚠️  This will delete ALL data including article history. Pass --confirm to proceed.[/red]")
        raise typer.Exit(1)

    import asyncio
    from shared.maintenance import reset as do_reset
    asyncio.run(do_reset())
    rprint("[bold red]✓ All system data wiped successfully.[/bold red]")


if __name__ == "__main__":
    app()
