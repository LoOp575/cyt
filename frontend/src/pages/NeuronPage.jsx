import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity, ArrowLeft, BrainCircuit, Check, CircleAlert, Clock3, Database,
  GitBranch, History, RefreshCw, ShieldCheck, Target,
} from "lucide-react";
import {
  fetchNeuronLiveStatus, fetchNeuronLiveJournal, fetchNeuronLiveAudit,
} from "../lib/api";

const FEATURE_META = [
  ["screenSignal", "Screen signal", "Screen-v2"],
  ["demandQuality", "Demand quality", "Demand"],
  ["stability", "Stability", "Flow"],
  ["fpStable", "FP stable", "Fokker–Planck"],
  ["fpTail", "FP tail", "Tail risk"],
  ["fpLiveDir", "FP live direction", "Intraday"],
  ["rvol", "Relative volume", "Volume"],
  ["vwapDist", "VWAP distance", "Price"],
  ["bias", "Bias", "Constant"],
];
const TABS = [
  ["live", "Live neural", Activity],
  ["synapse", "Synapse & weights", GitBranch],
  ["journal", "Prediction journal", History],
  ["audit", "Self audit", ShieldCheck],
];

function fmt(value, digits = 3) {
  return value === null || value === undefined || value === "" || !Number.isFinite(Number(value)) ? "—" : Number(value).toFixed(digits);
}
function fmtPrice(value) {
  return Number.isFinite(Number(value))
    ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(Number(value))
    : "—";
}
function fmtTime(value) {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString("id-ID", { hour12: false });
}
function tone(direction) {
  const d = String(direction || "").toUpperCase();
  if (d === "UP" || d === "LONG") return "up";
  if (d === "DOWN" || d === "SHORT" || d === "AVOID") return "down";
  return "flat";
}
function Stat({ label, value, detail, accent = "" }) {
  return <div className="rounded-xl border border-line bg-card p-3 sm:p-4 min-w-0">
    <div className="micro-label">{label}</div>
    <div className={`mt-2 font-display text-2xl sm:text-[28px] font-semibold tracking-tight ${accent}`}>{value ?? "—"}</div>
    {detail && <div className="mt-1 text-[11px] text-muted truncate">{detail}</div>}
  </div>;
}
function Signal({ label, state }) {
  const ok = state === true;
  return <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[10px] font-mono ${ok ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
    <span className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-emerald-500" : "bg-amber-500"}`} />{label}
  </span>;
}
function NeuralMap({ weights = {}, contributions = {} }) {
  const nodes = [
    { id: "screenSignal", x: 34, y: 42 }, { id: "demandQuality", x: 34, y: 105 },
    { id: "stability", x: 34, y: 168 }, { id: "fpStable", x: 34, y: 231 },
    { id: "fpTail", x: 34, y: 294 }, { id: "fpLiveDir", x: 34, y: 357 },
    { id: "rvol", x: 34, y: 420 }, { id: "vwapDist", x: 34, y: 483 },
    { id: "bias", x: 34, y: 546 },
  ];
  return <div className="neural-map relative overflow-hidden rounded-2xl border border-[#203B34] bg-[#0B1916] p-3 sm:p-5">
    <div className="absolute inset-0 neural-grid opacity-50" />
    <div className="relative flex items-center justify-between gap-2 text-[9px] uppercase tracking-[.18em] text-[#89A99A]">
      <span>Input dendrites</span><span>Synaptic pathways</span><span>Output</span>
    </div>
    <svg viewBox="0 0 760 590" role="img" aria-label="Diagram jaringan neuron dengan sembilan input yang terhubung ke neuron utama dan output" className="relative mt-3 w-full min-w-[520px]">
      <defs>
        <radialGradient id="neuronGlow"><stop offset="0%" stopColor="#6EE7B7" stopOpacity=".9"/><stop offset="100%" stopColor="#34D399" stopOpacity=".08"/></radialGradient>
        <filter id="softGlow"><feGaussianBlur stdDeviation="5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      {nodes.map((n, i) => {
        const c = Number(contributions[n.id] || 0);
        const w = Number(weights[n.id] || 0);
        const color = c >= 0 ? "#4ADE80" : "#FB7185";
        const opacity = Math.max(.18, Math.min(.95, Math.abs(w) * 1.8));
        return <g key={n.id}>
          <path d={`M 104 ${n.y} C 210 ${n.y}, 230 294, 332 294`} stroke={color} strokeWidth={1 + Math.min(4, Math.abs(w) * 3)} opacity={opacity} fill="none" strokeDasharray="7 8" className="synapse-flow"/>
          <circle cx="34" cy={n.y} r="15" fill="#16352C" stroke={color} strokeWidth="1.5"/>
          <circle cx="34" cy={n.y} r="4" fill={color}/>
          <text x="60" y={n.y + 4} fill="#D5E7DE" fontSize="12">{n.id}</text>
          <text x="300" y={n.y + 4} fill="#89A99A" fontSize="10" textAnchor="end">{w >= 0 ? "+" : ""}{w.toFixed(2)}</text>
        </g>;
      })}
      <circle cx="405" cy="294" r="78" fill="url(#neuronGlow)" opacity=".65"/>
      <circle cx="405" cy="294" r="54" fill="#15382D" stroke="#6EE7B7" strokeWidth="2" filter="url(#softGlow)"/>
      <circle cx="405" cy="294" r="38" fill="#0F2922" stroke="#2E8064" strokeWidth="1"/>
      <path d="M405 267 L405 321 M378 294 L432 294 M386 275 L424 313 M424 275 L386 313" stroke="#A7F3D0" strokeWidth="2" strokeLinecap="round" opacity=".8"/>
      <text x="405" y="370" fill="#D5E7DE" fontSize="13" textAnchor="middle" fontWeight="600">NEURON CORE</text>
      <text x="405" y="388" fill="#89A99A" fontSize="10" textAnchor="middle">tanh · RMSProp</text>
      <path d="M459 294 C 520 294, 530 294, 600 294" stroke="#6EE7B7" strokeWidth="3" fill="none" className="synapse-flow"/>
      <circle cx="630" cy="294" r="47" fill="#17372D" stroke="#6EE7B7" strokeWidth="2"/>
      <circle cx="630" cy="294" r="34" fill="#10251F" stroke="#327A60"/>
      <path d="M615 294 L626 305 L647 281" fill="none" stroke="#A7F3D0" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
      <text x="630" y="365" fill="#D5E7DE" fontSize="12" textAnchor="middle">PREDICTION</text>
      <text x="630" y="382" fill="#89A99A" fontSize="10" textAnchor="middle">UP / DOWN / FLAT</text>
    </svg>
    <div className="relative mt-1 flex flex-wrap items-center justify-between gap-2 text-[10px] text-[#89A99A]">
      <span>Line weight = synapse strength</span><span>Green = positive · rose = negative contribution</span>
    </div>
  </div>;
}
function WeightRow({ name, label, weight, contribution }) {
  const w = Number(weight || 0), c = Number(contribution || 0);
  const width = Math.min(100, Math.abs(w) / 1.5 * 100);
  return <div className="grid grid-cols-[minmax(0,1fr)_72px_82px] items-center gap-3 border-b border-line py-3 last:border-0">
    <div className="min-w-0">
      <div className="text-[12px] font-medium text-ink">{label}</div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-pine-50">
        <div className={`h-full rounded-full ${w < 0 ? "bg-rose-400" : "bg-emerald-500"}`} style={{ width: `${width}%` }} />
      </div>
    </div>
    <div className="text-right font-mono text-[11px] text-ink">{w >= 0 ? "+" : ""}{fmt(w, 4)}</div>
    <div className={`text-right font-mono text-[11px] ${c < 0 ? "text-rose-600" : "text-emerald-700"}`}>{c >= 0 ? "+" : ""}{fmt(c, 4)}</div>
  </div>;
}

export default function NeuronPage() {
  const [tab, setTab] = useState("live");
  const [status, setStatus] = useState(null);
  const [journal, setJournal] = useState([]);
  const [audit, setAudit] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [now, setNow] = useState(Date.now());

  const refresh = useCallback(async (quiet = false) => {
    if (quiet) setRefreshing(true); else setLoading(true);
    setError("");
    try {
      const [s, j, a] = await Promise.all([
        fetchNeuronLiveStatus(), fetchNeuronLiveJournal(40), fetchNeuronLiveAudit(),
      ]);
      setStatus(s); setJournal(j.rows || []); setAudit(a);
    } catch (e) {
      setError(e.message || "Gagal mengambil status Neuron.");
      setStatus((old) => old || { configured: false, live: false });
    } finally {
      setLoading(false); setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const poll = window.setInterval(() => refresh(true), 30000);
    const clock = window.setInterval(() => setNow(Date.now()), 1000);
    return () => { window.clearInterval(poll); window.clearInterval(clock); };
  }, [refresh]);

  const latest = status?.latestPrediction || journal[0] || null;
  const model = status?.model || {};
  const weights = model.state?.weights || {};
  const contributions = latest?.contributions || {};
  const countdown = 300 - (Math.floor(now / 1000) % 300);
  const pct = Math.max(0, Math.min(100, (300 - countdown) / 3));
  const activeTab = TABS.find((x) => x[0] === tab);
  const featuresAvailable = status?.featureHealth || {};
  const directionTone = tone(latest?.direction || latest?.verdict);
  const accuracy = audit?.metrics?.directionalAccuracy;

  const pendingCount = status?.pendingCount ?? journal.filter((r) => r.status === "pending").length;
  const labeledCount = audit?.metrics?.samples ?? status?.labeledCount ?? 0;

  return <main className="mx-auto max-w-[1440px] px-3 pb-12 pt-5 sm:px-6 lg:px-8">
    <div className="mb-5 flex items-center justify-between gap-3">
      <Link to="/" className="inline-flex items-center gap-2 rounded-lg text-xs font-medium text-muted hover:text-pine-700 focus-ring">
        <ArrowLeft size={15}/> Screener
      </Link>
      <button onClick={() => refresh(true)} disabled={refreshing} className="btn-ghost focus-ring px-3 py-2 text-xs disabled:opacity-50">
        <RefreshCw size={13} className={refreshing ? "animate-spin" : ""}/> Refresh
      </button>
    </div>

    <section className="relative overflow-hidden rounded-2xl border border-[#203B34] bg-[#0B1916] p-4 text-white sm:p-6">
      <div className="absolute -right-24 -top-28 h-80 w-80 rounded-full bg-emerald-400/10 blur-3xl"/>
      <div className="relative grid gap-6 xl:grid-cols-[1.15fr_.85fr]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300/25 bg-emerald-300/10 px-3 py-1 text-[10px] font-mono uppercase tracking-[.16em] text-emerald-200">
              <span className="live-dot"/> Neuron live core
            </span>
            <span className="text-[10px] font-mono uppercase tracking-[.16em] text-[#86A99A]">BTCUSDT · 5 minute cycle</span>
          </div>
          <h1 className="mt-4 font-display text-3xl font-semibold tracking-tight sm:text-5xl">A network that<br className="hidden sm:block"/> learns from its own calls.</h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-[#A8BDB3]">Setiap siklus membuat prediksi, menyimpan snapshot model, lalu menunggu harga aktual untuk mengaudit hasilnya. Bobot aktif tidak berubah diam-diam.</p>
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <Signal label={status?.configured ? "Database connected" : "Database not connected"} state={status?.configured === true}/>
            <Signal label={status?.cronReady ? "Scheduler configured" : "Scheduler not verified"} state={status?.cronReady === true}/>
            <Signal label={status?.live ? "Market feed live" : "Market feed waiting"} state={status?.live === true}/>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 self-end">
          <div className="rounded-xl border border-white/10 bg-white/[.04] p-4">
            <div className="text-[10px] uppercase tracking-[.16em] text-[#8CA99B]">Next cycle in</div>
            <div className="mt-2 font-mono text-4xl font-semibold tabular-nums">{String(Math.floor(countdown / 60)).padStart(2,"0")}:{String(countdown % 60).padStart(2,"0")}</div>
            <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-emerald-300 transition-all" style={{width:`${pct}%`}}/></div>
            <div className="mt-2 text-[10px] text-[#8CA99B]">UI clock · not scheduler proof</div>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[.04] p-4">
            <div className="text-[10px] uppercase tracking-[.16em] text-[#8CA99B]">Latest prediction</div>
            <div className={`mt-2 text-3xl font-semibold ${directionTone === "up" ? "text-emerald-300" : directionTone === "down" ? "text-rose-300" : "text-slate-200"}`}>{latest?.direction || latest?.verdict || "—"}</div>
            <div className="mt-1 font-mono text-sm text-[#B7C9C0]">{latest ? `${(Number(latest.probability_up || 0) * 100).toFixed(1)}% UP score` : "Awaiting first record"}</div>
            <div className="mt-3 text-[10px] text-[#8CA99B]">{latest ? fmtTime(latest.created_at || latest.generated_at) : "No stored prediction yet"}</div>
          </div>
        </div>
      </div>
    </section>

    <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Stat label="Predictions stored" value={status?.predictionCount ?? "—"} detail="Immutable journal records"/>
      <Stat label="Awaiting outcome" value={pendingCount} detail="Next 5m close not labeled"/>
      <Stat label="Audited samples" value={labeledCount} detail="Only matured predictions"/>
      <Stat label="Directional accuracy" value={accuracy == null ? "—" : `${(accuracy * 100).toFixed(1)}%`} detail="Historical, not a guarantee" accent="text-emerald-700"/>
    </div>

    {error && <div role="alert" className="mt-4 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800"><CircleAlert size={15} className="mt-0.5 shrink-0"/><span>{error}. Pastikan env database dan API sudah dikonfigurasi.</span></div>}
    {!status?.configured && !loading && <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900"><strong>Persistent storage belum tersambung.</strong> UI sudah siap, tetapi belum akan mengarang data live. Tambahkan SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, dan NEURON_CRON_SECRET pada environment Vercel, lalu jalankan migration yang disertakan.</div>}

    <div className="mt-6 flex gap-1 overflow-x-auto border-b border-line" role="tablist" aria-label="Neuron sections">
      {TABS.map(([id, label, Icon]) => <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)} className={`inline-flex shrink-0 items-center gap-2 border-b-2 px-3 py-3 text-xs font-medium transition-colors focus-ring ${tab === id ? "border-pine-700 text-pine-800" : "border-transparent text-muted hover:text-ink"}`}>
        <Icon size={14}/>{label}
      </button>)}
    </div>

    <div className="mt-5">
      {tab === "live" && <div className="grid gap-5 xl:grid-cols-[1.2fr_.8fr]">
        <section className="min-w-0">
          <div className="mb-3 flex items-center justify-between gap-3"><div><div className="micro-label">Neural topology</div><h2 className="mt-1 font-display text-xl font-semibold">Signal pathways</h2></div><span className="text-[10px] text-muted">9 dendrites · 1 core · 1 output</span></div>
          <NeuralMap weights={weights} contributions={contributions}/>
        </section>
        <section className="space-y-4">
          <div className="card p-4 sm:p-5">
            <div className="flex items-center justify-between"><div><div className="micro-label">Prediction snapshot</div><h2 className="mt-1 font-display text-lg font-semibold">BTC / USDT</h2></div><span className="chip">{latest?.model_version || model.state?.version || "model —"}</span></div>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <div><div className="micro-label">Reference price</div><div className="mt-1 font-mono text-xl font-semibold">{fmtPrice(latest?.reference_price)}</div></div>
              <div><div className="micro-label">UP score (uncalibrated)</div><div className="mt-1 font-mono text-xl font-semibold">{latest ? `${(Number(latest.probability_up || 0) * 100).toFixed(1)}%` : "—"}</div></div>
              <div><div className="micro-label">Neuron output</div><div className="mt-1 font-mono text-lg">{fmt(latest?.prediction_value,4)}</div></div>
              <div><div className="micro-label">Outcome target</div><div className="mt-1 text-xs">{fmtTime(latest?.target_at)}</div></div>
            </div>
            <div className="mt-4 rounded-lg bg-pine-50 p-3 text-[11px] leading-5 text-muted">Prediksi berstatus <strong>{latest?.status || "belum tersedia"}</strong>. Arah dihitung dari tanda output neuron; UP score dipetakan dari output tanh, bukan probabilitas terkalibrasi sampai audit cukup.</div>
          </div>
          <div className="card p-4 sm:p-5">
            <div className="flex items-center gap-2"><Database size={15} className="text-pine-700"/><h3 className="font-display text-base font-semibold">Input health</h3></div>
            <div className="mt-3 flex flex-wrap gap-2">
              {FEATURE_META.filter(([key]) => key !== "bias").map(([key,label]) => <Signal key={key} label={label} state={featuresAvailable[key] === true}/>)}
            </div>
            <p className="mt-3 text-[11px] leading-5 text-muted">Input yang tidak tersedia harus dicatat sebagai missing/neutral, bukan dianggap sinyal valid. Lihat detail sumber pada jurnal.</p>
          </div>
        </section>
      </div>}

      {tab === "synapse" && <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
        <section className="card p-4 sm:p-5">
          <div className="flex items-center justify-between"><div><div className="micro-label">Champion model</div><h2 className="mt-1 font-display text-xl font-semibold">Synapse weights</h2></div><span className="chip chip-live">Active</span></div>
          <p className="mt-2 text-xs text-muted">Bobot aktif saat ini. Perubahan bobot harus menghasilkan versi baru dan snapshot historis tidak boleh ditimpa.</p>
          <div className="mt-4 grid grid-cols-[minmax(0,1fr)_72px_82px] gap-3 border-b border-line pb-2 micro-label"><span>Neuron input</span><span className="text-right">Weight</span><span className="text-right">Contribution</span></div>
          {FEATURE_META.map(([key,label]) => <WeightRow key={key} name={key} label={label} weight={weights[key]} contribution={contributions[key]}/>)}
          {!model.state && <p className="mt-3 text-xs text-muted">Belum ada bobot dari database. Nilai default tidak ditampilkan sebagai bobot aktif.</p>}
        </section>
        <section className="space-y-4">
          <div className="card p-4 sm:p-5">
            <div className="micro-label">Model integrity</div><h2 className="mt-1 font-display text-xl font-semibold">Weight self-check</h2>
            <div className="mt-4 space-y-3 text-xs">
              {[
                ["Model version", model.version ? `v${model.version}` : "Not loaded"],
                ["RMSProp updates", model.state?.nUpdates ?? "—"],
                ["Snapshot checksum", model.checksum || "Not available"],
                ["Last changed", fmtTime(model.updated_at)],
                ["Promotion policy", "Champion / Candidate"],
              ].map(([k,v]) => <div key={k} className="flex items-center justify-between gap-4 border-b border-line pb-2"><span className="text-muted">{k}</span><strong className="text-right font-mono font-medium text-ink">{v}</strong></div>)}
            </div>
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-900"><strong>Learning safety lock.</strong> Audit dapat mengukur bobot, tetapi tidak langsung mengubah Champion. Candidate baru harus diuji pada data kronologis yang belum dipakai training, dibandingkan dengan Champion, lalu dipromosikan hanya jika metrik validasi membaik.</div>
        </section>
      </div>}

      {tab === "journal" && <section className="card overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4"><div><div className="micro-label">Append-only record</div><h2 className="mt-1 font-display text-xl font-semibold">Prediction journal</h2></div><span className="text-[11px] text-muted">{journal.length} latest records</span></div>
        {journal.length === 0 ? <div className="p-8 text-center"><History size={24} className="mx-auto text-faint"/><p className="mt-3 text-sm font-medium">Belum ada prediksi tersimpan</p><p className="mt-1 text-xs text-muted">Jurnal akan terisi setelah database dan cron worker aktif.</p></div> :
        <div className="overflow-x-auto"><table className="data-table min-w-[850px]"><thead><tr><th>Generated</th><th>Direction</th><th>Reference</th><th>UP probability</th><th>Outcome</th><th>Actual return</th><th>Model</th></tr></thead><tbody>
          {journal.map((row) => <tr key={row.id}><td className="whitespace-nowrap text-xs">{fmtTime(row.created_at)}</td><td><span className={`chip ${tone(row.direction) === "up" ? "text-emerald-700" : tone(row.direction) === "down" ? "text-rose-700" : ""}`}>{row.direction}</span></td><td className="font-mono text-xs">{fmtPrice(row.reference_price)}</td><td className="font-mono text-xs">{(Number(row.probability_up || 0)*100).toFixed(1)}%</td><td><span className={`text-xs ${row.status === "labeled" ? "text-emerald-700" : "text-amber-700"}`}>{row.status || "pending"}</span></td><td className="font-mono text-xs">{row.actual_return == null ? "—" : `${(Number(row.actual_return)*100).toFixed(3)}%`}</td><td className="font-mono text-xs">v{row.weights_version ?? "—"}</td></tr>)}
        </tbody></table></div>}
      </section>}

      {tab === "audit" && <div className="grid gap-5 xl:grid-cols-[.9fr_1.1fr]">
        <section className="grid grid-cols-2 gap-3 content-start">
          <Stat label="Samples" value={audit?.metrics?.samples ?? "—"} detail="Labeled outcomes"/>
          <Stat label="Directional accuracy" value={accuracy == null ? "—" : `${(accuracy*100).toFixed(2)}%`} detail="Actual 5m direction"/>
          <Stat label="Brier score" value={fmt(audit?.metrics?.brierScore,4)} detail="Lower is better"/>
          <Stat label="Mean absolute realized return" value={audit?.metrics?.meanAbsReturnError == null ? "—" : `${(audit.metrics.meanAbsReturnError*100).toFixed(3)}%`} detail="Prediction target vs actual"/>
          <div className="col-span-2 rounded-xl border border-line bg-card p-4"><div className="micro-label">Audit integrity</div><div className="mt-2 flex items-center gap-2 text-sm font-semibold">{audit?.metrics?.samples >= 100 ? <Check size={16} className="text-emerald-600"/> : <Clock3 size={16} className="text-amber-600"/>}{audit?.metrics?.samples >= 100 ? "Initial sample threshold reached" : "Collecting evidence"}</div><p className="mt-2 text-xs leading-5 text-muted">Akurasi belum layak dinilai dari sampel kecil. Minimum 100 outcome hanya ambang awal pemantauan, bukan sertifikasi model.</p></div>
        </section>
        <section className="card p-4 sm:p-5">
          <div className="micro-label">Audit report</div><h2 className="mt-1 font-display text-xl font-semibold">Does the model earn its weights?</h2>
          <p className="mt-2 text-xs leading-5 text-muted">Setiap outcome dibandingkan dengan snapshot prediksi dan bobot pada saat prediksi dibuat. Audit tidak membaca bobot terbaru untuk menilai prediksi lama.</p>
          <div className="mt-5 space-y-3">
            {[
              ["Brier score", "Kualitas probabilitas UP/DOWN, semakin kecil semakin baik."],
              ["Directional accuracy", "Persentase arah prediksi yang sama dengan return aktual."],
              ["Weight drift", "Perubahan bobot dibanding versi Champion sebelumnya."],
              ["Feature contribution", "Kontribusi dendrit saat prediksi dan hubungannya dengan error."],
              ["Candidate gate", "Perbandingan model baru dengan Champion pada periode uji kronologis."],
            ].map(([title,desc]) => <div key={title} className="flex gap-3"><span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-pine-50 text-pine-800"><Target size={14}/></span><div><div className="text-xs font-semibold">{title}</div><p className="mt-1 text-[11px] leading-5 text-muted">{desc}</p></div></div>)}
          </div>
          <div className="mt-5 rounded-lg bg-pine-50 p-3 text-[11px] leading-5 text-pine-900">{audit?.generatedAt ? `Last audit: ${fmtTime(audit.generatedAt)}` : "Audit belum tersedia. Tidak ada hasil yang dibuat-buat."}</div>
        </section>
      </div>}
    </div>

    <footer className="mt-8 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-4 text-[10px] text-muted">
      <span className="inline-flex items-center gap-1.5"><BrainCircuit size={13}/> CYT Neural Audit · BTCUSDT · 5m</span>
      <span>Model provisional · not a trading instruction</span>
    </footer>
  </main>;
}
