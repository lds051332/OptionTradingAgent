"""Search-engine surface: per-route <head> tags, robots.txt, and sitemap.xml.

Titles here must match `app.title*` in web/src/i18n.ts, because Google indexes the
rendered page and the SPA rewrites document.title after load.
"""

from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass
from xml.sax.saxutils import escape as xml_escape

from fastapi import Request

from option_desk.i18n import lang_from_headers
from option_desk.replay import list_scenarios, scenario_ids
from option_desk.web.ads import adsense_client

PUBLIC_URL_ENV = "OPTION_DESK_PUBLIC_URL"
GOOGLE_VERIFY_ENV = "OPTION_DESK_GOOGLE_SITE_VERIFICATION"

HEAD_START = "<!--seo:start-->"
HEAD_END = "<!--seo:end-->"
OG_IMAGE = "https://option-trading-agent.oss-cn-beijing.aliyuncs.com/morgan-dashan-icon.png"

LANGS = ("zh", "en")
HREFLANG = {"zh": "zh-CN", "en": "en"}
OG_LOCALE = {"zh": "zh_CN", "en": "en_US"}
HTML_LANG = {"zh": "zh-CN", "en": "en"}

_HTML_LANG_RE = re.compile(r'<html lang="[^"]*"')


@dataclass(frozen=True)
class PageMeta:
    title: str
    description: str


_PAGES: dict[str, dict[str, PageMeta]] = {
    "/": {
        "zh": PageMeta(
            "摩根大山 · 美股期权轮式策略决策台",
            "免费的美股期权轮式策略（Wheel）决策工具：持币卖 Put（CSP）、持股卖备兑 Call。"
            "自动筛选期权链，检查财报和宏观事件，规则把关后给出开仓建议。只给建议，不代下单。",
        ),
        "en": PageMeta(
            "摩根大山 · Wheel Strategy Desk for US Options",
            "A free decision tool for running the options wheel on US stocks: cash-secured puts and "
            "covered calls. It screens the option chain, checks earnings and macro events, and "
            "rule-checks every suggestion. Advice only — it never places orders.",
        ),
    },
    "/put": {
        "zh": PageMeta(
            "卖 Put 决策台 · 摩根大山",
            "输入标的、目标 Delta 和本金，筛选现金担保 Put（CSP）或牛市看跌价差，"
            "检查持有期内的财报和宏观事件，给出开仓建议和到期损益。",
        ),
        "en": PageMeta(
            "Put desk · 摩根大山",
            "Enter a ticker, target delta, and cash to screen cash-secured puts or bull put spreads, "
            "check earnings and macro events in the holding period, and get a suggestion with its "
            "payoff at expiry.",
        ),
    },
    "/call": {
        "zh": PageMeta(
            "卖 Call 决策台 · 摩根大山",
            "输入标的、持股数量和成本价，筛选备兑 Call（Covered Call），检查财报和宏观事件，"
            "并提示被指派时相对成本价的盈亏。",
        ),
        "en": PageMeta(
            "Call desk · 摩根大山",
            "Enter a ticker, share count, and cost basis to screen covered calls, check earnings and "
            "macro events, and see what assignment means against your cost basis.",
        ),
    },
    "/positions": {
        "zh": PageMeta(
            "我的持仓 · 摩根大山",
            "记录已开出的 CSP 和备兑 Call，估算盈亏，按止盈规则提示平仓或滚仓。数据只保存在你的浏览器里。",
        ),
        "en": PageMeta(
            "My positions · 摩根大山",
            "Log your open CSPs and covered calls, estimate P&L, and get close or roll prompts from "
            "your take-profit rules. Data stays in your browser.",
        ),
    },
    "/replay": {
        "zh": PageMeta(
            "规则回放 · 摩根大山",
            "三个录制好的案例，演示规则如何拦截模型的开仓建议：硬性风控、编造的合约、主动降风险。"
            "不请求行情，也不调用模型。",
        ),
        "en": PageMeta(
            "Rule replays · 摩根大山",
            "Three recorded cases showing how the rules override the model's trade ideas: a hard risk "
            "rule, a made-up contract, and cutting risk. No live quotes, no model calls.",
        ),
    },
    "/about": {
        "zh": PageMeta(
            "关于 · 摩根大山",
            "摩根大山轮式策略决策台是什么、怎么工作、数据从哪来、有哪些局限，以及作者和联系方式。",
        ),
        "en": PageMeta(
            "About · 摩根大山",
            "What the 摩根大山 wheel strategy desk is, how it works, where its data comes from, its "
            "limits, and who built it.",
        ),
    },
    "/privacy": {
        "zh": PageMeta(
            "隐私政策 · 摩根大山",
            "摩根大山决策台收集哪些数据、数据存在哪里、与哪些第三方共享，以及广告和 Cookie 的使用方式。",
        ),
        "en": PageMeta(
            "Privacy policy · 摩根大山",
            "What data the 摩根大山 desk collects, where it is stored, which third parties receive it, "
            "and how ads and cookies are used.",
        ),
    },
}

_SITEMAP_PATHS = ("/", "/put", "/call", "/replay", "/about", "/privacy")


def normalize_path(path: str) -> str:
    clean = path.split("?")[0].split("#")[0].strip("/")
    return f"/{clean}" if clean else "/"


def page_meta(path: str, lang: str) -> PageMeta | None:
    path = normalize_path(path)
    if path in _PAGES:
        return _PAGES[path][lang]
    if path.startswith("/replay/"):
        scenario = path.removeprefix("/replay/")
        for item in list_scenarios(lang):
            if item["id"] == scenario:
                return PageMeta(_PAGES["/replay"][lang].title, item["summary"])
    return None


def sitemap_paths() -> list[str]:
    return [*_SITEMAP_PATHS, *(f"/replay/{scenario}" for scenario in scenario_ids())]


def requested_lang(request: Request) -> str | None:
    value = (request.query_params.get("lang") or "").strip().lower()
    return value if value in LANGS else None


def page_lang(request: Request) -> str:
    """Mirror the SPA: ?lang wins, then the browser language, else English."""
    return requested_lang(request) or lang_from_headers(request.headers, fallback="en")


def site_url(request: Request) -> str:
    configured = os.environ.get(PUBLIC_URL_ENV, "").strip().rstrip("/")
    if configured:
        return configured
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto.split(',')[0].strip()}://{host.split(',')[0].strip()}"


def _url(base: str, path: str, lang: str | None = None) -> str:
    return f"{base}{path}" + (f"?lang={lang}" if lang else "")


def _alternates(base: str, path: str) -> list[tuple[str, str]]:
    pairs = [(HREFLANG[lang], _url(base, path, lang)) for lang in LANGS]
    pairs.append(("x-default", _url(base, path)))
    return pairs


def _attr(value: str) -> str:
    return html.escape(value, quote=True)


def _json_ld(base: str, lang: str) -> str:
    home = _PAGES["/"][lang]
    data = {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": home.title,
        "alternateName": "Option Desk",
        "url": f"{base}/",
        "description": home.description,
        "applicationCategory": "FinanceApplication",
        "operatingSystem": "Web",
        "inLanguage": [HREFLANG[item] for item in LANGS],
        "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
    }
    body = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{body}</script>'


def head_tags(path: str, lang: str, base: str, *, explicit_lang: bool) -> tuple[str, bool]:
    """Return the <head> fragment and whether the path is a known page."""
    path = normalize_path(path)
    meta = page_meta(path, lang)
    tags: list[str] = []
    verify = os.environ.get(GOOGLE_VERIFY_ENV, "").strip()
    if verify:
        tags.append(f'<meta name="google-site-verification" content="{_attr(verify)}" />')
    client = adsense_client()
    if client:
        tags.append(f'<meta name="google-adsense-account" content="{client}" />')
    if meta is None:
        home = _PAGES["/"][lang]
        tags.append(f"<title>{html.escape(home.title)}</title>")
        tags.append('<meta name="robots" content="noindex" />')
        return "\n    ".join(tags), False

    canonical = _url(base, path, lang if explicit_lang else None)
    tags += [
        f"<title>{html.escape(meta.title)}</title>",
        f'<meta name="description" content="{_attr(meta.description)}" />',
        f'<link rel="canonical" href="{_attr(canonical)}" />',
    ]
    tags += [
        f'<link rel="alternate" hreflang="{code}" href="{_attr(href)}" />'
        for code, href in _alternates(base, path)
    ]
    tags += [
        '<meta property="og:type" content="website" />',
        '<meta property="og:site_name" content="摩根大山" />',
        f'<meta property="og:title" content="{_attr(meta.title)}" />',
        f'<meta property="og:description" content="{_attr(meta.description)}" />',
        f'<meta property="og:url" content="{_attr(canonical)}" />',
        f'<meta property="og:image" content="{OG_IMAGE}" />',
        f'<meta property="og:locale" content="{OG_LOCALE[lang]}" />',
        '<meta name="twitter:card" content="summary" />',
    ]
    if path == "/":
        tags.append(_json_ld(base, lang))
    return "\n    ".join(tags), True


def render_shell(template: str, path: str, request: Request) -> tuple[str, int]:
    """Fill the SPA shell for one request. Unknown paths get a 404 + noindex shell."""
    lang = page_lang(request)
    fragment, known = head_tags(
        path,
        lang,
        site_url(request),
        explicit_lang=requested_lang(request) is not None,
    )
    start = template.find(HEAD_START)
    end = template.find(HEAD_END)
    if start != -1 and end > start:
        template = template[: start + len(HEAD_START)] + "\n    " + fragment + "\n    " + template[end:]
    template = _HTML_LANG_RE.sub(f'<html lang="{HTML_LANG[lang]}"', template, count=1)
    return template, 200 if known else 404


def robots_txt(request: Request) -> str:
    return "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /finch/",
            "",
            f"Sitemap: {site_url(request)}/sitemap.xml",
            "",
        ]
    )


def sitemap_xml(request: Request) -> str:
    base = site_url(request)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    for path in sitemap_paths():
        alternates = _alternates(base, path)
        for loc in (_url(base, path), *(_url(base, path, lang) for lang in LANGS)):
            lines.append("  <url>")
            lines.append(f"    <loc>{xml_escape(loc)}</loc>")
            lines += [
                f'    <xhtml:link rel="alternate" hreflang="{code}" href="{xml_escape(href)}" />'
                for code, href in alternates
            ]
            lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"
