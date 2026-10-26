from __future__ import annotations

from collections.abc import Mapping

# Add a key to BOTH "en" and "zh". t(lang, key, **kwargs) fills {placeholders}.
# Prefixes: md_ report, pipe_ SSE progress, web_ HTTP, note_ screener notes.
# New backend copy: put it here, then t(lang, "your_key"). Do not hardcode Chinese.

ZH_ALIASES = {"zh", "zh-cn", "zh_cn", "cn", "chinese", "中文"}
EN_ALIASES = {"en", "en-us", "english", "英文"}
LANG_HEADER = "x-option-desk-lang"


def normalize_lang(value: str | None) -> str:
    raw = (value or "en").strip().lower()
    if raw in ZH_ALIASES:
        return "zh"
    if raw in EN_ALIASES or raw == "en":
        return "en"
    if raw.startswith("zh"):
        return "zh"
    return "en"


def lang_from_headers(headers: Mapping[str, str] | None, fallback: str = "en") -> str:
    if headers is None:
        return normalize_lang(fallback)
    raw = (headers.get(LANG_HEADER) or "").strip()
    if raw:
        return normalize_lang(raw)
    accept = (headers.get("accept-language") or "").strip()
    if accept:
        return normalize_lang(accept.split(",")[0].split(";")[0])
    return normalize_lang(fallback)


def language_instruction(lang: str) -> str:
    if normalize_lang(lang) == "zh":
        return (
            "\n\nWrite all user-facing prose in Simplified Chinese: event titles, "
            "detail, why, premium_tradeoff, and portfolio_note. Keep enum values, "
            "tickers, contract_id, dates, and numbers unchanged. Call the "
            "conservative/standard candidates 档位, never 梯子 or 阶梯."
        )
    return (
        "\n\nWrite all user-facing prose in English: event titles, "
        "detail, why, premium_tradeoff, and portfolio_note. Keep enum values, "
        "tickers, contract_id, dates, and numbers unchanged. Do not write Chinese."
    )


UI = {
    "en": {
        "desk_title": "Put desk",
        "data_note": "yfinance delayed chain; Delta is a BS estimate.",
        "warning": "warning",
        "events": "Scouted events",
        "action": "Action",
        "mechanism": "Mechanism",
        "when": "When",
        "tickers": "Tickers",
        "title": "Title",
        "undated": "undated",
        "spot": "spot",
        "bucket": "Bucket",
        "contract": "Contract",
        "strike": "Strike",
        "dte": "DTE",
        "bid_ask": "Bid/Ask",
        "premium": "Premium",
        "csp_qty": "CSP qty",
        "assign": "Assign $",
        "hard_skip": "HARD SKIP",
        "soft_macro": "soft macro",
        "decision": "Desk decision",
        "structure": "Structure",
        "why": "Why",
        "wrote": "Wrote",
        "md_title": "Put desk",
        "md_fetched": "Fetched (UTC)",
        "md_cash": "Cash",
        "md_chain": "Chain/Delta: yfinance snapshot + Black-Scholes estimate, not exchange Greeks.",
        "md_warnings": "Warnings",
        "md_events": "Events",
        "md_none": "none",
        "md_holding": "Holding window",
        "md_hard": "Hard skip",
        "md_soft": "Soft macro",
        "md_buckets": "Delta buckets",
        "md_decisions": "Decisions",
        "md_tradeoff": "premium tradeoff",
        "md_payoff": "Expiration P/L",
        "md_max_profit": "max profit",
        "md_max_loss": "max loss",
        "md_breakeven": "breakeven",
        "md_payoff_note": "Mid estimate, hold to expiry. Excludes fees and early assignment.",
        "md_disclaimer": "Not investment advice. Confirm fills and assignment cash before sending any order.",
        "no_contract": "no contract",
        "as_of": "as-of",
        "cash_label": "cash",
        "md_spread_na": "n/a",
        "search_empty": "Web search came back empty, so there are no events to review.",
        "scout_failed": "The model couldn't classify events: {exc}",
        "screen_failed": "{ticker}: couldn't screen the option chain ({exc})",
        "screen_yahoo_meta": (
            "{ticker}: Yahoo returned incomplete quote data (currentTradingPeriod). "
            "This is usually a hiccup or rate limit on Yahoo's side, not your network — try again."
        ),
        "skipped_classify": " Event classification was skipped.",
        "pipe_run_started": "Analyzing {tickers}",
        "pipe_screen_started": "Fetching the {ticker} {right} chain and estimating delta…",
        "pipe_last_print_note": " (last trade, not a live quote)",
        "pipe_screen_done": "{ticker} at {spot}, {n} candidate bucket(s){note}",
        "pipe_calendar_started": "Checking {ticker} for earnings, FOMC, and macro events in the holding period…",
        "pipe_calendar_failed": "{ticker} calendar check failed: {exc}",
        "pipe_calendar_hard": "{ticker} must skip: {reasons}",
        "pipe_calendar_gate": "calendar rule",
        "pipe_calendar_soft": "{ticker} macro events to watch: {tags}",
        "pipe_calendar_clear": "{ticker}: no must-avoid events in the holding period",
        "pipe_no_candidates": "No candidate buckets, so the calendar and news checks were skipped. Everything is SKIP.",
        "pipe_desk_skip_all": "Done: nothing to open, everything is SKIP",
        "pipe_scout_search": "Searching the news for risks the calendar won't show…",
        "pipe_scout_hits": "Found {n} search results",
        "pipe_scout_llm": "Having the model sort through the events…",
        "pipe_scout_done": "News check done, {n} event(s)",
        "pipe_scout_done_empty": "News check done, nothing to watch",
        "pipe_desk_started": "Making the final call — picking a contract from the buckets…",
        "pipe_desk_done": "Final call ready",
        "pipe_run_finished": "Analysis complete",
        "pipe_run_error": "Analysis interrupted: {exc}",
        "web_invalid_ticker": "Invalid ticker: {item}",
        "web_need_ticker": "Enter at least one ticker",
        "web_too_many_tickers": "Up to {n} tickers",
        "web_delta_range": "Delta must be between {lo} and {hi}",
        "web_shares_range": "Shares must be between {lo} and {hi}",
        "web_cost_range": "Cost basis must be above 0 and no more than $1,000,000",
        "web_cash_range": "Cash must be between $1,000 and $10,000,000",
        "note_last_print": (
            "Last trade, not a live quote: there's no bid/ask, so the premium uses the last trade, "
            "which may be stale, and the spread is unknown. This is common with Yahoo data after hours. "
            "Check live quotes before placing an order."
        ),
        "note_iv_implied": (
            "Chain IV isn't usable, so delta is backed out from the last price. "
            "It's only used to pick buckets, not an exchange-provided Greek."
        ),
        "note_iv_floored": (
            "Chain IV is too low to back out from the last price, so it's floored at {floor}. "
            "Delta may be well off — use it only to pick buckets."
        ),
        "note_uncovered": "{leftover} shares aren't covered (each contract covers 100 shares).",
        "note_no_calls": "No calls with enough liquidity at {lo}–{hi} DTE.",
        "note_no_puts": "No puts with enough liquidity at {lo}–{hi} DTE.",
        "note_as_of": "Option chain is a live yfinance snapshot; --as-of only shifts DTE and calendar windows.",
        "regime_back": "VIX term structure inverted",
        "regime_contango": "VIX term structure normal",
        "regime_spy_below_50": "SPY below its 50-day average",
        "regime_spy_above_50": "SPY above its 50-day average",
        "regime_qqq_below_20": "QQQ below its 20-day average",
        "regime_qqq_above_20": "QQQ above its 20-day average",
        "pipe_regime_started": "Reading market conditions from VIX, SPY, and QQQ…",
        "pipe_regime_done": "Market {label}: {why}",
        "regime_label_on": "risk-on",
        "regime_label_neutral": "neutral",
        "regime_label_caution": "caution",
        "regime_label_off": "risk-off",
        "pipe_regime_failed": "Market regime unavailable: {exc}",
        "pipe_regime_none": "Market regime unavailable; the final call doesn't depend on it",
        "md_market": "Market regime",
        "md_iv": "IV vs HV",
        "md_em": "Expected move",
        "md_score": "score",
        "md_inside_em": "inside EM",
        "md_outside_em": "outside EM",
        "score": "Score",
        "market": "Market",
        "iv_vs_hv": "IV vs HV",
        "expected_move": "Expected move",
    },
    "zh": {
        "desk_title": "卖 Put 决策台",
        "data_note": "行情来自 yfinance 延迟快照；Delta 为 Black-Scholes 估算，非交易所官方希腊值。",
        "warning": "警告",
        "events": "侦察事件",
        "action": "动作",
        "mechanism": "机制",
        "when": "时间",
        "tickers": "标的",
        "title": "标题",
        "undated": "无日期",
        "spot": "现价",
        "bucket": "档位",
        "contract": "合约",
        "strike": "行权价",
        "dte": "剩余天数",
        "bid_ask": "买/卖价",
        "premium": "权利金",
        "csp_qty": "CSP张数",
        "assign": "指派占用",
        "hard_skip": "硬性跳过",
        "soft_macro": "软宏观",
        "decision": "终审建议",
        "structure": "结构",
        "why": "理由",
        "wrote": "已写入",
        "md_title": "卖 Put 决策台",
        "md_fetched": "拉取时间 (UTC)",
        "md_cash": "本金",
        "md_chain": "期权链/Delta：yfinance 快照 + BS 估算，不是交易所官方希腊值。",
        "md_warnings": "警告",
        "md_events": "事件",
        "md_none": "无",
        "md_holding": "持有窗口",
        "md_hard": "硬性跳过",
        "md_soft": "软宏观",
        "md_buckets": "候选档位",
        "md_decisions": "决策",
        "md_tradeoff": "权利金取舍",
        "md_payoff": "到期损益",
        "md_max_profit": "最大盈利",
        "md_max_loss": "最大亏损",
        "md_breakeven": "盈亏平衡",
        "md_payoff_note": "按 mid 估算、持有至到期；不含手续费与提前指派。",
        "md_disclaimer": "不构成投资建议。下单前请核对成交价与被指派所需现金。",
        "no_contract": "无合格合约",
        "as_of": "基准日",
        "cash_label": "本金",
        "md_spread_na": "无",
        "search_empty": "网页搜索没有结果，没有可分析的事件。",
        "scout_failed": "模型筛选事件失败：{exc}",
        "screen_failed": "{ticker}：期权链筛选失败（{exc}）",
        "screen_yahoo_meta": (
            "{ticker}：Yahoo 返回的行情数据不完整。多半是 Yahoo 那边不稳定或限流，"
            "不一定是本机断网，请再点一次开始分析。"
        ),
        "skipped_classify": " 已跳过事件分类。",
        "pipe_run_started": "开始分析 {tickers}",
        "pipe_screen_started": "正在拉取 {ticker} 的 {right} 期权链并估算 Delta…",
        "pipe_last_print_note": "（权利金按成交价算，不是实时报价）",
        "pipe_screen_done": "{ticker} 现价 {spot}，筛出 {n} 个候选档位{note}",
        "pipe_calendar_started": "正在检查 {ticker} 持有期内的财报、FOMC 和宏观事件…",
        "pipe_calendar_failed": "{ticker} 日历检查失败：{exc}",
        "pipe_calendar_hard": "{ticker} 必须回避：{reasons}",
        "pipe_calendar_gate": "日历规则",
        "pipe_calendar_soft": "{ticker} 需留意的宏观事件：{tags}",
        "pipe_calendar_clear": "{ticker} 持有期内没有必须回避的事件",
        "pipe_no_candidates": "没有候选档位，跳过日历和新闻检查，全部 SKIP",
        "pipe_desk_skip_all": "分析完成：没有可开的合约，全部 SKIP",
        "pipe_scout_search": "正在搜索日历上看不到的突发风险…",
        "pipe_scout_hits": "找到 {n} 条搜索结果",
        "pipe_scout_llm": "正在让模型筛选事件…",
        "pipe_scout_done": "新闻检查完成，{n} 个事件",
        "pipe_scout_done_empty": "新闻检查完成，没有需要留意的事件",
        "pipe_desk_started": "正在做最终决策，从候选档位里挑合约…",
        "pipe_desk_done": "最终建议已生成",
        "pipe_run_finished": "分析完成",
        "pipe_run_error": "分析中断：{exc}",
        "web_invalid_ticker": "无效标的：{item}",
        "web_need_ticker": "请至少填写一个标的",
        "web_too_many_tickers": "最多 {n} 个标的",
        "web_delta_range": "Delta 需在 {lo}–{hi} 之间",
        "web_shares_range": "持股数量需在 {lo}–{hi} 股之间",
        "web_cost_range": "成本价需大于 0，且不超过 $1,000,000",
        "web_cash_range": "本金需在 $1,000–$10,000,000 之间",
        "note_last_print": (
            "最新成交价，不是实时报价：没有买卖报价，权利金按最近一笔成交价计算，可能已经过时，买卖价差也未知。"
            "Yahoo 的盘后数据经常这样，下单前务必核对实时报价。"
        ),
        "note_iv_implied": "期权链上的 IV 不可用，Delta 是用成交价反推的，只用来挑档位，不是交易所给的 Greeks。",
        "note_iv_floored": (
            "期权链上的 IV 太低，无法用成交价反推，已按 {floor} 的下限计算。"
            "Delta 可能偏差很大，只用来挑档位。"
        ),
        "note_uncovered": "有 {leftover} 股没有被覆盖（每张合约对应 100 股）。",
        "note_no_calls": "{lo}–{hi} 天到期的合约里，没有流动性足够的 Call。",
        "note_no_puts": "{lo}–{hi} 天到期的合约里，没有流动性足够的 Put。",
        "note_as_of": "期权链是 yfinance 实时快照；--as-of 只移动剩余天数和日历窗口。",
        "regime_back": "VIX 期限结构倒挂",
        "regime_contango": "VIX 期限结构正常",
        "regime_spy_below_50": "SPY 低于 50 日均线",
        "regime_spy_above_50": "SPY 高于 50 日均线",
        "regime_qqq_below_20": "QQQ 低于 20 日均线",
        "regime_qqq_above_20": "QQQ 高于 20 日均线",
        "pipe_regime_started": "正在读取 VIX、SPY、QQQ，判断市场环境…",
        "pipe_regime_done": "市场环境 {label}：{why}",
        "regime_label_on": "Risk-On",
        "regime_label_neutral": "中性",
        "regime_label_caution": "谨慎",
        "regime_label_off": "Risk-Off",
        "pipe_regime_failed": "暂时拿不到市场环境数据：{exc}",
        "pipe_regime_none": "暂时拿不到市场环境数据，不影响最终建议",
        "md_market": "市场体制",
        "md_iv": "IV vs 已实现波动",
        "md_em": "预期波动",
        "md_score": "评分",
        "md_inside_em": "在预期波动内",
        "md_outside_em": "在预期波动外",
        "score": "评分",
        "market": "市场",
        "iv_vs_hv": "IV vs HV",
        "expected_move": "预期波动",
    },
}


def t(lang: str, key: str, **kwargs: object) -> str:
    pack = UI.get(normalize_lang(lang), UI["en"])
    text = pack.get(key, UI["en"][key])
    if kwargs:
        return text.format(**kwargs)
    return text


def localize_hard_reason(reason: str, lang: str) -> str:
    if normalize_lang(lang) != "zh":
        return reason
    replacements = (
        ("Earnings in holding window:", "持有期内有财报："),
        ("FOMC decision in holding window:", "持有期内有 FOMC 决议："),
    )
    out = reason
    for en, zh in replacements:
        if out.startswith(en):
            out = zh + out[len(en) :]
            break
    return out
