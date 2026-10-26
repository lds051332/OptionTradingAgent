import type { Lang } from "./i18n";

/** Paragraphs may contain `[text](href)` links; hrefs starting with "/" stay inside the SPA. */
export type InfoSection = { heading: string; body: string[] };
export type InfoDoc = { title: string; lead: string; updated?: string; sections: InfoSection[] };
export type InfoPageId = "about" | "privacy";

const EMAIL = "605465435@qq.com";
const REPO = "https://github.com/lds051332/OptionTradingAgent";

const about: Record<Lang, InfoDoc> = {
  zh: {
    title: "关于",
    lead: "摩根大山轮式策略决策台是一个免费的美股期权辅助决策工具，帮你在做轮式策略（Wheel）时更快地筛合约、查风险。它只给建议，不连接券商，也不会替你下单。",
    sections: [
      {
        heading: "它能做什么",
        body: [
          "持币卖 Put：输入标的、目标 Delta 和本金，筛选 3–9 天到期的现金担保 Put（CSP）或牛市看跌价差。",
          "持股卖 Call：输入持股数量和成本价，筛选备兑 Call，并提示一旦被指派，相对成本价是赚还是亏。",
          "我的持仓：记录已经开出的仓位，估算盈亏，按你设定的止盈规则提示平仓或滚仓。",
        ],
      },
      {
        heading: "它是怎么工作的",
        body: [
          "每次分析依次做这几件事：读取 VIX、SPY、QQQ 判断市场环境；拉取期权链并估算 Delta，筛出保守档（约 0.10 Delta）和标准档（约 0.20 Delta）两个候选；检查持有期内有没有财报或 FOMC 会议，有就直接跳过；搜索新闻，看有没有日历上看不到的突发风险；最后由大模型在候选合约里做决定。",
          "大模型的决定还要再过一层硬规则：只能从候选档位里选合约，不能编造；撞上财报必须跳过；市场偏弱时会被降到更保守的档位。[规则回放](/replay)页面演示了这几种情况。",
        ],
      },
      {
        heading: "数据来源和局限",
        body: [
          "期权链和股价来自 yfinance（Yahoo Finance），可能有延迟，盘后经常没有买卖报价。Delta 是用 Black-Scholes 模型估算的，不是交易所提供的官方数据。",
          "财报和宏观日历、新闻搜索都可能有遗漏，大模型也可能出错，所以所有结果都只能作为参考。",
        ],
      },
      {
        heading: "免责声明",
        body: [
          "本站内容不构成任何投资建议。期权交易风险很高：CSP 被指派时需要按行权价买入股票，股价大跌时亏损可能远超收到的权利金；备兑 Call 被指派时，股票会按行权价卖出。下单前请自行核实价格和风险，盈亏自负。",
        ],
      },
      {
        heading: "关于作者",
        body: [
          "这个工具由大山一个人开发和维护，服务器和大模型的费用都是自掏腰包，网站免费使用。",
          `代码在 GitHub 上开源：[lds051332/OptionTradingAgent](${REPO})。`,
        ],
      },
      {
        heading: "联系方式",
        body: [
          `发现 bug、想要新功能，或者想聊聊投资，欢迎发邮件到 [${EMAIL}](mailto:${EMAIL})，也可以扫页面上的二维码加我微信。`,
        ],
      },
    ],
  },
  en: {
    title: "About",
    lead: "The 摩根大山 wheel strategy desk is a free decision aid for selling options on US stocks. It helps you screen contracts and check risks faster when running the wheel. It only makes suggestions — it doesn't connect to a broker and never places orders.",
    sections: [
      {
        heading: "What it does",
        body: [
          "Cash-secured puts: enter a ticker, target delta, and cash to screen 3–9 DTE cash-secured puts or bull put spreads.",
          "Covered calls: enter your share count and cost basis to screen covered calls and see whether getting called away would be a gain or a loss.",
          "My positions: log the positions you've opened, estimate P&L, and get close or roll prompts based on your take-profit rules.",
        ],
      },
      {
        heading: "How it works",
        body: [
          "Each analysis runs these steps in order: read VIX, SPY, and QQQ to gauge the market; fetch the option chain, estimate delta, and pick two candidates — a conservative bucket (about 0.10 delta) and a standard bucket (about 0.20 delta); skip outright if earnings or an FOMC meeting falls in the holding period; search the news for risks the calendar won't show; and finally let a language model choose among the candidates.",
          "The model's choice then goes through hard rules: it can only pick a contract from the candidate buckets, it must skip around earnings, and it gets moved to the conservative bucket when the market looks weak. The [rule replays](/replay) page shows these cases.",
        ],
      },
      {
        heading: "Data sources and limits",
        body: [
          "Option chains and prices come from yfinance (Yahoo Finance). They may be delayed, and bid/ask quotes are often missing after hours. Delta is estimated with the Black-Scholes model, not taken from an exchange.",
          "Earnings and macro calendars and news search can miss things, and the model can be wrong, so treat every result as a reference only.",
        ],
      },
      {
        heading: "Disclaimer",
        body: [
          "Nothing on this site is investment advice. Options are risky: if a cash-secured put is assigned you buy the shares at the strike, and a sharp drop can cost far more than the premium you collected; if a covered call is assigned your shares are sold at the strike. Check prices and risks yourself before placing any order. You are responsible for your own results.",
        ],
      },
      {
        heading: "Who built it",
        body: [
          "The desk is built and run by one person, 大山 (Dashan). Server and model costs come out of pocket, and the site is free to use.",
          `The code is open source on GitHub: [lds051332/OptionTradingAgent](${REPO}).`,
        ],
      },
      {
        heading: "Contact",
        body: [
          `Found a bug, want a feature, or just want to talk investing? Email [${EMAIL}](mailto:${EMAIL}) or add me on WeChat with the QR code on the page.`,
        ],
      },
    ],
  },
};

const privacy: Record<Lang, InfoDoc> = {
  zh: {
    title: "隐私政策",
    updated: "最后更新：2026 年 10 月 26 日",
    lead: "这份政策说明摩根大山决策台（option.xdashan.top，下称「本站」）会处理哪些数据、怎么处理，以及你有哪些选择。本站没有注册和登录，不需要你提供姓名、手机号等身份信息。",
    sections: [
      {
        heading: "只保存在你浏览器里的数据",
        body: [
          "以下数据只保存在你浏览器的本地存储（localStorage）里，不会上传到服务器：界面语言、Cookie 同意选择、最近一次分析结果的缓存，以及「我的持仓」里记录的仓位和止盈规则。",
          "清除浏览器数据会把它们一起删掉。重要的持仓记录，请定期用持仓页的「导出」功能备份。",
        ],
      },
      {
        heading: "发送到服务器的数据",
        body: [
          "点击「开始分析」时，浏览器会把你填写的标的代码、目标 Delta、本金，或持股数量和成本价发送到服务器。在「我的持仓」点击「重新计算」时，会发送你记录的合约信息（标的、到期日、行权价、张数、开仓权利金）用于估值。",
          "这些数据只用于当次计算，本站不会把它们存进数据库，也不会建立用户档案。",
          "和大多数网站一样，服务器的访问日志会记录访问者的 IP 地址、访问时间、请求的网址和浏览器信息，只用于排查故障和防止滥用。",
        ],
      },
      {
        heading: "会接触到数据的第三方服务",
        body: [
          "行情和新闻：服务器会按标的代码向 Yahoo Finance（通过 yfinance）请求行情，向 DuckDuckGo 或 Tavily 搜索相关新闻。这些请求只包含标的代码和关键词，不包含你的个人信息。",
          "大模型：为了生成建议，服务器会把标的、候选合约、行情数据，以及你填写的本金或持股数量、成本价发送给大模型服务商（目前是 DeepSeek）。",
          "语言识别：第一次访问时，服务器会把你的 IP 地址发给 country.is 查询所在国家，用来决定默认显示中文还是英文。",
          "静态资源：页面字体从 Google Fonts 加载，Logo 和二维码图片从阿里云 OSS 加载。加载时这些服务会收到你的 IP 地址。",
          "打赏：只有你主动点击 PayPal 链接或扫码付款时，才会跳转到 PayPal、微信或支付宝，相关数据按它们各自的隐私政策处理。",
        ],
      },
      {
        heading: "广告和 Cookie",
        body: [
          "本站可能使用 Google AdSense 展示广告。开启广告后，页面底部会弹出提示，由你选择是否同意。在你做出选择之前，本站不会加载任何 Google 广告代码。",
          "如果你同意，Google 及其合作伙伴可能使用 Cookie 或类似技术，根据你在本站和其他网站上的访问情况展示个性化广告。如果你拒绝，Google 只会展示不依赖个人数据的非个性化广告。",
          "你可以随时点击页面底部的「Cookie 设置」修改选择，也可以在 [Google 广告设置](https://adssettings.google.com) 里关闭个性化广告。Google 如何使用这些数据，见 [Google 的说明](https://policies.google.com/technologies/partner-sites)。",
        ],
      },
      {
        heading: "未成年人",
        body: ["本站面向成年投资者，不面向未满 18 岁的用户，也不会有意收集未成年人的信息。"],
      },
      {
        heading: "政策变更和联系方式",
        body: [
          "本政策更新时，会修改页面顶部的日期。",
          `对本政策有任何疑问，或者想要求删除与你有关的数据，请发邮件到 [${EMAIL}](mailto:${EMAIL})。`,
        ],
      },
    ],
  },
  en: {
    title: "Privacy policy",
    updated: "Last updated: October 26, 2026",
    lead: "This policy explains what data the 摩根大山 desk (option.xdashan.top, \"the site\") handles, how, and what choices you have. The site has no sign-up or login and never asks for your name, phone number, or other identity details.",
    sections: [
      {
        heading: "Data that stays in your browser",
        body: [
          "The following is kept only in your browser's local storage (localStorage) and is never uploaded: your interface language, your cookie choice, a cache of your latest analysis, and every position and take-profit rule in My positions.",
          "Clearing your browser data deletes all of it, so back up important positions regularly with Export on the positions page.",
        ],
      },
      {
        heading: "Data sent to the server",
        body: [
          "When you click Analyze, your browser sends the ticker, target delta, and cash — or share count and cost basis — to the server. When you tap Revalue in My positions, it sends the contracts you logged (ticker, expiry, strike, contracts, entry premium) to be priced.",
          "This data is used only for that calculation. The site doesn't store it in a database or build user profiles.",
          "Like most websites, the server's access logs record visitors' IP addresses, request times, requested URLs, and browser details. They are used only to fix problems and prevent abuse.",
        ],
      },
      {
        heading: "Third-party services that receive data",
        body: [
          "Market data and news: the server requests quotes from Yahoo Finance (via yfinance) and searches DuckDuckGo or Tavily for news. These requests contain only tickers and keywords, not your personal information.",
          "Language model: to produce a suggestion, the server sends the ticker, candidate contracts, market data, and the cash, share count, or cost basis you entered to the model provider (currently DeepSeek).",
          "Language detection: on your first visit, the server sends your IP address to country.is to look up your country and pick Chinese or English as the default.",
          "Static files: fonts load from Google Fonts, and the logo and QR codes load from Alibaba Cloud OSS. These services receive your IP address when they serve the files.",
          "Tips: only if you choose to tip through PayPal, WeChat, or Alipay are you sent to those services, which handle your data under their own privacy policies.",
        ],
      },
      {
        heading: "Ads and cookies",
        body: [
          "The site may show ads through Google AdSense. When ads are on, a notice at the bottom of the page asks for your choice. No Google ad code loads until you choose.",
          "If you accept, Google and its partners may use cookies or similar technologies to show personalized ads based on your visits to this and other sites. If you decline, Google shows only non-personalized ads that don't rely on personal data.",
          "You can change your choice any time with Cookie settings at the bottom of the page, or turn off personalized ads in [Google Ad Settings](https://adssettings.google.com). See [how Google uses this data](https://policies.google.com/technologies/partner-sites).",
        ],
      },
      {
        heading: "Children",
        body: ["The site is meant for adult investors. It is not directed at anyone under 18 and does not knowingly collect their information."],
      },
      {
        heading: "Changes and contact",
        body: [
          "When this policy changes, the date at the top is updated.",
          `Questions about this policy, or requests to delete data about you, can go to [${EMAIL}](mailto:${EMAIL}).`,
        ],
      },
    ],
  },
};

export const INFO_PAGES: Record<InfoPageId, Record<Lang, InfoDoc>> = { about, privacy };
