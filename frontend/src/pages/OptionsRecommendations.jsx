import React from "react";
import RecoPage from "./_RecoPage.jsx";

export default function OptionsRecommendations() {
    return (
        <RecoPage
            title="Recommended Options"
            subtitle="All BUY/SELL options from the daily run"
            pickRows={(data) => data?.recommended_options ?? []}
        />
    );
}
