from option_desk.chain.greeks import abs_put_delta, call_delta, call_price, implied_vol, put_delta


def test_atm_put_delta_near_half():
    delta = put_delta(100.0, 100.0, 30 / 365.0, 0.20, r=0.0, q=0.0)
    assert delta is not None
    assert abs(delta - (-0.5)) < 0.03


def test_otm_put_abs_delta_less_than_atm():
    atm = abs_put_delta(100.0, 100.0, 7 / 365.0, 0.40, r=0.05)
    otm = abs_put_delta(100.0, 90.0, 7 / 365.0, 0.40, r=0.05)
    assert atm is not None and otm is not None
    assert otm < atm


def test_invalid_inputs_return_none():
    assert put_delta(0, 100, 0.02, 0.2) is None
    assert put_delta(100, 100, 0, 0.2) is None
    assert put_delta(100, 100, 0.02, 0) is None


def test_atm_call_delta_near_half():
    delta = call_delta(100.0, 100.0, 30 / 365.0, 0.20, r=0.0, q=0.0)
    assert delta is not None
    assert abs(delta - 0.5) < 0.03


def test_otm_call_delta_less_than_atm():
    atm = call_delta(100.0, 100.0, 7 / 365.0, 0.40, r=0.05)
    otm = call_delta(100.0, 110.0, 7 / 365.0, 0.40, r=0.05)
    assert atm is not None and otm is not None
    assert otm < atm


def test_implied_vol_roundtrip_call():
    t = 7 / 365.0
    price = call_price(100.0, 103.0, t, 0.40, r=0.04)
    assert price is not None
    recovered = implied_vol("C", 100.0, 103.0, t, price, r=0.04)
    assert recovered is not None
    assert abs(recovered - 0.40) < 0.01


def test_implied_vol_rejects_below_intrinsic():
    t = 7 / 365.0
    assert implied_vol("C", 100.0, 90.0, t, 0.10, r=0.04) is None
