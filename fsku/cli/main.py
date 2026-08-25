"""FSKU Command Line Interface with Rich institutional financial formatting."""

from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fsku import __version__
from fsku.core.database import get_db
from fsku.core.forward_curve import ForwardCurveEngine
from fsku.core.models import ForwardCurveRequest
from fsku.core.pricing import PricingEngine
from fsku.sync.engine import SyncEngine

app = typer.Typer(
    name="fsku",
    help="FSKU: Open-Source GPU Compute Benchmark Index & Forward Curve Platform",
    add_completion=False,
)
snapshot_app = typer.Typer(help="Manage point-in-time market snapshots")
app.add_typer(snapshot_app, name="snapshot")

console = Console()

@app.command("version")
def version_cmd():
    """Print the FSKU software version."""
    console.print(f"[bold white]FSKU[/bold white] Benchmark Platform version [green]{__version__}[/green]")

@app.command("stats")
def stats_cmd(
    db_path: Optional[str] = typer.Option(None, "--db-dir", help="Path to database storage directory"),
):
    """Display market KPIs and database statistics."""
    db = get_db(db_path)
    observations = db.observations.find()
    kpis = PricingEngine.calculate_kpis(observations)

    title = f"FSKU Market Tape Statistics (v{__version__})"
    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bold white")

    table.add_row("Total Active Observations", str(kpis["observation_count"]))
    table.add_row("Public Sources Represented", str(kpis["source_count"]))
    table.add_row("Distinct GPU Families", str(kpis["gpu_families_count"]))
    table.add_row("Median Tape Rate", f"${kpis['median_observed_rate']:.2f} / GPU-hour")
    table.add_row("H100 Price Dispersion", f"{kpis['h100_dispersion']:.1f}x (High / Low)")
    table.add_row("Lowest H100 Observation", f"{kpis['lowest_h100'].get('provider', '')} @ ${kpis['lowest_h100'].get('rate', 0):.2f}/GPU-hr")
    table.add_row("Highest H100 Observation", f"{kpis['highest_h100'].get('provider', '')} @ ${kpis['highest_h100'].get('rate', 0):.2f}/GPU-hr")
    table.add_row("Historical Snapshots Stored", str(db.snapshots.count()))
    table.add_row("Resync Audit Logs", str(db.sync_logs.count()))

    console.print(table)

@app.command("index")
def index_cmd(
    method: str = typer.Option("median", "--method", "-m", help="Methodology: median, trimmed_10, trimmed_20, provider_balanced, simple_mean, gpu_weighted"),
    db_path: Optional[str] = typer.Option(None, "--db-dir", help="Path to database storage directory"),
):
    """Display computed Spot Index benchmarks across all tracked GPU SKUs."""
    db = get_db(db_path)
    observations = db.observations.find()
    summaries = PricingEngine.calculate_sku_index_summaries(observations, method=method)

    table = Table(
        title=f"FSKU Spot Index Summary (Method: {method.upper()})",
        show_header=True,
        header_style="bold green",
    )
    table.add_column("GPU SKU", style="bold white")
    table.add_column("Index $/GPU-hr", justify="right", style="bold cyan")
    table.add_column("Min", justify="right", style="dim")
    table.add_column("Max", justify="right", style="dim")
    table.add_column("IQR Band", justify="right")
    table.add_column("Dispersion", justify="right")
    table.add_column("Obs", justify="right")
    table.add_column("Providers", justify="right")
    table.add_column("Confidence", style="bold")
    table.add_column("Status")

    for s in summaries:
        conf_color = "green" if s.confidence == "HIGH" else ("yellow" if s.confidence == "MODERATE" else "red")
        stat_color = "white" if s.market_status == "ACTIVE" else "magenta"
        table.add_row(
            s.sku,
            f"${s.index_price:.2f}",
            f"${s.min_price:.2f}",
            f"${s.max_price:.2f}",
            f"${s.iqr_low:.2f} - ${s.iqr_high:.2f}",
            f"{s.dispersion_ratio:.1f}x",
            str(s.observation_count),
            str(s.provider_count),
            f"[{conf_color}]{s.confidence}[/{conf_color}]",
            f"[{stat_color}]{s.market_status}[/{stat_color}]",
        )

    console.print(table)

@app.command("sensitivity")
def sensitivity_cmd(
    db_path: Optional[str] = typer.Option(None, "--db-dir", help="Path to database storage directory"),
):
    """Show methodology sensitivity matrix across calculation formulas."""
    db = get_db(db_path)
    observations = db.observations.find()
    sens = PricingEngine.calculate_sensitivity(observations)

    table = Table(
        title="FSKU Benchmark Methodology Sensitivity Analysis",
        show_header=True,
        header_style="bold yellow",
    )
    table.add_column("GPU SKU", style="bold white")
    table.add_column("Median (Base)", justify="right", style="bold green")
    table.add_column("10% Trim", justify="right")
    table.add_column("20% Trim", justify="right")
    table.add_column("Provider-Balanced", justify="right", style="cyan")
    table.add_column("Simple Mean", justify="right")
    table.add_column("GPU-Weighted", justify="right")
    table.add_column("Max Divergence", justify="right", style="bold red")

    for s in sens:
        table.add_row(
            s.sku,
            f"${s.baseline_median:.2f}",
            f"${s.trimmed_mean_10:.2f}",
            f"${s.trimmed_mean_20:.2f}",
            f"${s.provider_balanced:.2f}",
            f"${s.simple_mean:.2f}",
            f"${s.gpu_weighted_mean:.2f}",
            f"{s.max_divergence_pct:.1f}%",
        )

    console.print(table)

@app.command("ablation")
def ablation_cmd(
    sku: Optional[str] = typer.Option(None, "--sku", "-s", help="Filter ablation by target SKU (e.g. H100 SXM)"),
    db_path: Optional[str] = typer.Option(None, "--db-dir", help="Path to database storage directory"),
):
    """Show data source ablation resilience (price impact when removing a provider)."""
    db = get_db(db_path)
    observations = db.observations.find()
    results = PricingEngine.calculate_ablation(observations, target_sku=sku)

    table = Table(
        title="FSKU Source Ablation Stress Test (Provider Exclusions)",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Provider Excluded", style="bold white")
    table.add_column("Target SKU", style="white")
    table.add_column("Original Index", justify="right")
    table.add_column("Ablated Index", justify="right")
    table.add_column("Delta ($)", justify="right")
    table.add_column("Delta (%)", justify="right", style="bold")
    table.add_column("Remaining Obs", justify="right")
    table.add_column("Impact Level")

    for r in results:
        imp_color = "dim" if r.impact_level == "NEGLIGIBLE" else ("green" if r.impact_level == "LOW" else ("yellow" if r.impact_level == "MODERATE" else "red"))
        delta_color = "green" if r.delta_pct >= 0 else "red"
        table.add_row(
            r.provider_removed,
            r.sku,
            f"${r.original_price:.2f}",
            f"${r.ablated_price:.2f}",
            f"{r.delta_abs:+.2f}",
            f"[{delta_color}]{r.delta_pct:+.1f}%[/{delta_color}]",
            str(r.observations_remaining),
            f"[{imp_color}]{r.impact_level}[/{imp_color}]",
        )

    console.print(table)

@app.command("list")
def list_cmd(
    gpu: Optional[str] = typer.Option(None, "--gpu", "-g", help="Filter by GPU family or name (e.g. H100, B200)"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Filter by provider (e.g. RunPod, CoreWeave)"),
    basis: Optional[str] = typer.Option(None, "--basis", "-b", help="Filter by price basis (On-demand, Spot, etc.)"),
    sort_by: str = typer.Option("perGpu", "--sort", "-s", help="Sort field (perGpu, provider, gpu, total)"),
    reverse: bool = typer.Option(False, "--desc", "-d", help="Sort descending"),
    limit: Optional[int] = typer.Option(50, "--limit", "-n", help="Max rows to show"),
    db_path: Optional[str] = typer.Option(None, "--db-dir", help="Path to database storage directory"),
):
    """List normalized compute price observations from the NoSQL tape."""
    db = get_db(db_path)
    query = {}
    if provider:
        query["provider"] = {"$contains": provider}
    if gpu:
        query["gpu"] = {"$contains": gpu}
    if basis:
        query["basis"] = basis

    rows = db.observations.find(filter_query=query, sort_by=sort_by, reverse=reverse, limit=limit)

    if not rows:
        console.print("[yellow]No price observations matched your filter criteria.[/yellow]")
        return

    table = Table(
        title=f"FSKU Normalized Compute Price Tape ({len(rows)} rows)",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Provider", style="bold white")
    table.add_column("GPU / Instance", style="white")
    table.add_column("Basis", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Published $/hr", justify="right")
    table.add_column("Normalized $/GPU-hr", justify="right", style="bold green")
    table.add_column("VRAM", justify="right")
    table.add_column("Source", style="dim")

    for r in rows:
        table.add_row(
            r.get("provider", ""),
            f"{r.get('gpu', '')} ({r.get('instance', '')})",
            r.get("basis", ""),
            str(r.get("gpuCount", 1)),
            f"${r.get('total', 0):.2f}",
            f"${r.get('perGpu', 0):.2f}",
            f"{r.get('vram', 0)} GB",
            r.get("source", ""),
        )

    console.print(table)

@app.command("sync")
def sync_cmd(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Filter sync to specific provider"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview sync results without persisting"),
    label: Optional[str] = typer.Option(None, "--label", "-l", help="Custom snapshot label"),
    db_path: Optional[str] = typer.Option(None, "--db-dir", help="Path to database storage directory"),
):
    """Trigger an on-demand market feed resynchronization."""
    db = get_db(db_path)
    engine = SyncEngine(db=db)

    with console.status("[bold green]Synchronizing market feeds from compute providers...[/bold green]"):
        log = asyncio.run(engine.resync(provider_filter=provider, dry_run=dry_run, snapshot_label=label))

    status_color = "green" if log.status == "success" else ("yellow" if log.status == "partial" else "red")
    summary = (
        f"[bold]Status:[/bold] [{status_color}]{log.status.upper()}[/{status_color}]\n"
        f"[bold]Duration:[/bold] {log.duration_ms} ms\n"
        f"[bold]Providers Polled:[/bold] {', '.join(log.providers_polled)}\n"
        f"[bold]Added:[/bold] {log.added_count}  |  [bold]Updated:[/bold] {log.updated_count}  |  [bold]Unchanged:[/bold] {log.unchanged_count}\n"
        f"[bold]Total Active Rows in DB:[/bold] {log.total_active}\n"
        f"[bold]Snapshot ID:[/bold] {log.snapshot_id or 'None'}"
    )
    if log.errors:
        summary += f"\n[bold red]Errors:[/bold red] {'; '.join(log.errors)}"

    console.print(Panel(summary, title="FSKU Resync Report", border_style=status_color))

@app.command("forward")
def forward_cmd(
    gpu: str = typer.Option("H100", "--gpu", "-g", help="GPU family (H100, H200, B200, B300, A100)"),
    basis: str = typer.Option("firm", "--basis", "-b", help="Cash anchor basis: firm, all, spot"),
    cadence: int = typer.Option(24, "--cadence", "-c", help="Hardware architecture cadence (months)"),
    carry: float = typer.Option(5.0, "--carry", help="Annual carry + scarcity rate in %"),
    horizon: int = typer.Option(36, "--horizon", "-H", help="Curve horizon in months"),
    db_path: Optional[str] = typer.Option(None, "--db-dir", help="Path to database storage directory"),
):
    """Compute and display model-implied forward term structure."""
    db = get_db(db_path)
    req = ForwardCurveRequest(
        family=gpu,
        basis=basis,
        cadence=cadence,
        carry_rate=carry,
        horizon=horizon,
    )
    observations = db.observations.find()
    res = ForwardCurveEngine.calculate_forward_curve(observations, req)

    if not res:
        console.print(f"[red]Error: Could not calculate forward curve for GPU family '{gpu}'.[/red]")
        return

    roll_pct = (res.annual_factor - 1.0) * 100
    roll_style = "green" if roll_pct >= 0 else "red"
    overview = (
        f"[bold]GPU Family:[/bold] {res.family}  |  [bold]Cash Anchor S₀:[/bold] ${res.S0:.2f}/GPU-hr\n"
        f"[bold]Tech Deflation (d):[/bold] {res.d * 100:.1f}% / yr  |  [bold]Carry Rate (c):[/bold] {res.carry:.1f}% / yr\n"
        f"[bold]Net Annual Curve Roll:[/bold] [{roll_style}]{roll_pct:+.1f}% / yr[/{roll_style}]\n"
        f"[bold]Matched Generation Pairs:[/bold] {len(res.tech.observations)}\n"
        f"[bold]Mode:[/bold] {res.mode.upper()} {'(Fallback: All Tape)' if res.fallback else ''}"
    )
    console.print(Panel(overview, title=f"FSKU Implied Forward Curve: {res.family}", border_style="cyan"))

    table = Table(show_header=True, header_style="bold yellow")
    table.add_column("Tenor", style="bold white")
    table.add_column("Implied Rate", justify="right", style="bold green")
    table.add_column("Lower IQR", justify="right", style="dim")
    table.add_column("Upper IQR", justify="right", style="dim")
    table.add_column("vs Cash Anchor", justify="right")

    key_months = [m for m in [0, 3, 6, 12, 18, 24, 36, 48, 60] if m <= res.horizon]
    points_by_m = {p.m: p for p in res.points}

    for m in key_months:
        if m in points_by_m:
            p = points_by_m[m]
            chg = p.chg_pct * 100
            chg_style = "green" if chg >= 0 else "red"
            table.add_row(
                "Cash (0M)" if m == 0 else f"{m} Months",
                f"${p.base:.2f}",
                f"${p.low:.2f}",
                f"${p.high:.2f}",
                f"[{chg_style}]{chg:+.1f}%[/{chg_style}]",
            )

    console.print(table)

@app.command("compare")
def compare_cmd(
    families: str = typer.Option("H100,H200,B200,B300,A100", "--families", "-f", help="Comma-separated GPU families"),
    basis: str = typer.Option("firm", "--basis", "-b", help="Price basis: firm, all, spot"),
    cadence: int = typer.Option(24, "--cadence", "-c", help="Cadence in months"),
    carry: float = typer.Option(5.0, "--carry", help="Carry rate %"),
    horizon: int = typer.Option(36, "--horizon", "-H", help="Horizon months"),
    db_path: Optional[str] = typer.Option(None, "--db-dir", help="Path to database storage directory"),
):
    """Compare multiple GPU forward curves simultaneously."""
    db = get_db(db_path)
    observations = db.observations.find()
    fam_list = [f.strip() for f in families.split(",") if f.strip()]
    res = ForwardCurveEngine.compare_forward_curves(
        observations=observations,
        families=fam_list,
        basis=basis,
        cadence=cadence,
        carry_rate=carry,
        horizon=horizon,
    )

    table = Table(title=f"FSKU Cross-SKU Forward Curve Comparison (Basis: {basis.upper()})", show_header=True, header_style="bold cyan")
    table.add_column("Tenor", style="bold white")
    for fam in fam_list:
        table.add_column(fam, justify="right", style="bold")

    for t in res["tenors"]:
        row = ["Cash (0M)" if t == 0 else f"{t}M"]
        for fam in fam_list:
            if fam in res["curves"]:
                pts = {p["m"]: p["base"] for p in res["curves"][fam]["points"]}
                v = pts.get(t)
                row.append(f"${v:.2f}" if v is not None else "—")
            else:
                row.append("—")
        table.add_row(*row)

    console.print(table)

@snapshot_app.command("list")
def snapshot_list_cmd(
    limit: int = typer.Option(20, "--limit", "-n", help="Max snapshots to show"),
    db_path: Optional[str] = typer.Option(None, "--db-dir", help="Path to database storage directory"),
):
    """List historical market snapshots in the NoSQL database."""
    db = get_db(db_path)
    snaps = db.snapshots.find(sort_by="timestamp", reverse=True, limit=limit)

    if not snaps:
        console.print("[yellow]No market snapshots found.[/yellow]")
        return

    table = Table(title="FSKU Market Snapshots", show_header=True, header_style="bold cyan")
    table.add_column("Snapshot ID", style="bold white")
    table.add_column("Timestamp", style="dim")
    table.add_column("Label", style="white")
    table.add_column("Observations", justify="right")
    table.add_column("Median Rate", justify="right", style="green")
    table.add_column("H100 Spread", justify="right")

    for s in snaps:
        table.add_row(
            s["id"],
            s.get("timestamp", "")[:19].replace("T", " "),
            s.get("label", ""),
            str(s.get("observation_count", 0)),
            f"${s.get('median_rate', 0):.2f}",
            f"{s.get('h100_dispersion', 1.0):.1f}x",
        )

    console.print(table)

@snapshot_app.command("create")
def snapshot_create_cmd(
    label: str = typer.Option("Manual CLI snapshot", "--label", "-l", help="Label description for snapshot"),
    db_path: Optional[str] = typer.Option(None, "--db-dir", help="Path to database storage directory"),
):
    """Create a manual point-in-time market snapshot."""
    db = get_db(db_path)
    snap = db.create_snapshot(label=label)
    console.print(f"[bold green]Snapshot created successfully:[/bold green] [white]{snap['id']}[/white] ({snap['observation_count']} rows)")

@app.command("serve")
def serve_cmd(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host address to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload on code change"),
    db_path: Optional[str] = typer.Option(None, "--db-dir", help="Path to database storage directory"),
):
    """Start the FSKU FastAPI REST server and interactive web dashboard."""
    import uvicorn
    console.print(f"[bold green]Starting FSKU Benchmark Platform (Built by NATIVX) on http://{host}:{port}...[/bold green]")
    console.print(f"[dim]Interactive REST API docs available at http://{host}:{port}/api/docs[/dim]")
    uvicorn.run("fsku.api.app:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    app()
