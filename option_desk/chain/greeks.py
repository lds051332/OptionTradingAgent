from __future__ import annotations

from math import exp, log, sqrt

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


def years_from_dte(dte: int) -> float:
    return max(dte, 0) / 365.0
