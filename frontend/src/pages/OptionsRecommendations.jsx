import React from "react";
import RecoPage from "./_RecoPage.jsx";

function pickOptionsRows(payload) {
    if (!payload) return [];

    // if backend ever returns plain array
    if (Array.isArray(payload)) return payload;

    // common shapes:
    // 1) { recommended_options: [...] }
    if (Array.isArray(payload.recommended_options)) return payload.recommended_options;

    // 2) { report: { recommended_options: [...] } }
    if (payload.report && Array.isArray(payload.report.recommended_options)) return payload.report.recommended_options;

    // 3) { data: { recommended_options: [...] } }
    if (payload.data && Array.isArray(payload.data.recommended_options)) return payload.data.recommended_options;

    // 4) { result: { recommended_options: [...] } }
    if (payload.result && Array.isArray(payload.result.recommended_options)) return payload.result.recommended_options;

    return [];
}

export default function OptionsRecommendations() {
    return (
        <RecoPage
            title="Recommended Options"
            subtitle="All BUY/SELL options from the daily run"
            pickRows={pickOptionsRows}
        />
    );
}
