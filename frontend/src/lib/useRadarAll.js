import { useEffect, useState } from "react";

export function useRadarAll(symbols) {
  const [statuses, setStatuses] = useState({});
  const [loading, setLoading] = useState(true);
  const key = symbols.join(",");

  useEffect(() => {
    let cancelled = false;
    const list = key.split(",").filter(Boolean);
    const pending = {};
    for (const symbol of list) pending[symbol] = null;
    setStatuses(pending);
    setLoading(true);

    Promise.all(
      list.map((symbol) =>
        fetch(`/api/radar/${encodeURIComponent(symbol.toUpperCase())}`)
          .then((response) => (response.ok ? response.json() : null))
          .then((json) => [symbol, json])
          .catch(() => [symbol, null])
      )
    ).then((results) => {
      if (cancelled) return;
      const next = {};
      for (const [symbol, json] of results) next[symbol] = json;
      setStatuses(next);
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [key]);

  return { statuses, loading };
}
