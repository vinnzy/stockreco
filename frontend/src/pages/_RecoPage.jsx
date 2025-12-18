import React, { useEffect, useMemo, useState } from "react";
import Card from "../components/Card.jsx";
import Badge from "../components/Badge.jsx";
import { useLiveOptionQuotes } from "../hooks/useLiveOptionQuotes.js";

import {
    ResponsiveContainer,
    LineChart,
    Line,
    XAxis,
    YAxis,
    Tooltip,
    CartesianGrid,
    ReferenceLine,
} from "recharts";

/** ---------- helpers ---------- **/

function fmt(x) {
    if (x === null || x === undefined || x === "") return "—";
    const n = Number(x);
    if (Number.isFinite(n)) return n.toFixed(2).replace(/\.00$/, "");
    return String(x);
}

function ymdToNum(s) {
    if (!s) return null;
    const m = String(s).trim().match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return null;
    return Number(m[1] + m[2] + m[3]);
}

function todayYmd() {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
}

function getEntry(r) {
    return r?.entry ?? r?.entry_price ?? null;
}

function getSL(r) {
    return r?.stop_loss ?? r?.sl_premium ?? null;
}

function getSellBy(r) {
    return r?.sell_by ?? r?.diagnostics?.sell_by ?? r?.diagnostics?.sellBy ?? null;
}

function getSpot(r) {
    return r?.spot ?? r?.diagnostics?.spot ?? null;
}

function getAtrPoints(r) {
    return r?.diagnostics?.atr_points ?? r?.diagnostics?.atrPoints ?? null;
}

function getTargetPremium(r, idx /*0|1*/) {
    // supports:
    // - targets: [{underlying,premium}, {underlying,premium}]
    // - targets: {t1_premium, t2_premium}
    // - flattened: t1_premium, t2_premium
    const t = r?.targets;

    if (Array.isArray(t)) {
        const row = t[idx] || null;
        return row?.premium ?? row?.price ?? row?.t1_premium ?? row?.t2_premium ?? null;
    }
    if (t && typeof t === "object") {
        if (idx === 0) return t.t1_premium ?? t[0]?.premium ?? null;
        if (idx === 1) return t.t2_premium ?? t[1]?.premium ?? null;
    }
    return idx === 0 ? (r?.t1_premium ?? null) : (r?.t2_premium ?? null);
}

function guessOptionSymbol(r) {
    if (!r?.symbol || !r?.strike || !r?.side || !r?.expiry) return null;

    let expStr = String(r.expiry).trim().toUpperCase();

    try {
        const parts = expStr.split("-");
        if (parts.length === 3) {
            // "06-JAN-2026" -> "06JAN26"
            const day = parts[0].padStart(2, "0");
            const month = parts[1].substring(0, 3);
            const year = parts[2].substring(2, 4);
            expStr = `${day}${month}${year}`;
        } else {
            const d = new Date(expStr);
            if (isNaN(d.getTime())) return null;

            const day = String(d.getDate()).padStart(2, "0");
            const months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
            const month = months[d.getMonth()];
            const year = String(d.getFullYear()).substring(2, 4);
            expStr = `${day}${month}${year}`;
        }
    } catch {
        return null;
    }

    const sym = String(r.symbol).toUpperCase().replace(".NS", "");
    const strike = String(Math.round(Number(r.strike)));
    const side = String(r.side).toUpperCase();

    return `${sym}${expStr}${strike}${side}`;
}

function guessCommodityKey(r) {
    if (!r?.symbol || !r?.expiry) return null;
    const exp = r.expiry.replace(/-/g, "").slice(2); // 05FEB26
    return `MCXFUT:${r.symbol.toUpperCase()}:${exp}`;
}

function computePayoffSeries({ side, strike, spot, premium, atrPoints }) {
    const K = Number(strike);
    const S0 = Number(spot) || K || 0;
    const prem = Number(premium);

    if (!Number.isFinite(K) || !Number.isFinite(prem) || prem <= 0) return [];

    let low, high;
    const atr = Number(atrPoints);
    if (Number.isFinite(atr) && atr > 0 && Number.isFinite(S0) && S0 > 0) {
        low = Math.max(0, S0 - 2.2 * atr);
        high = S0 + 2.2 * atr;
    } else if (Number.isFinite(S0) && S0 > 0) {
        low = Math.max(0, S0 * 0.9);
        high = S0 * 1.1;
    } else {
        low = Math.max(0, K * 0.9);
        high = K * 1.1;
    }

    const n = 121;
    const step = (high - low) / (n - 1);

    const data = [];
    for (let i = 0; i < n; i++) {
        const S = low + i * step;

        let pnl;
        if (String(side).toUpperCase() === "CE") pnl = Math.max(0, S - K) - prem;
        else pnl = Math.max(0, K - S) - prem;

        data.push({ S: Number(S.toFixed(2)), pnl: Number(pnl.toFixed(2)) });
    }
    return data;
}

function Modal({ open, onClose, title, children }) {
    if (!open) return null;
    return (
        <div className="fixed inset-0 z-50">
            <div className="absolute inset-0 bg-black/40" onClick={onClose} />
            <div className="absolute inset-0 flex items-center justify-center p-4">
                <div className="w-full max-w-4xl rounded-2xl bg-white shadow-xl border border-slate-100">
                    <div className="flex items-start justify-between gap-4 p-5 border-b border-slate-100">
                        <div>
                            <div className="text-lg font-semibold text-slate-900">{title}</div>
                            <div className="text-xs text-slate-500 mt-1">
                                Payoff at expiry (intrinsic − premium). Not an IV/theta model.
                            </div>
                        </div>
                        <button
                            className="px-3 py-1 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50"
                            onClick={onClose}
                        >
                            Close
                        </button>
                    </div>
                    <div className="p-5">{children}</div>
                </div>
            </div>
        </div>
    );
}

/** ---------- table ---------- **/

function Table({ rows, quotes, onRowClick }) {
    return (
        <div className="overflow-x-auto border border-slate-100 rounded-2xl">
            <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                    <tr>
                        <th className="text-left px-4 py-3">Symbol</th>
                        <th className="text-left px-4 py-3">Action</th>
                        <th className="text-left px-4 py-3">Option</th>
                        <th className="text-left px-4 py-3">LTP</th>
                        <th className="text-left px-4 py-3">Entry ≤</th>
                        <th className="text-left px-4 py-3">SL</th>
                        <th className="text-left px-4 py-3">T1</th>
                        <th className="text-left px-4 py-3">T2</th>
                        <th className="text-left px-4 py-3">RR</th>
                        <th className="text-left px-4 py-3">Sell-by</th>
                        <th className="text-left px-4 py-3">Reviewer</th>
                        <th className="text-left px-4 py-3">Conf</th>
                    </tr>
                </thead>

                <tbody>
                    {rows.map((r) => {
                        const optSym = guessOptionSymbol(r);
                        const q = optSym ? quotes?.[optSym] : null;

                        const entry = getEntry(r);
                        const sl = getSL(r);
                        const t1 = getTargetPremium(r, 0);
                        const t2 = getTargetPremium(r, 1);
                        const rr = r.rr_ratio ?? (r.diagnostics?.rr_ratio) ?? null;

                        const sellBy = getSellBy(r);
                        const spot = getSpot(r);

                        const isExpired = !!r.__expired;

                        const ltpCell = (() => {
                            // If we have an option symbol, show option LTP (even for HOLD rows)
                            if (optSym) {
                                if (!q) return "—";
                                if (q.ok && Number.isFinite(Number(q.ltp))) return fmt(q.ltp);
                                // backend can return ok:false, ltp:null for not found
                                return "NF";
                            }

                            // If no option (pure HOLD row), show spot if available (so LTP column not empty)
                            if (Number.isFinite(Number(spot))) return fmt(spot);
                            return "—";
                        })();

                        const isApproved = r.__reviewerApproved === true;
                        const isRejected = r.__reviewerRejected === true;
                        const rejectionReason = r.__rejectionReason || "";

                        // Adjust confidence display for rejected items
                        const displayConfidence = isRejected ? 0 : (r.confidence || 0);

                        return (
                            <tr
                                key={`${r.symbol ?? ""}-${r.strike ?? ""}-${r.side ?? ""}-${r.expiry ?? ""}`}
                                className={[
                                    "border-t",
                                    isExpired ? "bg-slate-50 text-slate-400" : "hover:bg-slate-50/60",
                                    (!isExpired && r.side && r.strike && r.expiry) ? "cursor-pointer" : "",
                                ].join(" ")}
                                title={
                                    isExpired
                                        ? "Auto-invalidated (past sell-by)"
                                        : (r.side && r.strike ? "Click for payoff curve" : "")
                                }
                                onClick={() => {
                                    if (isExpired) return;
                                    if (!r.side || !r.strike) return;
                                    onRowClick?.(r, q);
                                }}
                            >
                                <td className="px-4 py-3 font-medium text-slate-900">
                                    {r.symbol}
                                    {isExpired ? (
                                        <span className="ml-2 text-xs font-semibold px-2 py-0.5 rounded bg-slate-200 text-slate-700">
                                            EXPIRED
                                        </span>
                                    ) : null}
                                </td>

                                <td className="px-4 py-3">
                                    <Badge action={isExpired ? "HOLD" : r.action} />
                                </td>

                                <td className="px-4 py-3 text-slate-700">
                                    {r.side ? `${fmt(r.strike)} ${r.side}${r.expiry ? ` (${r.expiry})` : ""}` : "—"}
                                </td>

                                <td className="px-4 py-3 text-slate-700">{ltpCell}</td>

                                <td className="px-4 py-3 text-slate-700">{fmt(entry)}</td>
                                <td className="px-4 py-3 text-rose-700">{fmt(sl)}</td>
                                <td className="px-4 py-3 text-emerald-700">{fmt(t1)}</td>
                                <td className="px-4 py-3 text-emerald-700">{fmt(t2)}</td>
                                <td className="px-4 py-3 text-slate-600">{fmt(rr)}</td>

                                <td className="px-4 py-3 text-slate-700">{sellBy ?? "—"}</td>

                                <td className="px-4 py-3">
                                    {isApproved ? (
                                        <span className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800">
                                            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                            </svg>
                                            APPROVED
                                        </span>
                                    ) : isRejected ? (
                                        <span
                                            className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-rose-100 text-rose-800 cursor-help"
                                            title={rejectionReason}
                                        >
                                            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                                            </svg>
                                            REJECTED
                                        </span>
                                    ) : (
                                        <span className="text-xs text-slate-400">—</span>
                                    )}
                                </td>

                                <td className="px-4 py-3">
                                    <span className={[
                                        "font-semibold",
                                        isApproved ? "text-emerald-700" : isRejected ? "text-rose-400 line-through" : "text-slate-700"
                                    ].join(" ")}>
                                        {Math.round(displayConfidence * 100)}%
                                    </span>
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}


/** ---------- page ---------- **/

export default function RecoPage({ title, subtitle, pickRows, apiPrefix = "/api/options" }) {
    const [asOf, setAsOf] = useState("");
    const [dates, setDates] = useState([]);
    const [latest, setLatest] = useState("");
    const [data, setData] = useState(null);

    const [payoffOpen, setPayoffOpen] = useState(false);
    const [payoffRow, setPayoffRow] = useState(null);
    const [payoffQuote, setPayoffQuote] = useState(null);

    useEffect(() => {
        // e.g. /api/options/dates or /api/options/intraday/dates
        const url = `${apiPrefix}/dates`;
        fetch(url)
            .then((r) => r.json())
            .then((d) => {
                setDates(d.dates || []);
                setLatest(d.latest_as_of || "");
                if (!asOf && d.latest_as_of) setAsOf(d.latest_as_of);
            })
            .catch(() => { });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [apiPrefix]);

    useEffect(() => {
        if (!asOf) return;
        // e.g. /api/options/2025-01-01 or /api/options/intraday/2025-01-01
        fetch(`${apiPrefix}/${encodeURIComponent(asOf)}`)
            .then((r) => r.json())
            .then(setData)
            .catch(() => setData(null));
    }, [asOf, apiPrefix]);

    const rowsRaw = useMemo(() => (Array.isArray(data) ? data : pickRows(data)), [data, pickRows]);

    // Build symbols to poll
    const optionSymbols = useMemo(() => {
        return (rowsRaw || []).map((r) =>
            r.instrument === "OPTION"
                ? guessOptionSymbol(r)
                : guessCommodityKey(r)
        )
    }, [rowsRaw]);

    // IMPORTANT: hook returns { quotes, loading }
    // IMPORTANT: pass asOf so backend can read from data/derivatives/<asOf>/
    const { quotes } = useLiveOptionQuotes(optionSymbols, { intervalMs: 15000, asOf });

    // Auto invalidate past sell_by (also checks diagnostics.sell_by)
    const rows = useMemo(() => {
        const today = ymdToNum(asOf || latest || todayYmd()); // use report date as basis

        return (rowsRaw || []).map((r) => {
            const sb = ymdToNum(getSellBy(r));
            const expired = !!(today && sb && today > sb);
            return { ...r, __expired: expired, sell_by: getSellBy(r) ?? r?.sell_by ?? null };
        }).sort((a, b) => {
            // Sort by reviewer status first (approved > no status > rejected)
            const statusA = a.__reviewerApproved ? 2 : a.__reviewerRejected ? 0 : 1;
            const statusB = b.__reviewerApproved ? 2 : b.__reviewerRejected ? 0 : 1;
            if (statusA !== statusB) return statusB - statusA;

            // Then by confidence descending (highest first)
            const confA = Number(a.confidence) || 0;
            const confB = Number(b.confidence) || 0;
            return confB - confA;
        });
    }, [rowsRaw, asOf, latest]);

    const payoffData = useMemo(() => {
        if (!payoffRow) return [];
        const side = payoffRow.side;
        const strike = payoffRow.strike;

        const spot =
            getSpot(payoffRow) ??
            (Array.isArray(payoffRow.targets) ? payoffRow.targets?.[0]?.underlying : null) ??
            payoffRow.strike;

        const premium =
            (payoffQuote && payoffQuote.ok && Number.isFinite(Number(payoffQuote.ltp)) ? Number(payoffQuote.ltp) : null) ??
            getEntry(payoffRow) ??
            null;

        const atrPoints = getAtrPoints(payoffRow);

        return computePayoffSeries({ side, strike, spot, premium, atrPoints });
    }, [payoffRow, payoffQuote]);

    const payoffMeta = useMemo(() => {
        if (!payoffRow) return null;
        const optSym = guessOptionSymbol(payoffRow);

        const spot =
            getSpot(payoffRow) ??
            (Array.isArray(payoffRow.targets) ? payoffRow.targets?.[0]?.underlying : null) ??
            payoffRow.strike;

        const premium =
            (payoffQuote && payoffQuote.ok && Number.isFinite(Number(payoffQuote.ltp)) ? Number(payoffQuote.ltp) : null) ??
            getEntry(payoffRow) ??
            null;

        return {
            optSym,
            spot,
            strike: payoffRow.strike,
            side: payoffRow.side,
            premium,
            sellBy: getSellBy(payoffRow),
            expiry: payoffRow.expiry,
            symbol: payoffRow.symbol,
        };
    }, [payoffRow, payoffQuote]);

    return (
        <div className="space-y-6">
            <div className="flex items-end justify-between gap-4 flex-wrap">
                <div>
                    <div className="text-3xl font-bold text-slate-900">{title}</div>
                    <div className="text-slate-500 mt-2">{subtitle}</div>
                </div>

                <div className="flex items-center gap-3">
                    <label className="text-sm text-slate-600">As-of</label>
                    <select
                        value={asOf}
                        onChange={(e) => setAsOf(e.target.value)}
                        className="border border-slate-200 rounded-xl px-4 py-2 bg-white min-w-[240px]"
                    >
                        {(dates.length ? dates : (latest ? [latest] : [])).map((d) => (
                            <option key={d} value={d}>
                                {d}
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            <Card
                title={title}
                subtitle={subtitle}
                right={
                    <span className="text-xs font-semibold px-2 py-1 rounded bg-slate-100 text-slate-700">
                        {rows.length}
                    </span>
                }
            >
                {rows.length ? (
                    <Table
                        rows={rows}
                        quotes={quotes}
                        onRowClick={(r, q) => {
                            setPayoffRow(r);
                            setPayoffQuote(q || null);
                            setPayoffOpen(true);
                        }}
                    />
                ) : (
                    <div className="text-slate-400">No rows.</div>
                )}
            </Card>

            <Modal
                open={payoffOpen}
                onClose={() => setPayoffOpen(false)}
                title={
                    payoffMeta
                        ? `${payoffMeta.symbol} ${fmt(payoffMeta.strike)} ${payoffMeta.side} (${payoffMeta.expiry})`
                        : "Payoff curve"
                }
            >
                {payoffMeta ? (
                    <div className="space-y-4">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                            <div className="bg-slate-50 border border-slate-100 rounded-xl p-3">
                                <div className="text-slate-500 text-xs">Option</div>
                                <div className="font-medium text-slate-900">{payoffMeta.optSym || "—"}</div>
                            </div>
                            <div className="bg-slate-50 border border-slate-100 rounded-xl p-3">
                                <div className="text-slate-500 text-xs">Spot</div>
                                <div className="font-medium text-slate-900">{fmt(payoffMeta.spot)}</div>
                            </div>
                            <div className="bg-slate-50 border border-slate-100 rounded-xl p-3">
                                <div className="text-slate-500 text-xs">Premium (LTP/Entry)</div>
                                <div className="font-medium text-slate-900">{fmt(payoffMeta.premium)}</div>
                            </div>
                            <div className="bg-slate-50 border border-slate-100 rounded-xl p-3">
                                <div className="text-slate-500 text-xs">Sell-by</div>
                                <div className="font-medium text-slate-900">{payoffMeta.sellBy ?? "—"}</div>
                            </div>
                        </div>

                        <div className="h-[420px] border border-slate-100 rounded-2xl">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={payoffData} margin={{ top: 18, right: 24, bottom: 12, left: 12 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="S" tickFormatter={(v) => String(Math.round(v))} />
                                    <YAxis tickFormatter={(v) => String(Math.round(v))} />
                                    <Tooltip />
                                    <ReferenceLine y={0} strokeDasharray="4 4" />
                                    <Line type="monotone" dataKey="pnl" dot={false} strokeWidth={2} />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>

                        <div className="text-xs text-slate-500">
                            Payoff is expiry intrinsic − premium (no IV/theta). For “price decay towards expiry”, we’ll
                            add a theta/IV decay overlay next.
                        </div>
                    </div>
                ) : (
                    <div className="text-slate-400">No selection.</div>
                )}
            </Modal>
        </div>
    );
}
