from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class DeltaBucket(str, Enum):
    CONSERVATIVE = "conservative"
    STANDARD = "standard"


class DeskAction(str, Enum):
    SKIP = "SKIP"
    OPEN = "OPEN"
    CLOSE_EARLY = "CLOSE_EARLY"


class Structure(str, Enum):
    CSP = "CSP"
    BULL_PUT_SPREAD = "BULL_PUT_SPREAD"


class EventAction(str, Enum):
    IGNORE = "ignore"
    REDUCE = "reduce"
    SPREAD_ONLY = "spread_only"
    SKIP = "skip"


class EventMechanism(str, Enum):
    GAP = "gap"
    REPRICING = "repricing"
    NOISE = "noise"


class ContractQuote(BaseModel):
    contract_id: str
    ticker: str
    expiry: date
    dte: int
    strike: float
    bid: float
    ask: float
    mid: float
    last: float | None = None
    iv: float
    delta: float
    open_interest: int = 0
    volume: int = 0
    spread_pct: float


class SpreadQuote(BaseModel):
    short: ContractQuote
    long: ContractQuote
    width: float
    max_loss_per_contract: float
    contracts: int


class BucketCandidate(BaseModel):
    bucket: DeltaBucket
    target_delta: float
    csp: ContractQuote
    spread: SpreadQuote | None = None
    csp_contracts: int
    assignment_cash: float
    premium_per_contract: float


class SoftMacroEvent(BaseModel):
    name: str
    event_date: date
    kind: Literal["CPI", "NFP", "PCE"]


class CalendarGate(BaseModel):
    ticker: str
    hard_skip: bool
    hard_reasons: list[str] = Field(default_factory=list)
    earnings_dates: list[date] = Field(default_factory=list)
    fomc_dates: list[date] = Field(default_factory=list)
    soft_macros: list[SoftMacroEvent] = Field(default_factory=list)
    holding_start: date
    holding_end: date


class TickerSnapshot(BaseModel):
    ticker: str
    spot: float
    as_of: date
    fetched_at: datetime
    buckets: dict[DeltaBucket, BucketCandidate] = Field(default_factory=dict)
    calendar: CalendarGate
    notes: list[str] = Field(default_factory=list)


class ScoutedEvent(BaseModel):
    title: str
    expected_time: str | None = None
    tickers: list[str] = Field(default_factory=list)
    mechanism: EventMechanism
    already_priced: bool = False
    action: EventAction
    sources: list[str] = Field(default_factory=list)
    detail: str = ""


class EventList(BaseModel):
    events: list[ScoutedEvent] = Field(default_factory=list)


class DeskLLMDecision(BaseModel):
    """Fields the desk model may emit. Payoff is computed later, never by the LLM."""

    ticker: str
    action: DeskAction
    structure: Structure | None = None
    delta_bucket: DeltaBucket | None = None
    contract_id: str | None = None
    assignment_ok: bool = True
    why: str
    premium_tradeoff: str | None = None


class PayoffPoint(BaseModel):
    spot: float
    pnl: float


class ExpirationPayoff(BaseModel):
    structure: Structure
    spot: float
    expiry: date
    dte: int
    short_strike: float
    long_strike: float | None = None
    breakeven: float
    credit_per_share: float
    contracts: int
    max_profit: float
    max_loss: float
    loss_limited: bool
    assignment_cash: float | None = None
    pnl_at_spot: float
    x_min: float
    x_max: float
    points: list[PayoffPoint] = Field(default_factory=list)


class TickerDecision(DeskLLMDecision):
    payoff: ExpirationPayoff | None = None


class DeskLLMResult(BaseModel):
    """Shape the model is allowed to emit. used_llm is filled by the caller."""

    decisions: list[DeskLLMDecision]
    portfolio_note: str = ""


class DeskOutput(BaseModel):
    decisions: list[TickerDecision]
    portfolio_note: str = ""
    used_llm: bool = False


class DeskRun(BaseModel):
    as_of: date
    fetched_at: datetime
    cash: float
    snapshots: list[TickerSnapshot]
    events: list[ScoutedEvent]
    desk: DeskOutput
    warnings: list[str] = Field(default_factory=list)
    llm_label: str = "heuristic"
    language: str = "en"
