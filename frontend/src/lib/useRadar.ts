import { useEffect, useState } from "react";

export interface RadarSignal {
  time: string;
  ratio: number;
  cluster_hits: number;
  change_pct: number;
  vetoed: boolean;
  triggered: boolean;
  buy_share: number;
  close: number;
}

export interface RadarSummary {
  symbol: string;
  status: "TRIGGER" | "IDLE";
  today: RadarSignal | null;
  signals: RadarSignal[];
}

interface RadarState {
  data: RadarSummary | null;
  loading: boolean;
  error: string | null;
}

/** Fetch one coin's radar summary from the same-origin API. */
export function useRadar(symbol: string, enabled = true): RadarState {
  const [state, setState] = useState<RadarState>({
    data: null,
    loading: Boolean(enabled && symbol),
    error: null,
  });

  useEffect(() => {
    if (!enabled || !symbol) {
      setState({ data: null, loading: false, error: null });
      return undefined;
    }

    const controller = new AbortController();
    setState((current) => ({ ...current, loading: true, error: null }));

    fetch(`/api/radar/${encodeURIComponent(symbol.toUpperCase())}`, {
      signal: controller.signal,
      headers: { accept: "application/json" },
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Radar request failed (HTTP ${response.status})`);
        }
        return (await response.json()) as RadarSummary;
      })
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((error: unknown) => {
        if (error instanceof Error && error.name === "AbortError") return;
        setState({
          data: null,
          loading: false,
          error: error instanceof Error ? error.message : "Radar request failed",
        });
      });

    return () => controller.abort();
  }, [symbol, enabled]);

  return state;
}
