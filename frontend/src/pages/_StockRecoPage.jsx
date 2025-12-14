import React, { useEffect, useMemo, useState } from "react";
import Card from "../components/Card.jsx";
import Badge from "../components/Badge.jsx";

function fmt(x) {
    if (x === null || x === undefined || x === "") return "—";
    const n = Number(x);
    if (Number.isFinite(n)) return n.toFixed(3).replace(/\.000$/, "");
    return String(x);
}

function small(x) {
    if (x === null || x === undefined) return "—";
    const n = Number(x);
    if (Number.isFinite(n)) return n.toFixed(2);
    return String(x);
}

function getLabel(x) {
    if (x == null) return "—";
    if (typeof x === "string") return x;
    if (typeof x === "object") return x.ticker || x.symbol || x.name || "—";
    return String(x);
}

function getConf(x) {
    if (!x || typeof x !== "object") return null;

    // Prefer p_up as "confidence"
    if (Number.isFinite(Number(x.p_up))) return Number(x.p_up);

    // Next: explicit confidence
    if (Number.isFinite(Number(x.confidence))) return Number(x.confidence);

    // Fallback: options_score (still 0..1 usually)
    if (Number.isFinite(Number(x.options_score))) return Number(x.options_score);

    return null;
}

function fmtPct(v) {
    if (v == null) return null;
    const n = Number(v);
    if (!Number.isFinite(n)) return null;
    // if already looks like 0..1, convert to %
    const pct = n <= 1.0 ? n * 100 : n;
    return `${Math.round(pct)}%`;
}

function Table({ rows }) {
    return (
        <div className="overflow-x-auto border border-slate-100 rounded-2xl">
            <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                    <tr>
                        <th className="text-left px-4 py-3">Rank</th>
                        <th className="text-left px-4 py-3">Ticker</th>
                        <th className="text-left px-4 py-3">p_up</th>
                        <th className="text-left px-4 py-3">p_expand</th>
                        <th className="text-left px-4 py-3">options_score</th>
                        <th className="text-left px-4 py-3">RS(5d)</th>
                        <th className="text-left px-4 py-3">RSI</th>
                        <th className="text-left px-4 py-3">ADX</th>
                        <th className="text-left px-4 py-3">ATR%</th>
                    </tr>
                </thead>
                <tbody>
                    {rows.map((r) => {
                        const s = r.signals || {};
                        return (
                            <tr key={r.ticker} className="border-t hover:bg-slate-50/60">
                                <td className="px-4 py-3 text-slate-700">{r.rank}</td>
                                <td className="px-4 py-3 font-medium text-slate-900">{r.ticker}</td>
                                <td className="px-4 py-3 text-slate-700">{small(r.p_up)}</td>
                                <td className="px-4 py-3 text-slate-700">{small(r.p_expand)}</td>
                                <td className="px-4 py-3 text-slate-700">{small(r.options_score ?? r.score)}</td>
                                <td className="px-4 py-3 text-slate-700">{small(s.rel_strength_5d)}</td>
                                <td className="px-4 py-3 text-slate-700">{small(s.rsi_14)}</td>
                                <td className="px-4 py-3 text-slate-700">{small(s.adx_14)}</td>
                                <td className="px-4 py-3 text-slate-700">{small(s.atr_pct)}</td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

function ListBox({ title, items, emptyText }) {
    return (
        <Card title={title} subtitle="">
            {items?.length ? (
                <ul className="space-y-2 text-sm text-slate-700">
                    {items.map((x, i) => (
                        <li key={i} className="bg-slate-50 border border-slate-100 rounded-xl p-3">
                            {x}
                        </li>
                    ))}
                </ul>
            ) : (
                <div className="text-slate-400">{emptyText}</div>
            )}
        </Card>
    );
}

export default function StockRecoPage({ mode }) {
    const [targetDate, setTargetDate] = useState("");
    const [dates, setDates] = useState([]);
    const [report, setReport] = useState(null);

    useEffect(() => {
        fetch("/api/stockreco/dates")
            .then((r) => r.json())
            .then((d) => {
                const ds = d.dates || [];
                setDates(ds);
                if (!targetDate && d.latest_target_date) setTargetDate(d.latest_target_date);
            })
            .catch(() => { });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (!targetDate) return;
        fetch(`/api/stockreco/${encodeURIComponent(targetDate)}/${encodeURIComponent(mode)}`)
            .then((r) => r.json())
            .then((d) => setReport(d.report || null))
            .catch(() => setReport(null));
    }, [targetDate, mode]);

    const proposerTop = report?.proposer?.top10 || [];
    const approved = report?.reviewer?.approved || [];
    const rejected = report?.reviewer?.rejected || [];
    const notes = report?.analyst?.regime_notes || [];

    const finalPicks = report?.analyst?.final || [];

    const title = mode === "strict" ? "Strict Recommendations" : "Aggressive Recommendations";

    const subtitle = useMemo(() => {
        const asOf = report?.as_of ? `As-of EOD used: ${report.as_of}` : "";
        const tgt = report?.target_date ? `Target date: ${report.target_date}` : "";
        return [tgt, asOf].filter(Boolean).join(" • ");
    }, [report]);

    return (
        <div className="space-y-6">
            <div className="flex items-end justify-between gap-4 flex-wrap">
                <div>
                    <div className="text-3xl font-bold text-slate-900">{title}</div>
                    <div className="text-slate-500 mt-2">{subtitle || "Stock momentum report (EOD-based)"}</div>
                </div>

                <div className="flex items-center gap-3">
                    <label className="text-sm text-slate-600">Target date</label>
                    <select
                        value={targetDate}
                        onChange={(e) => setTargetDate(e.target.value)}
                        className="border border-slate-200 rounded-xl px-4 py-2 bg-white min-w-[240px]"
                    >
                        {dates.map((d) => (
                            <option key={d} value={d}>
                                {d}
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            <Card
                title="Top 10 by options suitability"
                subtitle="Proposed stock list (for next session; confirm intraday)"
                right={
                    <span className="text-xs font-semibold px-2 py-1 rounded bg-slate-100 text-slate-700">
                        {proposerTop.length}
                    </span>
                }
            >
                {proposerTop.length ? <Table rows={proposerTop} /> : <div className="text-slate-400">No rows.</div>}
            </Card>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                <Card
                    title="Reviewer — Approved"
                    subtitle="Stocks that passed reviewer filters"
                    right={<span className="text-xs font-semibold px-2 py-1 rounded bg-slate-100 text-slate-700">{approved.length}</span>}
                >
                    {approved.length ? (
                        <ul className="space-y-2 text-sm text-slate-700">
                            {approved.map((x, i) => {
                                const label = getLabel(x);
                                const conf = fmtPct(getConf(x));

                                return (
                                    <li key={i} className="bg-emerald-50 border border-emerald-100 rounded-xl p-3">
                                        <div className="flex items-start justify-between gap-3">
                                            <div className="font-medium text-slate-900">{label}</div>
                                            {conf ? (
                                                <span className="text-xs font-semibold px-2 py-1 rounded bg-white/70 border border-emerald-200 text-emerald-800">
                                                    {conf}
                                                </span>
                                            ) : null}
                                        </div>

                                        {x && typeof x === "object" && x.reason ? (
                                            <div className="text-slate-600 mt-1">{x.reason}</div>
                                        ) : null}
                                    </li>
                                );
                            })}
                        </ul>
                    ) : (
                        <div className="text-slate-400">No approved picks.</div>
                    )}

                </Card>

                <Card
                    title="Reviewer — Rejected"
                    subtitle="Stocks that failed reviewer filters"
                    right={<span className="text-xs font-semibold px-2 py-1 rounded bg-slate-100 text-slate-700">{rejected.length}</span>}
                >
                    {rejected.length ? (
                        <ul className="space-y-2 text-sm text-slate-700">
                            {rejected.map((x, i) => {
                                const label = getLabel(x);
                                const conf = fmtPct(getConf(x));

                                return (
                                    <li key={i} className="bg-rose-50 border border-rose-100 rounded-xl p-3">
                                        <div className="flex items-start justify-between gap-3">
                                            <div className="font-medium text-slate-900">{label}</div>
                                            {conf ? (
                                                <span className="text-xs font-semibold px-2 py-1 rounded bg-white/70 border border-rose-200 text-rose-800">
                                                    {conf}
                                                </span>
                                            ) : null}
                                        </div>

                                        {x && typeof x === "object" && x.reason ? (
                                            <div className="text-slate-600 mt-1">{x.reason}</div>
                                        ) : null}
                                    </li>
                                );
                            })}
                        </ul>
                    ) : (
                        <div className="text-slate-400">No rejected picks.</div>
                    )}

                </Card>
            </div>

            <ListBox title="Regime notes" items={notes} emptyText="No regime notes." />

            <Card
                title="Analyst — Final picks"
                subtitle="Final actionable list (could be empty on NO-TRADE days)"
                right={<Badge action={finalPicks.length ? "BUY" : "HOLD"} />}
            >
                {finalPicks.length ? (
                    <ul className="space-y-2 text-sm text-slate-700">
                        {finalPicks.map((x, i) => (
                            <li key={i} className="bg-slate-50 border border-slate-100 rounded-xl p-3">
                                {typeof x === "string" ? x : JSON.stringify(x)}
                            </li>
                        ))}
                    </ul>
                ) : (
                    <div className="text-slate-400">
                        NO-TRADE: No high-conviction options trades for the next session (per rules).
                    </div>
                )}
            </Card>
        </div>
    );
}
