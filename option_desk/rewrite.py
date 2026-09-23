"""Compare a model proposal with the stamped desk decision."""

from __future__ import annotations

from option_desk.schemas import DeskOutput

_FIELDS = ("action", "structure", "delta_bucket", "contract_id")


def decision_changes(proposal: DeskOutput, stamped: DeskOutput) -> list[dict]:
    after_by = {decision.ticker: decision for decision in stamped.decisions}
    rows: list[dict] = []
    for before in proposal.decisions:
        after = after_by.get(before.ticker)
        if after is None:
            continue
        for field in _FIELDS:
            left = _text(getattr(before, field))
            right = _text(getattr(after, field))
            rows.append(
                {
                    "ticker": before.ticker,
                    "field": field,
                    "before": left,
                    "after": right,
                    "changed": left != right,
                }
            )
    return rows


def _text(value: object) -> str:
    if value is None:
        return ""
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    return str(value)
