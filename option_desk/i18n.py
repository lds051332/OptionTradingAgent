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
        "search_empty": "Web search returned no hits; event scout is empty.",
        "scout_failed": "Event scout LLM failed: {exc}",
        "screen_failed": "{ticker}: failed to screen ({exc})",
        "screen_yahoo_meta": (
            "{ticker}: Yahoo sent incomplete quote metadata (currentTradingPeriod). "
            "Usually a source hiccup or rate limit, not a dead local network — retry the run."
        ),
        "skipped_classify": " Skipped event classification.",
        "pipe_run_started": "Analyzing {tickers}",
        "pipe_screen_started": "Pulling {ticker} {right} chain and estimating Delta…",
        "pipe_last_print_note": " (last print, not NBBO)",
        "pipe_screen_done": "{ticker} spot {spot}, {n} candidate bucket(s){note}",
        "pipe_calendar_started": "Checking {ticker} holding-window calendar (earnings / FOMC / macro)…",
        "pipe_calendar_failed": "{ticker} calendar check failed: {exc}",
        "pipe_calendar_hard": "{ticker} hard skip: {reasons}",
        "pipe_calendar_gate": "calendar gate",
        "pipe_calendar_soft": "{ticker} soft macro: {tags}",
        "pipe_calendar_clear": "{ticker} no hard calendar conflict in the holding window",
        "pipe_no_candidates": "No candidate buckets; skip calendar and scout, SKIP all",
        "pipe_desk_skip_all": "Desk done: no contract to open, all SKIP",
        "pipe_scout_search": "Searching for off-calendar gap risk…",
        "pipe_scout_hits": "Collected {n} search hits",
        "pipe_scout_llm": "Classifying events with the LLM…",
        "pipe_scout_done": "Scout done, {n} event(s)",
        "pipe_scout_done_empty": "Scout done, nothing to follow",
        "pipe_desk_started": "Desk reviewing, picking a contract from the buckets…",
        "pipe_desk_done": "Desk done",
        "pipe_run_finished": "Run finished",
        "pipe_run_error": "Run interrupted: {exc}",
        "web_invalid_ticker": "Invalid ticker: {item}",
        "web_need_ticker": "Enter at least one ticker",
        "web_too_many_tickers": "At most {n} tickers",
        "web_delta_range": "Delta must be between {lo} and {hi}",
        "web_shares_range": "Share count must be between {lo} and {hi}",
        "web_cost_range": "Cost basis must be greater than 0 and at most $1,000,000",
        "web_cash_range": "Cash must be between $1,000 and $10,000,000",
        "note_last_print": (
            "Last print, not NBBO: bid/ask missing, premium is last trade, spread unknown. "
            "Common on Yahoo after hours. Confirm live quotes before sending an order."
        ),
        "note_iv_implied": (
            "Chain IV unusable; Delta is implied from the last print for screening only, "
            "not an exchange Greek."
        ),
        "note_iv_floored": (
            "Chain IV too low to invert from last; floored at {floor}. "
            "Delta may be far off — screening only."
        ),
        "note_uncovered": "{leftover} shares uncovered (contracts cover lots of 100).",
        "note_no_calls": "No liquid calls in DTE {lo}-{hi}.",
        "note_no_puts": "No liquid puts in DTE {lo}-{hi}.",
        "note_as_of": "Option chain is a live yfinance snapshot; --as-of only shifts DTE and calendar windows.",
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
        "search_empty": "网页搜索没有结果，事件侦察为空。",
        "scout_failed": "事件侦察 LLM 失败：{exc}",
        "screen_failed": "{ticker}：筛链失败（{exc}）",
        "screen_yahoo_meta": (
            "{ticker}：Yahoo 返回的行情元数据不完整。多半是源站抽风或限流，"
            "不一定是本机断网，请再点一次开始分析。"
        ),
        "skipped_classify": " 已跳过事件分类。",
        "pipe_run_started": "开始分析 {tickers}",
        "pipe_screen_started": "正在拉取 {ticker} {right} 链并估算 Delta…",
        "pipe_last_print_note": "（权利金为成交价，非盘口）",
        "pipe_screen_done": "{ticker} 现价 {spot}，筛出 {n} 档候选{note}",
        "pipe_calendar_started": "正在核对 {ticker} 持有期日历（财报 / FOMC / 宏观）…",
        "pipe_calendar_failed": "{ticker} 日历核对失败：{exc}",
        "pipe_calendar_hard": "{ticker} 硬性跳过：{reasons}",
        "pipe_calendar_gate": "日历门控",
        "pipe_calendar_soft": "{ticker} 软宏观：{tags}",
        "pipe_calendar_clear": "{ticker} 持有期内无硬日历冲突",
        "pipe_no_candidates": "没有候选档位，跳过日历与侦察，直接 SKIP",
        "pipe_desk_skip_all": "终审完成：无合约可开，全部 SKIP",
        "pipe_scout_search": "正在搜索日历外突发风险…",
        "pipe_scout_hits": "已收集 {n} 条搜索结果",
        "pipe_scout_llm": "正在用 LLM 分类事件…",
        "pipe_scout_done": "侦察完成，{n} 条事件",
        "pipe_scout_done_empty": "侦察完成，无需要跟进的事件",
        "pipe_desk_started": "终审中，正在候选档位里选约…",
        "pipe_desk_done": "终审完成",
        "pipe_run_finished": "本轮分析结束",
        "pipe_run_error": "分析中断：{exc}",
        "web_invalid_ticker": "无效标的：{item}",
        "web_need_ticker": "至少填写一个标的",
        "web_too_many_tickers": "最多 {n} 个标的",
        "web_delta_range": "Delta 须在 {lo}–{hi} 之间",
        "web_shares_range": "持股数量须在 {lo}–{hi} 股",
        "web_cost_range": "成本价须大于 0 且不超过 $1,000,000",
        "web_cash_range": "本金须在 $1,000–$10,000,000",
        "note_last_print": (
            "过期成交价，不是盘口：买卖价为空，权利金用最新成交，价差未知。"
            "Yahoo 盘后常见。下单前必须核实现价与买卖盘。"
        ),
        "note_iv_implied": "链上 IV 不可用，Delta 由成交价反推，只用于选档，不是交易所 Greek。",
        "note_iv_floored": (
            "链上 IV 过低且无法从成交价反推，已套 {floor} 下限。"
            "Delta 偏差可能很大，仅供参考。"
        ),
        "note_uncovered": "{leftover} 股未覆盖（每张合约对应 100 股）。",
        "note_no_calls": "DTE {lo}-{hi} 没有流动性足够的 call。",
        "note_no_puts": "DTE {lo}-{hi} 没有流动性足够的 put。",
        "note_as_of": "期权链是 yfinance 实时快照；--as-of 只移动剩余天数和日历窗口。",
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
