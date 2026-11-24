import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Brain, Zap, CheckCircle2, AlertTriangle, RotateCcw, Activity, FlaskConical, ShieldCheck } from "lucide-react";
import {
  neuronPredict,
  neuronCloseEpisode,
  neuronRefit,
  neuronValidate,
  neuronStats,
} from "../lib/api";

const NEURON_KEY = "meridian:neuron:state";
const MEMORY_KEY = "meridian:memory:state";

function loadState(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
function saveState(key, val) {
  try {
    localStorage.setItem(key, JSON.stringify(val));
  } catch {
    /* quota / private mode — ignore */
  }
}

const VERDICT_TONE = {
  LONG: { bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200" },
  SHORT: { bg: "bg-rose-50", text: "text-rose-700", border: "border-rose-200" },
  WATCH: { bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200" },
  NEUTRAL: { bg: "bg-pine-50", text: "text-pine-700", border: "border-pine-200" },
};

function VerdictBadge({ verdict }) {
  const v = (verdict || "NEUTRAL").toUpperCase();
  const tone = VERDICT_TONE[v] || VERDICT_TONE.NEUTRAL;
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-mono font-semibold uppercase tracking-wide border ${tone.bg} ${tone.text} ${tone.border}`}>
      {v}
    </span>
  );
}

function StatTile({ label, value, hint }) {
  return (
    <div className="card p-3">
      <p className="micro-label !text-[9px]">{label}</p>
      <p className="font-display text-xl font-semibold text-ink mt-1">{value}</p>
      {hint && <p className="text-[10px] text-faint mt-0.5">{hint}</p>}
    </div>
  );
}

function DendriteContributions({ contributions }) {
  if (!contributions) return null;
  const entries = Object.entries(contributions).filter(([k]) => k !== "bias");
  const maxAbs = Math.max(0.0001, ...entries.map(([, v]) => Math.abs(v)));
  return (
    <div className="mt-3 space-y-1">
      {entries.map(([name, val]) => {
        const pct = Math.abs(val) / maxAbs;
        const pos = val >= 0;
        return (
          <div key={name} className="flex items-center gap-2 text-[11px]">
            <span className="font-mono text-muted w-28 shrink-0">{name}</span>
            <div className="relative flex-1 h-3 bg-pine-50 rounded">
              <div
                className={`absolute top-0 h-3 rounded ${pos ? "bg-emerald-400 left-1/2" : "bg-rose-400 right-1/2"}`}
                style={{ width: `${(pct * 50).toFixed(1)}%` }}
              />
              <div className="absolute left-1/2 top-0 h-3 w-px bg-line" />
            </div>
            <span className={`font-mono w-16 text-right ${pos ? "text-emerald-700" : "text-rose-700"}`}>
              {val >= 0 ? "+" : ""}{val.toFixed(4)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function SectionCard({ icon: Icon, title, subtitle, children, action }) {
  return (
    <section className="card p-5">
      <div className="flex items-start justify-between gap-3 border-b border-line pb-3">
        <div className="flex items-start gap-3">
          <span className="grid place-items-center w-8 h-8 rounded-lg bg-pine-800 text-paper shrink-0">
            <Icon size={16} strokeWidth={1.75} />
          </span>
          <div>
            <h3 className="font-display text-[15px] font-semibold text-ink">{title}</h3>
            {subtitle && <p className="text-[11px] text-muted mt-0.5">{subtitle}</p>}
          </div>
        </div>
        {action}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export default function NeuronPage() {
  const [neuronState, setNeuronState] = useState(null);
  const [memoryState, setMemoryState] = useState(null);
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [realizedReturn, setRealizedReturn] = useState("");
  const [lastPrediction, setLastPrediction] = useState(null);
  const [lastEpisode, setLastEpisode] = useState(null);
  const [lastClose, setLastClose] = useState(null);
  const [lastRefit, setLastRefit] = useState(null);
  const [lastValidate, setLastValidate] = useState(null);
  const [lastStats, setLastStats] = useState(null);
  const [loading, setLoading] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setNeuronState(loadState(NEURON_KEY));
    setMemoryState(loadState(MEMORY_KEY));
  }, []);

  function commitState(neuron, memory) {
    if (neuron) { setNeuronState(neuron); saveState(NEURON_KEY, neuron); }
    if (memory) { setMemoryState(memory); saveState(MEMORY_KEY, memory); }
  }

  async function runLoading(label, fn) {
    setLoading(label); setError(null);
    try { return await fn(); }
    catch (e) { setError(e.message || String(e)); return null; }
    finally { setLoading(null); }
  }

  async function onPredict() {
    const r = await runLoading("predict", () =>
      neuronPredict({ symbol, neuronState, memoryState })
    );
    if (r) {
      commitState(r.neuronState, r.memoryState);
      setLastPrediction(r.prediction);
      setLastEpisode(r.episode);
      setLastClose(null);
    }
  }

  async function onClose() {
    if (!lastEpisode) { setError("Belum ada episode pending. Jalankan Predict dulu."); return; }
    const rr = parseFloat(realizedReturn);
    if (Number.isNaN(rr)) { setError("Realized return harus angka (persen, mis. 4 atau -2.5)."); return; }
    const r = await runLoading("close", () =>
      neuronCloseEpisode({ episode: lastEpisode, realizedReturn: rr, neuronState, memoryState })
    );
    if (r) {
      commitState(r.neuronState, r.memoryState);
      setLastClose(r);
      setLastEpisode(null);
      setRealizedReturn("");
    }
  }

  async function onRefit() {
    if (!memoryState) { setError("Memory belum ada state. Jalankan Predict minimal sekali."); return; }
    const r = await runLoading("refit", () => neuronRefit({ neuronState, memoryState }));
    if (r) setLastRefit(r.proposal);
  }

  async function onValidate() {
    if (!memoryState) { setError("Memory belum ada state."); return; }
    const r = await runLoading("validate", () => neuronValidate({ neuronState, memoryState }));
    if (r) setLastValidate(r.evaluation);
  }

  async function onStats() {
    const r = await runLoading("stats", () => neuronStats({ memoryState }));
    if (r) setLastStats({ stats: r.stats, trustedPatterns: r.trustedPatterns });
  }

  function onReset() {
    localStorage.removeItem(NEURON_KEY);
    localStorage.removeItem(MEMORY_KEY);
    setNeuronState(null); setMemoryState(null);
    setLastPrediction(null); setLastEpisode(null); setLastClose(null);
    setLastRefit(null); setLastValidate(null); setLastStats(null);
    setError(null);
  }

  const nUpdates = neuronState?.nUpdates ?? 0;
  const pendingEps = memoryState?.episodes_pending ?? memoryState?.pending ?? 0;
  const closedEps = memoryState?.episodes_closed ?? memoryState?.closed ?? 0;

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 py-8 md:py-10">
      <Link to="/" className="inline-flex items-center gap-2 text-[12px] font-medium text-muted hover:text-pine-700 transition-colors focus-ring rounded">
        <ArrowLeft size={14} strokeWidth={2} /> Back to screener
      </Link>

      <div className="mt-5 border-b border-line pb-6 max-w-3xl">
        <p className="micro-label text-gold-600">Neuron Lab</p>
        <h1 className="font-display text-4xl font-semibold tracking-tight mt-2 flex items-center gap-3">
          <Brain size={32} strokeWidth={1.75} className="text-pine-800" />
          Adaptive Online Neuron
        </h1>
        <p className="mt-3 text-[14px] leading-6 text-muted">
          Neuron 10-dendrite (screen signal, demand quality, stability, FP stable/tail/live, rvol, unlock gate,
          vwap dist) dengan aktivasi <code className="font-mono text-[12px] bg-pine-50 px-1.5 py-0.5 rounded">tanh</code>,
          RMSProp online, surprise gate, dan pattern trust Wilson LB. <strong className="text-ink">Stateless di server</strong> —
          bobot & memory episode disimpan di browser lu (localStorage), dikirim balik tiap request.
        </p>
      </div>

      {/* ---------- state status bar ---------- */}
      <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatTile label="Neuron updates" value={nUpdates} hint="RMSProp steps sejak init" />
        <StatTile label="Episodes pending" value={pendingEps} hint="Menunggu outcome" />
        <StatTile label="Episodes closed" value={closedEps} hint="Sudah belajar" />
        <StatTile label="Model" value={lastPrediction?.model || "—"} hint={lastPrediction?.provisional ? "PROVISIONAL" : "ready"} />
      </div>

      {error && (
        <div className="mt-5 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-[13px] text-rose-700 flex items-start gap-2">
          <AlertTriangle size={15} strokeWidth={2} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="mt-6 grid lg:grid-cols-2 gap-5">
        {/* ---------- PREDICT ---------- */}
        <SectionCard
          icon={Zap}
          title="1 · Predict"
          subtitle="Hitung dendrite dari screen-v2 + catat episode pending"
          action={
            <button
              onClick={onPredict}
              disabled={loading === "predict"}
              className="focus-ring rounded-full px-4 py-1.5 text-[12px] font-medium bg-pine-800 text-paper hover:bg-pine-700 disabled:opacity-50 transition-colors"
            >
              {loading === "predict" ? "Menghitung…" : "Predict"}
            </button>
          }
        >
          <label className="block">
            <span className="micro-label">Symbol</span>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              placeholder="BTCUSDT"
              className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2 text-[13px] font-mono focus:outline-none focus:border-pine-700"
            />
          </label>

          {lastPrediction && (
            <div className="mt-4 border-t border-line pt-4">
              <div className="flex items-center gap-3 flex-wrap">
                <VerdictBadge verdict={lastPrediction.verdict} />
                <span className="font-mono text-[12px] text-muted">
                  y = <strong className="text-ink">{lastPrediction.y.toFixed(3)}</strong>
                </span>
                <span className="font-mono text-[12px] text-muted">
                  confidence = <strong className="text-ink">{lastPrediction.confidence.toFixed(3)}</strong>
                </span>
              </div>
              <p className="micro-label mt-4">Dendrite contributions</p>
              <DendriteContributions contributions={lastPrediction.contributions} />
              {lastEpisode && (
                <p className="mt-3 text-[11px] text-faint font-mono">
                  episode #{lastEpisode.id} · pending close
                </p>
              )}
            </div>
          )}
        </SectionCard>

        {/* ---------- CLOSE EPISODE ---------- */}
        <SectionCard
          icon={CheckCircle2}
          title="2 · Episode close + learn"
          subtitle="Tutup episode pending → RMSProp update + surprise gate"
          action={
            <button
              onClick={onClose}
              disabled={loading === "close" || !lastEpisode}
              className="focus-ring rounded-full px-4 py-1.5 text-[12px] font-medium bg-pine-800 text-paper hover:bg-pine-700 disabled:opacity-50 transition-colors"
            >
              {loading === "close" ? "Belajar…" : "Close & learn"}
            </button>
          }
        >
          {lastEpisode ? (
            <div className="text-[12px] text-muted">
              Pending: <span className="font-mono text-ink">#{lastEpisode.id}</span>{" "}
              ({lastEpisode.symbol}) · verdict <VerdictBadge verdict={lastEpisode.verdict} />
            </div>
          ) : (
            <p className="text-[12px] text-faint">Tidak ada episode pending. Jalankan Predict dulu.</p>
          )}
          <label className="block mt-3">
            <span className="micro-label">Realized return (%)</span>
            <input
              type="number"
              step="0.1"
              value={realizedReturn}
              onChange={(e) => setRealizedReturn(e.target.value)}
              placeholder="mis. 4 atau -2.5"
              className="mt-1 w-full rounded-lg border border-line bg-paper px-3 py-2 text-[13px] font-mono focus:outline-none focus:border-pine-700"
            />
          </label>
          {lastClose?.learning && (
            <div className="mt-3 border-t border-line pt-3 text-[11px] font-mono text-muted space-y-0.5">
              <p>surprise_gate: <span className="text-ink">{String(lastClose.learning.surprise_gate ?? lastClose.learning.surprise)}</span></p>
              <p>weight_delta: <span className="text-ink">{JSON.stringify(lastClose.learning.weight_delta ?? lastClose.learning.delta ?? {}).slice(0, 120)}</span></p>
            </div>
          )}
          {lastClose?.stats && (
            <p className="mt-2 text-[11px] text-faint">
              closed: {lastClose.stats.closed} · winRate: {lastClose.stats.winRate ?? "—"}
            </p>
          )}
        </SectionCard>

        {/* ---------- REFIT ---------- */}
        <SectionCard
          icon={FlaskConical}
          title="3 · Refit (guru offline)"
          subtitle="Propose bobot baru dari episode CLOSED (≥30 disarankan). Hasil = USULAN."
          action={
            <button
              onClick={onRefit}
              disabled={loading === "refit" || !memoryState}
              className="focus-ring rounded-full px-4 py-1.5 text-[12px] font-medium bg-pine-800 text-paper hover:bg-pine-700 disabled:opacity-50 transition-colors"
            >
              {loading === "refit" ? "Fitting…" : "Refit"}
            </button>
          }
        >
          {!lastRefit ? (
            <p className="text-[12px] text-faint">Klik Refit untuk usulan bobot via logistic regression (temporal split 75/25).</p>
          ) : (
            <div className="text-[11px] font-mono text-muted space-y-1">
              <p>verdict: <span className="text-ink">{lastRefit.verdict ?? lastRefit.action ?? "—"}</span></p>
              <p>train_size: <span className="text-ink">{lastRefit.train_size ?? "—"}</span> · test_size: <span className="text-ink">{lastRefit.test_size ?? "—"}</span></p>
              <p>train_auc: <span className="text-ink">{lastRefit.train_auc?.toFixed?.(3) ?? "—"}</span> · test_auc: <span className="text-ink">{lastRefit.test_auc?.toFixed?.(3) ?? "—"}</span></p>
              {lastRefit.weights && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-pine-700">proposed weights ({Object.keys(lastRefit.weights).length})</summary>
                  <pre className="mt-1 p-2 bg-pine-50 rounded text-[10px] overflow-x-auto">{JSON.stringify(lastRefit.weights, null, 2)}</pre>
                </details>
              )}
            </div>
          )}
        </SectionCard>

        {/* ---------- VALIDATE ---------- */}
        <SectionCard
          icon={ShieldCheck}
          title="4 · Validate (weight lab gate)"
          subtitle="Brier / AUC / precision gate + relatif vs baseline. ≥50 CLOSED disarankan."
          action={
            <button
              onClick={onValidate}
              disabled={loading === "validate" || !memoryState}
              className="focus-ring rounded-full px-4 py-1.5 text-[12px] font-medium bg-pine-800 text-paper hover:bg-pine-700 disabled:opacity-50 transition-colors"
            >
              {loading === "validate" ? "Evaluating…" : "Validate"}
            </button>
          }
        >
          {!lastValidate ? (
            <p className="text-[12px] text-faint">Klik Validate untuk jalankan weight lab gate.</p>
          ) : (
            <div className="text-[11px] font-mono text-muted space-y-1">
              <p>decision: <span className="text-ink">{lastValidate.decision ?? lastValidate.verdict ?? "—"}</span></p>
              <p>brier: <span className="text-ink">{lastValidate.brier?.toFixed?.(4) ?? "—"}</span> · auc: <span className="text-ink">{lastValidate.auc?.toFixed?.(3) ?? "—"}</span> · precision: <span className="text-ink">{lastValidate.precision?.toFixed?.(3) ?? "—"}</span></p>
              <p>relatif_vs_baseline: <span className="text-ink">{lastValidate.relative ?? lastValidate.delta ?? "—"}</span></p>
              {lastValidate.reasons && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-pine-700">reasons</summary>
                  <pre className="mt-1 p-2 bg-pine-50 rounded text-[10px] overflow-x-auto">{JSON.stringify(lastValidate.reasons, null, 2)}</pre>
                </details>
              )}
            </div>
          )}
        </SectionCard>
      </div>

      {/* ---------- STATS + RESET ---------- */}
      <div className="mt-5 grid lg:grid-cols-2 gap-5">
        <SectionCard
          icon={Activity}
          title="5 · Hippocampus stats"
          subtitle="Episode counts, win rate, pattern trust (Wilson LB)"
          action={
            <button
              onClick={onStats}
              disabled={loading === "stats"}
              className="focus-ring rounded-full px-4 py-1.5 text-[12px] font-medium bg-pine-800 text-paper hover:bg-pine-700 disabled:opacity-50 transition-colors"
            >
              {loading === "stats" ? "Loading…" : "Refresh"}
            </button>
          }
        >
          {!lastStats ? (
            <p className="text-[12px] text-faint">Klik Refresh untuk load statistik memory.</p>
          ) : (
            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono text-muted">
              <p>episodes: <span className="text-ink">{lastStats.stats.episodes}</span></p>
              <p>pending: <span className="text-ink">{lastStats.stats.pending}</span></p>
              <p>closed: <span className="text-ink">{lastStats.stats.closed}</span></p>
              <p>scored: <span className="text-ink">{lastStats.stats.scored}</span></p>
              <p>winRate: <span className="text-ink">{lastStats.stats.winRate ?? "—"}</span></p>
              <p>patterns: <span className="text-ink">{lastStats.stats.patterns}</span></p>
              <p>trusted: <span className="text-ink">{lastStats.stats.trustedPatterns}</span></p>
              <p>trusted list: <span className="text-ink">{Array.isArray(lastStats.trustedPatterns) ? lastStats.trustedPatterns.length : 0}</span></p>
            </div>
          )}
        </SectionCard>

        <SectionCard
          icon={RotateCcw}
          title="Reset state"
          subtitle="Hapus neuronState + memoryState dari localStorage"
          action={
            <button
              onClick={onReset}
              className="focus-ring rounded-full px-4 py-1.5 text-[12px] font-medium border border-rose-200 text-rose-700 hover:bg-rose-50 transition-colors"
            >
              Reset
            </button>
          }
        >
          <p className="text-[12px] text-muted">
            Bobot kembali ke init default (zero weights + bias 1.0). Semua episode hilang.
            Berguna kalau lu mau mulai sesi belajar baru dari nol.
          </p>
          <p className="text-[11px] text-faint mt-2 font-mono">
            storage keys: <code>{NEURON_KEY}</code>, <code>{MEMORY_KEY}</code>
          </p>
        </SectionCard>
      </div>

      {/* ---------- flow legend ---------- */}
      <div className="mt-6 card p-4 text-[11px] text-muted leading-5">
        <p className="micro-label">Alur belajar</p>
        <pre className="mt-2 font-mono text-[10px] text-faint overflow-x-auto">{`predict (dendrite dari screen-v2 + fp + unlock)  ->  episode PENDING
episode/close (+4% misal)                        ->  episode CLOSED, RMSProp update
episode >= 30 CLOSED                             ->  refit = usulan bobot baru
episode >= 50 CLOSED                             ->  weight_lab: Brier/AUC/precision
LOLOS gerbang                                    ->  bobot baru boleh dipasang (PROVISIONAL)`}</pre>
      </div>
    </div>
  );
}
