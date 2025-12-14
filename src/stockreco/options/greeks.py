from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

# --- Black-Scholes helpers (European) ---
# NOTE: For NSE index/stock options these are not perfectly European, but this is good enough for
# sizing theta burn / IV sensitivity heuristics at EOD.

def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

@dataclass
class Greeks:
    iv: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    vega: Optional[float] = None
    theta_per_day: Optional[float] = None
    rho: Optional[float] = None

def bs_price(S: float, K: float, T: float, r: float, sigma: float, cp: str) -> float:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    cp = cp.upper()
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if cp in ("C", "CE", "CALL"):
        return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    else:
        return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)

def bs_greeks(S: float, K: float, T: float, r: float, sigma: float, cp: str) -> Greeks:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return Greeks()
    cp = cp.upper()
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    pdf = _norm_pdf(d1)
    if cp in ("C", "CE", "CALL"):
        delta = _norm_cdf(d1)
        theta = (-S * pdf * sigma / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * _norm_cdf(d2))
    else:
        delta = _norm_cdf(d1) - 1
        theta = (-S * pdf * sigma / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * _norm_cdf(-d2))
    gamma = pdf / (S * sigma * math.sqrt(T))
    vega = S * pdf * math.sqrt(T)  # per 1.0 vol
    rho = K * T * math.exp(-r * T) * (_norm_cdf(d2) if cp in ("C", "CE", "CALL") else -_norm_cdf(-d2))
    return Greeks(
        iv=sigma,
        delta=delta,
        gamma=gamma,
        vega=vega,
        theta_per_day=theta / 365.0,
        rho=rho,
    )

def implied_vol(
    premium: float,
    S: float,
    K: float,
    T: float,
    r: float,
    cp: str,
    *,
    max_iter: int = 60,
    tol: float = 1e-6,
) -> Optional[float]:
    if premium is None or premium <= 0 or S <= 0 or K <= 0 or T <= 0:
        return None
    # Safe bounds
    lo, hi = 1e-4, 5.0  # 0.01% to 500% annualized
    # If premium is above hi vol price, return hi (rare)
    try:
        if bs_price(S, K, T, r, hi, cp) < premium:
            return hi
    except Exception:
        return None
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        price = bs_price(S, K, T, r, mid, cp)
        if abs(price - premium) < tol:
            return mid
        if price > premium:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)

def intrinsic_extrinsic(S: float, K: float, premium: float, cp: str) -> Tuple[float, float]:
    cp = cp.upper()
    if cp in ("C", "CE", "CALL"):
        intrinsic = max(0.0, S - K)
    else:
        intrinsic = max(0.0, K - S)
    extrinsic = max(0.0, (premium or 0.0) - intrinsic)
    return intrinsic, extrinsic
