from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from option_desk.i18n import localize_hard_reason, normalize_lang, t
from option_desk.schemas import DeltaBucket, DeskRun, TickerSnapshot


def _spread_text(cand, lang: str) -> str:
    if not cand.spread:
        return t(lang, "md_spread_na")
    if normalize_lang(lang) == "zh":
        return (
            f"多头 {cand.spread.long.strike:g} "
            f"（最大亏损 ${cand.spread.max_loss_per_contract:.0f}，"
            f"{cand.spread.contracts} 张）"
        )
    return (
        f"long {cand.spread.long.strike:g} "
        f"(max loss ${cand.spread.max_loss_per_contract:.0f}, "
        f"{cand.spread.contracts} ct)"
    )


def _bucket_rows(snapshot: TickerSnapshot, lang: str) -> list[str]:
    rows = []
    for bucket in (DeltaBucket.CONSERVATIVE, DeltaBucket.STANDARD):
        cand = snapshot.buckets.get(bucket)
        if not cand:
            rows.append(f"- **{bucket.value}**: {t(lang, 'no_contract')}")
            continue
        if normalize_lang(lang) == "zh":
            last_mark = " 成交价" if cand.csp.quote_source.value == "last" else ""
            rows.append(
                f"- **{bucket.value}** `{cand.csp.contract_id}` "
                f"{t(lang, 'strike')} {cand.csp.strike:g} "
                f"Δ={cand.csp.delta:.3f} {t(lang, 'dte')}={cand.csp.dte} "
                f"{t(lang, 'bid_ask')} {cand.csp.bid:.2f}/{cand.csp.ask:.2f} "
                f"{t(lang, 'premium')} ${cand.premium_per_contract:.0f}/张{last_mark} "
                f"CSP {cand.csp_contracts} 张 {t(lang, 'assign')} ${cand.assignment_cash:,.0f}；"
                f"价差 {_spread_text(cand, lang)}"
            )
            continue
        last_mark = " last-print" if cand.csp.quote_source.value == "last" else ""
        rows.append(
            f"- **{bucket.value}** `{cand.csp.contract_id}` strike {cand.csp.strike:g} "
            f"Δ={cand.csp.delta:.3f} DTE={cand.csp.dte} "
            f"bid/ask {cand.csp.bid:.2f}/{cand.csp.ask:.2f} "
            f"premium ${cand.premium_per_contract:.0f}/ct{last_mark} "
            f"CSP {cand.csp_contracts} ct assign ${cand.assignment_cash:,.0f}; "
            f"spread {_spread_text(cand, lang)}"
        )
    return rows


def render_markdown(run: DeskRun) -> str:
    lang = run.language
    lines = [
        f"# {t(lang, 'md_title')} {run.as_of.isoformat()}",
        "",
        f"- {t(lang, 'md_fetched')}: {run.fetched_at.isoformat()}",
        f"- {t(lang, 'md_cash')}: ${run.cash:,.0f}",
        f"- LLM: {run.llm_label}",
        f"- {t(lang, 'md_chain')}",
        "",
    ]
    if run.warnings:
        lines.append(f"## {t(lang, 'md_warnings')}")
        lines.extend(f"- {w}" for w in run.warnings)
        lines.append("")
    lines.append(f"## {t(lang, 'md_events')}")
    if not run.events:
        lines.append(f"- {t(lang, 'md_none')}")
    else:
        for event in run.events:
            lines.append(
                f"- [{event.action.value} / {event.mechanism.value}] {event.title} "
                f"({event.expected_time or t(lang, 'undated')}) "
                f"tickers={','.join(event.tickers)}"
            )
    lines.append("")
    for snap in run.snapshots:
        lines += [
            f"## {snap.ticker} @ {snap.spot:.2f}",
            f"- {t(lang, 'md_holding')}: {snap.calendar.holding_start} → {snap.calendar.holding_end}",
            f"- {t(lang, 'md_hard')}: {snap.calendar.hard_skip}",
        ]
        if snap.calendar.hard_reasons:
            lines.extend(f"- {localize_hard_reason(r, lang)}" for r in snap.calendar.hard_reasons)
        if snap.calendar.soft_macros:
            lines.append(
                f"- {t(lang, 'md_soft')}: "
                + ", ".join(f"{m.kind} {m.event_date}" for m in snap.calendar.soft_macros)
            )
        lines.extend(snap.notes)
        lines.append("")
        lines.append(f"### {t(lang, 'md_buckets')}")
        lines.extend(_bucket_rows(snap, lang))
        lines.append("")
    lines.append(f"## {t(lang, 'md_decisions')}")
    for decision in run.desk.decisions:
        extra = []
        if decision.structure:
            extra.append(decision.structure.value)
        if decision.delta_bucket:
            extra.append(decision.delta_bucket.value)
        if decision.contract_id:
            extra.append(decision.contract_id)
        suffix = f" ({', '.join(extra)})" if extra else ""
        lines.append(f"- **{decision.ticker} {decision.action.value}**{suffix}: {decision.why}")
        if decision.premium_tradeoff:
            lines.append(f"  - {t(lang, 'md_tradeoff')}: {decision.premium_tradeoff}")
        if decision.payoff:
            po = decision.payoff
            loss = (
                f"${po.max_loss:,.0f} ({t(lang, 'md_max_loss')} {'capped' if po.loss_limited else '@ $0'})"
                if normalize_lang(lang) != "zh"
                else f"${po.max_loss:,.0f}（{'有限' if po.loss_limited else '股价到 $0'}）"
            )
            lines.append(
                f"  - {t(lang, 'md_payoff')}: {t(lang, 'md_max_profit')} ${po.max_profit:,.0f}; "
                f"{t(lang, 'md_breakeven')} {po.breakeven:g}; {loss}"
            )
            lines.append(f"  - {t(lang, 'md_payoff_note')}")
    if run.desk.portfolio_note:
        lines += ["", f"_{run.desk.portfolio_note}_"]
    lines.append("")
    lines.append(t(lang, "md_disclaimer"))
    return "\n".join(lines) + "\n"


def print_run(run: DeskRun, console: Console | None = None) -> None:
    console = console or Console()
    lang = run.language
    console.print(
        f"[bold]{t(lang, 'desk_title')}[/bold] {t(lang, 'as_of')} {run.as_of} | "
        f"{t(lang, 'cash_label')} ${run.cash:,.0f} | LLM={run.llm_label}"
    )
    console.print(f"[dim]{t(lang, 'data_note')}[/dim]")
    for warning in run.warnings:
        console.print(f"[yellow]{t(lang, 'warning')}[/yellow] {warning}")

    if run.events:
        events = Table(title=t(lang, "events"))
        events.add_column(t(lang, "action"))
        events.add_column(t(lang, "mechanism"))
        events.add_column(t(lang, "when"))
        events.add_column(t(lang, "tickers"))
        events.add_column(t(lang, "title"))
        for event in run.events:
            events.add_row(
                event.action.value,
                event.mechanism.value,
                event.expected_time or t(lang, "undated"),
                ",".join(event.tickers),
                event.title,
            )
        console.print(events)

    for snap in run.snapshots:
        table = Table(title=f"{snap.ticker}  {t(lang, 'spot')} {snap.spot:.2f}")
        table.add_column(t(lang, "bucket"))
        table.add_column(t(lang, "contract"))
        table.add_column(t(lang, "strike"))
        table.add_column("Δ")
        table.add_column(t(lang, "dte"))
        table.add_column(t(lang, "bid_ask"))
        table.add_column(t(lang, "premium"))
        table.add_column(t(lang, "csp_qty"))
        table.add_column(t(lang, "assign"))
        for bucket in (DeltaBucket.CONSERVATIVE, DeltaBucket.STANDARD):
            cand = snap.buckets.get(bucket)
            if not cand:
                table.add_row(bucket.value, "—", "—", "—", "—", "—", "—", "—", "—")
                continue
            table.add_row(
                bucket.value,
                cand.csp.contract_id,
                f"{cand.csp.strike:g}",
                f"{cand.csp.delta:.3f}",
                str(cand.csp.dte),
                f"{cand.csp.bid:.2f}/{cand.csp.ask:.2f}",
                (
                    f"${cand.premium_per_contract:.0f} last"
                    if cand.csp.quote_source.value == "last"
                    else f"${cand.premium_per_contract:.0f}"
                ),
                str(cand.csp_contracts),
                f"{cand.assignment_cash:,.0f}",
            )
        console.print(table)
        if snap.calendar.hard_skip:
            reasons = "; ".join(localize_hard_reason(r, lang) for r in snap.calendar.hard_reasons)
            console.print(f"[red]{t(lang, 'hard_skip')}[/red] {reasons}")
        elif snap.calendar.soft_macros:
            console.print(
                f"[cyan]{t(lang, 'soft_macro')}[/cyan] "
                + ", ".join(f"{m.kind} {m.event_date}" for m in snap.calendar.soft_macros)
            )

    decisions = Table(title=t(lang, "decision"))
    decisions.add_column("Ticker")
    decisions.add_column(t(lang, "action"))
    decisions.add_column(t(lang, "structure"))
    decisions.add_column(t(lang, "bucket"))
    decisions.add_column(t(lang, "contract"))
    decisions.add_column(t(lang, "why"))
    for decision in run.desk.decisions:
        decisions.add_row(
            decision.ticker,
            decision.action.value,
            decision.structure.value if decision.structure else "—",
            decision.delta_bucket.value if decision.delta_bucket else "—",
            decision.contract_id or "—",
            decision.why,
        )
    console.print(decisions)
    if run.desk.portfolio_note:
        console.print(f"[dim]{run.desk.portfolio_note}[/dim]")


def write_report(run: DeskRun, reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    names = "_".join(s.ticker for s in run.snapshots) or "empty"
    path = reports_dir / f"{run.as_of.isoformat()}_{names}_{stamp}.md"
    path.write_text(render_markdown(run), encoding="utf-8")
    return path
