from __future__ import annotations

from math import exp, log, sqrt

from scipy.optimize import brentq
from scipy.stats import norm


def put_delta(
    spot: float,
    strike: float,
    t_years: float,
    iv: float,
    r: float = 0.04,
    q: float = 0.0,
) -> float | None:
    """Black-Scholes put delta. Returns a negative number; None if undefined."""
    if spot <= 0 or strike <= 0 or t_years <= 0 or iv <= 0:
        return None
    sigma_sqrt_t = iv * sqrt(t_years)
    if sigma_sqrt_t == 0:
        return None
    d1 = (log(spot / strike) + (r - q + 0.5 * iv * iv) * t_years) / sigma_sqrt_t
    return float(-exp(-q * t_years) * norm.cdf(-d1))


def abs_put_delta(
    spot: float,
    strike: float,
    t_years: float,
    iv: float,
    r: float = 0.04,
    q: float = 0.0,
) -> float | None:
    value = put_delta(spot, strike, t_years, iv, r, q)
    if value is None:
        return None
    return abs(value)


def call_delta(
    spot: float,
    strike: float,
    t_years: float,
    iv: float,
    r: float = 0.04,
    q: float = 0.0,
) -> float | None:
    """Black-Scholes call delta. Returns a positive number in (0, 1); None if undefined."""
    if spot <= 0 or strike <= 0 or t_years <= 0 or iv <= 0:
        return None
    sigma_sqrt_t = iv * sqrt(t_years)
    if sigma_sqrt_t == 0:
        return None
    d1 = (log(spot / strike) + (r - q + 0.5 * iv * iv) * t_years) / sigma_sqrt_t
    return float(exp(-q * t_years) * norm.cdf(d1))


def years_from_dte(dte: int) -> float:
    return max(dte, 0) / 365.0


def _d1_d2(
    spot: float,
    strike: float,
    t_years: float,
    iv: float,
    r: float,
    q: float,
) -> tuple[float, float] | None:
    if spot <= 0 or strike <= 0 or t_years <= 0 or iv <= 0:
        return None
    sigma_sqrt_t = iv * sqrt(t_years)
    if sigma_sqrt_t == 0:
        return None
    d1 = (log(spot / strike) + (r - q + 0.5 * iv * iv) * t_years) / sigma_sqrt_t
    return d1, d1 - sigma_sqrt_t


def call_price(
    spot: float,
    strike: float,
    t_years: float,
    iv: float,
    r: float = 0.04,
    q: float = 0.0,
) -> float | None:
    pair = _d1_d2(spot, strike, t_years, iv, r, q)
    if pair is None:
        return None
    d1, d2 = pair
    return float(spot * exp(-q * t_years) * norm.cdf(d1) - strike * exp(-r * t_years) * norm.cdf(d2))


def put_price(
    spot: float,
    strike: float,
    t_years: float,
    iv: float,
    r: float = 0.04,
    q: float = 0.0,
) -> float | None:
    pair = _d1_d2(spot, strike, t_years, iv, r, q)
    if pair is None:
        return None
    d1, d2 = pair
    return float(strike * exp(-r * t_years) * norm.cdf(-d2) - spot * exp(-q * t_years) * norm.cdf(-d1))


def implied_vol(
    right: str,
    spot: float,
    strike: float,
    t_years: float,
    market_price: float,
    r: float = 0.04,
    q: float = 0.0,
    lo: float = 1e-4,
    hi: float = 5.0,
) -> float | None:
    """Black-Scholes IV from a traded price. None if the price sits outside the vol bounds."""
    if market_price <= 0 or spot <= 0 or strike <= 0 or t_years <= 0:
        return None
    priced = call_price if right.upper() == "C" else put_price
    low = priced(spot, strike, t_years, lo, r, q)
    high = priced(spot, strike, t_years, hi, r, q)
    if low is None or high is None:
        return None
    if market_price < low - 1e-6 or market_price > high + 1e-6:
        return None

    def _gap(sigma: float) -> float:
        value = priced(spot, strike, t_years, sigma, r, q)
        assert value is not None
        return value - market_price

    try:
        return float(brentq(_gap, lo, hi, maxiter=80))
    except (ValueError, RuntimeError):
        return None
