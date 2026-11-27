import type { RadarSummary } from "../lib/useRadar";

interface Props {
  symbol: string;
  compact?: boolean;
  preloaded?: RadarSummary | null; // ← BARU: data dari useRadarAll
}

export default function RadarBadge({ symbol, compact = true }: Props) {
  const data = preloaded ?? null;
  const loading = preloaded === undefined;
  const error = false;

  // ---------- KONDISI LOADING ----------
  if (loading) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
        ⏳ radar...
      </span>
    );
  }

  // ---------- KONDISI ERROR ----------
  if (error || !data) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-xs text-red-400">
        radar off
      </span>
    );
  }

  // ---------- STATUS TRIGGER 🔴 ----------
  if (data.status === "TRIGGER") {
    const t = data.today;
    return (
      <span
        className="inline-flex items-center gap-1 rounded-full bg-red-500 px-2 py-0.5 text-xs font-bold text-white animate-pulse"
        title={
          t
            ? `Vol ${t.ratio}x baseline | ${t.change_pct > 0 ? "+" : ""}${t.change_pct}% | buy ${Math.round(t.buy_share * 100)}%`
            : ""
        }
      >
        🚨 PUMP RADAR
      </span>
    );
  }

  // ---------- STATUS IDLE ⚪ ----------
  const lastSignal = data.signals[data.signals.length - 1];
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
