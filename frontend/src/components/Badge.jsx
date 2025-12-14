import React from "react";

export default function Badge({ action }) {
    const cls =
        action === "BUY"
            ? "bg-emerald-100 text-emerald-700"
            : action === "SELL"
                ? "bg-rose-100 text-rose-700"
                : "bg-amber-100 text-amber-800";
    return (
        <span className={["px-2 py-1 rounded-md text-xs font-semibold", cls].join(" ")}>
            {action}
        </span>
    );
}
