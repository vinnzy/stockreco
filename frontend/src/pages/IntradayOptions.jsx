import React from "react";
import RecoPage from "./_RecoPage.jsx";

// Reuse pickOptionsRows if the structure is same, 
// OR define specific one if Intraday JSON is flat list (it is flat list based on my agent).
// Intraday Reco JSON is just `[ { ... }, { ... } ]`.
// So we can just passthrough or map fields.

function pickIntradayRows(payload) {
    if (!payload) return [];
    if (payload.reviewer && Array.isArray(payload.reviewer.approved)) {
        // Mark them as approved so the UI shows the badge
        return payload.reviewer.approved.map(r => ({ ...r, __reviewerApproved: true }));
    }
    if (Array.isArray(payload)) return payload;
    return [];
}

export default function IntradayOptions() {
    return (
        <RecoPage
            title="Intraday Options >15%"
            subtitle="Quick profit opportunities for the next trading day."
            pickRows={pickIntradayRows}
            apiPrefix="/api/options/intraday"
        />
    );
}
