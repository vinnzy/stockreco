import React, { useEffect, useState, useMemo } from "react";
import Card from "../components/Card.jsx";

const API_PREFIX = "/api/options/performance";

function fmt(x) {
    if (x === null || x === undefined || x === "") return "—";
    const n = Number(x);
    if (Number.isFinite(n)) return n.toFixed(2).replace(/\.00$/, "");
    return String(x);
}

function OutcomeBadge({ outcome }) {
    if (!outcome) return <span className="text-slate-400">—</span>;
    outcome = outcome.toUpperCase();

    let color = "bg-slate-100 text-slate-700";
    if (outcome.includes("SUCCESS")) color = "bg-emerald-100 text-emerald-800";
    if (outcome.includes("FAILURE")) color = "bg-rose-100 text-rose-800";
    if (outcome.includes("HOLD")) color = "bg-blue-100 text-blue-800";
    if (outcome.includes("PENDING")) color = "bg-yellow-100 text-yellow-800";

    return (
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${color}`}>
            {outcome}
        </span>
    );
}

function PerformanceTable({ rows }) {
    return (
        <div className="h-full flex flex-col">
            <div className="overflow-auto border border-slate-100 rounded-2xl flex-1">
                <table className="min-w-full text-sm relative">
                    <thead className="bg-slate-50 text-slate-600 sticky top-0 z-10 shadow-sm">
                        <tr>
                            <th className="text-left px-4 py-3 bg-slate-50">Symbol</th>
                            <th className="text-left px-4 py-3 bg-slate-50">Option</th>
                            <th className="text-left px-4 py-3 bg-slate-50">Expiry</th>
                            <th className="text-left px-4 py-3 bg-slate-50">Entry</th>
                            <th className="text-left px-4 py-3 bg-slate-50">Target 1</th>
                            <th className="text-left px-4 py-3 bg-slate-50">Target 2</th>
                            <th className="text-left px-4 py-3 bg-slate-50">SL</th>
                            <th className="text-left px-4 py-3 bg-slate-50">Close</th>
                            <th className="text-left px-4 py-3 bg-slate-50">High</th>
                            <th className="text-left px-4 py-3 bg-slate-50">Low</th>
                            <th className="text-left px-4 py-3 bg-slate-50">Outcome</th>
                            <th className="text-left px-4 py-3 bg-slate-50">T1 Hit</th>
                            <th className="text-left px-4 py-3 bg-slate-50">T2 Hit</th>
                            <th className="text-left px-4 py-3 bg-slate-50">Failed On</th>
                            <th className="text-left px-4 py-3 bg-slate-50">Reviewer</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white">
                        {rows.map((r, i) => (
                            <tr key={i} className="hover:bg-slate-50/50">
                                <td className="px-4 py-3 font-medium text-slate-900">{r.symbol}</td>
                                <td className="px-4 py-3">
                                    {fmt(r.strike)} {r.side}
                                </td>
                                <td className="px-4 py-3 text-slate-500">{r.expiry}</td>
                                <td className="px-4 py-3 font-medium">{fmt(r.entry)}</td>
                                <td className="px-4 py-3 text-emerald-600">{fmt(r.target1)}</td>
                                <td className="px-4 py-3 text-emerald-600">{fmt(r.target2)}</td>
                                <td className="px-4 py-3 text-rose-600">{fmt(r.sl)}</td>
                                <td className="px-4 py-3 font-medium text-slate-700">{fmt(r.day_close)}</td>
                                <td className="px-4 py-3 font-medium">{fmt(r.day_high)}</td>
                                <td className="px-4 py-3 font-medium">{fmt(r.day_low)}</td>
                                <td className="px-4 py-3">
                                    <OutcomeBadge outcome={r.outcome} />
                                </td>
                                <td className="px-4 py-3 text-xs text-slate-500">
                                    {r.t1_hit_date || "—"}
                                </td>
                                <td className="px-4 py-3 text-xs text-slate-500">
                                    {r.t2_hit_date || "—"}
                                </td>
                                <td className="px-4 py-3 text-xs text-rose-500">
                                    {r.failure_date || "—"}
                                </td>
                                <td className="px-4 py-3">
                                    {r.reviewer_decision === "APPROVED" ? (
                                        <span className="text-emerald-700 font-medium text-xs">PASSED</span>
                                    ) : r.reviewer_decision === "REJECTED" ? (
                                        <span className="text-rose-700 font-medium text-xs border-b border-dotted border-rose-300 cursor-help" title={r.reviewer_reason}>
                                            REJECTED
                                        </span>
                                    ) : (
                                        <span className="text-slate-400 text-xs">UNKNOWN</span>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function calculateSuccessRate(rows) {
    if (!rows || rows.length === 0) return { rate: 0, count: 0, total: 0 };

    // Filter for decisive outcomes
    const decisive = rows.filter(r => {
        const out = String(r.outcome).toUpperCase();
        return out.includes("SUCCESS") || out.includes("FAILURE");
    });

    const successes = decisive.filter(r => String(r.outcome).toUpperCase().includes("SUCCESS"));

    if (decisive.length === 0) return { rate: 0, count: 0, total: 0 };

    return {
        rate: Math.round((successes.length / decisive.length) * 100),
        count: successes.length,
        total: decisive.length
    };
}

export default function OptionsPerformance() {
    const [asOf, setAsOf] = useState("");
    const [dates, setDates] = useState([]);
    const [latest, setLatest] = useState("");
    const [data, setData] = useState(null);

    useEffect(() => {
        fetch(`${API_PREFIX}/dates`)
            .then((r) => r.json())
            .then((d) => {
                setDates(d.dates || []);
                setLatest(d.latest_as_of || "");
                if (!asOf && d.latest_as_of) setAsOf(d.latest_as_of);
            })
            .catch(() => { });
    }, []);

    useEffect(() => {
        if (!asOf) return;
        fetch(`${API_PREFIX}/${encodeURIComponent(asOf)}`)
            .then((r) => r.json())
            .then(setData)
            .catch(() => setData(null));
    }, [asOf]);

    const rows = useMemo(() => {
        if (!data?.results) return [];

        return [...data.results].sort((a, b) => {
            // Sort by reviewer status: APPROVED (2) > UNKNOWN (1) > REJECTED (0)
            const getScore = (decision) => {
                if (decision === "APPROVED") return 2;
                if (decision === "REJECTED") return 0;
                return 1;
            };

            const scoreA = getScore(a.reviewer_decision);
            const scoreB = getScore(b.reviewer_decision);

            if (scoreA !== scoreB) return scoreB - scoreA;

            // Then by confidence descending
            const confA = Number(a.reco_confidence) || 0;
            const confB = Number(b.reco_confidence) || 0;
            return confB - confA;
        });
    }, [data]);

    const stats = useMemo(() => {
        if (!data?.results) return null;

        // Overall Stats for Rate Cards
        const overall = calculateSuccessRate(rows);

        // Top Picks Stats (High Confidence >= 70%) for Rate Cards
        const highConfRows = rows.filter(r => (Number(r.reco_confidence) || 0) >= 0.70);
        highConfRows.sort((a, b) => (Number(b.reco_confidence) || 0) - (Number(a.reco_confidence) || 0));

        const topPicksSource = highConfRows.slice(0, 15);
        const topPicks = calculateSuccessRate(topPicksSource);

        // Raw Counts for Original Cards
        const total = data.results.length;
        const success = data.results.filter(r => String(r.outcome).includes("SUCCESS")).length;
        const fail = data.results.filter(r => String(r.outcome).includes("FAILURE")).length;
        const hold = data.results.filter(r => String(r.outcome).includes("HOLD") || String(r.outcome).includes("PENDING")).length;

        return { overall, topPicks, counts: { total, success, fail, hold } };
    }, [data, rows]);

    return (
        <div className="flex flex-col h-[calc(100vh-4rem)] space-y-4">
            {/* Header Section - Fixed */}
            <div className="flex-none space-y-4">
                <div className="flex items-end justify-between gap-4 flex-wrap">
                    <div>
                        <div className="text-3xl font-bold text-slate-900">Options Performance</div>
                        <div className="text-slate-500 mt-1 text-sm">
                            Comparing recommendations against actual outcomes
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <label className="text-sm text-slate-600">Date</label>
                        <select
                            value={asOf}
                            onChange={(e) => setAsOf(e.target.value)}
                            className="border border-slate-200 rounded-xl px-4 py-2 bg-white min-w-[200px] text-sm"
                        >
                            {(dates.length ? dates : (latest ? [latest] : [])).map((d) => (
                                <option key={d} value={d}>
                                    {d}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                {/* All Summary Cards */}
                {rows.length > 0 && stats && (
                    <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
                        {/* New Rate Cards (First 2 Slots) */}
                        <div className="col-span-1 lg:col-span-1 bg-white p-3 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between">
                            <div>
                                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Overall Rate</div>
                                <div className="text-[10px] text-slate-400">Success%</div>
                            </div>
                            <div className={`text-2xl font-bold ${stats.overall.rate >= 50 ? 'text-emerald-600' : 'text-slate-700'}`}>
                                {stats.overall.rate}%
                            </div>
                        </div>

                        <div className="col-span-1 lg:col-span-1 bg-gradient-to-br from-indigo-50 to-white p-3 rounded-2xl border border-indigo-100 shadow-sm flex flex-col justify-between">
                            <div>
                                <div className="text-xs font-semibold text-indigo-900 uppercase tracking-wider">Top Picks Rate</div>
                                <div className="text-[10px] text-indigo-400">Top 15 w/ Conf ≥ 70%</div>
                            </div>
                            <div className={`text-2xl font-bold ${stats.topPicks.rate >= 70 ? 'text-indigo-600' : 'text-slate-700'}`}>
                                {stats.topPicks.rate}%
                            </div>
                        </div>

                        {/* Original Count Cards (Next 4 Slots) */}
                        <div className="col-span-1 lg:col-span-1 bg-white p-3 rounded-2xl border border-slate-100">
                            <div className="text-xs text-slate-500">Total Recos</div>
                            <div className="text-xl font-bold text-slate-900">{stats.counts.total}</div>
                        </div>
                        <div className="col-span-1 lg:col-span-1 bg-emerald-50 p-3 rounded-2xl border border-emerald-100">
                            <div className="text-xs text-emerald-700">Success</div>
                            <div className="text-xl font-bold text-emerald-900">{stats.counts.success}</div>
                        </div>
                        <div className="col-span-1 lg:col-span-1 bg-rose-50 p-3 rounded-2xl border border-rose-100">
                            <div className="text-xs text-rose-700">Failure</div>
                            <div className="text-xl font-bold text-rose-900">{stats.counts.fail}</div>
                        </div>
                        <div className="col-span-1 lg:col-span-1 bg-blue-50 p-3 rounded-2xl border border-blue-100">
                            <div className="text-xs text-blue-700">Hold</div>
                            <div className="text-xl font-bold text-blue-900">{stats.counts.hold}</div>
                        </div>
                    </div>
                )}
            </div>

            {/* Table Section - Flexible & Scrollable */}
            <div className="flex-1 min-h-0">
                <Card
                    title={`Performance Data`}
                    subtitle={`Last Updated: ${data?.last_updated || "—"}`}
                    className="h-full flex flex-col"
                    right={
                        <span className="text-xs font-semibold px-2 py-1 rounded bg-slate-100 text-slate-700">
                            {rows.length} rows
                        </span>
                    }
                >
                    {rows.length ? (
                        <div className="flex-1 overflow-hidden">
                            <PerformanceTable rows={rows} />
                        </div>
                    ) : (
                        <div className="text-slate-400 p-4">No performance data found for this date.</div>
                    )}
                </Card>
            </div>
        </div>
    );
}
