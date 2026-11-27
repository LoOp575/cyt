// ============================================================
// useRadarAll.ts — status radar untuk BANYAK coin sekaligus
// ============================================================
import { useEffect, useState } from "react";
import type { RadarSummary } from "./useRadar";

const API_URL = "http://localhost:8000"; // ⚠️ samain sama useRadar.ts

export function useRadarAll(symbols: string[]) {
  const [statuses, setStatuses] = useState<Record<string, RadarSummary | null>>({});
  const [loading, setLoading] = useState(true);

  // join biar gak re-fetch terus tiap render
  const key = symbols.join(",");

  useEffect(() => {
    let batal = false;
    setLoading(true);

    const list = key.split(",").filter(Boolean);

    Promise.all(
      list.map((sym) =>
        fetch(`${API_URL}/api/radar/${sym.toUpperCase()}`)
          .then((r) => (r.ok ? r.json() : null))
          .then((json: RadarSummary | null) => [sym, json] as const)
          .catch(() => [sym, null] as const)
      )
    ).then((results) => {
      if (batal) return;
      const map: Record<string, RadarSummary | null> = {};
      for (const [sym, json] of results) map[sym] = json;
      setStatuses(map);
      setLoading(false);
    });

    return () => { batal = true; };
  }, [key]);

  return { statuses, loading };
}
