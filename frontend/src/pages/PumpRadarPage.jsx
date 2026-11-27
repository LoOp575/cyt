import React, { useState } from "react";
import { Activity, AlertTriangle, BarChart3, RefreshCw, Search, Waves } from "lucide-react";
import { fetchPumpRadarV2, fetchPumpRadarV2Backtest } from "../lib/api";

const fmt = (value, digits = 2) =>
  value === null || value === undefined || Number.isNaN(Number(value))
    ? "—"
    : Number(value).toLocaleString("en-US", { maximumFractionDigits: digits });

const pct = (value) => (value === null || value === undefined ? "—" : `${fmt(value)}%`);
const mult = (value) => (value === null || value === undefined ? "—" : `${fmt(value)}×`);

function Metric({ label, value, note }) {
  return (
    <div className="rounded-xl border border-line bg-white/70 p-4 min-w-0">
      <p className="micro-label text-muted">{label}</p>
      <p className="mt-2 font-display text-2xl font-semibold text-ink break-words">{value}</p>
      {note && <p className="mt-1 text-[11px] text-muted">{note}</p>}
    </div>
  );
}

function Outcome({ label, data }) {
  return (
    <div className="rounded-xl border border-line p-4">
      <p className="text-sm font-semibold text-ink">{label}</p>
      <div className="grid grid-cols-3 gap-2 mt-3">
        {[
          ["24H median", data?.return24hPct?.median],
          ["72H median", data?.return72hPct?.median],
          ["7D median", data?.return7dPct?.median],
        ].map(([name, value]) => (
          <div key={name}>
            <p className="text-[10px] text-muted">{name}</p>
            <p className={`mt-1 text-sm font-semibold ${value > 0 ? "text-pine-700" : value < 0 ? "text-red-600" : "text-ink"}`}>
              {pct(value)}
            </p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-[11px] text-muted">
        Sinyal: {data?.signals ?? 0} · Win rate 7D: {pct(data?.return7dPct?.positiveRatePct)}
      </p>
    </div>
  );
}

export default function PumpRadarPage() {
  const [symbol, setSymbol] = useState("SEIUSDT");
  const [history, setHistory] = useState("365");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [asset, setAsset] = useState(null);
  const [backtest, setBacktest] = useState(null);

  const run = async (event) => {
    event?.preventDefault();
    const clean = symbol.trim().toUpperCase().replace(/[^A-Z0-9]/g, "");
    if (!clean) return;
    setLoading(true);
    setError("");
    try {
      const [liveResult, testResult] = await Promise.all([
        fetchPumpRadarV2(clean, Math.max(120, Number(history) || 365)),
        fetchPumpRadarV2Backtest(clean, Math.max(120, Number(history) || 365), 1),
      ]);
      setAsset(liveResult);
      setBacktest(testResult);
    } catch (err) {
      setError(err.message || "Pump Radar V2 gagal memuat data.");
      setAsset(null);
      setBacktest(null);
    } finally {
      setLoading(false);
    }
  };

  const m = asset?.metrics || {};
  const dormant = asset?.signals?.dormant;
  const active = asset?.signals?.active;

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 pb-14">
      <section className="pt-10 md:pt-14 pb-8 border-b border-line">
        <p className="micro-label text-gold-600">Dual detector · Closed daily candles</p>
        <div className="mt-3 flex flex-col lg:flex-row lg:items-end lg:justify-between gap-5">
          <div className="max-w-2xl">
            <h1 className="font-display text-4xl sm:text-5xl font-semibold tracking-tight text-ink">
              Pump Radar <span className="italic text-pine-700">V2.</span>
            </h1>
            <p className="mt-4 text-sm leading-6 text-muted max-w-xl">
              Memisahkan anomali volume saat harga masih tertahan dari ekspansi volume yang sudah
              disertai momentum harga. Menggabungkan Base Volume, Quote Volume, Price Demand,
              dan taker buy pressure.
            </p>
          </div>
          <form onSubmit={run} className="flex flex-wrap items-end gap-2">
            <label className="block">
              <span className="micro-label text-muted">Pair USDT</span>
              <input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="SEIUSDT"
                className="mt-1 w-36 rounded-lg border border-line bg-white px-3 py-2.5 text-sm outline-none focus:border-pine-600" />
            </label>
            <label className="block">
              <span className="micro-label text-muted">Histori</span>
              <select value={history} onChange={(e) => setHistory(e.target.value)}
                className="mt-1 rounded-lg border border-line bg-white px-3 py-2.5 text-sm outline-none focus:border-pine-600">
                <option value="180">180 hari</option>
                <option value="365">365 hari</option>
                <option value="730">730 hari</option>
              </select>
            </label>
            <button disabled={loading} className="btn-primary focus-ring disabled:opacity-60">
              <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
              {loading ? "Menganalisis…" : "Analisis"}
            </button>
          </form>
        </div>
      </section>

      {error && (
        <div className="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertTriangle size={16} className="inline mr-2" />{error}
        </div>
      )}

      {!asset && !loading && !error && (
        <div className="mt-8 rounded-2xl border border-dashed border-line p-8 text-center">
          <Search size={24} className="mx-auto text-muted" />
          <p className="mt-3 font-medium text-ink">Masukkan pair untuk menjalankan dua detektor</p>
          <p className="mt-1 text-sm text-muted">Default studi kasus: SEIUSDT · data Binance live</p>
        </div>
      )}

      {loading && (
        <div className="mt-8 grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 8 }).map((_, i) => <div key={i} className="skeleton h-24 rounded-xl" />)}
        </div>
      )}

      {asset && (
        <>
          <section className="py-6 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-display text-2xl font-semibold text-ink">{asset.symbol}</p>
              <p className="text-xs text-muted mt-1">
                {asset.bars} candle tertutup · {asset.source || "unknown source"} · {asset.live ? "LIVE" : "NON-LIVE"}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className={`rounded-full px-3 py-1.5 text-xs font-semibold ${dormant ? "bg-emerald-100 text-emerald-800" : "bg-stone-100 text-stone-600"}`}>
                {dormant ? "Dormant anomaly" : "Dormant: tidak aktif"}
              </span>
              <span className={`rounded-full px-3 py-1.5 text-xs font-semibold ${active ? "bg-sky-100 text-sky-800" : "bg-stone-100 text-stone-600"}`}>
                {active ? "Active expansion" : "Active: tidak aktif"}
              </span>
            </div>
          </section>

          {!asset.ok && (
            <div className="rounded-xl border border-gold-200 bg-gold-50 p-4 text-sm text-gold-800">
              Data belum cukup untuk penilaian: {asset.reason || asset.status}. Minimal 100 candle harian tertutup.
            </div>
          )}

          {asset.ok && (
            <>
              <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Metric label="Dormant score" value={fmt(asset.scores?.dormant, 1) + "/100"} note="Skor heuristik, bukan probabilitas" />
                <Metric label="Active score" value={fmt(asset.scores?.active, 1) + "/100"} note="Skor heuristik, bukan probabilitas" />
                <Metric label="Drawdown 90D" value={pct(m.drawdown90dPct)} />
                <Metric label="Price change 24H" value={pct(m.change24hPct)} />
                <Metric label="Base RVOL daily" value={mult(m.baseRvolDaily)} note="Jumlah token vs median 30D" />
                <Metric label="Quote RVOL daily" value={mult(m.quoteRvolDaily)} note="Nilai USDT vs median 30D" />
                <Metric label="Quote RVOL 7D" value={mult(m.quoteRvol7d)} note="Agregat 7D vs baseline terpisah" />
                <Metric label="Buy share" value={pct(m.buyShareQuotePct)} note={`Sell share: ${pct(m.sellShareBasePct)}`} />
              </section>

              <section className="mt-8">
                <div className="flex items-center gap-2 mb-3">
                  <Waves size={17} className="text-pine-700" />
                  <h2 className="font-display text-xl font-semibold">Volume & Price Demand</h2>
                </div>
                <div className="overflow-x-auto rounded-xl border border-line bg-white">
                  <table className="w-full text-sm">
                    <tbody>
                      {[
                        ["Base Volume 24H", fmt(m.baseVolume, 2)],
                        ["Base Volume 7D", fmt(m.baseVolume7d, 2)],
                        ["Base growth 7D", pct(m.baseGrowth7dPct)],
                        ["Quote Volume 24H", "$" + fmt(m.quoteVolumeUsdt, 2)],
                        ["Quote Volume 7D", "$" + fmt(m.quoteVolume7dUsdt, 2)],
                        ["Quote growth 7D", pct(m.quoteGrowth7dPct)],
                        ["Price change 7D", pct(m.change7dPct)],
                        ["Buy share (quote)", pct(m.buyShareQuotePct)],
                        ["Price Demand Efficiency", fmt(m.priceDemandEfficiency, 5)],
                        ["Quote/Base growth gap", m.volumePriceDistortionPctPoints === null ? "—" : fmt(m.volumePriceDistortionPctPoints) + " pp"],
                      ].map(([label, value]) => (
                        <tr key={label} className="border-b border-line last:border-0">
                          <td className="px-4 py-3 text-muted">{label}</td>
                          <td className="px-4 py-3 text-right font-mono font-medium text-ink">{value}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="mt-8 grid md:grid-cols-2 gap-3">
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-5">
                  <div className="flex items-center gap-2 text-emerald-800">
                    <Activity size={17} /><h2 className="font-semibold">A · Dormant Volume Anomaly</h2>
                  </div>
                  <p className="mt-2 text-sm text-muted">Drawdown besar, volume abnormal, tetapi harga 7D masih tertahan.</p>
                  <p className="mt-4 text-3xl font-display font-semibold text-ink">{fmt(asset.scores.dormant, 1)}<span className="text-sm text-muted"> / 100</span></p>
                  <p className="mt-2 text-xs text-muted">{dormant ? "Seluruh syarat pemicu terpenuhi." : "Syarat pemicu belum terpenuhi."}</p>
                </div>
                <div className="rounded-2xl border border-sky-200 bg-sky-50/50 p-5">
                  <div className="flex items-center gap-2 text-sky-800">
                    <BarChart3 size={17} /><h2 className="font-semibold">B · Active Volume Expansion</h2>
                  </div>
                  <p className="mt-2 text-sm text-muted">Lonjakan volume disertai kenaikan harga dan momentum positif.</p>
                  <p className="mt-4 text-3xl font-display font-semibold text-ink">{fmt(asset.scores.active, 1)}<span className="text-sm text-muted"> / 100</span></p>
                  <p className="mt-2 text-xs text-muted">{active ? "Seluruh syarat pemicu terpenuhi." : "Syarat pemicu belum terpenuhi."}</p>
                </div>
              </section>
            </>
          )}

          {backtest?.ok && (
            <section className="mt-10">
              <div className="flex items-center gap-2 mb-3">
                <BarChart3 size={17} className="text-pine-700" />
                <h2 className="font-display text-xl font-semibold">Walk-forward backtest</h2>
              </div>
              <p className="text-xs text-muted mb-4">
                {backtest.bars} candle · step {backtest.stepDays} hari · return dihitung setelah sinyal, tanpa memakai candle masa depan untuk mendeteksi sinyal.
              </p>
              <div className="grid md:grid-cols-2 gap-3">
                <Outcome label="A · Dormant Volume Anomaly" data={backtest.categories?.DORMANT_VOLUME_ANOMALY} />
                <Outcome label="B · Active Volume Expansion" data={backtest.categories?.ACTIVE_VOLUME_EXPANSION} />
              </div>
              <p className="mt-3 text-[11px] leading-5 text-muted">{backtest.note}</p>
            </section>
          )}
        </>
      )}

      <section className="mt-10 rounded-xl border border-gold-200 bg-gold-50/60 p-4">
        <p className="text-xs leading-5 text-gold-800">
          Catatan metodologi: Base Volume mengukur unit token, Quote Volume mengukur nilai transaksi USDT.
          Taker-buy share menunjukkan sisi agresor, bukan bukti whale accumulation. Parameter dan skor masih
          eksperimental sampai diuji lintas koin dan periode yang tidak dipakai untuk tuning.
        </p>
      </section>
    </div>
  );
}
