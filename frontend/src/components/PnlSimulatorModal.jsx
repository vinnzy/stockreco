import React, { useMemo } from "react";

const fmt = (x) =>
    x === null || x === undefined || Number.isNaN(x) ? "—" : `₹${Number(x).toFixed(2)}`;

export default function PnlSimulatorModal({ open, onClose, row, quote }) {
    const table = useMemo(() => {
        if (!row) return [];

        const spot = Number(row.spot || row.underlying_ltp || row.underlyingLtp);
        const entry = Number(row.entry_price);
        const p0 = Number((quote?.ok ? quote.ltp : row.ltp) || 0);

        const delta = Number((quote?.ok ? quote.delta : row.delta) || 0);
        const gamma = Number((quote?.ok ? quote.gamma : row.diagnostics?.gamma) || 0);

        if (!spot || !entry || !p0) return [];

        // -2% .. +2% underlying range (tweak if you want wider)
        const steps = [-0.02, -0.015, -0.01, -0.005, 0, 0.005, 0.01, 0.015, 0.02];

        return steps.map((pct) => {
            const S = spot * (1 + pct);
            const dS = S - spot;

            // fast approximation using Δ and Γ
            const priceEst = p0 + delta * dS + 0.5 * gamma * dS * dS;

            const pnl = priceEst - entry;
            const pnlPct = (pnl / entry) * 100;

            return { pct, S, priceEst, pnl, pnlPct };
        });
    }, [row, quote]);

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="absolute inset-0 bg-black/40" onClick={onClose} />
            <div className="relative w-[920px] max-w-[95vw] rounded-2xl bg-white shadow-xl p-5">
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <div className="text-lg font-semibold">PnL Simulator</div>
                        <div className="text-sm text-slate-600">
                            {row.symbol} — {row.side} {row.strike} {row.expiry ? `(${row.expiry})` : ""}
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="rounded-lg px-3 py-1.5 text-sm bg-slate-100 hover:bg-slate-200"
                    >
                        Close
                    </button>
                </div>

                <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
                    <div className="rounded-xl bg-slate-50 p-3">
                        <div className="text-slate-500">Entry</div>
                        <div className="font-semibold">{fmt(row.entry_price)}</div>
                    </div>
                    <div className="rounded-xl bg-slate-50 p-3">
                        <div className="text-slate-500">Live LTP</div>
                        <div className="font-semibold">{fmt(quote?.ok ? quote.ltp : row.ltp)}</div>
                    </div>
                    <div className="rounded-xl bg-slate-50 p-3">
                        <div className="text-slate-500">Stop Loss</div>
                        <div className="font-semibold text-rose-700">{fmt(row.sl_premium)}</div>
                    </div>
                </div>

                <div className="mt-4 overflow-auto rounded-xl border border-slate-100">
                    <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-slate-600">
                            <tr>
                                <th className="px-3 py-2 text-left">Move</th>
                                <th className="px-3 py-2 text-left">Underlying</th>
                                <th className="px-3 py-2 text-left">Est. Option</th>
                                <th className="px-3 py-2 text-left">PnL</th>
                                <th className="px-3 py-2 text-left">PnL %</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table.map((r, i) => {
                                const c = r.pnl >= 0 ? "text-emerald-700" : "text-rose-700";
                                return (
                                    <tr key={i} className="border-t">
                                        <td className="px-3 py-2">{(r.pct * 100).toFixed(1)}%</td>
                                        <td className="px-3 py-2">{fmt(r.S)}</td>
                                        <td className="px-3 py-2">{fmt(r.priceEst)}</td>
                                        <td className={`px-3 py-2 font-medium ${c}`}>{fmt(r.pnl)}</td>
                                        <td className={`px-3 py-2 font-medium ${c}`}>{r.pnlPct.toFixed(1)}%</td>
                                    </tr>
                                );
                            })}
                            {table.length === 0 && (
                                <tr>
                                    <td className="px-3 py-3 text-slate-400" colSpan={5}>
                                        Not enough data (need spot + entry + ltp, plus delta/gamma if available).
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>

                <div className="mt-3 text-xs text-slate-500">
                    Uses fast Δ/Γ approximation (good for intuition; not full re-pricing).
                </div>
            </div>
        </div>
    );
}
