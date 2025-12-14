from __future__ import annotations
from typing import Optional, Literal

Mode = Literal["strict", "opportunistic", "speculative"]

def delta_based_sl(
    *,
    entry: float,
    spot: float,
    delta: Optional[float],
    gamma: Optional[float],
    mode: Mode,
    max_loss_frac: float,
) -> float:
    """
    Returns a premium SL (absolute) for a long option position.

    Guarantees a numeric SL:
    - If delta/gamma missing -> fallback to premium-based SL (max_loss_frac)
    - If values are weird -> clamp to sensible bounds
    """

    # hard fallback
    fallback = max(0.01, entry * (1.0 - max_loss_frac))

    if entry <= 0:
        return 0.01

    if delta is None or delta == 0 or spot <= 0:
        return fallback

    d = abs(float(delta))
    g = abs(float(gamma)) if gamma is not None else 0.0

    # Mode tuning: stricter -> tighter SL, speculative -> looser
    if mode == "strict":
        k = 0.85
    elif mode == "opportunistic":
        k = 1.00
    else:
        k = 1.15

    # Rough premium sensitivity: delta dominates; gamma small stabilizer
    # We want SL distance (in premium) proportional to allowed loss and inversely to delta.
    allowed_loss = max(0.01, entry * max_loss_frac)
    delta_adjust = max(0.20, min(1.25, 1.0 / max(0.15, d)))  # higher delta -> smaller adjust
    gamma_adjust = 1.0 + min(0.35, g * spot)  # modest widening if gamma large

    loss = allowed_loss * k * (0.75 + 0.25 * delta_adjust) * gamma_adjust
    sl = entry - loss

    # clamp so SL is not above entry and not below 0.01
    if sl >= entry:
        sl = entry * 0.99
    return max(0.01, sl)
