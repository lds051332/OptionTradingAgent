from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ManagementResult:
    action: str | None
    reasons: list[str] = field(default_factory=list)


def get_management_recommendation(
    *,
    quote_available: bool,
    profit_capture: float | None,
    dte: int | None,
    delta: float | None,
    spot: float | None,
    strike: float,
    strategy: str,
    assignment_ok: bool,
    profit_target: float = 0.75,
    near_expiry_dte: int = 2,
    near_expiry_profit_target: float = 0.50,
) -> ManagementResult:
    if not quote_available:
        return ManagementResult(action=None, reasons=[])

    close_reasons: list[str] = []
    if profit_capture is not None and profit_capture >= profit_target:
        close_reasons.append("PROFIT_TARGET_REACHED")
    if (
        dte is not None
        and profit_capture is not None
        and dte <= near_expiry_dte
        and profit_capture >= near_expiry_profit_target
    ):
        close_reasons.append("NEAR_EXPIRY_PROFIT")
    if close_reasons:
        return ManagementResult(action="CLOSE", reasons=close_reasons)

    roll = False
    if not assignment_ok and spot is not None:
        if strategy == "CSP":
            if spot < strike or (delta is not None and abs(delta) >= 0.50):
                roll = True
        elif strategy == "COVERED_CALL":
            if spot > strike or (delta is not None and delta >= 0.50):
                roll = True
    if roll:
        return ManagementResult(action="ROLL", reasons=["ASSIGNMENT_RISK"])

    return ManagementResult(action="HOLD", reasons=["HOLD"])
