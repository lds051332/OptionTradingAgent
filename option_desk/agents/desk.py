from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from option_desk.agents.structured import invoke_structured
from option_desk.config import Settings
from option_desk.i18n import language_instruction, localize_hard_reason, normalize_lang
from option_desk.schemas import (
    DeltaBucket,
    DeskAction,
    DeskLLMResult,
    DeskOutput,
    EventAction,
    ScoutedEvent,
    Structure,
    TickerDecision,
    TickerSnapshot,
)

SYSTEM = """You are the portfolio manager of a narrow US equity put-selling desk.

Universe is only the tickers in the snapshot. Strategy: sell 3-9 DTE puts, cash-secured or bull put spreads.
Delta 0.20 is the default home base (standard). conservative (~0.10-0.12) is allowed to buy gap cushion.
You MUST pick contract_id from the provided ladder. Never invent a strike or expiry.

Hard rules:
- If calendar.hard_skip is true (earnings or FOMC in the holding window): action=SKIP. Do not open a smaller-delta put instead.
- Export-control / hyperscaler-capex gap events labeled skip: SKIP, not conservative.
- CPI/NFP/PCE or events labeled reduce: prefer conservative, or standard + BULL_PUT_SPREAD.
- Events labeled spread_only: structure must be BULL_PUT_SPREAD if a spread exists, else SKIP.
- ignore events do not change the default: OPEN standard CSP if the ladder has it.
- CLOSE_EARLY is only valid when the user has an existing position; this CLI has no position feed, so do not use it.
- assignment_ok must be true only if the chosen strike is still a price you would buy the stock.
- If even the conservative strike is not a stock you would own, SKIP.
- Respect cash: sum of CSP assignment_cash across OPEN CSP names cannot exceed cash. Prefer SKIP on the second name rather than over-assign.
- Compare premium_per_contract between buckets when recommending conservative; mention the tradeoff.
"""


def _bucket_brief(snapshot: TickerSnapshot) -> str:
    lines = []
    for bucket, cand in snapshot.buckets.items():
        spread = "none"
        if cand.spread:
            spread = (
                f"long {cand.spread.long.strike:g} id={cand.spread.long.contract_id} "
                f"max_loss={cand.spread.max_loss_per_contract} qty={cand.spread.contracts}"
            )
        lines.append(
            f"  {bucket.value}: id={cand.csp.contract_id} strike={cand.csp.strike:g} "
            f"delta={cand.csp.delta:.3f} dte={cand.csp.dte} mid={cand.csp.mid:.2f} "
            f"premium=${cand.premium_per_contract:.0f}/ct CSP_qty={cand.csp_contracts} "
            f"assign=${cand.assignment_cash:.0f} spread[{spread}]"
        )
    if not lines:
        lines.append("  (no liquid candidates)")
    return "\n".join(lines)


def _premium_tradeoff(snapshot: TickerSnapshot, lang: str = "en") -> str:
    cons = snapshot.buckets.get(DeltaBucket.CONSERVATIVE)
    std = snapshot.buckets.get(DeltaBucket.STANDARD)
    if not cons or not std:
        return "n/a"
    give_up = std.premium_per_contract - cons.premium_per_contract
    if normalize_lang(lang) == "zh":
        return (
            f"标准档 ${std.premium_per_contract:.0f}/张 vs 保守档 "
            f"${cons.premium_per_contract:.0f}/张 "
            f"（少收 ${give_up:.0f}）"
        )
    return (
        f"standard ${std.premium_per_contract:.0f}/ct vs conservative "
        f"${cons.premium_per_contract:.0f}/ct "
        f"(gives up ${give_up:.0f})"
    )


def _hard_why(reasons: list[str], lang: str) -> str:
    if not reasons:
        return _L(lang, "Hard calendar gate.", "硬日历门控。")
    return "; ".join(localize_hard_reason(r, lang) for r in reasons)


def snapshot_prompt(
    snapshots: list[TickerSnapshot],
    events: list[ScoutedEvent],
    cash: float,
) -> str:
    blocks = [f"Cash available: ${cash:,.0f}", ""]
    for snap in snapshots:
        cal = snap.calendar
        soft = ", ".join(f"{m.kind} {m.event_date.isoformat()}" for m in cal.soft_macros) or "none"
        hard = "; ".join(cal.hard_reasons) or "none"
        event_lines = [
            f"    {e.action.value}/{e.mechanism.value} {e.title} ({e.expected_time or 'undated'})"
            for e in events
            if not e.tickers or snap.ticker in e.tickers
        ]
        blocks.append(
            f"{snap.ticker} spot={snap.spot:.2f}\n"
            f"  hard_skip={cal.hard_skip} reasons={hard}\n"
            f"  soft_macro={soft}\n"
            f"  premium_tradeoff={_premium_tradeoff(snap)}\n"
            f"  ladder:\n{_bucket_brief(snap)}\n"
            f"  events:\n" + ("\n".join(event_lines) if event_lines else "    none")
        )
    return "\n\n".join(blocks)


def _L(lang: str, en: str, zh: str) -> str:
    return zh if normalize_lang(lang) == "zh" else en


def heuristic_desk(
    snapshots: list[TickerSnapshot],
    events: list[ScoutedEvent],
    cash: float,
    lang: str = "en",
) -> DeskOutput:
    decisions: list[TickerDecision] = []
    remaining = cash
    for snap in snapshots:
        relevant = [e for e in events if not e.tickers or snap.ticker in e.tickers]
        skip_event = next((e for e in relevant if e.action == EventAction.SKIP), None)
        reduce_event = next(
            (e for e in relevant if e.action in (EventAction.REDUCE, EventAction.SPREAD_ONLY)),
            None,
        )
        if snap.calendar.hard_skip:
            decisions.append(
                TickerDecision(
                    ticker=snap.ticker,
                    action=DeskAction.SKIP,
                    why=_hard_why(snap.calendar.hard_reasons, lang),
                )
            )
            continue
        if skip_event:
            decisions.append(
                TickerDecision(
                    ticker=snap.ticker,
                    action=DeskAction.SKIP,
                    why=_L(lang, f"Scout skip: {skip_event.title}", f"侦察建议跳过：{skip_event.title}"),
                )
            )
            continue
        want_spread = bool(
            reduce_event and reduce_event.action == EventAction.SPREAD_ONLY
        )
        want_cons = bool(reduce_event or snap.calendar.soft_macros)
        bucket = None
        if want_cons and DeltaBucket.CONSERVATIVE in snap.buckets:
            bucket = snap.buckets[DeltaBucket.CONSERVATIVE]
        elif (not want_cons) and DeltaBucket.STANDARD in snap.buckets:
            bucket = snap.buckets[DeltaBucket.STANDARD]
        elif DeltaBucket.STANDARD in snap.buckets:
            bucket = snap.buckets[DeltaBucket.STANDARD]
        elif DeltaBucket.CONSERVATIVE in snap.buckets:
            bucket = snap.buckets[DeltaBucket.CONSERVATIVE]
        if bucket is None:
            decisions.append(
                TickerDecision(
                    ticker=snap.ticker,
                    action=DeskAction.SKIP,
                    why=_L(lang, "No liquid put in either delta bucket.", "两档都没有流动性足够的 put。"),
                )
            )
            continue
        structure = Structure.CSP
        if want_spread:
            if bucket.spread and bucket.spread.contracts > 0:
                structure = Structure.BULL_PUT_SPREAD
            else:
                decisions.append(
                    TickerDecision(
                        ticker=snap.ticker,
                        action=DeskAction.SKIP,
                        why=_L(
                            lang,
                            "spread_only but no protective long put.",
                            "要求只做价差，但没有可用的保护性多头 put。",
                        ),
                    )
                )
                continue
        if structure == Structure.CSP:
            if bucket.csp_contracts <= 0 or bucket.assignment_cash > remaining:
                decisions.append(
                    TickerDecision(
                        ticker=snap.ticker,
                        action=DeskAction.SKIP,
                        why=_L(
                            lang,
                            "CSP assignment cash exceeds remaining buying power.",
                            "CSP 被指派所需现金超过剩余本金。",
                        ),
                    )
                )
                continue
            remaining -= bucket.assignment_cash
        why = _L(lang, "Default standard CSP.", "默认开标准档 CSP。")
        if want_cons:
            why = _L(
                lang,
                "Soft macro or reduce event → conservative (or spread).",
                "有软宏观或降风险事件，改用保守档（或价差）。",
            )
        decisions.append(
            TickerDecision(
                ticker=snap.ticker,
                action=DeskAction.OPEN,
                structure=structure,
                delta_bucket=bucket.bucket,
                contract_id=bucket.csp.contract_id,
                assignment_ok=True,
                why=why,
                premium_tradeoff=_premium_tradeoff(snap, lang),
            )
        )
    return DeskOutput(
        decisions=decisions,
        portfolio_note=_L(lang, "Heuristic desk (no LLM).", "启发式终审（未调用 LLM）。"),
        used_llm=False,
    )


def enforce_desk_rules(
    output: DeskOutput,
    snapshots: list[TickerSnapshot],
    cash: float,
    lang: str = "en",
) -> DeskOutput:
    by_ticker = {s.ticker: s for s in snapshots}
    remaining = cash
    cleaned: list[TickerDecision] = []
    seen: set[str] = set()
    for decision in output.decisions:
        snap = by_ticker.get(decision.ticker)
        if snap is None or decision.ticker in seen:
            continue
        seen.add(decision.ticker)
        if snap.calendar.hard_skip:
            cleaned.append(
                TickerDecision(
                    ticker=decision.ticker,
                    action=DeskAction.SKIP,
                    why=_hard_why(snap.calendar.hard_reasons, lang),
                )
            )
            continue
        if decision.action == DeskAction.CLOSE_EARLY:
            cleaned.append(
                TickerDecision(
                    ticker=decision.ticker,
                    action=DeskAction.SKIP,
                    why=_L(
                        lang,
                        "CLOSE_EARLY ignored: this CLI has no live position feed.",
                        "忽略 CLOSE_EARLY：当前 CLI 没有持仓数据。",
                    ),
                )
            )
            continue
        if decision.action != DeskAction.OPEN:
            cleaned.append(
                decision.model_copy(
                    update={"structure": None, "delta_bucket": None, "contract_id": None}
                )
            )
            continue
        bucket_key = decision.delta_bucket
        if bucket_key is None or bucket_key not in snap.buckets:
            cleaned.append(
                TickerDecision(
                    ticker=decision.ticker,
                    action=DeskAction.SKIP,
                    why=_L(
                        lang,
                        "OPEN rejected: delta bucket missing from ladder.",
                        "OPEN 被拒绝：所选 Delta 档不在梯子上。",
                    ),
                )
            )
            continue
        cand = snap.buckets[bucket_key]
        if decision.contract_id != cand.csp.contract_id:
            cleaned.append(
                TickerDecision(
                    ticker=decision.ticker,
                    action=DeskAction.SKIP,
                    why=_L(
                        lang,
                        "OPEN rejected: contract_id is not on the ladder.",
                        "OPEN 被拒绝：contract_id 不在梯子上。",
                    ),
                )
            )
            continue
        structure = decision.structure or Structure.CSP
        if structure == Structure.BULL_PUT_SPREAD and (not cand.spread or cand.spread.contracts <= 0):
            cleaned.append(
                TickerDecision(
                    ticker=decision.ticker,
                    action=DeskAction.SKIP,
                    why=_L(
                        lang,
                        "OPEN rejected: no valid bull put spread on this bucket.",
                        "OPEN 被拒绝：该档没有可用的牛市看跌价差。",
                    ),
                )
            )
            continue
        if structure == Structure.CSP:
            if cand.csp_contracts <= 0 or cand.assignment_cash > remaining:
                cleaned.append(
                    TickerDecision(
                        ticker=decision.ticker,
                        action=DeskAction.SKIP,
                        why=_L(
                            lang,
                            "OPEN rejected: CSP would exceed remaining cash if assigned.",
                            "OPEN 被拒绝：CSP 被指派后会超过剩余本金。",
                        ),
                    )
                )
                continue
            remaining -= cand.assignment_cash
        cleaned.append(
            decision.model_copy(
                update={
                    "structure": structure,
                    "contract_id": cand.csp.contract_id,
                    "premium_tradeoff": decision.premium_tradeoff or _premium_tradeoff(snap, lang),
                }
            )
        )
    for snap in snapshots:
        if snap.ticker not in seen:
            if snap.calendar.hard_skip:
                why = _hard_why(snap.calendar.hard_reasons, lang)
            else:
                why = _L(
                    lang,
                    "Desk omitted this ticker; default SKIP.",
                    "终审未覆盖该标的，默认跳过。",
                )
            cleaned.append(TickerDecision(ticker=snap.ticker, action=DeskAction.SKIP, why=why))
    return DeskOutput(
        decisions=cleaned,
        portfolio_note=output.portfolio_note,
        used_llm=output.used_llm,
    )


def run_desk_llm(
    snapshots: list[TickerSnapshot],
    events: list[ScoutedEvent],
    cash: float,
    settings: Settings,
    llm,
) -> DeskOutput:
    if llm is None:
        return enforce_desk_rules(
            heuristic_desk(snapshots, events, cash, settings.output_language),
            snapshots,
            cash,
            settings.output_language,
        )
    try:
        parsed = invoke_structured(
            llm,
            DeskLLMResult,
            [
                SystemMessage(content=SYSTEM + language_instruction(settings.output_language)),
                HumanMessage(content=snapshot_prompt(snapshots, events, cash)),
            ],
            provider=settings.llm_endpoint().provider,
        )
        raw = DeskOutput(
            decisions=parsed.decisions,
            portfolio_note=parsed.portfolio_note,
            used_llm=True,
        )
    except Exception as exc:
        fallback = heuristic_desk(snapshots, events, cash, settings.output_language)
        fallback.portfolio_note = _L(
            settings.output_language,
            f"LLM desk failed ({exc}); used heuristic.",
            f"LLM 终审失败（{exc}）；改用启发式。",
        )
        return enforce_desk_rules(fallback, snapshots, cash, settings.output_language)
    return enforce_desk_rules(raw, snapshots, cash, settings.output_language)
