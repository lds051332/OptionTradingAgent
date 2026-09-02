from __future__ import annotations

from option_desk.schemas import (
    DeskAction,
    DeskOutput,
    ExpirationPayoff,
    PayoffPoint,
    Structure,
    TickerDecision,
    TickerSnapshot,
)

_CONTRACT_MULT = 100.0


def expiration_pnl(
    spot_at_expiry: float,
    *,
    short_strike: float,
    credit_per_share: float,
    long_strike: float | None = None,
    contracts: int,
) -> float:
    """Expiration P/L in dollars for the full position, European-style."""
    short_intr = max(short_strike - spot_at_expiry, 0.0)
    long_intr = max((long_strike or 0.0) - spot_at_expiry, 0.0) if long_strike is not None else 0.0
    per_share = credit_per_share - short_intr + long_intr
    return round(per_share * _CONTRACT_MULT * contracts, 2)


def _window(
    spot: float,
    short_strike: float,
    long_strike: float | None,
    breakeven: float,
) -> tuple[float, float]:
    anchors = [spot, short_strike, breakeven]
    if long_strike is not None:
        anchors.append(long_strike)
    lo = min(anchors)
    hi = max(anchors)
    span = max(hi - lo, max(short_strike * 0.08, 8.0))
    pad = span * 0.35
    x_min = max(0.0, lo - pad)
    x_max = hi + pad
    if x_max <= x_min:
        x_max = x_min + 10.0
    return round(x_min, 4), round(x_max, 4)


def _unique_spots(*values: float) -> list[float]:
    out: list[float] = []
    for value in sorted(values):
        if not out or abs(value - out[-1]) > 1e-6:
            out.append(round(value, 4))
    return out


def build_payoff(decision: TickerDecision, snapshot: TickerSnapshot) -> ExpirationPayoff | None:
    if decision.action != DeskAction.OPEN or decision.delta_bucket is None:
        return None
    bucket = snapshot.buckets.get(decision.delta_bucket)
    if bucket is None:
        return None
    if decision.contract_id and decision.contract_id != bucket.csp.contract_id:
        return None

    structure = decision.structure or Structure.CSP
    short = bucket.csp
    long_strike: float | None = None
    credit = short.mid
    contracts = bucket.csp_contracts
    assignment_cash: float | None = bucket.assignment_cash
    loss_limited = False

    if structure == Structure.BULL_PUT_SPREAD:
        spread = bucket.spread
        if spread is None or spread.contracts <= 0:
            return None
        long_strike = spread.long.strike
        credit = short.mid - spread.long.mid
        contracts = spread.contracts
        assignment_cash = None
        loss_limited = True

    if contracts <= 0:
        return None

    breakeven = short.strike - credit
    x_min, x_max = _window(snapshot.spot, short.strike, long_strike, breakeven)
    kinks = [x_min, x_max, short.strike, breakeven]
    if long_strike is not None:
        kinks.append(long_strike)

    def pnl_at(spot: float) -> float:
        return round(
            expiration_pnl(
                spot,
                short_strike=short.strike,
                credit_per_share=credit,
                long_strike=long_strike,
                contracts=contracts,
            ),
            2,
        )

    max_profit = pnl_at(x_max)
    max_loss = -pnl_at(0.0 if not loss_limited else (long_strike or 0.0))
    return ExpirationPayoff(
        structure=structure,
        spot=snapshot.spot,
        expiry=short.expiry,
        dte=short.dte,
        short_strike=short.strike,
        long_strike=long_strike,
        breakeven=round(breakeven, 4),
        credit_per_share=round(credit, 4),
        contracts=contracts,
        max_profit=max_profit,
        max_loss=round(max_loss, 2),
        loss_limited=loss_limited,
        assignment_cash=assignment_cash,
        pnl_at_spot=pnl_at(snapshot.spot),
        x_min=x_min,
        x_max=x_max,
        points=[PayoffPoint(spot=s, pnl=pnl_at(s)) for s in _unique_spots(*kinks)],
    )


def attach_payoffs(output: DeskOutput, snapshots: list[TickerSnapshot]) -> DeskOutput:
    by_ticker = {snap.ticker: snap for snap in snapshots}
    decisions: list[TickerDecision] = []
    for decision in output.decisions:
        snap = by_ticker.get(decision.ticker)
        payoff = build_payoff(decision, snap) if snap else None
        decisions.append(decision.model_copy(update={"payoff": payoff}))
    return output.model_copy(update={"decisions": decisions})
