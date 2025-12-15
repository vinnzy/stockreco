import React from "react";
import { NavLink } from "react-router-dom";
import { Home, ShieldCheck, Zap, Layers } from "lucide-react";

const Item = ({ to, icon: Icon, label }) => (
    <NavLink
        to={to}
        className={({ isActive }) =>
            [
                "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium",
                isActive ? "bg-white/10 text-white" : "text-slate-200 hover:bg-white/5 hover:text-white",
            ].join(" ")
        }
    >
        <Icon size={18} />
        <span>{label}</span>
    </NavLink>
);

export default function Sidebar() {
    return (
        <aside className="w-72 bg-slate-900 text-white p-6">
            <div className="text-2xl font-bold tracking-tight mb-10">AlgoTrade</div>

            <nav className="space-y-2">
                <Item to="/" icon={Home} label="Home" />

                <div className="mt-6 text-xs font-semibold text-slate-400 tracking-widest">
                    RECOMMENDATIONS
                </div>

                <div className="space-y-2 mt-2">
                    <Item to="/recommendations/strict" icon={ShieldCheck} label="Strict" />
                    <Item to="/recommendations/aggressive" icon={Zap} label="Aggressive" />
                    <Item to="/recommendations/options" icon={Layers} label="Options" />
                    <Item to="/recommendations/mcx" icon={Layers} label="MCX" />
                </div>
            </nav>
        </aside>
    );
}
