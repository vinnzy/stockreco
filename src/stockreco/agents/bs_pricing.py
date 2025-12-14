from __future__ import annotations
import math
from typing import Literal

OptionType = Literal["CE", "PE"]

def _norm_cdf(x: float) -> float:
    # Abramowitz-Stegun approximation
    k = 1.0 / (1.0 + 0.2316419 * abs(x))
    ksum = k * (0.319381530 + k * (-0.356563782 + k * (1.781477937 + k * (-1.821255978 + 1.330274429 * k))))
    cdf = 1.0 - (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x) * ksum
    return cdf if x >= 0 else 1.0 - cdf

def bs_price(S: float, K: float, r: float, t_years: float, iv: float, opt_type: OptionType) -> float:
    if t_years <= 0 or iv <= 0:
        return max(S - K, 0.0) if opt_type == "CE" else max(K - S, 0.0)
    sigma = iv
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * t_years) / (sigma * math.sqrt(t_years))
    d2 = d1 - sigma * math.sqrt(t_years)
    if opt_type == "CE":
        return S * _norm_cdf(d1) - K * math.exp(-r * t_years) * _norm_cdf(d2)
    return K * math.exp(-r * t_years) * _norm_cdf(-d2) - S * _norm_cdf(-d1)
