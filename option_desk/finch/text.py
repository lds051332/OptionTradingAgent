from __future__ import annotations

from option_desk.i18n import normalize_lang

# Buyer-facing copy for the Finch channel. Same shape as option_desk.i18n.UI:
# add every key to BOTH "en" and "zh".
COPY: dict[str, dict[str, str]] = {
    "en": {
        "capability": (
            "**Option Desk** reviews short-dated (3–9 DTE) US equity options for the wheel strategy "
            "and stamps each ticker **OPEN** or **SKIP**. It recommends; it never places orders.\n\n"
            "**Two books**\n"
            "- **Cash-secured puts**: send tickers and the cash you set aside. You get CSP or bull put "
            "spread, the conservative (~0.11Δ) or standard (~0.20Δ) bucket, the exact contract, the "
            "reasoning, and expiration P/L.\n"
            "- **Covered calls**: send the ticker, shares held (100 or more) and cost basis. You get the "
            "covered-call bucket and contract, and whether assignment is acceptable against your cost.\n\n"
            "**What it checks**: live yfinance option chain with Black-Scholes Delta; ATM IV vs 20/60/120-day "
            "realized volatility; 1-sigma expected move; a 0–100 contract score; VIX + SPY/QQQ regime; "
            "earnings and FOMC inside the holding window (hard skip); CPI / NFP / PCE (soft); and a news "
            "scout for off-calendar gap risk. The final pick must be a contract already in the screened buckets.\n\n"
            "**Examples**\n"
            "- `Sell puts on NVDA and MSFT, cash 50000`\n"
            "- `Covered call on AAPL, 300 shares, cost 180`\n"
            "- `NVDA 卖put 现金5万` (write in Chinese to get a Chinese report)\n\n"
            "Up to {n} tickers per request. A run usually takes about a minute.\n\n"
            "_Not investment advice. Not automated trading. Options can lose the entire premium; confirm "
            "quotes, fills and assignment cash before any order._"
        ),
        "ask_intro": "To run the desk I still need:",
        "ask_tickers": "- Tickers, up to {n} (uppercase symbols such as NVDA, MSFT, or cashtags like $nvda)",
        "ask_cash": "- Cash you set aside for cash-secured puts (for example: cash 50000)",
        "ask_shares": "- Shares you hold, at least 100 (for example: 300 shares)",
        "ask_cost": "- Your cost basis per share (for example: cost 180)",
        "ask_mode": "Say “covered call” for the covered-call desk; otherwise I run the cash-secured put desk.",
        "ask_example": "Example: `NVDA MSFT sell puts, cash 50000` or `covered call AAPL, 300 shares, cost 180`",
        "problem_delta": "- Delta must be between {lo} and {hi} (default 0.20).",
        "problem_cash": "- Cash must be between $1,000 and $10,000,000.",
        "problem_shares": "- Shares must be between 100 and 1,000,000.",
        "problem_cost": "- Cost basis must be above $0 and at most $1,000,000.",
        "note_dropped": "One request analyses at most {n} tickers, so this run covers {kept} and skips {dropped}.",
        "stage_queued": "Queued",
        "stage_starting": "Starting",
        "stage_regime": "Reading the VIX / SPY / QQQ regime",
        "stage_screen": "Screening the {ticker} option chain",
        "stage_calendar": "Checking {ticker} earnings and FOMC dates",
        "stage_scout": "Searching the news for gap risk",
        "stage_classify": "Classifying events",
        "stage_desk": "Desk review",
        "stage_done": "Done",
        "err_analysis": "The analysis could not finish. Please try again later.",
        "err_input": (
            "Not enough information to run the desk. Please start a new request with tickers and cash, "
            "or ticker, shares and cost basis for a covered call."
        ),
        "err_daily": "Today's free analysis quota is used up. Please try again tomorrow.",
        "err_data": "The market data source is rate-limiting right now. Please try again in a few minutes.",
        "skip_no_data": "No option chain came back for this ticker; see the warnings below.",
        "title_put": "Cash-secured put desk",
        "title_call": "Covered-call desk",
        "inputs_put": "Input: {tickers} · cash ${cash} · standard Δ {delta}",
        "inputs_call": "Input: {tickers} · {shares} shares · cost ${cost} · standard Δ {delta}",
        "sec_decision": "Decision",
        "sec_candidates": "Candidates",
        "assign_ok": "Assignment at this strike is acceptable.",
        "assign_not_ok": "Assignment at this strike is NOT acceptable versus your cost basis.",
        "per_ct": "/ct",
        "last_print": " (last print, confirm live quotes)",
        "qty_put": "CSP {n} ct, assignment ${cash}",
        "qty_call": "{n} ct covered",
        "spread": "spread: long {strike} (max loss ${loss}/ct, {n} ct)",
        "loss_capped": "capped",
        "loss_zero": "stock to $0",
        "calendar": "Holding window {start} → {end}",
        "hard": "hard skip: {reasons}",
        "fetched": "Chain fetched {ts} UTC.",
        "more_events": "…and {n} more.",
    },
    "zh": {
        "capability": (
            "**Option Desk（摩根大山期权决策台）** 针对美股 3–9 天到期的期权做 wheel 策略开仓评估，"
            "给每个标的盖 **OPEN** 或 **SKIP** 章。只给建议，从不下单。\n\n"
            "**两个决策台**\n"
            "- **卖 Put（现金担保）**：告诉我标的和可用现金。输出 CSP 或牛市看跌价差、保守档（约 0.11Δ）"
            "或标准档（约 0.20Δ）、具体合约、理由和到期损益。\n"
            "- **备兑 Call**：告诉我标的、持股数（至少 100 股）和每股成本。输出备兑档位与合约，"
            "以及相对成本价被指派是否可以接受。\n\n"
            "**会检查什么**：yfinance 实时期权链 + Black-Scholes 估算 Delta；ATM IV 与 20/60/120 日已实现波动对比；"
            "1σ 预期波动；0–100 合约评分；VIX + SPY/QQQ 市场体制；持有期内的财报与 FOMC（硬性跳过）；"
            "CPI / NFP / PCE（软标签）；以及新闻侦察日历外的跳空风险。最终只能从筛出的档位里选合约。\n\n"
            "**示例**\n"
            "- `NVDA MSFT 卖put 现金5万`\n"
            "- `备兑 AAPL 300股 成本180`\n"
            "- `Sell puts on NVDA, cash 50000`（用英文提问会得到英文报告）\n\n"
            "每次最多 {n} 个标的，一次分析通常一分钟左右。\n\n"
            "_不构成投资建议，不自动交易。期权可能亏掉全部权利金；下单前请核对报价、成交价与被指派所需现金。_"
        ),
        "ask_intro": "开跑前还差这几项：",
        "ask_tickers": "- 标的代码，最多 {n} 个（如 NVDA、MSFT，也可以写英伟达、微软）",
        "ask_cash": "- 卖 Put 可用的现金（如：现金 5万）",
        "ask_shares": "- 持股数量，至少 100 股（如：300股）",
        "ask_cost": "- 每股持仓成本（如：成本 180）",
        "ask_mode": "要做备兑 Call 请写“备兑”或“covered call”，否则默认走卖 Put。",
        "ask_example": "示例：`NVDA MSFT 卖put 现金5万` 或 `备兑 AAPL 300股 成本180`",
        "problem_delta": "- Delta 需在 {lo} 到 {hi} 之间（默认 0.20）。",
        "problem_cash": "- 现金需在 $1,000 到 $10,000,000 之间。",
        "problem_shares": "- 持股需在 100 到 1,000,000 股之间。",
        "problem_cost": "- 每股成本需大于 $0 且不超过 $1,000,000。",
        "note_dropped": "每次最多分析 {n} 个标的，本次分析 {kept}，未分析 {dropped}。",
        "stage_queued": "排队中",
        "stage_starting": "开始分析",
        "stage_regime": "读取 VIX / SPY / QQQ 市场体制",
        "stage_screen": "筛选 {ticker} 期权链",
        "stage_calendar": "检查 {ticker} 财报与 FOMC 日期",
        "stage_scout": "搜索新闻中的跳空风险",
        "stage_classify": "给事件分类",
        "stage_desk": "终审",
        "stage_done": "完成",
        "err_analysis": "分析没能完成，请稍后再试。",
        "err_input": "信息不足，无法开跑。请重新发起，写明标的和现金；备兑请写标的、持股数和成本。",
        "err_daily": "今天的免费分析次数已用完，请明天再试。",
        "err_data": "行情数据源暂时限流，请几分钟后再试。",
        "skip_no_data": "没拿到这只标的的期权链，见下方警告。",
        "title_put": "卖 Put 决策台",
        "title_call": "备兑 Call 决策台",
        "inputs_put": "输入：{tickers} · 现金 ${cash} · 标准档 Δ {delta}",
        "inputs_call": "输入：{tickers} · 持股 {shares} 股 · 成本 ${cost} · 标准档 Δ {delta}",
        "sec_decision": "结论",
        "sec_candidates": "候选合约",
        "assign_ok": "在这个行权价被指派可以接受。",
        "assign_not_ok": "相对持仓成本，在这个行权价被指派不可接受。",
        "per_ct": "/张",
        "last_print": "（成交价而非盘口，下单前请核实报价）",
        "qty_put": "CSP {n} 张，指派占用 ${cash}",
        "qty_call": "可卖 {n} 张",
        "spread": "价差：多头 {strike}（最大亏损 ${loss}/张，{n} 张）",
        "loss_capped": "有限",
        "loss_zero": "股价到 $0",
        "calendar": "持有窗口 {start} → {end}",
        "hard": "硬性跳过：{reasons}",
        "fetched": "期权链拉取时间 {ts} UTC。",
        "more_events": "……另有 {n} 条。",
    },
}


def ft(lang: str, key: str, **kwargs: object) -> str:
    pack = COPY.get(normalize_lang(lang), COPY["en"])
    text = pack.get(key, COPY["en"][key])
    return text.format(**kwargs) if kwargs else text
