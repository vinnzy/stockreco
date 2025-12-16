import React from "react";
import RecoPage from "./_RecoPage.jsx";

function pickOptionsRows(payload) {
    if (!payload) return [];

    // if backend ever returns plain array (old format)
    if (Array.isArray(payload)) return payload;

    // New format: structured with reviewer
    // We need to extract both approved and rejected to mark them accordingly
    let rows = [];
    let approvedSymbols = new Set();
    let rejectedMap = new Map(); // symbol -> rejection reason

    // 1) Check for new structured format with reviewer
    if (payload.reviewer) {
        // Get approved recommendations
        const approved = payload.reviewer.approved || payload.final || [];
        rows = Array.isArray(approved) ? approved : [];

        // Track approved symbols
        approved.forEach(r => {
            const key = `${r.symbol}-${r.strike}-${r.side}-${r.expiry}`;
            approvedSymbols.add(key);
        });

        // Track rejected recommendations with reasons
        const rejected = payload.reviewer.rejected || [];
        rejected.forEach(r => {
            const key = `${r.symbol}-${r.strike}-${r.side}-${r.expiry}`;
            rejectedMap.set(key, r.reason);
        });

        // Also include rejected items in the display (marked as rejected)
        // Get all recommendations from recommender
        const allRecos = payload.recommender || [];
        allRecos.forEach(r => {
            const key = `${r.symbol}-${r.strike}-${r.side}-${r.expiry}`;
            if (!approvedSymbols.has(key) && rejectedMap.has(key)) {
                // This is a rejected recommendation, add it with rejection info
                rows.push({
                    ...r,
                    __reviewerRejected: true,
                    __rejectionReason: rejectedMap.get(key)
                });
            }
        });

        // Mark approved items
        rows = rows.map(r => {
            const key = `${r.symbol}-${r.strike}-${r.side}-${r.expiry}`;
            if (approvedSymbols.has(key)) {
                return { ...r, __reviewerApproved: true };
            }
            return r;
        });

        return rows;
    }

    // 2) Fallback: { final: [...] }
    if (Array.isArray(payload.final)) return payload.final;

    // Old common shapes:
    // 3) { recommended_options: [...] }
    if (Array.isArray(payload.recommended_options)) return payload.recommended_options;

    // 4) { report: { recommended_options: [...] } }
    if (payload.report && Array.isArray(payload.report.recommended_options)) return payload.report.recommended_options;

    // 5) { data: { recommended_options: [...] } }
    if (payload.data && Array.isArray(payload.data.recommended_options)) return payload.data.recommended_options;

    // 6) { result: { recommended_options: [...] } }
    if (payload.result && Array.isArray(payload.result.recommended_options)) return payload.result.recommended_options;

    return [];
}

export default function OptionsRecommendations() {
    return (
        <RecoPage
            title="Recommended Options"
            subtitle="Options filtered by reviewer for quality and risk management"
            pickRows={pickOptionsRows}
        />
    );
}
