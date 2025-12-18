import React, { useEffect, useMemo, useState } from "react";
import Card from "../components/Card.jsx";
import Badge from "../components/Badge.jsx";
import { useLiveOptionQuotes } from "../hooks/useLiveOptionQuotes.js";

// Helper functions copied and adapted
function fmt(x) {
    if (x === null || x === undefined || x === "") return "—";
    const n = Number(x);
    if (Number.isFinite(n)) return n.toFixed(2).replace(/\.00$/, "");
    return String(x);
}

function guessOptionSymbol(r) {
    if (!r?.symbol || !r?.strike || !r?.side || !r?.expiry) return null;
    let expStr = String(r.expiry).trim().toUpperCase();
    try {
        const parts = expStr.split("-");
        if (parts.length === 3) {
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

function Table({ rows, quotes }) {
    return (
        <div className="overflow-x-auto border border-slate-100 rounded-2xl">
            <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                    <tr>
                        <th className="text-left px-4 py-3">Symbol</th>
                        <th className="text-left px-4 py-3">Analyst Verdict</th>
                        <th className="text-left px-4 py-3">Side</th>
                        <th className="text-left px-4 py-3">Analysis Summary</th>
                        <th className="text-left px-4 py-3">Adj. Conf</th>
                        <th className="text-left px-4 py-3">LTP</th>
                        <th className="text-left px-4 py-3">Entry</th>
                        <th className="text-left px-4 py-3">Targets</th>
                        <th className="text-left px-4 py-3">SL</th>
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row, i) => {
                        // row is AnalystRecommendation { symbol, final_verdict, analysis_summary, analyst_confidence, reco: OptionReco }
                        const r = row.reco;
                        const optSym = guessOptionSymbol(r);
                        const q = optSym ? quotes?.[optSym] : null;

                        const ltpCell = (() => {
                            if (optSym) {
                                if (!q) return "—";
                                if (q.ok && Number.isFinite(Number(q.ltp))) return fmt(q.ltp);
                                return "NF";
                            }
                            return "—";
                        })();

                        // Verdict styling
                        const verdict = row.final_verdict;
                        let verdictClass = "bg-slate-100 text-slate-700";
                        if (verdict === "STRONG_BUY") verdictClass = "bg-emerald-100 text-emerald-800 font-bold";
                        else if (verdict === "BUY") verdictClass = "bg-green-50 text-green-700";
                        else if (verdict === "WATCH") verdictClass = "bg-amber-50 text-amber-700";
                        else if (verdict === "AVOID") verdictClass = "bg-rose-50 text-rose-700";

                        const targets = r.targets || [];
                        const t1 = targets[0]?.premium ?? targets[0]?.price ?? r.t1_premium;
                        const t2 = targets[1]?.premium ?? targets[1]?.price ?? r.t2_premium;

                        return (
                            <tr key={i} className="border-t hover:bg-slate-50/60">
                                <td className="px-4 py-3 font-medium text-slate-900">{row.symbol}</td>
                                <td className="px-4 py-3">
                                    <span className={`text-xs px-2 py-1 rounded-md ${verdictClass}`}>
                                        {verdict}
                                    </span>
                                </td>
                                <td className="px-4 py-3 text-slate-700">
                                    {r.side} {fmt(r.strike)} ({r.expiry})
                                </td>
                                <td className="px-4 py-3 text-slate-600 max-w-md">
                                    {row.analysis_summary}
                                </td>
                                <td className="px-4 py-3 font-semibold text-slate-700">
                                    {Math.round(row.analyst_confidence * 100)}%
                                </td>
                                <td className="px-4 py-3 font-mono text-slate-700">{ltpCell}</td>
                                <td className="px-4 py-3 text-slate-700">{fmt(r.entry_price)}</td>
                                <td className="px-4 py-3 text-emerald-700">
                                    {fmt(t1)} / {fmt(t2)}
                                </td>
                                <td className="px-4 py-3 text-rose-700">{fmt(r.sl_premium)}</td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

export default function OptionsAnalyst() {
    const [asOf, setAsOf] = useState("");
    const [dates, setDates] = useState([]);
    const [latest, setLatest] = useState("");
    const [data, setData] = useState(null);

    // Initial load: fetch dates
    useEffect(() => {
        fetch("/api/options/analyst/dates")
            .then(r => r.json())
            .then(d => {
                setDates(d.dates || []);
                setLatest(d.latest_as_of || "");
                if (d.latest_as_of) setAsOf(d.latest_as_of);
            })
            .catch(() => { });
    }, []);

    // Fetch report on date change
    useEffect(() => {
        if (!asOf) return;
        fetch(`/api/options/analyst/${asOf}`)
            .then(r => r.json())
            .then(setData)
            .catch(() => setData(null));
    }, [asOf]);

    // Data processing
    const rows = useMemo(() => {
        if (!data || !data.analyst_recos) return [];
        // Sort: STRONG_BUY > BUY > WATCH ... then confidence
        const vScore = { "STRONG_BUY": 3, "BUY": 2, "WATCH": 1, "AVOID": 0 };
        return [...data.analyst_recos].sort((a, b) => {
            const sa = vScore[a.final_verdict] || 0;
            const sb = vScore[b.final_verdict] || 0;
            if (sa !== sb) return sb - sa;
            return b.analyst_confidence - a.analyst_confidence;
        });
    }, [data]);

    // Live Quotes setup
    const optionSymbols = useMemo(() => {
        return rows.map(row => guessOptionSymbol(row.reco));
    }, [rows]);

    // asOf is needed for backend to know which folder to look in for ltp csv
    const { quotes } = useLiveOptionQuotes(optionSymbols, { intervalMs: 15000, asOf });

    return (
        <div className="space-y-6">
            <div className="flex items-end justify-between gap-4 flex-wrap">
                <div>
                    <div className="text-3xl font-bold text-slate-900">Analyst Recommendations</div>
                    <div className="text-slate-500 mt-2">
                        Deep-dive analysis combining technicals, market context, and risk models.
                    </div>
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
                title="Analyst Coverage"
                subtitle="High-probability setups filtered by the Analyst Layer"
                right={
                    <span className="text-xs font-semibold px-2 py-1 rounded bg-slate-100 text-slate-700">
                        {rows.length}
                    </span>
                }
            >
                {rows.length ? (
                    <Table rows={rows} quotes={quotes} />
                ) : (
                    <div className="text-slate-400 p-4">No analyst recommendations available for this date.</div>
                )}
            </Card>
        </div>
    );
}
