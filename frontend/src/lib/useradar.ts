// ============================================================
// useRadar.ts — Hook PUMP RADAR untuk Meridian
// ============================================================
import { useEffect, useState } from "react";

// ---------- TIPE DATA (harus cocok sama jawaban backend) ----------
export interface RadarSignal {
  time: string;        // "20 Nov"
  ratio: number;       // volume vs baseline, mis. 2.85
  cluster_hits: number;
  change_pct: number;  // perubahan harga hari itu, mis. +4.2
  vetoed: boolean;
  triggered: boolean;
  buy_share: number;   // porsi taker buy, mis. 0.61
  close: number;
}

export interface RadarSummary {
  symbol: string;
  status: "TRIGGER" | "IDLE";
  today: RadarSignal | null;
  signals: RadarSignal[];
}

// ---------- HOOK ----------
const API_URL = ""; // ⚠️ SESUAIKAN port backend lu!

export function useRadar(symbol: string) {
  const [data, setData]     = useState<RadarSummary | null>(null);
  const [loading, setLoad]  = useState(true);
  const [error, setError]   = useState<string | null>(null);

  useEffect(() => {
    let batal = false; // cegah update kalau komponen udah unmount

    setLoad(true);
    setError(null);

    fetch(`${API_URL}/api/radar/${symbol.toUpperCase()}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((json: RadarSummary) => {
        if (!batal) setData(json);
      })
      .catch((e) => {
        if (!batal) setError(e.message);
      })
      .finally(() => {
        if (!batal) setLoad(false);
      });

    return () => { batal = true; };
  }, [symbol]);

  return { data, loading, error };
}
