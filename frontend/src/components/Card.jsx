import React from "react";

export default function Card({ title, subtitle, right, children }) {
    return (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100">
            <div className="p-5 flex items-start justify-between gap-4">
                <div>
                    <div className="text-base font-semibold text-slate-900">{title}</div>
                    {subtitle ? <div className="text-sm text-slate-500 mt-1">{subtitle}</div> : null}
                </div>
                {right}
            </div>
            <div className="px-5 pb-5">{children}</div>
        </div>
    );
}
