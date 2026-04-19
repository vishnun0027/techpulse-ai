"""
techpulse-ops — Operator CLI
Uses the service-role Supabase key from .env (bypasses RLS).
Intended for server admins, cron jobs, and deployment pipelines.
"""
from typing import Any
import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

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
    console.rule("[bold blue]Summarizer Service")
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
    """Execute the complete end-to-end pipeline: collect → summarize → deliver."""
    console.rule("[bold cyan]Full Pipeline Orchestration")
    run_collect()
    run_summarize()
    run_deliver()
    rprint("\n[bold green]✓ Full pipeline sequence complete.[/bold green]")


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
