"""Command-line interface: ``papich-bench run | report | list-answerers | validate``."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from papich_bench import answerers as _answerers  # noqa: F401
from papich_bench.config import ConfigError, RunConfig, Settings
from papich_bench.dataset import load_dataset
from papich_bench.models import RunReport
from papich_bench.registry import available_answerers
from papich_bench.report import to_html, to_markdown
from papich_bench.runner import run_benchmark

app = typer.Typer(add_completion=False, help=__doc__)
console = Console()


@app.command()
def run(
    config: Path = typer.Option("configs/default.yaml", "--config", "-c", help="Run config YAML."),
    dataset: Path | None = typer.Option(None, help="Override the dataset path in the config."),
    answerers: str | None = typer.Option(
        None,
        "--answerers",
        "-a",
        help="Comma-separated labels or answerer names; runs only those config entries.",
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Ignore the on-disk cache."),
    html_out: Path | None = typer.Option(None, "--html", help="Also write an HTML report here."),
) -> None:
    """Run the benchmark and print a leaderboard."""
    cfg = _load_config(config, dataset, answerers)
    settings = Settings()

    with console.status("[bold]Running benchmark…", spinner="dots"):
        report = asyncio.run(
            run_benchmark(
                cfg,
                settings,
                use_cache=not no_cache,
                on_progress=lambda msg: console.log(msg, style="dim"),
            )
        )

    out_path = _save_report(cfg, report)
    _print_leaderboard(report)
    console.print(f"\nResults written to [cyan]{out_path}[/cyan]")

    if html_out is not None:
        html_out.write_text(to_html(report), encoding="utf-8")
        console.print(f"HTML report written to [cyan]{html_out}[/cyan]")


@app.command()
def report(
    results: Path = typer.Argument(..., help="A results JSON file produced by `run`."),
    fmt: str = typer.Option("markdown", "--format", "-f", help="markdown | html"),
    out: Path | None = typer.Option(None, "--out", "-o", help="Write to a file instead of stdout."),
) -> None:
    """Re-render a saved results file (no API calls)."""
    loaded = RunReport.model_validate_json(results.read_text(encoding="utf-8"))
    rendered = to_html(loaded) if fmt == "html" else to_markdown(loaded)
    if out is not None:
        out.write_text(rendered, encoding="utf-8")
        console.print(f"Wrote [cyan]{out}[/cyan]")
    else:
        console.print(rendered)


@app.command("list-answerers")
def list_answerers() -> None:
    """List the answerers available to run."""
    for name in available_answerers():
        console.print(f"• {name}")


@app.command()
def validate(
    config: Path = typer.Option("configs/default.yaml", "--config", "-c"),
) -> None:
    """Validate a config + its dataset without making any API calls."""
    cfg = _load_config(config, None, None)
    flows = load_dataset(cfg.dataset)
    for spec in cfg.answerers:
        if spec.name not in available_answerers():
            raise typer.BadParameter(f"unknown answerer: {spec.name}")
    n_steps = sum(len(f.steps) for f in flows)
    console.print(
        f"[green]OK[/green] — {len(flows)} items ({n_steps} steps), "
        f"{len(cfg.answerers)} answerers, judge={cfg.judge.backend}:{cfg.judge.model}"
    )


def _load_config(config: Path, dataset: Path | None, answerers: str | None) -> RunConfig:
    try:
        cfg = RunConfig.from_yaml(config)
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"config not found: {config}") from exc
    if dataset is not None:
        cfg.dataset = str(dataset)
    if answerers is not None:
        cfg.answerers = cfg.select_answerers(n.strip() for n in answerers.split(",") if n.strip())
    return cfg


def _save_report(cfg: RunConfig, report: RunReport) -> Path:
    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = report.created_at.strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"{stamp}.json"
    out_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return out_path


def _print_leaderboard(report: RunReport) -> None:
    table = Table(title="Leaderboard", show_lines=False)
    table.add_column("#", justify="right")
    table.add_column("Answerer")
    table.add_column("Score", justify="right")
    table.add_column("Judged", justify="right")
    table.add_column("Found", justify="right")
    table.add_column("Truthful", justify="right")
    table.add_column("Errors", justify="right")
    table.add_column("Latency", justify="right")
    rows = report.leaderboard()
    for rank, row in enumerate(rows, start=1):
        table.add_row(
            str(rank),
            row.answerer,
            f"{row.score_pct:.0f}%",
            f"{row.n}/{row.n_total}",
            f"{row.mean_found:.2f}",
            f"{row.mean_truthful:.2f}",
            str(row.n_errors),
            f"{row.mean_latency_s:.1f}s",
        )
    console.print(table)

    unjudged = sum(r.n_unjudged for r in rows)
    if unjudged:
        console.print(
            f"[yellow]⚠ {unjudged} answered step(s) were not judged[/yellow] "
            "(judge rate-limited or errored) — scores above average only the judged steps. "
            "Re-run to fill them in from cache, or see the free-tier note in the README."
        )


def main() -> None:
    try:
        app()
    except ConfigError as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
