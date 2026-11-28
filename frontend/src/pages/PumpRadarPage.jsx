import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, AlertTriangle, BarChart3, CheckCircle2, Clock3, RefreshCw, Radar, Search, Waves } from "lucide-react";
import { fetchPumpRadarV2Scan } from "../lib/api";

const CACHE_KEY = "cyt-pump-radar-v2-daily-scan";
const BATCH_SIZE = 30;

const fmt = (value, digits = 2) =>
  value === null || value === undefined || !Number.isFinite(Number(value))
    ? "—"
    : Number(value).toLocaleString("en-US", { maximumFractionDigits: digits });

const fmtVolume = (value) => {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  const n = Number(value);
  if (Math.abs(n) >= 1e9) return \`\${fmt(n / 1e9)} B\`;
  if (Math.abs(n) >= 1e6) return \`\${fmt(n / 1e6)} M\`;
  if (Math.abs(n) >= 1e3) return \`\${fmt(n / 1e3)} K\`;
  return fmt(n, 2);
};

const fmtPct = (value) => value === null || value === undefined ? "—" : \`\${fmt(value)}%\`;
const fmtRatio = (value) => value === null || value === undefined ? "—" : \`\${fmt(value)}×\`;

const CATEGORY = {
  EXTREME_ANOMALY: { label: "Extreme", tone: "bg-red-100 text-red-800 border-red-200" },
  STRONG_ANOMALY: { label: "Strong", tone: "bg-orange-100 text-orange-800 border-orange-200" },
  ANOMALY: { label: "Anomaly", tone: "bg-amber-100 text-amber-800 border-amber-200" },
  INCREASING: { label: "Increasing", tone: "bg-sky-100 text-sky-800 border-sky-200" },
  NORMAL: { label: "Normal", tone: "bg-stone-100 text-stone-600 border-stone-200" },
};

function StatusPill({ category }) {
  const item = CATEGORY[category] || { label: category || "Unknown", tone: "bg-stone-100 text-stone-600 border-stone-200" };
  return <span className={\`inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-[11px] font-semibold \${item.tone}\`}>{item.label}</span>;
}

function SummaryCard({ label, value, note, icon: Icon }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-4 min-w-0">
      <div className="flex items-center justify-between gap-2">
        <p className="micro-label text-muted">{label}</p>
        {Icon && <Icon size={16} className="text-pine-700" />}
      </div>
      <p className="mt-3 font-display text-3xl font-semibold text-ink">{value}</p>
      {note && <p className="mt-1 text-[11px] leading-4 text-muted">{note}</p>}
    </div>
  );
}

export default function PumpRadarPage() {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [scanned, setScanned] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("ALL");
  const [lastScan, setLastScan] = useState("");
  const [source, setSource] = useState("");
  const started = useRef(false);

  const scanAll = async () => {
    setLoading(true);
    setError("");
    setRows([]);
    setScanned(0);
    setTotal(0);
    let offset = 0;
    let all = [];
    try {
      while (true) {
        const batch = await fetchPumpRadarV2Scan(offset, BATCH_SIZE);
        if (!batch?.ok) throw new Error("Respons pemindaian Binance tidak valid.");
        all = all.concat(batch.results || []);
        setRows([...all]);
        setScanned(all.length);
        setTotal(batch.universeTotal || all.length);
        setSource(batch.source || "Binance USD-M Futures");
        if (batch.nextOffset === null || batch.nextOffset === undefined) break;
        offset = batch.nextOffset;
      }
      const completedAt = new Date().toISOString();
      const snapshot = {
        date: new Date(Date.now() - 86400000).toISOString().slice(0, 10),
        completedAt,
        total: all.length,
        source: "binance-usdm-futures",
        rows: all,
      };
      try { localStorage.setItem(CACHE_KEY, JSON.stringify(snapshot)); } catch { /* cache is optional */ }
      setLastScan(completedAt);
    } catch (err) {
      setError(err.message || "Pemindaian gagal. Hasil batch yang sudah selesai tetap ditampilkan.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    let cached = null;
    try { cached = JSON.parse(localStorage.getItem(CACHE_KEY) || "null"); } catch { cached = null; }
    const targetDate = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
    if (cached?.date === targetDate && Array.isArray(cached.rows) && cached.rows.length) {
      setRows(cached.rows);
      setTotal(cached.total || cached.rows.length);
      setScanned(cached.rows.length);
      setLastScan(cached.completedAt || "");
      setSource("Binance USD-M Futures · cache harian");
    } else {
      scanAll();
    }
  }, []);

  const validRows = useMemo(() => rows.filter((row) => row.ok && row.metrics), [rows]);
  const filteredRows = useMemo(() => {
    const selected = filter === "ALL" ? validRows : validRows.filter((row) => row.category === filter);
    return [...selected].sort((a, b) => (b.metrics?.baseRvolDaily || 0) - (a.metrics?.baseRvolDaily || 0));
  }, [validRows, filter]);

  const counts = useMemo(() => ({
    extreme: validRows.filter((r) => r.category === "EXTREME_ANOMALY").length,
    strong: validRows.filter((r) => r.category === "STRONG_ANOMALY").length,
    anomaly: validRows.filter((r) => r.category === "ANOMALY").length,
    increasing: validRows.filter((r) => r.category === "INCREASING").length,
    normal: validRows.filter((r) => r.category === "NORMAL").length,
  }), [validRows]);

  const progress = total > 0 ? Math.min(100, (scanned / total) * 100) : 0;

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 pb-14">
      <section className="pt-10 md:pt-14 pb-7 border-b border-line">
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-5">
          <div className="max-w-3xl">
            <p className="micro-label text-gold-600">Binance USD-M · USDT Perpetual · Closed Daily Candle</p>
            <h1 className="mt-3 font-display text-4xl sm:text-5xl font-semibold tracking-tight text-ink">
              Pump Radar <span className="italic text-pine-700">V2.</span>
            </h1>
            <p className="mt-4 text-sm leading-6 text-muted max-w-2xl">
              Memindai pasangan Futures USDT dan mencari lonjakan Base Volume harian dibandingkan
              rata-rata tujuh candle tertutup sebelumnya. Harga dan Quote Volume menjadi konteks,
              bukan syarat yang menunda sinyal awal.
            </p>
          </div>
          <button type="button" onClick={scanAll} disabled={loading} className="btn-primary focus-ring disabled:opacity-60">
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
            {loading ? "Memindai pasar…" : "Scan ulang seluruh pasar"}
          </button>
        </div>
        <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted">
          <span className="inline-flex items-center gap-1.5"><Radar size={14} /> {source || "Binance USD-M Futures"}</span>
          <span className="inline-flex items-center gap-1.5"><Clock3 size={14} /> Candle harian UTC yang sudah tutup</span>
          {lastScan && <span>Terakhir scan: {new Date(lastScan).toLocaleString()}</span>}
        </div>
      </section>

      {loading && (
        <section className="mt-6 rounded-xl border border-line bg-white p-4">
          <div className="flex items-center justify-between gap-3 text-sm">
            <span className="font-medium text-ink">Memindai pasangan Futures</span>
            <span className="font-mono text-muted">{scanned.toLocaleString()} / {total ? total.toLocaleString() : "…"}</span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-stone-100">
            <div className="h-full rounded-full bg-pine-700 transition-all" style={{ width: \`\${progress}%\` }} />
          </div>
          <p className="mt-2 text-[11px] text-muted">Data diproses per batch agar permintaan candle tidak membebani satu request server.</p>
        </section>
      )}

      {error && (
        <div className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertTriangle size={16} className="inline mr-2" />{error}
        </div>
      )}

      <section className="mt-6 grid grid-cols-2 lg:grid-cols-5 gap-3">
        <SummaryCard label="Extreme" value={counts.extreme} note="≥ 5× baseline" icon={Activity} />
        <SummaryCard label="Strong" value={counts.strong} note="3× sampai < 5×" icon={Waves} />
        <SummaryCard label="Anomaly" value={counts.anomaly} note="2× sampai < 3×" icon={AlertTriangle} />
        <SummaryCard label="Increasing" value={counts.increasing} note="1,5× sampai < 2×" icon={BarChart3} />
        <SummaryCard label="Pair valid" value={validRows.length.toLocaleString()} note={\`Dari \${total.toLocaleString()} kontrak\`} icon={CheckCircle2} />
      </section>

      <section className="mt-8">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3 mb-4">
          <div>
            <h2 className="font-display text-2xl font-semibold text-ink">Daily Base Volume Anomaly</h2>
            <p className="mt-1 text-xs text-muted">Urutan berdasarkan Base RVOL terbesar. Klik pair untuk membuka detail token.</p>
          </div>
          <label className="flex items-center gap-2 text-xs text-muted">
            <Search size={14} />
            <select value={filter} onChange={(event) => setFilter(event.target.value)} className="rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink">
              <option value="ALL">Semua kategori</option>
              <option value="EXTREME_ANOMALY">Extreme</option>
              <option value="STRONG_ANOMALY">Strong</option>
              <option value="ANOMALY">Anomaly</option>
              <option value="INCREASING">Increasing</option>
              <option value="NORMAL">Normal</option>
            </select>
          </label>
        </div>

        <div className="overflow-x-auto rounded-2xl border border-line bg-white">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="bg-stone-50 text-left">
              <tr className="border-b border-line">
                <th className="px-4 py-3 text-[10px] uppercase tracking-wider text-muted">Pair</th>
                <th className="px-4 py-3 text-right text-[10px] uppercase tracking-wider text-muted">Base Volume</th>
                <th className="px-4 py-3 text-right text-[10px] uppercase tracking-wider text-muted">Avg prior 7D</th>
                <th className="px-4 py-3 text-right text-[10px] uppercase tracking-wider text-muted">Base RVOL</th>
                <th className="px-4 py-3 text-right text-[10px] uppercase tracking-wider text-muted">7D RVOL</th>
                <th className="px-4 py-3 text-right text-[10px] uppercase tracking-wider text-muted">Quote RVOL</th>
                <th className="px-4 py-3 text-right text-[10px] uppercase tracking-wider text-muted">Price 24H</th>
                <th className="px-4 py-3 text-right text-[10px] uppercase tracking-wider text-muted">Buy Share</th>
                <th className="px-4 py-3 text-right text-[10px] uppercase tracking-wider text-muted">Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => {
                const m = row.metrics;
                return (
                  <tr key={row.symbol} className="border-b border-line last:border-0 hover:bg-pine-50/50">
                    <td className="px-4 py-3">
                      <Link to={\`/token/\${row.symbol}\`} className="font-semibold text-ink hover:text-pine-700 focus-ring rounded">
                        {row.symbol}
                      </Link>
                      <p className="mt-0.5 text-[10px] text-muted">{m.evaluatedDate ? new Date(Number(m.evaluatedDate)).toISOString().slice(0, 10) : "—"}</p>
                    </td>
                    <td className="px-4 py-3 text-right font-mono">{fmtVolume(m.baseVolume)}</td>
                    <td className="px-4 py-3 text-right font-mono text-muted">{fmtVolume(m.baseVolumePrior7dAverage)}</td>
                    <td className="px-4 py-3 text-right font-mono font-semibold">{fmtRatio(m.baseRvolDaily)}</td>
                    <td className="px-4 py-3 text-right font-mono">{fmtRatio(m.baseRvol7d)}</td>
                    <td className="px-4 py-3 text-right font-mono">{fmtRatio(m.quoteRvolDaily)}</td>
                    <td className={\`px-4 py-3 text-right font-mono \${m.priceChange24hPct > 0 ? "text-pine-700" : m.priceChange24hPct < 0 ? "text-red-600" : "text-ink"}\`}>{fmtPct(m.priceChange24hPct)}</td>
                    <td className="px-4 py-3 text-right font-mono">{fmtPct(m.buyShareQuotePct)}</td>
                    <td className="px-4 py-3 text-right"><StatusPill category={row.category} /></td>
                  </tr>
                );
              })}
              {!filteredRows.length && !loading && (
                <tr><td colSpan="9" className="px-4 py-12 text-center text-sm text-muted">Belum ada hasil untuk kategori ini. Jalankan scan pasar untuk mengambil data terbaru.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[11px] text-muted">
          Pair yang gagal diambil atau belum memiliki 15 candle harian ditampilkan sebagai data tidak valid dan tidak ikut ranking.
          {scanned > 0 ? \` \${scanned - validRows.length} pair dilewati atau belum cukup data.\` : ""}
        </p>
      </section>

      <section className="mt-8 rounded-xl border border-gold-200 bg-gold-50/60 p-4">
        <p className="text-xs leading-5 text-gold-800">
          Rumus Base RVOL harian = Base Volume candle terbaru ÷ rata-rata Base Volume tujuh candle sebelumnya.
          Weekly RVOL membandingkan total tujuh hari terbaru dengan total tujuh hari sebelumnya.
          Ambang 1,5× / 2× / 3× / 5× masih eksperimental. Sinyal menunjukkan anomali aktivitas, bukan bukti whale accumulation atau instruksi entry.
        </p>
      </section>
    </div>
  );
}
