import React, { useMemo } from "react";
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    Tooltip,
    CartesianGrid,
    ResponsiveContainer,
    ReferenceLine,
} from "recharts";


function fmt2(x) {
    const n = Number(x);
    if (!Number.isFinite(n)) return "—";
    return n.toFixed(2);
}

function payoffPerUnit({ side, strike, premium }, spotAtExpiry) {
    // Long option payoff at expiry (per unit)
    const S = Number(spotAtExpiry);
    const K = Number(strike);
    const P = Number(premium);
    if (!Number.isFinite(S) || !Number.isFinite(K) || !Number.isFinite(P)) return null;

    if (String(side).toUpperCase() === "CE") {
        return Math.max(0, S - K) - P;
    }
    if (String(side).toUpperCase() === "PE") {
        return Math.max(0, K - S) - P;
    }
    return null;
}

function buildRange({ spot, strike }) {
    const base = Number(spot) > 0 ? Number(spot) : Number(strike);
    const span = Math.max(200, base * 0.06); // ±6% or 200pts min
    const lo = Math.max(1, base - span);
    const hi = base + span;
    return { lo, hi };
}

export default function PayoffModal({ open, onClose, row, quote }) {
    const payload = useMemo(() => {
        if (!row) return null;

        const side = row.side;
        const strike = row.strike;
        // use live LTP if available, else entry as premium proxy
        const premium =
            (quote && quote.ok && Number.isFinite(Number(quote.ltp)) ? Number(quote.ltp) : null) ??
            (Number.isFinite(Number(row.entry)) ? Number(row.entry) : null) ??
            (Number.isFinite(Number(row.entry_price)) ? Number(row.entry_price) : null);

        // spot is best-effort: diagnostics.spot, row.spot, else strike
        const spot =
            (Number.isFinite(Number(row.spot)) ? Number(row.spot) : null) ??
            (Number.isFinite(Number(row.diagnostics?.spot)) ? Number(row.diagnostics.spot) : null) ??
            (Number.isFinite(Number(strike)) ? Number(strike) : null);

        if (!side || !Number.isFinite(Number(strike)) || !Number.isFinite(Number(premium))) return null;

        const { lo, hi } = buildRange({ spot, strike });
        const steps = 80;
        const step = (hi - lo) / steps;

        const data = [];
        for (let i = 0; i <= steps; i++) {
            const S = lo + i * step;
            const pnl = payoffPerUnit({ side, strike, premium }, S);
            data.push({ S: Math.round(S), pnl: pnl == null ? 0 : Number(pnl) });
        }

        const breakeven =
            String(side).toUpperCase() === "CE" ? Number(strike) + Number(premium) : Number(strike) - Number(premium);

        return { side, strike: Number(strike), premium: Number(premium), spot, breakeven, data };
    }, [row, quote]);

    if (!open || !row) return null;

    return (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4" onMouseDown={onClose}>
            <div
                className="w-full max-w-3xl bg-white rounded-2xl shadow-xl border border-slate-100"
                onMouseDown={(e) => e.stopPropagation()}
            >
                <div className="p-5 border-b border-slate-100 flex items-start justify-between gap-4">
                    <div>
                        <div className="text-lg font-semibold text-slate-900">Payoff curve (Expiry)</div>
                        <div className="text-sm text-slate-500 mt-1">
                            {row.symbol} — {row.strike} {row.side} ({row.expiry})
                        </div>
                    </div>

                    <button
                        onClick={onClose}
                        className="px-3 py-1.5 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50"
                    >
                        Close
                    </button>
                </div>

                <div className="p-5 space-y-4">
                    {!payload ? (
                        <div className="text-slate-500">Not enough data to simulate payoff (need side/strike + premium).</div>
                    ) : (
                        <>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                                <div className="rounded-xl border border-slate-100 p-3">
                                    <div className="text-slate-500">Premium</div>
                                    <div className="font-semibold text-slate-900">{fmt2(payload.premium)}</div>
                                </div>
                                <div className="rounded-xl border border-slate-100 p-3">
                                    <div className="text-slate-500">Strike</div>
                                    <div className="font-semibold text-slate-900">{fmt2(payload.strike)}</div>
                                </div>
                                <div className="rounded-xl border border-slate-100 p-3">
                                    <div className="text-slate-500">Breakeven</div>
                                    <div className="font-semibold text-slate-900">{fmt2(payload.breakeven)}</div>
                                </div>
                                <div className="rounded-xl border border-slate-100 p-3">
                                    <div className="text-slate-500">Spot (ref)</div>
                                    <div className="font-semibold text-slate-900">{fmt2(payload.spot)}</div>
                                </div>
                            </div>

                            <div className="h-[360px] w-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={payload.data}>
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis dataKey="S" tick={{ fontSize: 12 }} />
                                        <YAxis tick={{ fontSize: 12 }} />
                                        <Tooltip
                                            formatter={(v) => [fmt2(v), "PnL"]}
                                            labelFormatter={(l) => `Underlying: ${l}`}
                                        />
                                        <ReferenceLine y={0} strokeDasharray="4 4" />
                                        <ReferenceLine x={payload.breakeven} strokeDasharray="4 4" />
                                        <Line type="monotone" dataKey="pnl" dot={false} strokeWidth={2} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>

                            <div className="text-xs text-slate-500">
                                This is a **per-unit expiry payoff** (does not include intraday theta/IV). Premium uses live LTP if
                                available, else entry.
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
