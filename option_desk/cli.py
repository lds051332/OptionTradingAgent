from __future__ import annotations

from datetime import date

import typer
from rich.console import Console

from option_desk.config import get_settings, load_project_env, parse_tickers
from option_desk.i18n import normalize_lang, t
from option_desk.pipeline import run_desk
from option_desk.report import print_run, write_report

load_project_env()

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.command()
def analyze(
    tickers: str | None = typer.Option(
        None, "--tickers", help="Comma-separated symbols, default NVDA,MSFT"
    ),
    as_of: str | None = typer.Option(
        None, "--as-of", help="YYYY-MM-DD. Shifts DTE/calendar; chain is still live."
    ),
    lang: str | None = typer.Option(
        None,
        "--lang",
        help="Output language: en or zh. Default OPTION_DESK_OUTPUT_LANGUAGE or en.",
    ),
) -> None:
    """Screen put candidates, gate the calendar, scout events, and print a desk decision."""
    settings = get_settings()
    if lang is not None:
        settings = settings.model_copy(update={"output_language": normalize_lang(lang)})
    symbols = parse_tickers(tickers, settings)
    as_of_date = date.fromisoformat(as_of) if as_of else date.today()
    if as_of_date > date.today():
        raise typer.BadParameter("--as-of cannot be in the future")
    run = run_desk(symbols, as_of=as_of_date, settings=settings)
    print_run(run, console)
    path = write_report(run, settings.reports_dir)
    console.print(f"[green]{t(run.language, 'wrote')}[/green] {path}")


@app.command()
def version() -> None:
    from option_desk import __version__

    console.print(__version__)


def main() -> None:
    app()


if __name__ == "__main__":
    app()
