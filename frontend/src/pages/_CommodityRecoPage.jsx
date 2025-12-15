import React, { useEffect, useMemo, useState } from "react";
import Card from "../components/Card.jsx";
import Badge from "../components/Badge.jsx";

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

function Table({ rows }) {
    return (
        <div className="overflow-x-auto border border-slate-100 rounded-2xl">
            <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                    <tr>
                        <th className="text-left px-4 py-3">Symbol</th>
                        <th className="text-left px-4 py-3">Action</th>
                        <th className="text-left px-4 py-3">Expiry</th>
                        <th className="text-left px-4 py-3">LTP</th>
                        <th className="text-left px-4 py-3">Entry</th>
                        <th className="text-left px-4 py-3">SL</th>
                        <th className="text-left px-4 py-3">T1</th>
                        <th className="text-left px-4 py-3">T2</th>
                        <th className="text-left px-4 py-3">Sell-by</th>
                        <th className="text-left px-4 py-3">Conf</th>
                    </tr>
                </thead>

                <tbody>
                    {rows.map((r, idx) => {
                        const isExpired = !!r.__expired;

                        // CommodityRecoAgent schema
                        const entry = r.entry_price ?? r.entry ?? null;
                        const sl = r.sl ?? r.stop_loss ?? null;
                        const t1 = r.t1 ?? null;
                        const t2 = r.t2 ?? null;

                        return (
                            <tr
                                key={`${r.symbol ?? ""}-${r.expiry ?? ""}-${idx}`}
                                className={[
                                    "border-t",
                                    isExpired ? "bg-slate-50 text-slate-400" : "hover:bg-slate-50/60",
                                ].join(" ")}
                                title={isExpired ? "Auto-invalidated (past sell-by)" : ""}
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
                                    <Badge action={isExpired ? "HOLD" : (r.action ?? "HOLD")} />
                                </td>

                                <td className="px-4 py-3 text-slate-700">{r.expiry ?? "—"}</td>

                                <td className="px-4 py-3 text-slate-700">{fmt(r.ltp)}</td>

                                <td className="px-4 py-3 text-slate-700">{fmt(entry)}</td>
                                <td className="px-4 py-3 text-rose-700">{fmt(sl)}</td>
                                <td className="px-4 py-3 text-emerald-700">{fmt(t1)}</td>
                                <td className="px-4 py-3 text-emerald-700">{fmt(t2)}</td>
                                <td className="px-4 py-3 text-slate-700">{r.sell_by ?? "—"}</td>
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

/** ---------- page ---------- **/

export default function CommodityRecoPage({ title, subtitle, pickRows, apiBase = "/api/commodities" }) {
    const [asOf, setAsOf] = useState("");
    const [dates, setDates] = useState([]);
    const [latest, setLatest] = useState("");
    const [data, setData] = useState(null);

    useEffect(() => {
        fetch(`${apiBase}/dates`)
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
        fetch(`${apiBase}/${encodeURIComponent(asOf)}`)
            .then((r) => r.json())
            .then(setData)
            .catch(() => setData(null));
    }, [asOf]);

    const rowsRaw = Array.isArray(data) ? data : [];
    const rows = useMemo(() => {
        const today = ymdToNum(todayYmd());
        return (rowsRaw || []).map((r) => {
            const sb = ymdToNum(r?.sell_by);
            const expired = !!(today && sb && today > sb);
            return { ...r, __expired: expired };
        });
    }, [rowsRaw]);

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
