import React, { useEffect, useState, useMemo } from "react";
import Badge from "../components/Badge.jsx";
import { useLiveOptionQuotes } from "../hooks/useLiveOptionQuotes.js";

import PnlSimulatorModal from "../components/PnlSimulatorModal.jsx";
import Card from "../components/Card.jsx";

function fmt(x) {
    if (x === null || x === undefined || x === "") return "—";
    const n = Number(x);
    if (Number.isFinite(n)) return n.toFixed(2).replace(/\.00$/, "");
    return String(x);
}

function guessOptionSymbol(r) {
    if (!r?.symbol || !r?.strike || !r?.side || !r?.expiry) return null;

    // Parse expiry date - could be "06-JAN-2026" or "2026-01-06"
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
            // ISO "2026-01-06" -> "06JAN26"
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

    // IMPORTANT: strip ".NS" so it matches op*.csv tradingsymbol keys
    const sym = String(r.symbol).toUpperCase().replace(".NS", "");

    const strike = String(Math.round(Number(r.strike)));
    const side = String(r.side).toUpperCase();

    // NSE format: SYMBOL + DDMMMYY + STRIKE + CE/PE
    // e.g., ADANIENT24FEB262280CE
    return `${sym}${expStr}${strike}${side}`;
}

function getLtp(r) {
    return r?.ltp ?? r?.LTP ?? null;
}
function getEntry(r) {
    return r?.entry_price ?? r?.entry ?? r?.Entry ?? null;
}
function getSL(r) {
    return r?.sl_premium ?? r?.sl ?? r?.SL ?? null;
}
function getT1(r) {
    if (Array.isArray(r?.targets) && r.targets[0]?.premium != null) return r.targets[0].premium;
    return r?.t1_premium ?? r?.t1 ?? r?.T1 ?? null;
}
function getT2(r) {
    if (Array.isArray(r?.targets) && r.targets[1]?.premium != null) return r.targets[1].premium;
    return r?.t2_premium ?? r?.t2 ?? r?.T2 ?? null;
}

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
                        <th className="text-left px-4 py-3">Conf</th>
                    </tr>
                </thead>

                <tbody>
                    {rows.map((r) => {
                        const optSymRaw = guessOptionSymbol(r);
                        const optSym = optSymRaw ? String(optSymRaw).trim().toUpperCase().replace(".NS", "") : null;
                        const q = optSym ? quotes?.[optSym] : null;


                        const rowLtp = getLtp(r);
                        const rowEntry = getEntry(r);
                        const rowSl = getSL(r);
                        const rowT1 = getT1(r);
                        const rowT2 = getT2(r);

                        // Check if quote exists and has valid ltp (not NaN)
                        const liveLtp = q && typeof q.ltp === "number" && !isNaN(q.ltp) ? q.ltp : rowLtp;

                        return (
                            <tr
                                key={(r.symbol ?? "") + (r.strike ?? "") + (r.side ?? "") + (r.expiry ?? "")}
                                className="border-t hover:bg-slate-50/60 cursor-pointer"
                                title="Click to open PnL simulator"
                                onClick={() => onRowClick?.(r, q)}
                            >
                                <td className="px-4 py-3 font-medium text-slate-900">{r.symbol}</td>

                                <td className="px-4 py-3">
                                    <Badge action={r.action} />
                                </td>

                                <td className="px-4 py-3 text-slate-700">
                                    {r.side ? `${fmt(r.strike)} ${r.side}${r.expiry ? ` (${r.expiry})` : ""}` : "—"}
                                </td>

                                <td className="px-4 py-3 font-semibold text-slate-900">{fmt(liveLtp)}</td>
                                <td className="px-4 py-3 text-slate-700">{fmt(rowEntry)}</td>
                                <td className="px-4 py-3 text-rose-700">{fmt(rowSl)}</td>
                                <td className="px-4 py-3 text-emerald-700">{fmt(rowT1)}</td>
                                <td className="px-4 py-3 text-emerald-700">{fmt(rowT2)}</td>

                                <td className="px-4 py-3 text-slate-700">
                                    {Math.round((r.confidence || 0) * 100)}%
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

export default function RecoPage({ title, subtitle, pickRows }) {
    const [asOf, setAsOf] = useState("");
    const [dates, setDates] = useState([]);
    const [data, setData] = useState(null);
    const [modalRow, setModalRow] = useState(null);
    const [modalQuote, setModalQuote] = useState(null);

    useEffect(() => {
        fetch("/api/options/dates")
            .then((r) => r.json())
            .then((d) => {
                const ds = d.dates || [];
                setDates(ds);
                if (!asOf && d.latest_as_of) setAsOf(d.latest_as_of);
            })
            .catch(() => { });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (!asOf) return;
        fetch(`/api/options/${encodeURIComponent(asOf)}`)
            .then((r) => r.json())
            .then((d) => setData(d || null))
            .catch(() => setData(null));
    }, [asOf]);

    const rows = useMemo(() => {
        if (!data || !pickRows) return [];
        return pickRows(data) || [];
    }, [data, pickRows]);

    const optionSymbols = useMemo(() => {
        return rows.map((r) => guessOptionSymbol(r)).filter(Boolean);
    }, [rows]);

    const quotes = useLiveOptionQuotes(optionSymbols, { intervalMs: 15000 });


    const handleRowClick = (row, quote) => {
        setModalRow(row);
        // Normalize quote structure for modal (adds 'ok' field if valid)
        if (quote && typeof quote.ltp === "number" && !isNaN(quote.ltp)) {
            setModalQuote({ ...quote, ok: true });
        } else {
            setModalQuote(null);
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex items-end justify-between gap-4 flex-wrap">
                <div>
                    <div className="text-3xl font-bold text-slate-900">{title}</div>
                    {subtitle && <div className="text-slate-500 mt-2">{subtitle}</div>}
                </div>
                <div className="flex items-center gap-3">
                    <label className="text-sm text-slate-600">As-of</label>
                    <select
                        value={asOf}
                        onChange={(e) => setAsOf(e.target.value)}
                        className="border border-slate-200 rounded-xl px-4 py-2 bg-white"
                    >
                        <option value="">Select date...</option>
                        {dates.map((d) => (
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
                    <Table rows={rows} quotes={quotes} onRowClick={handleRowClick} />
                ) : (
                    <div className="text-slate-400">No recommendations available.</div>
                )}
            </Card>

            <PnlSimulatorModal
                open={!!modalRow}
                onClose={() => {
                    setModalRow(null);
                    setModalQuote(null);
                }}
                row={modalRow}
                quote={modalQuote}
            />
        </div>
    );
}
