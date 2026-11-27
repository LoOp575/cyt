export default function RadarBadge({ preloaded }) {
  const data = preloaded ?? null;
  const loading = preloaded === undefined;

  if (loading) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
        ⏳ radar...
      </span>
    );
  }

  if (!data) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-xs text-red-400">
        radar off
      </span>
    );
  }

  if (data.status === "TRIGGER") {
    const today = data.today;
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full bg-red-500 px-2 py-0.5 text-xs font-bold text-white animate-pulse"
        title={
          today
            ? `Vol ${today.ratio}x baseline | ${today.change_pct > 0 ? "+" : ""}${today.change_pct}% | buy ${Math.round(today.buy_share * 100)}%`
            : ""
        }
      >
        🚨 PUMP RADAR
      </span>
    );
  }

  const lastSignal = data.signals?.[data.signals.length - 1];
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500"
      title={
        lastSignal
          ? `Sinyal terakhir: ${lastSignal.time} (vol ${lastSignal.ratio}x)`
          : "Belum ada sinyal 90 hari terakhir"
      }
    >
      {lastSignal ? `⚪ idle · sinyal ${lastSignal.time}` : "⚪ idle"}
    </span>
  );
}
