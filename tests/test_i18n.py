from datetime import date, datetime, timezone

from option_desk.agents.desk import heuristic_desk
from option_desk.i18n import language_instruction, localize_hard_reason, normalize_lang, t
from option_desk.report import render_markdown
from option_desk.schemas import DeskAction, DeskOutput, DeskRun, TickerDecision
from tests.test_desk import _snap


def test_normalize_lang_aliases():
    assert normalize_lang("zh") == "zh"
    assert normalize_lang("zh-CN") == "zh"
    assert normalize_lang("中文") == "zh"
    assert normalize_lang("en") == "en"
    assert normalize_lang(None) == "en"


def test_ui_pack_and_instruction():
    assert t("zh", "decision") == "终审建议"
    assert t("en", "decision") == "Desk decision"
    assert "Simplified Chinese" in language_instruction("zh")
    assert language_instruction("en") == ""


def test_localize_hard_reason_zh():
    raw = "FOMC decision in holding window: 2026-09-16"
    assert "FOMC 决议" in localize_hard_reason(raw, "zh")
    assert localize_hard_reason(raw, "en") == raw


def test_heuristic_desk_zh_why():
    snap = _snap("NVDA")
    out = heuristic_desk([snap], events=[], cash=55000, lang="zh")
    assert out.decisions[0].action == DeskAction.OPEN
    assert "默认开标准档" in out.decisions[0].why
    assert "启发式终审" in out.portfolio_note


def test_markdown_zh_headers():
    snap = _snap("NVDA")
    run = DeskRun(
        as_of=date(2026, 9, 2),
        fetched_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
        cash=55000,
        snapshots=[snap],
        events=[],
        desk=DeskOutput(
            decisions=[
                TickerDecision(ticker="NVDA", action=DeskAction.SKIP, why="测试理由"),
            ],
            portfolio_note="组合备注",
        ),
        language="zh",
    )
    md = render_markdown(run)
    assert "# 卖 Put 决策台" in md
    assert "## 决策" in md
    assert "测试理由" in md
    assert "不构成投资建议" in md
