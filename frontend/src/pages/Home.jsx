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

            <Card title="Quick Navigation">
                <div className="grid grid-cols-2 gap-4">
                    <a href="/recommendations/strict" className="block p-4 rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors">
                        <div className="font-semibold text-slate-900">Strict</div>
                        <div className="text-xs text-slate-500">High confidence stocks</div>
                    </a>
                    <a href="/recommendations/aggressive" className="block p-4 rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors">
                        <div className="font-semibold text-slate-900">Aggressive</div>
                        <div className="text-xs text-slate-500">Momentum stocks</div>
                    </a>
                    <a href="/recommendations/options" className="block p-4 rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors">
                        <div className="font-semibold text-slate-900">Options</div>
                        <div className="text-xs text-slate-500">EOD Recommendations</div>
                    </a>
                    <a href="/recommendations/intraday" className="block p-4 rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors bg-gradient-to-br from-indigo-50 to-white border-indigo-100">
                        <div className="font-semibold text-indigo-900">Intraday Options</div>
                        <div className="text-xs text-indigo-600/80">Quick &gt;15% targets</div>
                    </a>
                </div>
            </Card>
        </div>
    );
}
