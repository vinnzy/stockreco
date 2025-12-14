import React, { useEffect, useState } from "react";
import Card from "../components/Card.jsx";

export default function Home() {
    const [meta, setMeta] = useState(null);

    useEffect(() => {
        fetch("/api/v1/meta").then((r) => r.json()).then(setMeta).catch(() => setMeta(null));
    }, []);

    return (
        <div className="space-y-6">
            <div>
                <div className="text-3xl font-bold text-slate-900">Home</div>
                <div className="text-slate-500 mt-2">Select a stock to view data tables</div>
            </div>

            <Card
                title="Status"
                subtitle="Backend + reports detection"
                right={
                    meta?.latest_as_of ? (
                        <span className="text-xs font-semibold px-2 py-1 rounded bg-slate-100 text-slate-700">
                            Latest: {meta.latest_as_of}
                        </span>
                    ) : null
                }
            >
                <div className="text-sm text-slate-600">
                    API: <code className="bg-slate-50 px-2 py-1 rounded">/api/v1/meta</code>
                </div>
                <div className="text-sm text-slate-600 mt-2">
                    Reports dir: <code className="bg-slate-50 px-2 py-1 rounded">{meta?.reports_dir ?? "—"}</code>
                </div>
            </Card>

            <Card title="Select Stock" subtitle="(tables + charts next)">
                <select className="w-full border border-slate-200 rounded-xl px-4 py-3 bg-white text-slate-700">
                    <option>Select a stock</option>
                </select>
            </Card>
        </div>
    );
}
