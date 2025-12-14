import React from "react";
import Sidebar from "./Sidebar.jsx";

export default function Shell({ children }) {
    return (
        <div className="min-h-screen flex">
            <Sidebar />
            <main className="flex-1 p-8">{children}</main>
        </div>
    );
}
