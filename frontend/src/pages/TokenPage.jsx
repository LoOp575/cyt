import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowLeft,
  CheckCircle2,
  CircleAlert,
  Clock,
  Lock,
  ShieldAlert,
  TrendingUp,
  XCircle,
} from "lucide-react";
import { fetchSymbol, fetchTokenIntel } from "../lib/api";
import { useLiveTickers } from "../lib/useLiveTickers";
import { fmtDate, fmtPct, fmtPrice, fmtProb, fmtUsdCompact } from "../lib/format";
import VerdictBadge from "../components/VerdictBadge";
import ScoreBar from "../components/ScoreBar";

function fmtUnlockDate(v) {
  if (v == null || v === "") return "—";
  const ms = typeof v === "number" ? v : Date.parse(String(v));
  if (Number.isNaN(ms)) return String(v);
  return new Date(ms).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
}

function IntelRow({ label, value, sub }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5 border-b border-line/60 last:border-0">
      <span className="text-[11px] text-muted shrink-0">{label}</span>
      <span className="text-right">
        <span className="font-mono text-[12.5px] font-semibold text-ink tabular-nums">{value}</span>
        {sub && <span className="block text-[9.5px] text-faint">{sub}</span>}
      </span>
    </div>
  );
}

function PlanDeniedNote({ text }) {
  return (
    <div className="rounded-lg border border-gold-200 bg-gold-100 px-3 py-2 flex items-start gap-2">
      <Lock size={13} strokeWidth={2} className="text-gold-700 mt-0.5 shrink-0" />
      <p className="text-[11px] leading-4 text-gold-700">{text}</p>
    </div>
  );
}

/** Kartu "Intel Koin" — konteks CryptoRank: profil, unlock, investor/funding. */
function TokenIntelCard({ symbol }) {
  const [intel, setIntel] = useState({ loading: true, data: null, error: null });

  useEffect(() => {
    let alive = true;
    setIntel({ loading: true, data: null, error: null });
    fetchTokenIntel(symbol)
      .then((data) => alive && setIntel({ loading: false, data, error: null }))
      .catch((err) => alive && setIntel({ loading: false, data: null, error: err.message || "Intel gagal dimuat." }));
    return () => {
      alive = false;
    };
  }, [symbol]);

  if (intel.loading) {
    return (
      <div className="mt-6 card px-5 py-4">
        <div className="flex items-center gap-2">
          <div className="skeleton h-4 w-44" />
        </div>
        <div className="skeleton h-20 w-full mt-3" />
      </div>
    );
  }

  const d = intel.data;
  if (intel.error || !d) {
    return (
      <div className="mt-6 card px-5 py-4">
        <h3 className="font-display text-base font-semibold">Intel koin (CryptoRank)</h3>
        <p className="text-[12px] text-muted mt-2">{intel.error || "Intel tidak tersedia."}</p>
      </div>
    );
  }

  const profile = d.profile || {};
  const p = profile.ok ? profile.data || {} : null;
  const unlock = d.unlock || {};
  const u = unlock.ok ? unlock.data || null : null;
  const funding = d.funding || {};
  const fd = funding.ok ? funding.data || {} : null;
  const plan = d.plan || {};

  return (
    <div className="mt-6 card px-5 py-4">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-base font-semibold">Intel koin — pasokan, unlock &amp; investor</h3>
        <span className="micro-label !text-[9px]">
          CryptoRank{plan.ok && plan.tier ? ` · ${plan.tier}` : ""}
        </span>
      </div>

      {!d.ok && d.reason && (
        <p className="mt-2 text-[11.5px] text-gold-700">{d.reason}</p>
      )}

      <div className="mt-3 grid lg:grid-cols-3 gap-5">
        {/* ---------- profil pasar ---------- */}
        <div>
          <p className="micro-label !text-[9px] mb-1.5">Profil pasar</p>
          {p ? (
            <div>
              <IntelRow label="Nama" value={p.name || "—"} sub={p.slug ? `cryptorank.io/coins/${p.slug}` : null} />
              <IntelRow label="Rank" value={p.rank ?? "—"} />
              <IntelRow label="Market cap" value={fmtUsdCompact(p.marketCap)} />
              <IntelRow label="FDV" value={fmtUsdCompact(p.fullyDilutedValuation)} />
              <IntelRow
                label="Supply beredar"
                value={p.circulatingSupply != null ? Number(p.circulatingSupply).toLocaleString("en-US", { notation: "compact", maximumFractionDigits: 2 }) : "—"}
                sub={p.totalSupply != null ? `total ${Number(p.totalSupply).toLocaleString("en-US", { notation: "compact", maximumFractionDigits: 2 })}` : null}
              />
            </div>
          ) : (
            <p className="text-[11.5px] text-muted leading-4">{profile.reason || "Profil tidak tersedia."}</p>
          )}
        </div>

        {/* ---------- unlock ---------- */}
        <div>
          <p className="micro-label !text-[9px] mb-1.5">Token unlock · 30 hari ke depan</p>
          {unlock.ok && u ? (
            <div className="rounded-lg border border-line bg-paper px-3 py-2.5">
              <p className="font-mono text-[13px] font-semibold text-[#8A3324] tabular-nums">
                {u.percentOfMcap != null ? `${u.percentOfMcap.toFixed(2)}% dari market cap` : "—"}
              </p>
              <p className="text-[11px] text-muted mt-0.5">
                Jadwal <strong>{fmtUnlockDate(u.date)}</strong>
                {u.unlockValueUsd != null && <> · nilai {fmtUsdCompact(u.unlockValueUsd)}</>}
                {u.tokens != null && <> · {Number(u.tokens).toLocaleString("en-US", { notation: "compact", maximumFractionDigits: 2 })} token</>}
              </p>
              <p className="text-[10px] text-faint mt-1.5 leading-4">
                Informasi jadwal unlock saja. Data ini tidak masuk ke skor, filter, ranking, atau verdict model.
              </p>
            </div>
          ) : unlock.planDenied ? (
            <PlanDeniedNote text={unlock.reason || "Feed unlock butuh paket Pro CryptoRank."} />
          ) : (
            <div className="flex items-start gap-2 text-[11.5px] text-up leading-4">
              <CheckCircle2 size={14} strokeWidth={2} className="mt-0.5 shrink-0" />
              <span>{unlock.reason || "Tidak ada unlock besar terjadwal dalam 30 hari."}</span>
            </div>
          )}
        </div>

        {/* ---------- investor / funding ---------- */}
        <div>
          <p className="micro-label !text-[9px] mb-1.5">Investor &amp; funding</p>
          {fd ? (
            <div>
              <IntelRow label="Total dana terkumpul" value={fmtUsdCompact(fd.totalRaiseUsd)} />
              <IntelRow label="Valuasi terakhir" value={fmtUsdCompact(fd.lastValuationUsd)} />
              <IntelRow label="Jumlah ronde" value={String((fd.rounds || []).length)} />
              {(fd.investors || []).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {fd.investors.slice(0, 12).map((inv) => (
                    <span
                      key={inv.name}
                      className={`chip text-[10px] ${inv.isLead ? "border-gold-300 bg-gold-100 text-gold-700 font-semibold" : "border-lineStrong text-muted"}`}
                      title={inv.isLead ? "Lead investor" : inv.tier ? `Tier ${inv.tier}` : "Investor"}
                    >
                      {inv.isLead ? "★ " : ""}{inv.name}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ) : funding.planDenied ? (
            <PlanDeniedNote text={funding.reason || "Data investor butuh paket Pro CryptoRank."} />
          ) : (
            <p className="text-[11.5px] text-muted leading-4">{funding.reason || "Data investor tidak tersedia."}</p>
          )}
        </div>
      </div>

      {/* ---------- riwayat ronde pendanaan ---------- */}
      {fd && (fd.rounds || []).length > 0 && (
        <div className="mt-4 border-t border-line pt-3 overflow-x-auto">
          <table className="data-table min-w-[560px]">
            <thead>
              <tr>
                <th>Tanggal</th>
                <th>Tahap</th>
                <th className="text-right">Dana</th>
                <th className="text-right">Valuasi</th>
                <th>Investor utama</th>
              </tr>
            </thead>
            <tbody>
              {fd.rounds.slice(0, 6).map((r, i) => {
                const lead = (r.funds || []).find((x) => x.isLead) || (r.funds || [])[0];
                return (
                  <tr key={i}>
                    <td className="font-mono text-[11px]">{fmtUnlockDate(r.date)}</td>
                    <td className="text-[12px]">{r.stage || "—"}</td>
                    <td className="text-right font-mono text-[11.5px]">{fmtUsdCompact(r.raiseUsd)}</td>
                    <td className="text-right font-mono text-[11.5px]">{fmtUsdCompact(r.valuationUsd)}</td>
                    <td className="text-[12px]">{lead ? lead.name : "—"}{(r.funds || []).length > 1 && <span className="text-faint"> +{r.funds.length - 1}</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-[9px] text-faint mt-3 leading-4">
        Sumber: CryptoRank (informasi tambahan). Data unlock hanya ditampilkan sebagai konteks pasokan dan tidak memengaruhi skor, filter, ranking, atau verdict. Blok yang tidak tersedia diberi alasan eksplisit, bukan digarisi data kosong.
      </p>
    </div>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-lineStrong bg-card px-3 py-2 shadow-lift text-[11px]">
      <p className="font-mono text-[10px] uppercase tracking-micro text-muted mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="font-mono tabular-nums text-ink flex items-center justify-between gap-4">
          <span className="text-muted">{p.name}</span>
          <span>{p.dataKey === "close" ? `$${fmtPrice(p.value)}` : p.dataKey === "takerBuyRatio" ? p.value.toFixed(3) : fmtUsdCompact(p.value)}</span>
        </p>
      ))}
    </div>
  );
}

function MetricTile({ label, value, sub, tone = "ink" }) {
  const color = tone === "up" ? "text-up" : tone === "down" ? "text-down" : tone === "gold" ? "text-gold-600" : "text-ink";
  return (
    <div className="rounded-xl border border-line bg-paper px-4 py-3">
      <p className="micro-label !text-[9px]">{label}</p>
      <p className={`mt-1 font-mono text-[15px] font-semibold tabular-nums ${color}`}>{value}</p>
      {sub && <p className="text-[10px] text-muted mt-0.5 leading-4">{sub}</p>}
    </div>
  );
}

export default function TokenPage() {
  const { symbol } = useParams();
  const [state, setState] = useState({ loading: true, error: null, data: null });
  const { ticks: liveTicks, live } = useLiveTickers(symbol ? [symbol] : []);

  useEffect(() => {
    let alive = true;
    setState({ loading: true, error: null, data: null });
    fetchSymbol(symbol)
      .then((data) => alive && setState({ loading: false, error: null, data }))
      .catch((err) => alive && setState({ loading: false, error: err.message || "Failed to load asset.", data: null }));
    return () => {
      alive = false;
    };
  }, [symbol]);

  if (state.loading) {
    return (
      <div className="mx-auto max-w-7xl px-4 sm:px-6 py-10">
        <div className="skeleton h-5 w-40" />
        <div className="skeleton h-12 w-72 mt-6" />
        <div className="skeleton h-64 w-full mt-8" />
      </div>
    );
  }

  if (state.error || !state.data) {
    return (
      <div className="mx-auto max-w-3xl px-4 sm:px-6 py-16 text-center">
        <XCircle size={40} strokeWidth={1.5} className="text-down mx-auto" />
        <h1 className="font-display text-2xl font-semibold mt-4">Couldn’t load {symbol}</h1>
        <p className="text-muted text-sm mt-2">{state.error}</p>
        <Link to="/" className="btn-primary focus-ring mt-6 inline-flex">Back to screener</Link>
      </div>
    );
  }

  const d = state.data;
  // Koin ASLI tapi riwayatnya belum mencapai MIN_BARS: bukan demo, bukan error.
  if (d.insufficient) {
    const bars = d.bars ?? 0;
    const minBars = d.minBars ?? 61;
    return (
      <div className="mx-auto max-w-3xl px-4 sm:px-6 py-12">
        <Link to="/" className="inline-flex items-center gap-2 text-[12px] font-medium text-muted hover:text-pine-700 transition-colors focus-ring rounded">
          <ArrowLeft size={14} strokeWidth={2} /> Back to screener
        </Link>
        <h1 className="font-display text-4xl sm:text-5xl font-semibold tracking-tight text-ink mt-6">
          {String(d.symbol || "").replace(/USDT$/, "")}
          <span className="text-faint text-3xl align-top">/USDT</span>
        </h1>
        <div className="mt-5 rounded-xl border border-gold-300 bg-gold-100 px-4 py-3 flex items-start gap-3">
          <Clock size={17} strokeWidth={1.75} className="text-gold-700 mt-0.5 shrink-0" />
          <div className="text-[12px] leading-5 text-gold-700">
            <p className="font-semibold">Belum bisa dianalisis — riwayat koin terlalu pendek.</p>
            <p className="mt-1">
              Koin ini <em>terdaftar</em> di bursa dan datanya <em>asli</em> (dari {d.sources?.klines || "bursa"}),
              tetapi baru <span className="font-mono font-semibold">{bars}/{minBars}</span> candle harian.
              Model butuh {minBars} hari untuk menilai kualitas permintaan. Bukan data simulasi.
            </p>
          </div>
        </div>
        <p className="mt-4 text-[11px] text-faint">
          Harga terakhir: <span className="font-mono text-ink">${fmtPrice(d.price)}</span>
          {d.market?.quoteVolume ? ` · volume 24h ${fmtUsdCompact(d.market.quoteVolume)}` : ""}
        </p>
        {(d.series || []).length > 0 && (
          <p className="mt-1 text-[11px] text-faint">
            {d.series.length} candle harian asli tersimpan — akan otomatis bisa dinilai setelah mencapai {minBars} hari.
          </p>
        )}
      </div>
    );
  }

  const f = d.features || {};
  const s = d.scores || {};
  const m = d.market || {};
  const risk = d.risk || {};
  const filters = d.filters || {};
  const liveTick = liveTicks[String(symbol || "").toUpperCase()];
  const change = liveTick?.changePercent ?? m.priceChangePercent ?? 0;
  const headlinePrice = liveTick?.price ?? d.price;
  const isDemo = d.sources ? !d.sources.live : true;
  const series = (d.series || []).map((p) => ({ ...p, label: fmtDate(p.t) }));
  const triggeredFilters = Object.entries(filters).filter(([, v]) => v === true).map(([k]) => k);

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 py-8 md:py-10">
      {/* ---------- breadcrumb + headline ---------- */}
      <Link to="/" className="inline-flex items-center gap-2 text-[12px] font-medium text-muted hover:text-pine-700 transition-colors focus-ring rounded">
        <ArrowLeft size={14} strokeWidth={2} /> Back to screener
      </Link>

      <div className="mt-5 flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 border-b border-line pb-6">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-display text-4xl sm:text-5xl font-semibold tracking-tight text-ink">
              {d.symbol.replace(/USDT$/, "")}
              <span className="text-faint text-3xl align-top">/USDT</span>
            </h1>
            <VerdictBadge tone={d.verdictTone} label={d.verdictLabel || d.verdict} size="lg" />
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-4 font-mono text-[12px] tabular-nums">
            <span className="text-xl text-ink font-semibold">${fmtPrice(headlinePrice)}</span>
            <span className={change >= 0 ? "text-up" : "text-down"}>
              {change >= 0 ? "▲" : "▼"} {Math.abs(change).toFixed(2)}% 24h
            </span>
            {live && (
              <span className="chip-live" title="Price streaming live from Binance public WebSocket">
                <span className="live-dot" /> Live
              </span>
            )}
            {m.quoteVolume != null && <span className="text-muted">24h vol {fmtUsdCompact(m.quoteVolume)}</span>}
            <span className="text-faint">VWAP-20 {fmtPrice(f.vwap20)} ({fmtPct(f.closeVsVwap20, { signed: true })})</span>
          </div>
          <p className="micro-label !text-[9px] mt-3">
            {isDemo ? "Seed candles (bukan data bursa)" : `Live candles · ${d.sources?.klines}`} · last 90 daily bars
          </p>
        </div>
        <div className="flex items-center gap-2">
          <TrendingUp size={16} className="text-gold-500" strokeWidth={1.75} />
          <p className="text-[11px] text-muted max-w-[220px] leading-4">Accumulation thesis: demand building ahead of price recognition.</p>
        </div>
      </div>

      {/* ---------- verdict banner ---------- */}
      <div className="mt-6 rounded-2xl bg-pine-800 text-paper px-6 py-6 md:px-8 md:py-7 shadow-card">
        <p className="micro-label !text-gold-300">Model verdict</p>
        <h2 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight mt-2 text-paper">{d.verdictLabel || d.verdict}</h2>
        <ul className="mt-4 grid md:grid-cols-2 gap-x-8 gap-y-2.5">
          {(d.reasons || []).map((reason, i) => {
            const negative = /reject|flat\/negative|died|exodus|excluded|no edge|not met/i.test(reason);
            const Icon = negative ? XCircle : CheckCircle2;
            return (
              <li key={i} className="flex items-start gap-2.5 text-[12.5px] leading-5 text-pine-100">
                <Icon size={15} strokeWidth={2} className={`mt-0.5 shrink-0 ${negative ? "text-[#E8A79A]" : "text-gold-300"}`} />
                <span>{reason}</span>
              </li>
            );
          })}
        </ul>
      </div>

      {/* ---------- trigger chips ---------- */}
      {triggeredFilters.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="micro-label !text-[9px]">Triggered filters:</span>
          {triggeredFilters.map((key) => (
            <span key={key} className="chip border-[#E3B7AC] bg-[#F6E4E0] text-[#8A3324]">{key.replace(/([A-Z])/g, " $1").trim()}</span>
          ))}
        </div>
      )}

      {/* ---------- charts + evidence ---------- */}
      <div className="mt-6 grid lg:grid-cols-3 gap-4">
        <div className="card p-5 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-base font-semibold">Price vs demand accumulation</h3>
            <span className="micro-label !text-[9px]">90d · daily</span>
          </div>
          <div className="h-56 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={series} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="#ECE9E2" strokeDasharray="3 4" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#9AA096" }} tickLine={false} axisLine={false} minTickGap={40} />
                <YAxis domain={["dataMin", "dataMax"]} tick={{ fontSize: 10, fill: "#9AA096" }} tickLine={false} axisLine={false} width={52} tickFormatter={(v) => (v >= 1000 ? v.toLocaleString("en-US", { notation: "compact" }) : v)} />
                <Tooltip content={<ChartTooltip />} />
                <ReferenceLine y={f.vwap20} stroke="#B18A44" strokeDasharray="6 5" strokeWidth={1.25} />
                <Area type="monotone" dataKey="close" name="Close" stroke="#144338" strokeWidth={2} fill="#144338" fillOpacity={0.09} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <h4 className="font-display text-sm font-semibold mt-5 text-ink">Unit volume vs buy-side share</h4>
          <div className="h-44 mt-2">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={series} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="#ECE9E2" strokeDasharray="3 4" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#9AA096" }} tickLine={false} axisLine={false} minTickGap={40} />
                <YAxis yAxisId="vol" orientation="left" tick={{ fontSize: 10, fill: "#9AA096" }} tickLine={false} axisLine={false} width={46} tickFormatter={(v) => v.toLocaleString("en-US", { notation: "compact", maximumFractionDigits: 1 })} />
                <YAxis yAxisId="ratio" orientation="right" domain={[0.3, 0.75]} tick={{ fontSize: 10, fill: "#9AA096" }} tickLine={false} axisLine={false} width={30} tickFormatter={(v) => v.toFixed(2)} />
                <Tooltip content={<ChartTooltip />} />
                <Bar yAxisId="vol" dataKey="baseVolume" name="Base volume" fill="#D2B985" radius={[2, 2, 0, 0]} maxBarSize={14} />
                <Line yAxisId="ratio" type="monotone" dataKey="takerBuyRatio" name="Taker buy" stroke="#1F4A38" strokeWidth={1.75} dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ---------- evidence panel ---------- */}
        <div className="card p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-base font-semibold">Evidence</h3>
            <span className="micro-label !text-[9px]">0–100</span>
          </div>
          <ScoreBar label="Demand quality" value={s.demandQuality ?? 0} tone="pine" />
          <ScoreBar label="Signal strength" value={s.signal ?? 0} tone="gold" />
          <ScoreBar label="Instability risk" value={s.instability ?? 0} tone="red" invertNote="Higher = more filing-style red flags. Excluded from longs at ≥ 55." />
          <div className="border-t border-line pt-4 grid grid-cols-2 gap-3">
            <div>
              <p className="micro-label !text-[9px]">p(acceleration)</p>
              <p className="font-mono text-2xl font-semibold text-pine-800 tabular-nums mt-1">{fmtProb(s.pAcceleration)}</p>
              <p className="text-[10px] text-muted leading-4 mt-0.5">heuristic, uncalibrated</p>
            </div>
            <div>
              <p className="micro-label !text-[9px]">p(adverse event)</p>
              <p className="font-mono text-2xl font-semibold text-down tabular-nums mt-1">{fmtProb(s.pAdverse)}</p>
              <p className="text-[10px] text-muted leading-4 mt-0.5">instability tail risk proxy</p>
            </div>
          </div>
          <div className="border-t border-line pt-4">
            <p className="micro-label !text-[9px] mb-2">Red-flag scan · 30d</p>
            {risk.abnormalEvents30d > 0 ? (
              <div className="flex items-start gap-2.5 text-[12px] leading-5 text-[#8A3324]">
                <ShieldAlert size={16} strokeWidth={2} className="mt-0.5 shrink-0" />
                <span>
                  <strong>{risk.abnormalEvents30d} abnormal-move day{risk.abnormalEvents30d > 1 ? "s" : ""}</strong> detected (clustered: {fmtPct(risk.clusteredEvents, { digits: 0 })}).
                  Correction magnitude {(risk.correctionMagnitude ?? 0).toFixed(2)} vs normal days.
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-2.5 text-[12px] text-up">
                <CheckCircle2 size={16} strokeWidth={2} />
                <span>No abnormal-move days in the last 30 sessions.</span>
              </div>
            )}
            <p className="text-[9px] text-faint mt-2 leading-4">Internal-control inputs (material weakness disclosures) have no public crypto equivalent — explicitly unscored.</p>
          </div>
        </div>
      </div>

      {/* ---------- metric grid ---------- */}
      <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricTile label="Organic demand Δ30d" value={fmtPct(f.gOrganic, { signed: true })} tone={f.gOrganic >= 0 ? "up" : "down"} sub={`vs reported USD ${fmtPct(f.gQuoteVolReported, { signed: true })}`} />
        <MetricTile label="Acceleration" value={fmtPct(f.acceleration, { signed: true })} tone={f.acceleration >= 0 ? "up" : "down"} sub="demand growth vs prior window" />
        <MetricTile label="Lead vs price" value={fmtPct(f.leadVsPrice, { signed: true })} tone={f.leadVsPrice >= 0 ? "up" : "down"} sub="organic demand − price growth" />
        <MetricTile label="Demand–price gap" value={fmtPct(f.gap, { signed: true })} tone="gold" sub="under-recognition multiple" />
        <MetricTile label="Cash conversion" value={(f.cashConversion ?? 0).toFixed(2)} sub="taker buy share of unit volume" />
        <MetricTile label="Flow stability" value={(f.flowStability ?? 0).toFixed(2)} sub="participation trend decay" />
        <MetricTile label="Retention quality" value={(f.retentionQuality ?? 0).toFixed(2)} sub="NRR & GRR analogs, churn-penalised" />
        <MetricTile label="Distortion removed" value={fmtPct(f.distortionRemoved, { signed: true })} sub="price & mix stripped from reported growth" />
      </div>

      {/* ---------- CryptoRank intel: unlock, investor, profil pasar ---------- */}
      <TokenIntelCard symbol={symbol} />

      {/* ---------- exit triggers ---------- */}
      <div className="mt-6 card px-5 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-start gap-3">
          <CircleAlert size={18} strokeWidth={1.75} className="text-warn mt-0.5 shrink-0" />
          <div>
            <p className="micro-label !text-[9px]">Exit triggers for existing positions</p>
            {(d.exitTriggers || []).length > 0 ? (
              <ul className="mt-1.5 text-[12px] text-ink leading-5 list-disc list-inside">
                {d.exitTriggers.map((t) => <li key={t}>{t}</li>)}
              </ul>
            ) : (
              <p className="mt-1.5 text-[12px] text-muted">No exit trigger active: organic demand positive, engagement stable.</p>
            )}
          </div>
        </div>
        <Link to="/methodology" className="btn-ghost focus-ring shrink-0">Read the model</Link>
      </div>
    </div>
  );
}
