import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from shared.redis_client import redis, STREAM_RAW
from shared.db import supabase
from datetime import datetime, timezone, timedelta

console = Console()

def get_stats():
    # 1. Redis Stats
    try:
        pending = redis.execute(command=["XLEN", STREAM_RAW]) or 0
    except:
        pending = "Error"

    # 2. Database Stats
    try:
        # Total articles
        total_res = supabase.table("articles").select("count", count="exact").execute()
        total = total_res.count or 0
        
        # Delivered
        delivered_res = supabase.table("articles").select("count", count="exact").eq("is_delivered", True).execute()
        delivered = delivered_res.count or 0
        
        # To deliver (Ready)
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        ready_res = supabase.table("articles").select("count", count="exact").eq("is_delivered", False).gte("created_at", since).gte("score", 2.5).execute()
        ready = ready_res.count or 0
    except Exception as e:
        total = delivered = ready = "Error"

    # 3. Telemetry (Recent Runs)
    try:
        telemetry = supabase.table("telemetry").select("*").order("timestamp", desc=True).limit(5).execute().data or []
    except:
        telemetry = []

    return pending, total, delivered, ready, telemetry

def generate_layout(stats):
    pending, total, delivered, ready, telemetry = stats
    
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3)
    )
    
    # Header
    layout["header"].update(Panel("TechPulse AI — System Monitor", style="bold cyan"))
    
    # Main content split into stats and logs
    layout["main"].split_row(
        Layout(name="stats"),
        Layout(name="logs")
    )
    
    # Stats Table
    stats_table = Table(title="System Pipeline")
    stats_table.add_column("Metric", style="magenta")
    stats_table.add_column("Value", style="bold green")
    
    stats_table.add_row("Pending in Redis (Raw)", str(pending))
    stats_table.add_row("Total in Database", str(total))
    stats_table.add_row("Total Delivered", str(delivered))
    stats_table.add_row("Ready for Delivery (Top 24h)", str(ready))
    
    layout["stats"].update(Panel(stats_table, border_style="blue"))
    
    # Logs Table
    logs_table = Table(title="Recent Activity (Telemetry)")
    logs_table.add_column("Time", style="dim")
    logs_table.add_column("Service")
    logs_table.add_column("Metrics")
    
    for entry in telemetry:
        ts = datetime.fromisoformat(entry['timestamp']).strftime("%H:%M:%S")
        svc = entry['service'].capitalize()
        metrics = ", ".join([f"{k}: {v}" for k, v in entry['metrics'].items()])
        color = "green" if entry.get('success', True) else "red"
        logs_table.add_row(ts, f"[{color}]{svc}[/]", metrics)
        
    layout["logs"].update(Panel(logs_table, border_style="blue"))
    
    # Footer
    layout["footer"].update(Panel(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim"))
    
    return layout

def run_monitor():
    with Live(generate_layout(get_stats()), refresh_per_second=0.5) as live:
        try:
            while True:
                live.update(generate_layout(get_stats()))
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    if "--live" in sys.argv:
        run_monitor()
    else:
        console.print(generate_layout(get_stats()))
