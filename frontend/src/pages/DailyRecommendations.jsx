import React, { useEffect, useState } from "react";
import Card from "../components/Card.jsx";
import Badge from "../components/Badge.jsx";

function fmt(x) {
    if (x === null || x === undefined || x === "") return "—";
    const n = Number(x);
    if (Number.isFinite(n)) return n.toFixed(2).replace(/\.00$/, "");
    return String(x);
}

function Table({ rows }) {
    return (
        <div className="overflow-x-auto border border-slate-100 rounded-2xl">
            <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                    <tr>
                        <th className="text-left px-4 py-3">Symbol</th>
                        <th className="text-left px-4 py-3">Action</th>
                        <th className="text-left px-4 py-3">Option</th>
                        <th className="text-left px-4 py-3">Entry ≤</th>
                        <th className="text-left px-4 py-3">SL</th>
                        <th className="text-left px-4 py-3">T1</th>
                        <th className="text-left px-4 py-3">T2</th>
                        <th className="text-left px-4 py-3">Conf</th>
                    </tr>
                </thead>
                <tbody>
                    {rows.map((r) => (
                        <tr key={(r.symbol ?? "") + (r.strike ?? "") + (r.side ?? "")} className="border-t">
                            <td className="px-4 py-3 font-medium text-slate-900">{r.symbol}</td>
                            <td className="px-4 py-3"><Badge action={r.action} /></td>
                            <td className="px-4 py-3 text-slate-700">
                                {r.side ? `${fmt(r.strike)} ${r.side}${r.expiry ? ` (${r.expiry})` : ""}` : "—"}
                            </td>
                            <td className="px-4 py-3 text-slate-700">{fmt(r.entry_price)}</td>
                            <td className="px-4 py-3 text-rose-700">{fmt(r.sl_premium)}</td>
                            <td className="px-4 py-3 text-emerald-700">{fmt(r.t1_premium)}</td>
                            <td className="px-4 py-3 text-emerald-700">{fmt(r.t2_premium)}</td>
                            <td className="px-4 py-3 text-slate-700">{Math.round((r.confidence || 0) * 100)}%</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

export default function DailyRecommendations() {
    const [asOf, setAsOf] = useState("");
    const [data, setData] = useState(null);

    useEffect(() => {
        const url = asOf
            ? `/api/v1/recommendations/daily?as_of=${encodeURIComponent(asOf)}`
            : "/api/v1/recommendations/daily";
        fetch(url).then((r) => r.json()).then(setData).catch(() => setData(null));
    }, [asOf]);

    const strict = data?.strict ?? [];
    const aggressive = data?.aggressive ?? [];
    const options = data?.recommended_options ?? [];

    return (
        <div className="space-y-6">
            <div className="flex items-end justify-between gap-4 flex-wrap">
                <div>
                    <div className="text-3xl font-bold text-slate-900">Daily Recommendations</div>
                    <div className="text-slate-500 mt-2">Strict: conf ≥ 60% • Aggressive: conf ≥ 30%</div>
                </div>
                <div className="flex items-center gap-3">
                    <label className="text-sm text-slate-600">As-of</label>
                    <input
                        value={asOf}
                        onChange={(e) => setAsOf(e.target.value)}
                        placeholder={data?.as_of || "YYYY-MM-DD (optional)"}
                        className="border border-slate-200 rounded-xl px-4 py-2 bg-white"
                    />
                </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                <Card
                    title="Recommended stocks with strict option"
                    subtitle="High-confidence option trades"
                    right={<span className="text-xs font-semibold px-2 py-1 rounded bg-slate-100 text-slate-700">{strict.length}</span>}
                >
                    {strict.length ? <Table rows={strict} /> : <div className="text-slate-400">No strict trades.</div>}
                </Card>

                <Card
                    title="Recommended stocks with aggressive option"
                    subtitle="More trades, lower confidence threshold"
                    right={<span className="text-xs font-semibold px-2 py-1 rounded bg-slate-100 text-slate-700">{aggressive.length}</span>}
                >
                    {aggressive.length ? <Table rows={aggressive} /> : <div className="text-slate-400">No aggressive trades.</div>}
                </Card>
            </div>

            <Card
                title="Recommended options"
                subtitle="All BUY/SELL options from the daily run"
                right={<span className="text-xs font-semibold px-2 py-1 rounded bg-slate-100 text-slate-700">{options.length}</span>}
            >
                {options.length ? <Table rows={options} /> : <div className="text-slate-400">No option recommendations today.</div>}
            </Card>
        </div>
    );
}
