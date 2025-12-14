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
                        <tr
                            key={(r.symbol ?? "") + (r.strike ?? "") + (r.side ?? "") + (r.expiry ?? "")}
                            className="border-t hover:bg-slate-50/60"
                        >
                            <td className="px-4 py-3 font-medium text-slate-900">{r.symbol}</td>
                            <td className="px-4 py-3">
                                <Badge action={r.action} />
                            </td>
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

export default function RecoPage({ title, subtitle, pickRows }) {
    const [asOf, setAsOf] = useState("");
    const [dates, setDates] = useState([]);
    const [latest, setLatest] = useState("");
    const [data, setData] = useState(null);


    useEffect(() => {
        fetch("/api/options/dates")
            .then((r) => r.json())
            .then((d) => {
                setDates(d.dates || []);
                setLatest(d.latest_as_of || "");
                if (!asOf && d.latest_as_of) setAsOf(d.latest_as_of);
            })

            .catch(() => { });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (!asOf) return;
        fetch(`/api/options/${encodeURIComponent(asOf)}`)
            .then((r) => r.json())
            .then(setData)
            .catch(() => setData(null));
    }, [asOf]);



    const rows = Array.isArray(data) ? data : pickRows(data);


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
                {rows.length ? <Table rows={rows} /> : <div className="text-slate-400">No rows.</div>}
            </Card>
        </div>
    );
}
