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

/**
 * useLiveOptionQuotes(symbols, { intervalMs, asOf })
 * - symbols: array|string|Set of UI-style symbols (NIFTY06JAN2626100CE...)
 * - asOf: optional YYYY-MM-DD (your derivatives folder date)
 *
 * Returns: { quotes, loading }
 * quotes shape: { [SYMBOL]: { ok: boolean, ltp: number|null } }
 */
export function useLiveOptionQuotes(symbols, { intervalMs = 15000, asOf = null } = {}) {
    const [quotes, setQuotes] = useState({});
    const [loading, setLoading] = useState(false);

    const aliveRef = useRef(true);

    // Normalize + de-dupe
    const normSymbols = useMemo(() => {
        const arr = toArray(symbols).map(normSym).filter(Boolean);
        return Array.from(new Set(arr));
    }, [symbols]);

    // stable signature prevents infinite loops
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
            setLoading(true);
            try {
                const list = sig.split("|").filter(Boolean);
                const qs = new URLSearchParams();
                list.forEach((s) => qs.append("options", s));
                if (asOf) qs.set("as_of", asOf);

                const res = await fetch(`/api/options/ltp?${qs.toString()}`);
                const json = await res.json();

                const raw = json?.data || {};
                const normalized = {};
                for (const [k, v] of Object.entries(raw)) normalized[normSym(k)] = v;

                if (stopped || !aliveRef.current) return;
                setQuotes(normalized);
            } catch {
                // keep old values if fetch fails
            } finally {
                if (stopped || !aliveRef.current) return;
                setLoading(false);
            }
        }

        fetchQuotes();
        timer = setInterval(fetchQuotes, intervalMs);

        return () => {
            stopped = true;
            if (timer) clearInterval(timer);
        };
    }, [sig, intervalMs, asOf]);

    return { quotes, loading };
}

// ✅ also provide default export so BOTH import styles work
export default useLiveOptionQuotes;
