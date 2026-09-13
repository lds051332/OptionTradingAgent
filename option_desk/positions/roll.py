from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from option_desk.chain.screener import fetch_spot, load_call_quotes, load_put_quotes
from option_desk.config import Settings, get_settings
from option_desk.positions.quotes import estimated_close_price as close_mark
from option_desk.positions.quotes import load_open_contract_quote
from option_desk.schemas import ContractQuote, QuoteSource


@dataclass(frozen=True)
class RollCandidate:
    contract: ContractQuote
    estimated_net_per_share: float | None
    estimated_net: float | None
    recommended: bool


def find_roll_candidates(
    quotes: list[ContractQuote],
    *,
    current_expiry,
    current_strike: float,
    target_delta: float,
    estimated_close_price: float | None,
    contracts: int,
    limit: int = 12,
) -> list[RollCandidate]:
    filtered = [
        quote
        for quote in quotes
        if not (quote.expiry == current_expiry and abs(quote.strike - current_strike) < 0.011)
    ]
    filtered.sort(
        key=lambda quote: (
            abs(quote.delta - target_delta),
            0 if quote.quote_source is QuoteSource.NBBO else 1,
            quote.spread_pct,
            -quote.open_interest,
            -quote.volume,
        )
    )
    picked = filtered[:limit]
    out: list[RollCandidate] = []
    for index, quote in enumerate(picked):
        net_share = None if estimated_close_price is None else round(quote.mid - estimated_close_price, 4)
        net = None if net_share is None else round(net_share * contracts * 100, 2)
        out.append(
            RollCandidate(
                contract=quote,
                estimated_net_per_share=net_share,
                estimated_net=net,
                recommended=index == 0,
            )
        )
    return out


def collect_roll_candidates(
    *,
    ticker: str,
    option_type: str,
    expiry: date,
    strike: float,
    contracts: int,
    estimated_close_price: float | None = None,
    target_delta: float | None = None,
    as_of: date | None = None,
    settings: Settings | None = None,
) -> tuple[list[RollCandidate], ContractQuote | None, float | None]:
    settings = settings or get_settings()
    as_of = as_of or date.today()
    symbol = ticker.upper()
    spot = fetch_spot(symbol)
    right = "C" if option_type == "CALL" else "P"
    if right == "C":
        quotes = load_call_quotes(symbol, spot, as_of, settings)
    else:
        quotes = load_put_quotes(symbol, spot, as_of, settings)
    current = load_open_contract_quote(symbol, expiry, strike, right, spot, as_of, settings)
    close_px = estimated_close_price
    if close_px is None and current is not None:
        close_px = close_mark(current)
    target = settings.standard_delta if target_delta is None else target_delta
    return (
        find_roll_candidates(
            quotes,
            current_expiry=expiry,
            current_strike=strike,
            target_delta=target,
            estimated_close_price=close_px,
            contracts=contracts,
        ),
        current,
        spot,
    )
