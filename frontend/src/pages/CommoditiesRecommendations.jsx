import React from "react";
import CommodityRecoPage from "./_CommodityRecoPage.jsx";

export default function CommoditiesRecommendations() {
    return (
        <CommodityRecoPage
            title="MCX Futures"
            subtitle="Daily commodity futures recommendations (GOLD, GOLDM, etc.)"
            apiBase="/api/mcx"
            pickRows={(d) => (Array.isArray(d) ? d : [])}
        />
    );
}
