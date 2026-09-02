from __future__ import annotations

ZH_ALIASES = {"zh", "zh-cn", "zh_cn", "cn", "chinese", "中文"}
EN_ALIASES = {"en", "en-us", "english", "英文"}


def normalize_lang(value: str | None) -> str:
    raw = (value or "en").strip().lower()
    if raw in ZH_ALIASES:
        return "zh"
    if raw in EN_ALIASES or raw == "en":
        return "en"
    if raw.startswith("zh"):
        return "zh"
    return "en"


def language_instruction(lang: str) -> str:
    if normalize_lang(lang) != "zh":
        return ""
    return (
        "\n\nWrite all user-facing prose in Simplified Chinese: event titles, "
        "detail, why, premium_tradeoff, and portfolio_note. Keep enum values, "
        "tickers, contract_id, dates, and numbers unchanged. Call the "
        "conservative/standard candidates 档位, never 梯子 or 阶梯."
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
    },
}


def t(lang: str, key: str) -> str:
    pack = UI.get(normalize_lang(lang), UI["en"])
    return pack.get(key, UI["en"][key])


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
