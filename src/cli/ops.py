"""
techpulse-ops — Operator CLI
Uses the service-role Supabase key from .env (bypasses RLS).
Intended for server admins, cron jobs, and deployment pipelines.
"""
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

def _get_db():
    """Return the shared Supabase service-role client."""
    from shared.db import supabase
    return supabase


# ── run sub-commands ─────────────────────────────────────────────────────────

@run_app.command("collect")
def run_collect():
    """Fetch new articles from all RSS sources into Redis queue."""
    console.rule("[bold blue]Collector")
    from services.collector.main import collect
    collect()
    rprint("[green]✓ Collector finished.[/green]")


@run_app.command("summarize")
def run_summarize():
    """Summarize articles from Redis queue using the AI model."""
    console.rule("[bold blue]Summarizer")
    import asyncio
    from services.summarizer.main import summarize
    asyncio.run(summarize())
    rprint("[green]✓ Summarizer finished.[/green]")


@run_app.command("deliver")
def run_deliver():
    """Deliver high-score articles to all tenant webhooks."""
    console.rule("[bold blue]Delivery")
    from services.delivery.main import deliver
    deliver()
    rprint("[green]✓ Delivery finished.[/green]")


@run_app.command("all")
def run_all():
    """Run the full pipeline: collect → summarize → deliver."""
    console.rule("[bold cyan]Full Pipeline")
    run_collect()
    run_summarize()
    run_deliver()
    rprint("\n[bold green]✓ Full pipeline complete.[/bold green]")


# ── monitor ──────────────────────────────────────────────────────────────────

@app.command("monitor")
def monitor(live: bool = typer.Option(True, "--live/--once", help="Auto-refresh or single snapshot")):
    """Live system monitor — queue depth, telemetry, stats."""
    import subprocess, sys
    args = [sys.executable, "-m", "shared.monitor"]
    if live:
        args.append("--live")
    subprocess.run(args)


# ── tenants sub-commands ──────────────────────────────────────────────────────

@tenants_app.command("list")
def tenants_list():
    """List all registered tenant profiles."""
    db = _get_db()
    res = db.table("tenant_profiles").select("user_id, slack_webhook_url, discord_webhook_url, created_at").execute()
    rows = res.data or []

    if not rows:
        rprint("[yellow]No tenants registered yet.[/yellow]")
        raise typer.Exit()

    table = Table(title="Registered Tenants", show_lines=True)
    table.add_column("User ID", style="cyan", no_wrap=True)
    table.add_column("Slack", style="dim")
    table.add_column("Discord", style="dim")
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
def tenants_stats():
    """Show per-tenant article counts."""
    db = _get_db()
    res = db.table("articles").select("user_id, is_delivered").execute()
    rows = res.data or []

    from collections import defaultdict
    counts: dict = defaultdict(lambda: {"total": 0, "delivered": 0})
    for r in rows:
        uid = r["user_id"]
        counts[uid]["total"] += 1
        if r.get("is_delivered"):
            counts[uid]["delivered"] += 1

    table = Table(title="Per-Tenant Article Stats", show_lines=True)
    table.add_column("User ID", style="cyan")
    table.add_column("Total Articles", justify="right")
    table.add_column("Delivered", justify="right", style="green")
    table.add_column("Pending", justify="right", style="yellow")

    for uid, c in sorted(counts.items()):
        pending = c["total"] - c["delivered"]
        table.add_row(uid, str(c["total"]), str(c["delivered"]), str(pending))

    console.print(table)


# ── reset ─────────────────────────────────────────────────────────────────────

@app.command("reset")
def reset(
    confirm: bool = typer.Option(False, "--confirm", help="Must pass --confirm to execute reset"),
):
    """⚠️  Wipe ALL data from articles, telemetry, and Redis queue."""
    if not confirm:
        rprint("[red]⚠️  This will delete ALL data. Pass --confirm to proceed.[/red]")
        raise typer.Exit(1)

    import asyncio
    from shared.maintenance import reset as do_reset
    asyncio.run(do_reset())
    rprint("[bold red]✓ All data wiped.[/bold red]")


if __name__ == "__main__":
    app()
