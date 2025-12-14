import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Shell from "./components/Shell.jsx";
import Home from "./pages/Home.jsx";

import StrictRecommendations from "./pages/StrictRecommendations.jsx";
import AggressiveRecommendations from "./pages/AggressiveRecommendations.jsx";
import OptionsRecommendations from "./pages/OptionsRecommendations.jsx";

export default function App() {
    return (
        <Shell>
            <Routes>
                <Route path="/" element={<Home />} />

                <Route path="/recommendations/strict" element={<StrictRecommendations />} />
                <Route path="/recommendations/aggressive" element={<AggressiveRecommendations />} />
                <Route path="/recommendations/options" element={<OptionsRecommendations />} />

                <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
        </Shell>
    );
}
