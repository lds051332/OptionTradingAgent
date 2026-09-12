export type Lang = "zh" | "en";

const STORAGE_KEY = "option-desk:lang";

/** Add a page: add a sibling object in `zh` (and the same shape in `en`), then t("newpage.title"). */
const zh = {
  common: {
    brand: "摩根大山",
    back: "返回",
    loading: "正在打开决策台…",
    loadFailed: "打不开决策台",
    retry: "重试",
    lang: "语言",
  },
  home: {
    title: "本周两本账",
    lead: "现金一边卖 put，被指派后翻到对面卖 call。先选你现在站在哪一侧。",
    putTitle: "持币卖 Put",
    putBody: "现金担保。CSP 或牛市看跌价差。被指派后再换到持股账。",
    putAction: "打开卖 Put 决策台",
    callTitle: "持股卖 Call",
    callBody: "手里已经有股票。只卖 covered call，到期要么收租，要么按行权价卖掉。",
    callAction: "打开卖 Call 决策台",
  },
  app: {
    titleHome: "摩根大山 · Option Desk",
    titlePut: "卖 Put 决策台 · 摩根大山",
    titleCall: "卖 Call 决策台 · 摩根大山",
  },
  desk: {
    putTitle: "卖 Put 决策台",
    callTitle: "卖 Call 决策台",
    putHint: "填好标的、Delta 和本金后开始。",
    callHint: "填好标的、Delta、持股数量和成本价后开始。",
    putDisclaimer: "不构成投资建议。下单前请核对成交价与被指派所需现金。",
    callDisclaimer: "不构成投资建议。下单前请核对成交价；被指派即按行权价卖出持股。",
    collapse: "收起",
    editParams: "改参数",
    rerun: "重新分析",
    ticker: "标的",
    delta: "Delta 锚",
    shares: "持股数量",
    cash: "本金 USD",
    costBasis: "成本价 USD",
    costPlaceholder: "买入均价",
    start: "开始分析",
    running: "分析进行中…",
    working: "工作中",
    cached: "本机留底 · {when}",
    noTicker: "未选标的",
    noCost: "未填成本",
    costPrefix: "成本 ${value}",
    sharesPart: "{n}股",
    promptPut: "分析 {symbol} · Δ {delta} · 本金 ${cash}",
    promptCall: "分析 {symbol} · Δ {delta} · {shares}股 · 成本 ${cost}",
    failed: "分析失败",
    stepScreen: "筛链 {ticker}",
    stepCalendar: "日历 {ticker}",
    stepScout: "事件侦察",
    stepDesk: "终审",
    stepError: "中断",
    spotBuckets: "{ticker} 现价 {spot} · 候选档位",
    lastPrintKicker: "Last print · 非盘口",
    lastPrintBody: "买卖价为空，权利金用最新成交价，价差未知。Yahoo 盘后常见。下单前必须核实现价与买卖盘。",
    ivNote: "链上 IV 不可用，Δ 由成交价反推（失败则套下限），只用于选档，不是交易所 Greek。",
    noCalls: "两档都没有合格 call。",
    noPuts: "两档都没有合格合约。",
    colBucket: "档位",
    colContract: "合约",
    colPremium: "权利金",
    spread: "价差 {strike} / {n}张",
    noSpread: "无价差",
    contracts: "{n}张",
    ivImplied: "Δ反推",
    ivFloored: "IV下限",
    lastMark: "成交价",
    assignAtStrike: "行权价卖出 ${cash}",
    holding: "持有窗口 {start} → {end}",
    hardSkip: "硬性跳过",
    softMacro: "软宏观",
    noCalendar: "无硬日历冲突",
    noEvents: "没有需要跟进的日历外事件。",
    undated: "无日期",
    verdict: "终审盖章",
    structSpread: "牛市看跌价差",
    structCC: "Covered Call",
    structCSP: "CSP",
  },
  payoff: {
    kicker: "到期结算 {expiry} · {dte}DTE · {n} 张 · {structure}",
    maxProfit: "最大盈利",
    breakeven: "盈亏平衡",
    maxLoss: "最大亏损",
    credit: "净权利金 / 张",
    toZero: "{loss} · 到 $0",
    aria: "{ticker} {structure}到期损益图，盈亏平衡 {breakeven}",
    spot: "现价 {spot}",
    footAtSpot: "到期若仍在现价：{pnl}",
    footCallAssign: " · 若指派按行权价卖出，收入 {cash}",
    footPutAssign: " · 若指派需现金 {cash}",
    footCost: " · 成本 {cost}",
    footNote: "。按链上 mid 估算，非成交价；不含手续费与提前指派。",
    protect: "保护 {strike}",
  },
  ticker: {
    placeholder: "输入或选择，如 NVDA",
    openList: "打开标的列表",
    closeList: "收起标的列表",
    empty: "没有匹配，继续输入自定义代码",
    custom: "使用该代码",
    current: "当前",
  },
  frame: {
    payLabel: "打赏",
    contactLabel: "加微信",
    tipTitle: "打赏",
    tipBody: "即将失业的贫穷码农，服务器费用和 token 都是我自掏，随意打赏，万分感谢。",
    tipFootCompact: "点开放大，长按保存。",
    tipFoot: "另一部手机可以直接扫。这部手机请点开放大，长按保存后再用微信或支付宝从相册识别。",
    contactTitle: "加微信",
    contactBody: "报 bug、想加功能、或者想聊聊投资，都欢迎加我微信或发邮件。",
    contactEmailLabel: "邮箱",
    contactEmailCopy: "点击复制",
    contactEmailCopied: "已复制",
    contactFootCompact: "点开放大，长按保存。",
    contactFoot: "另一部手机可以直接扫。这部手机请点开放大，长按保存后用微信从相册识别。",
    payMethods: "收款方式",
    openQr: "点开放大",
    close: "关闭",
    qrLabel: "二维码",
    saveScan: "长按保存到相册，打开{app}从相册扫一扫。",
    wechat: "微信",
    wechatAlt: "微信收款码",
    alipay: "支付宝",
    alipayAlt: "支付宝收款码",
    paypal: "PayPal",
    paypalHint: "美元。点开后在 PayPal 完成付款，金额仍可改。",
    paypalHintCompact: "USD，点开付款。",
    paypalAmounts: "PayPal 金额",
    paypalCustom: "自己填",
    paypalAmount: "PayPal {amount}",
    paypalCustomAria: "打开 PayPal，自己填写金额",
    addWechat: "加微信",
    addWechatAlt: "个人微信二维码",
  },
  api: {
    requestFailed: "请求失败 ({status})",
    noStream: "浏览器不支持流式响应",
  },
} as const;

type NestedStrings<T> = {
  [K in keyof T]: T[K] extends string ? string : NestedStrings<T[K]>;
};

const en: NestedStrings<typeof zh> = {
  common: {
    brand: "摩根大山",
    back: "Back",
    loading: "Opening the desk…",
    loadFailed: "Could not open the desk",
    retry: "Try again",
    lang: "Language",
  },
  home: {
    title: "Two books this week",
    lead: "The cash book sells puts. Assignment flips you to the stock book to sell calls. Pick the side you are on.",
    putTitle: "Cash-secured puts",
    putBody: "Cash collateral. CSP or a bull put spread. After assignment, switch to the stock book.",
    putAction: "Open the put desk",
    callTitle: "Covered calls",
    callBody: "You already hold the shares. Covered calls only — collect rent or get called away at the strike.",
    callAction: "Open the call desk",
  },
  app: {
    titleHome: "摩根大山 · Option Desk",
    titlePut: "Put desk · 摩根大山",
    titleCall: "Call desk · 摩根大山",
  },
  desk: {
    putTitle: "Put desk",
    callTitle: "Call desk",
    putHint: "Fill ticker, delta, and cash, then start.",
    callHint: "Fill ticker, delta, share count, and cost basis, then start.",
    putDisclaimer: "Not investment advice. Confirm fills and assignment cash before sending any order.",
    callDisclaimer: "Not investment advice. Confirm fills; assignment sells the shares at the strike.",
    collapse: "Collapse",
    editParams: "Edit",
    rerun: "Run again",
    ticker: "Ticker",
    delta: "Delta anchor",
    shares: "Shares",
    cash: "Cash USD",
    costBasis: "Cost basis USD",
    costPlaceholder: "Average cost",
    start: "Analyze",
    running: "Analyzing…",
    working: "Working",
    cached: "Saved locally · {when}",
    noTicker: "No ticker",
    noCost: "No cost basis",
    costPrefix: "cost ${value}",
    sharesPart: "{n} sh",
    promptPut: "Analyze {symbol} · Δ {delta} · cash ${cash}",
    promptCall: "Analyze {symbol} · Δ {delta} · {shares} sh · cost ${cost}",
    failed: "Analysis failed",
    stepScreen: "Screen {ticker}",
    stepCalendar: "Calendar {ticker}",
    stepScout: "Event scout",
    stepDesk: "Desk",
    stepError: "Interrupted",
    spotBuckets: "{ticker} spot {spot} · candidate buckets",
    lastPrintKicker: "Last print · not NBBO",
    lastPrintBody: "Bid/ask empty, premium is last trade, spread unknown. Common on Yahoo after hours. Confirm live quotes before sending an order.",
    ivNote: "Chain IV unusable; Δ is implied from last (or floored). Screening only, not an exchange Greek.",
    noCalls: "No liquid call in either bucket.",
    noPuts: "No liquid contract in either bucket.",
    colBucket: "Bucket",
    colContract: "Contract",
    colPremium: "Premium",
    spread: "spread {strike} / {n} ct",
    noSpread: "no spread",
    contracts: "{n} ct",
    ivImplied: "Δ implied",
    ivFloored: "IV floor",
    lastMark: "last",
    assignAtStrike: "called away ${cash}",
    holding: "Holding window {start} → {end}",
    hardSkip: "Hard skip",
    softMacro: "Soft macro",
    noCalendar: "No hard calendar conflict",
    noEvents: "No off-calendar event to follow.",
    undated: "undated",
    verdict: "Desk stamp",
    structSpread: "Bull put spread",
    structCC: "Covered Call",
    structCSP: "CSP",
  },
  payoff: {
    kicker: "Expiry {expiry} · {dte} DTE · {n} ct · {structure}",
    maxProfit: "Max profit",
    breakeven: "Breakeven",
    maxLoss: "Max loss",
    credit: "Net credit / ct",
    toZero: "{loss} · to $0",
    aria: "{ticker} {structure} expiration P/L, breakeven {breakeven}",
    spot: "spot {spot}",
    footAtSpot: "If still at spot at expiry: {pnl}",
    footCallAssign: " · if called away, proceeds {cash}",
    footPutAssign: " · assignment cash {cash}",
    footCost: " · cost {cost}",
    footNote: ". Mid estimate from the chain, not a fill. Excludes fees and early assignment.",
    protect: "protect {strike}",
  },
  ticker: {
    placeholder: "Type or pick, e.g. NVDA",
    openList: "Open ticker list",
    closeList: "Close ticker list",
    empty: "No match — keep typing a custom symbol",
    custom: "Use this symbol",
    current: "current",
  },
  frame: {
    payLabel: "Tip jar",
    contactLabel: "WeChat",
    tipTitle: "Tip jar",
    tipBody: "Broke engineer keeping the lights on. Server and tokens come out of pocket. Anything helps — thank you.",
    tipFootCompact: "Tap to enlarge, then long-press to save.",
    tipFoot: "Scan from another phone. On this phone, tap to enlarge, long-press to save, then pick it from WeChat or Alipay photos.",
    contactTitle: "Add on WeChat",
    contactBody: "Bugs, feature ideas, or just talk shop — WeChat or email works.",
    contactEmailLabel: "Email",
    contactEmailCopy: "Tap to copy",
    contactEmailCopied: "Copied",
    contactFootCompact: "Tap to enlarge, then long-press to save.",
    contactFoot: "Scan from another phone. On this phone, tap to enlarge, long-press to save, then pick it from WeChat photos.",
    payMethods: "Pay rails",
    openQr: "Enlarge",
    close: "Close",
    qrLabel: "QR codes",
    saveScan: "Long-press to save, then scan from {app} photos.",
    wechat: "WeChat",
    wechatAlt: "WeChat pay QR",
    alipay: "Alipay",
    alipayAlt: "Alipay pay QR",
    paypal: "PayPal",
    paypalHint: "USD. Opens PayPal — you can still change the amount there.",
    paypalHintCompact: "USD · tap to pay",
    paypalAmounts: "PayPal amounts",
    paypalCustom: "Custom",
    paypalAmount: "PayPal {amount}",
    paypalCustomAria: "Open PayPal and enter any amount",
    addWechat: "Add WeChat",
    addWechatAlt: "Personal WeChat QR",
  },
  api: {
    requestFailed: "Request failed ({status})",
    noStream: "This browser cannot stream the response",
  },
};

const TICKER_NAMES: Record<Lang, Record<string, string>> = {
  zh: {
    SPY: "标普 500 ETF",
    QQQ: "纳指 100 ETF",
    NVDA: "英伟达",
    TSLA: "特斯拉",
    AAPL: "苹果",
    AMZN: "亚马逊",
    MSFT: "微软",
    META: "Meta",
    AMD: "超微",
    IWM: "罗素 2000 ETF",
    GOOGL: "谷歌",
    NFLX: "奈飞",
    AVGO: "博通",
    PLTR: "Palantir",
    TQQQ: "三倍做多纳指",
    IBIT: "比特币现货 ETF",
    COIN: "Coinbase",
    SOXL: "三倍做多半导体",
    MSTR: "Strategy",
    HOOD: "Robinhood",
  },
  en: {
    SPY: "S&P 500 ETF",
    QQQ: "Nasdaq-100 ETF",
    NVDA: "NVIDIA",
    TSLA: "Tesla",
    AAPL: "Apple",
    AMZN: "Amazon",
    MSFT: "Microsoft",
    META: "Meta",
    AMD: "AMD",
    IWM: "Russell 2000 ETF",
    GOOGL: "Alphabet",
    NFLX: "Netflix",
    AVGO: "Broadcom",
    PLTR: "Palantir",
    TQQQ: "3x Nasdaq",
    IBIT: "Bitcoin spot ETF",
    COIN: "Coinbase",
    SOXL: "3x Semiconductors",
    MSTR: "Strategy",
    HOOD: "Robinhood",
  },
};

const messages = { zh, en } as const;

type Leaves<T> = T extends string
  ? never
  : {
      [K in keyof T & string]: T[K] extends string ? K : `${K}.${Leaves<T[K]> & string}`;
    }[keyof T & string];

export type MsgKey = Leaves<typeof zh>;

let activeLang: Lang = "zh";

function getPath(pack: unknown, path: string): string {
  let node: unknown = pack;
  for (const part of path.split(".")) {
    if (!node || typeof node !== "object" || !(part in node)) return "";
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === "string" ? node : "";
}

export function readStoredLang(): Lang | null {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "zh" || stored === "en") return stored;
  } catch {
    /* ignore */
  }
  return null;
}

export function browserLang(): Lang {
  const nav = (typeof navigator !== "undefined" ? navigator.language : "")?.toLowerCase() ?? "";
  return nav.startsWith("zh") ? "zh" : nav ? "en" : "zh";
}

export function detectLang(): Lang {
  return readStoredLang() ?? browserLang();
}

export function getLang(): Lang {
  return activeLang;
}

export function setActiveLang(lang: Lang, options?: { persist?: boolean }): void {
  activeLang = lang;
  if (options?.persist !== false) {
    try {
      window.localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      /* ignore */
    }
  }
  if (typeof document !== "undefined") {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  }
}

export function t(lang: Lang, key: MsgKey, vars?: Record<string, string | number>): string {
  let text = getPath(messages[lang], key) || getPath(messages.en, key) || key;
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      text = text.replaceAll(`{${name}}`, String(value));
    }
  }
  return text;
}

export function tx(key: MsgKey, vars?: Record<string, string | number>): string {
  return t(activeLang, key, vars);
}

export function tickerName(lang: Lang, symbol: string): string {
  return TICKER_NAMES[lang][symbol] ?? TICKER_NAMES.en[symbol] ?? symbol;
}

export function dateLocale(lang: Lang): string {
  return lang === "zh" ? "zh-CN" : "en-US";
}
