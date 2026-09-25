from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from option_desk.config import MAX_RUN_DELTA, MAX_RUN_SHARES, MIN_RUN_DELTA, MIN_RUN_SHARES

DEFAULT_DELTA = 0.20
MIN_CASH = 1_000
MAX_CASH = 10_000_000
MAX_COST_BASIS = 1_000_000

_CJK = re.compile(r"[\u3400-\u9fff]")
_NUMBER = r"(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?"
_UNITS = {"万": 1e4, "w": 1e4, "k": 1e3, "千": 1e3, "m": 1e6, "百万": 1e6}

TICKER_ALIASES = {
    "英伟达": "NVDA",
    "辉达": "NVDA",
    "微软": "MSFT",
    "苹果": "AAPL",
    "特斯拉": "TSLA",
    "谷歌": "GOOGL",
    "亚马逊": "AMZN",
    "脸书": "META",
    "奈飞": "NFLX",
    "网飞": "NFLX",
    "台积电": "TSM",
    "博通": "AVGO",
    "超威": "AMD",
    "英特尔": "INTC",
    "美光": "MU",
    "甲骨文": "ORCL",
    "阿里巴巴": "BABA",
    "拼多多": "PDD",
    "京东": "JD",
    "可口可乐": "KO",
}

# Words people type next to tickers. A real ticker that collides (NOW, ON, ALL, ...) still works as a $cashtag.
STOPWORDS = frozenset(
    """
    CSP CC PUT PUTS CALL CALLS SELL BUY CASH COST BASIS DELTA SHARE DTE IV HV OTM ITM ATM USD US USA
    ETF OPEN SKIP ROLL HOLD AND OR THE FOR ON IN OF TO MY ME AT IS IT WITH BY AN AI EM PNL PL OK HI NO
    YES VIX FOMC CPI NFP PCE EPS GDP API LLM NYSE WEEK DAYS DAY NEXT THIS THAT WHAT HOW CAN YOU SHOW
    GIVE BEST SAFE RISK LOW HIGH MAX MIN NEW NOW HELP WANT NEED HAVE HAS OWN ABOUT SOME ANY ALL BOTH
    ALSO JUST ONLY IF DO GET SET PER FROM INTO OVER UNDER NEAR OUT AVG BULL BEAR WHEEL STOCK IDEA PLAN
    TRADE RUN DESK USE ARE WAS WILL BE AM AS SO UP DOWN GO LET LETS HERE THEN THAN WHEN WHICH WHO WHY
    ETC VS PM EST UTC CST
    """.split()
)

_CASHTAG = re.compile(r"\$([A-Za-z]{1,5}(?:\.[A-Za-z])?)(?![A-Za-z0-9])")
_UPPER = re.compile(r"(?<![A-Za-z0-9.$])([A-Z]{2,5}(?:\.[A-Z])?)(?![A-Za-z0-9])")
_LOWER = re.compile(r"(?<![A-Za-z0-9.$])([a-z]{2,5})(?![A-Za-z0-9])")

_EXPLICIT_CALL = re.compile(
    r"covered[\s_-]*calls?|备兑|(?<![a-z])cc(?![a-z])|sell(?:ing)?\s+(?:a\s+)?calls?(?![a-z])|卖\s*calls?",
    re.IGNORECASE,
)
_EXPLICIT_PUT = re.compile(
    r"cash[\s_-]*secured|(?<![a-z])csp(?![a-z])|(?<![a-z])puts?(?![a-z])|现金担保|卖\s*put",
    re.IGNORECASE,
)
_WEAK_CALL = re.compile(r"(?<![a-z])calls?(?![a-z])", re.IGNORECASE)
_SHARES = re.compile(_NUMBER + r"\s*(?:股|shares?(?![a-z])|sh(?![a-z]))", re.IGNORECASE)
_SHARES_LABELED = re.compile(
    r"(?:持股|持有|shares?\s*(?:held|owned)?|holding|hold|own)\s*(?:数量|数)?\s*(?:是|为|:|：|=)?\s*"
    + _NUMBER
    + r"(?!\s*(?:万|w|k|千|m|美元|刀|块|\.\d))",
    re.IGNORECASE,
)
_COST = re.compile(
    r"(?:持仓成本|成本价?|均价|买入价|cost(?:\s*basis)?|basis|avg(?:\s*cost)?|average\s+cost|bought\s+at)"
    r"\s*(?:是|为|在|of|at|:|：|=)?\s*\$?\s*" + _NUMBER,
    re.IGNORECASE,
)
_DELTA_AFTER = re.compile(r"(?:delta|Δ|δ)\s*(?:=|:|：|of|at)?\s*(\d*\.\d+|\d+)", re.IGNORECASE)
_DELTA_BEFORE = re.compile(r"(\d*\.\d+)\s*(?:delta|Δ|δ)", re.IGNORECASE)
_CASH_LABELED = re.compile(
    r"(?:可用资金|可用现金|现金|资金|本金|cash|capital|budget|buying\s*power)"
    r"\s*(?:是|有|为|of|:|：|=)?\s*\$?\s*" + _NUMBER + r"\s*(万|w|k|千|m|百万)?",
    re.IGNORECASE,
)
_CASH_DOLLAR = re.compile(r"\$\s*" + _NUMBER + r"\s*(k|m)?(?![A-Za-z0-9])", re.IGNORECASE)
_CASH_UNIT = re.compile(_NUMBER + r"\s*(万|w|k|千|m|百万)(?![A-Za-z0-9])", re.IGNORECASE)
_BARE = re.compile(r"(?<![\d.])" + _NUMBER + r"(?![\d.%])")


@dataclass
class DeskRequest:
    mode: str = "put"
    tickers: list[str] = field(default_factory=list)
    cash: float | None = None
    shares: float | None = None
    cost_basis: float | None = None
    delta: float = DEFAULT_DELTA
    language: str = "en"
    dropped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeskRequest":
        known = {name: data[name] for name in cls.__dataclass_fields__ if name in data}
        return cls(**known)


@dataclass
class ParseResult:
    request: DeskRequest
    missing: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.missing and not self.problems


def detect_language(texts: list[str]) -> str:
    return "zh" if any(_CJK.search(text or "") for text in texts) else "en"


def is_capability_probe(text: str) -> bool:
    """Finch's default connection-test prompt."""
    return re.sub(r"[^a-z ]", "", (text or "").lower()).strip() == "describe your capabilities"


def _amount(whole: str, frac: str | None, unit: str | None = None) -> float:
    value = float(whole.replace(",", "") + (f".{frac}" if frac else ""))
    return value * _UNITS.get((unit or "").lower(), 1)


def _blank(text: str, match: re.Match[str]) -> str:
    start, end = match.span()
    return text[:start] + " " * (end - start) + text[end:]


def _first(pattern: re.Pattern[str], text: str) -> tuple[re.Match[str] | None, str]:
    match = pattern.search(text)
    return (match, _blank(text, match)) if match else (None, text)


def _mode_hint(text: str) -> str | None:
    call = _EXPLICIT_CALL.search(text)
    put = _EXPLICIT_PUT.search(text)
    if call and put:
        return "call" if call.start() < put.start() else "put"
    if call:
        return "call"
    if put:
        return "put"
    if _WEAK_CALL.search(text) or _SHARES.search(text):
        return "call"
    return None


def _tickers(text: str, language: str) -> list[str]:
    found: list[tuple[int, str]] = []
    for alias, symbol in TICKER_ALIASES.items():
        for match in re.finditer(re.escape(alias), text):
            found.append((match.start(), symbol))
    for match in _CASHTAG.finditer(text):
        found.append((match.start(), match.group(1).upper()))
    for match in _UPPER.finditer(text):
        if match.group(1) not in STOPWORDS:
            found.append((match.start(), match.group(1)))
    if language == "zh":
        for match in _LOWER.finditer(text):
            symbol = match.group(1).upper()
            if symbol not in STOPWORDS:
                found.append((match.start(), symbol))
    ordered: list[str] = []
    for _, symbol in sorted(found):
        if symbol not in ordered:
            ordered.append(symbol)
    return ordered


def _delta(text: str) -> tuple[float | None, str]:
    for pattern in (_DELTA_AFTER, _DELTA_BEFORE):
        match, rest = _first(pattern, text)
        if match:
            value = float(match.group(1))
            return (value / 100 if value > 1 else value), rest
    return None, text


def _cash(text: str) -> tuple[float | None, str]:
    match, rest = _first(_CASH_LABELED, text)
    if match:
        return _amount(match.group(1), match.group(2), match.group(3)), rest
    match, rest = _first(_CASH_DOLLAR, text)
    if match:
        return _amount(match.group(1), match.group(2), match.group(3)), rest
    match, rest = _first(_CASH_UNIT, text)
    if match:
        return _amount(match.group(1), match.group(2), match.group(3)), rest
    for match in _BARE.finditer(text):
        value = _amount(match.group(1), match.group(2))
        if value >= MIN_CASH:
            return value, _blank(text, match)
    return None, text


def _fields(text: str, mode: str, language: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    rest = text
    delta, rest = _delta(rest)
    if delta is not None:
        out["delta"] = delta
    if mode == "call":
        match, rest = _first(_COST, rest)
        if match:
            out["cost_basis"] = _amount(match.group(1), match.group(2))
        match, rest = _first(_SHARES, rest)
        if not match:
            match, rest = _first(_SHARES_LABELED, rest)
        if match:
            out["shares"] = _amount(match.group(1), match.group(2))
    else:
        cash, rest = _cash(rest)
        if cash is not None:
            out["cash"] = cash
    tickers = _tickers(text, language)
    if tickers:
        out["tickers"] = tickers
    return out


def parse_texts(texts: list[str], max_tickers: int) -> ParseResult:
    """Parse every user turn in order; a later turn overrides an earlier value for the same field."""
    language = detect_language(texts)
    request = DeskRequest(language=language)
    for text in texts:
        hint = _mode_hint(text or "")
        if hint:
            request.mode = hint
        for name, value in _fields(text or "", request.mode, language).items():
            setattr(request, name, value)

    if len(request.tickers) > max_tickers:
        request.dropped = request.tickers[max_tickers:]
        request.tickers = request.tickers[:max_tickers]

    result = ParseResult(request=request)
    if not request.tickers:
        result.missing.append("tickers")
    if not MIN_RUN_DELTA <= request.delta <= MAX_RUN_DELTA:
        result.problems.append("delta")
    if request.mode == "call":
        if request.shares is None:
            result.missing.append("shares")
        elif not MIN_RUN_SHARES <= request.shares <= MAX_RUN_SHARES:
            result.problems.append("shares")
        if request.cost_basis is None:
            result.missing.append("cost_basis")
        elif not 0 < request.cost_basis <= MAX_COST_BASIS:
            result.problems.append("cost_basis")
    elif request.cash is None:
        result.missing.append("cash")
    elif not MIN_CASH <= request.cash <= MAX_CASH:
        result.problems.append("cash")
    return result
