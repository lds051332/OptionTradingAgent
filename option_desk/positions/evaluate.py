from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from option_desk.chain.screener import fetch_spot
from option_desk.config import Settings, get_settings
from option_desk.positions.calculations import (
    calculate_estimated_close_pnl,
    calculate_mark_pnl,
    calculate_profit_capture,
)
from option_desk.positions.management import ManagementResult, get_management_recommendation
from option_desk.positions.market import is_us_equity_rth
from option_desk.positions.quotes import estimated_close_price, load_expiry_quotes
from option_desk.schemas import ContractQuote


@dataclass
class PositionInput:
    id: str
    ticker: str
    strategy: str
    option_type: str
    expiry: date
    strike: float
    contracts: int
    entry_premium: float
    assignment_ok: bool = True


@dataclass
class RuleSettings:
    profit_target: float = 0.75
    near_expiry_dte: int = 2
    near_expiry_profit_target: float = 0.50


@dataclass
class PositionEvaluation:
    position_id: str
    fetched_at: datetime
    market_open: bool
    underlying_spot: float | None
    contract: ContractQuote | None
    estimated_close_price: float | None
    mark_pnl: float | None
    estimated_close_pnl: float | None
    profit_capture: float | None
    itm: bool | None
    management: ManagementResult
    warnings: list[str] = field(default_factory=list)


def _is_itm(strategy: str, spot: float, strike: float) -> bool:
    if strategy == "COVERED_CALL":
        return spot > strike
    return spot < strike


def _empty_eval(
    item: PositionInput,
    fetched_at: datetime,
    market_open: bool,
    warnings: list[str],
    *,
    underlying_spot: float | None,
) -> PositionEvaluation:
    return PositionEvaluation(
        position_id=item.id,
        fetched_at=fetched_at,
        market_open=market_open,
        underlying_spot=underlying_spot,
        contract=None,
        estimated_close_price=None,
        mark_pnl=None,
        estimated_close_pnl=None,
        profit_capture=None,
        itm=None,
        management=get_management_recommendation(
            quote_available=False,
            profit_capture=None,
            dte=None,
            delta=None,
            spot=underlying_spot,
            strike=item.strike,
            strategy=item.strategy,
            assignment_ok=item.assignment_ok,
        ),
        warnings=warnings,
    )


def evaluate_positions(
    positions: list[PositionInput],
    *,
    as_of: date | None = None,
    settings: Settings | None = None,
    rules: RuleSettings | None = None,
    now: datetime | None = None,
) -> list[PositionEvaluation]:
    if not positions:
        return []
    settings = settings or get_settings()
    rules = rules or RuleSettings()
    as_of = as_of or date.today()
    fetched_at = now or datetime.now(timezone.utc)
    market_open = is_us_equity_rth(fetched_at)

    spots: dict[str, float | None] = {}
    ticker_errors: dict[str, str] = {}
    quote_cache: dict[tuple[str, date, str], list[ContractQuote] | None] = {}

    for item in positions:
        symbol = item.ticker.upper()
        if symbol in spots or symbol in ticker_errors:
            continue
        try:
            spots[symbol] = fetch_spot(symbol)
        except Exception as exc:
            ticker_errors[symbol] = str(exc)
            spots[symbol] = None

    out: list[PositionEvaluation] = []
    for item in positions:
        symbol = item.ticker.upper()
        warnings: list[str] = []
        spot = spots.get(symbol)
        if symbol in ticker_errors:
            out.append(
                _empty_eval(
                    item,
                    fetched_at,
                    market_open,
                    ["QUOTE_UNAVAILABLE"],
                    underlying_spot=None,
                )
            )
            continue
        right = "C" if item.option_type == "CALL" else "P"
        cache_key = (symbol, item.expiry, right)
        if cache_key not in quote_cache:
            try:
                quote_cache[cache_key] = load_expiry_quotes(
                    symbol, item.expiry, float(spot or 0), as_of, settings, right
                )
            except Exception:
                quote_cache[cache_key] = None
        quotes = quote_cache.get(cache_key)
        contract = None
        if quotes:
            nearest = min(quotes, key=lambda quote: abs(quote.strike - item.strike))
            if abs(nearest.strike - item.strike) <= 0.051:
                contract = nearest
        if contract is None:
            out.append(
                _empty_eval(
                    item,
                    fetched_at,
                    market_open,
                    ["QUOTE_UNAVAILABLE"],
                    underlying_spot=spot,
                )
            )
            continue

        close_px = estimated_close_price(contract)
        capture = calculate_profit_capture(item.entry_premium, contract.mid)
        mark_pnl = calculate_mark_pnl(item.entry_premium, contract.mid, item.contracts)
        close_pnl = calculate_estimated_close_pnl(item.entry_premium, close_px, item.contracts)
        itm = _is_itm(item.strategy, float(spot), item.strike) if spot is not None else None
        management = get_management_recommendation(
            quote_available=True,
            profit_capture=capture,
            dte=contract.dte,
            delta=contract.delta,
            spot=spot,
            strike=item.strike,
            strategy=item.strategy,
            assignment_ok=item.assignment_ok,
            profit_target=rules.profit_target,
            near_expiry_dte=rules.near_expiry_dte,
            near_expiry_profit_target=rules.near_expiry_profit_target,
        )
        if not market_open:
            warnings.append("MARKET_CLOSED")
        out.append(
            PositionEvaluation(
                position_id=item.id,
                fetched_at=fetched_at,
                market_open=market_open,
                underlying_spot=spot,
                contract=contract,
                estimated_close_price=close_px,
                mark_pnl=mark_pnl,
                estimated_close_pnl=close_pnl,
                profit_capture=capture,
                itm=itm,
                management=management,
                warnings=warnings,
            )
        )
    return out
