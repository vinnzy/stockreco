import React from "react";
import CommodityRecoPage from "./_CommodityRecoPage.jsx";

export default function CommoditiesRecommendations() {
    return (
        <CommodityRecoPage
            title="MCX Commodities"
            subtitle="Daily commodity futures and options recommendations"
            apiBase="/api/mcx"
            pickRows={(d) => (Array.isArray(d) ? d : [])}
        />
    );
}
