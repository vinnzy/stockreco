def build_options_playbook(p_up: float) -> list[str]:
    # Simple default template tuned for next-day intraday attempts.
    # You will still need to check liquidity, spreads, and IV on your broker.
    delta = "0.45–0.55" if p_up >= 0.62 else "0.35–0.50"
    risk = "tight" if p_up >= 0.62 else "moderate"
    return [
        f"Prefer liquid weekly expiry; choose ~{delta} delta call (or slightly ITM).",
        "Entry only on confirmation: (a) gap-up holds above VWAP for 10–15m, OR (b) breakout above first 30m high with volume.",
        f"Stop: premium -15% ({risk}) OR underlying breaks VWAP/structure; also use time-stop (exit by 2:30pm if no move).",
        "Targets: scale out +20–30%, trail remainder for +40–50% when momentum continues.",
        "Avoid entries if bid-ask spreads are wide or IV is extremely elevated vs recent days."
    ]
