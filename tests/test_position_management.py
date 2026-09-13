from option_desk.positions.management import get_management_recommendation


def test_close_at_profit_target():
    result = get_management_recommendation(
        quote_available=True,
        profit_capture=0.76,
        dte=6,
        delta=0.07,
        spot=180,
        strike=170,
        strategy="CSP",
        assignment_ok=True,
    )
    assert result.action == "CLOSE"
    assert "PROFIT_TARGET_REACHED" in result.reasons


def test_near_expiry_close():
    result = get_management_recommendation(
        quote_available=True,
        profit_capture=0.51,
        dte=1,
        delta=0.20,
        spot=180,
        strike=170,
        strategy="CSP",
        assignment_ok=True,
    )
    assert result.action == "CLOSE"
    assert "NEAR_EXPIRY_PROFIT" in result.reasons


def test_close_beats_roll_when_both_fire():
    result = get_management_recommendation(
        quote_available=True,
        profit_capture=0.82,
        dte=5,
        delta=0.70,
        spot=160,
        strike=170,
        strategy="CSP",
        assignment_ok=False,
    )
    assert result.action == "CLOSE"


def test_csp_assignment_roll():
    result = get_management_recommendation(
        quote_available=True,
        profit_capture=0.20,
        dte=6,
        delta=0.30,
        spot=165,
        strike=170,
        strategy="CSP",
        assignment_ok=False,
    )
    assert result.action == "ROLL"
    assert result.reasons == ["ASSIGNMENT_RISK"]


def test_covered_call_assignment_roll():
    result = get_management_recommendation(
        quote_available=True,
        profit_capture=0.10,
        dte=5,
        delta=0.55,
        spot=180,
        strike=170,
        strategy="COVERED_CALL",
        assignment_ok=False,
    )
    assert result.action == "ROLL"


def test_hold_when_no_rules_fire():
    result = get_management_recommendation(
        quote_available=True,
        profit_capture=0.35,
        dte=6,
        delta=0.18,
        spot=180,
        strike=170,
        strategy="CSP",
        assignment_ok=True,
    )
    assert result.action == "HOLD"


def test_invalid_quote_is_not_hold():
    result = get_management_recommendation(
        quote_available=False,
        profit_capture=None,
        dte=None,
        delta=None,
        spot=None,
        strike=170,
        strategy="CSP",
        assignment_ok=True,
    )
    assert result.action is None
    assert result.reasons == []
