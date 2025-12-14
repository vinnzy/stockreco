import { useEffect, useMemo, useRef, useState } from "react";

function normSym(s) {
    if (!s) return null;
    return String(s).trim().toUpperCase().replace(".NS", "");
}

function toArray(x) {
    if (!x) return [];
    if (Array.isArray(x)) return x;
    if (typeof x === "string") return [x];
    if (x instanceof Set) return Array.from(x);
    if (typeof x === "object" && Array.isArray(x.symbols)) return x.symbols;
    return [];
}

export function useLiveOptionQuotes(symbols, { intervalMs = 15000 } = {}) {
    const [quotes, setQuotes] = useState({});
    const aliveRef = useRef(true);

    // Normalize + de-dupe
    const normSymbols = useMemo(() => {
        const arr = toArray(symbols).map(normSym).filter(Boolean);
        return Array.from(new Set(arr));
    }, [symbols]);

    // 🔑 stable signature prevents infinite loops
    const sig = useMemo(() => normSymbols.slice().sort().join("|"), [normSymbols]);

    useEffect(() => {
        aliveRef.current = true;
        return () => {
            aliveRef.current = false;
        };
    }, []);

    useEffect(() => {
        if (!sig) {
            setQuotes({});
            return;
        }

        let timer = null;
        let stopped = false;

        async function fetchQuotes() {
            try {
                const list = sig.split("|").filter(Boolean);
                const qs = list.map((s) => `options=${encodeURIComponent(s)}`).join("&");

                const res = await fetch(`/api/options/ltp?${qs}`);
                const json = await res.json();

                const raw = json?.data || {};
                const normalized = {};
                for (const [k, v] of Object.entries(raw)) normalized[normSym(k)] = v;

                if (stopped || !aliveRef.current) return;
                setQuotes(normalized);
            } catch {
                // keep old values
            }
        }

        fetchQuotes();
        timer = setInterval(fetchQuotes, intervalMs);

        return () => {
            stopped = true;
            if (timer) clearInterval(timer);
        };
    }, [sig, intervalMs]);

    return quotes;
}
