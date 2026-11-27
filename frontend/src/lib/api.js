const API_BASE = process.env.REACT_APP_API_BASE || "";

async function postJSON(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { accept: "application/json", "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  let payload = null;
  try {
    payload = await res.json();
  } catch {
    /* fall through */
  }
  if (!res.ok) {
    const detail = payload?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.errors?.join(", ") || `Request failed (HTTP ${res.status})`;
    throw new Error(message);
  }
  return payload;
}

async function fetchJSON(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { accept: "application/json" },
  });
  let payload = null;
  try {
    payload = await res.json();
  } catch {
    /* fall through */
  }
  if (!res.ok) {
    const detail = payload?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.errors?.join(", ") || `Request failed (HTTP ${res.status})`;
    throw new Error(message);
  }
  return payload;
}

export function fetchScreen(limit = 18, minQuote) {
  const q = minQuote ? `&minQuote=${encodeURIComponent(minQuote)}` : "";
  return fetchJSON(`/api/screen?limit=${limit}${q}`);
}

export function fetchSymbol(symbol) {
  return fetchJSON(`/api/screen/${encodeURIComponent(symbol)}`);
}

/** Konteks CryptoRank untuk satu koin: profil + unlock + investor/funding + plan. */
export function fetchTokenIntel(symbol) {
  return fetchJSON(`/api/token-intel/${encodeURIComponent(symbol)}`);
}

/** Cari pair USDT di SELURUH daftar bursa (bukan hanya yang sudah dimuat). */
export function searchAssets(query) {
  return fetchJSON(`/api/search?q=${encodeURIComponent(query)}`);
}

export function runCalibration({ lookbackDays = 730, stepDays = 7, label = "pos" } = {}) {
  return postJSON("/api/calibrate/run", { lookbackDays, stepDays, label });
}

export function runCalibrationSweep({ lookbackDays = 730, stepDays = 7 } = {}) {
  return postJSON("/api/calibrate/sweep", { lookbackDays, stepDays, label: "pos" });
}

export function fetchCalibrationFormulas() {
  return fetchJSON("/api/calibrate/formulas");
}

export function fetchCalibrationHistory(limit = 25) {
  return fetchJSON(`/api/calibrate/history?limit=${limit}`);
}


/* ---------- Pump Radar V2: dual detector + walk-forward outcomes ---------- */
export function fetchPumpRadarV2(symbol, history = 180) {
  const params = new URLSearchParams({ history: String(history) });
  return fetchJSON(`/api/pump-radar/v2/${encodeURIComponent(symbol)}?${params.toString()}`);
}
export function fetchPumpRadarV2Backtest(symbol, history = 365, step = 1) {
  const params = new URLSearchParams({ history: String(history), step: String(step) });
  return fetchJSON(
    `/api/pump-radar/v2/${encodeURIComponent(symbol)}/backtest?${params.toString()}`
  );
}

/* ---------- Fokker–Planck distribution & spoofing lab (additive) ---------- */

export function fetchFpSpec() {
  return fetchJSON("/api/fokker-planck/spec");
}

export function fetchFpUniverse({
  limit = 18,
  horizonDays = 7,
  stableBand = 0.05,
  source = "auto",
  minQuote,
} = {}) {
  const params = new URLSearchParams({
    limit: String(limit),
    horizonDays: String(horizonDays),
    stableBand: String(stableBand),
    source: String(source),
  });
  if (minQuote !== undefined && minQuote !== null) {
    params.set("minQuote", String(minQuote));
  }
  return fetchJSON(`/api/fokker-planck/universe?${params.toString()}`);
}

export function fetchFpAsset(
  symbol,
  {
    horizonDays = 7,
    stableBand = 0.05,
    microHorizonSec = 30,
    microBand = 0.004,
    source = "auto",
  } = {}
) {
  const params = new URLSearchParams({
    horizonDays: String(horizonDays),
    stableBand: String(stableBand),
    microHorizonSec: String(microHorizonSec),
    microBand: String(microBand),
    source: String(source),
  });
  return fetchJSON(`/api/fokker-planck/asset/${encodeURIComponent(symbol)}?${params.toString()}`);
}

export function simulateFp(payload) {
  return postJSON("/api/fokker-planck/simulate", payload);
}

export function runFpBacktest({
  horizonDays = 7,
  stableBand = 0.05,
  stepDays = 7,
  lookbackDays = 240,
  limit = 16,
  source = "auto",
} = {}) {
  return postJSON("/api/fokker-planck/backtest", {
    horizonDays,
    stableBand,
    stepDays,
    lookbackDays,
    limit,
    source,
  });
}

/* ---------- Fokker–Planck Model v2 & Side-by-Side Comparator (isolated) ---------- */

export function fetchFpV2Spec() {
  return fetchJSON("/api/fokker-planck-v2/spec");
}

export function fetchFpV2Universe({
  limit = 18,
  horizonDays = 7,
  stableBand = 0.05,
  source = "auto",
  minQuote,
} = {}) {
  const params = new URLSearchParams({
    limit: String(limit),
    horizonDays: String(horizonDays),
    stableBand: String(stableBand),
    source: String(source),
  });
  if (minQuote !== undefined && minQuote !== null) {
    params.set("minQuote", String(minQuote));
  }
  return fetchJSON(`/api/fokker-planck-v2/compare/universe?${params.toString()}`);
}

export function fetchFpV2Asset(
  symbol,
  {
    horizonDays = 7,
    stableBand = 0.05,
    microHorizonSec = 30,
    microBand = 0.004,
    source = "auto",
  } = {}
) {
  const params = new URLSearchParams({
    horizonDays: String(horizonDays),
    stableBand: String(stableBand),
    microHorizonSec: String(microHorizonSec),
    microBand: String(microBand),
    source: String(source),
  });
  return fetchJSON(
    `/api/fokker-planck-v2/compare/asset/${encodeURIComponent(symbol)}?${params.toString()}`
  );
}

export function simulateFpV2(payload) {
  return postJSON("/api/fokker-planck-v2/compare/simulate", payload);
}

export function fetchFpV2Intraday(
  symbol,
  { horizonMin = 30, targetBand = null, source = "auto" } = {}
) {
  const params = new URLSearchParams({
    horizonMin: String(horizonMin),
    source: String(source),
  });
  if (targetBand !== null && targetBand !== undefined && Number(targetBand) > 0) {
    params.set("targetBand", String(targetBand));
  }
  return fetchJSON(
    `/api/fokker-planck-v2/intraday/${encodeURIComponent(symbol)}?${params.toString()}`
  );
}

export function postFpV2IntradayWs(symbol, payload) {
  return postJSON(
    `/api/fokker-planck-v2/intraday/${encodeURIComponent(symbol)}`,
    payload
  );
}

/* ---------- FP Live (5 · 15 · 30 · 60 Min) Dedicated Menu ---------- */

export function fetchFpLive(
  symbol,
  { horizonMin = 30, targetBand = null, source = "auto" } = {}
) {
  const params = new URLSearchParams({
    horizonMin: String(horizonMin),
    source: String(source),
  });
  if (targetBand !== null && targetBand !== undefined && Number(targetBand) > 0) {
    params.set("targetBand", String(targetBand));
  }
  return fetchJSON(`/api/fp-live/${encodeURIComponent(symbol)}?${params.toString()}`);
}

export function postFpLiveWs(symbol, payload) {
  return postJSON(`/api/fp-live/${encodeURIComponent(symbol)}`, payload);
}

export function runFpV2Backtest({
  horizonDays = 7,
  stableBand = 0.05,
  stepDays = 7,
  lookbackDays = 240,
  limit = 16,
  source = "auto",
} = {}) {
  return postJSON("/api/fokker-planck-v2/compare/backtest", {
    horizonDays,
    stableBand,
    stepDays,
    lookbackDays,
    limit,
    source,
  });
}

/* ---------- Neuron — online adaptive learning (stateless, state in client) ----------
 * Server Vercel ephemeral — neuronState & memoryState disimpan di localStorage
 * client, dikirim balik di body tiap request. Flow:
 *   predict (dendrite dari screen-v2 + fp + unlock) -> episode PENDING
 *   episode/close (+4% misal)                      -> episode CLOSED, RMSProp update
 *   episode >= 30 CLOSED                           -> refit = usulan bobot baru
 *   episode >= 50 CLOSED                           -> validate (Brier/AUC/precision gate)
 * Bobot ACCEPT tetap PROVISIONAL — wajib monitoring live.
 */

export function neuronPredict({ symbol, neuronState, memoryState } = {}) {
  return postJSON("/api/neuron/predict", { symbol, neuronState, memoryState });
}

export function neuronCloseEpisode({ episode, realizedReturn, neuronState, memoryState }) {
  return postJSON("/api/neuron/episode/close", { episode, realizedReturn, neuronState, memoryState });
}

export function neuronRefit({ neuronState, memoryState } = {}) {
  return postJSON("/api/neuron/refit", { neuronState, memoryState });
}

export function neuronValidate({ neuronState, memoryState, candidateWeights, baselineWeights } = {}) {
  return postJSON("/api/neuron/validate", { neuronState, memoryState, candidateWeights, baselineWeights });
}

export function neuronStats({ memoryState } = {}) {
  return postJSON("/api/neuron/stats", { memoryState });
}


/* ---------- Neuron Live Core — persistent journal & self-audit ---------- */
export function fetchNeuronLiveStatus() {
  return fetchJSON("/api/neuron/live/status");
}
export function fetchNeuronLiveJournal(limit = 40) {
  return fetchJSON(`/api/neuron/live/journal?limit=${encodeURIComponent(limit)}`);
}
export function fetchNeuronLiveAudit() {
  return fetchJSON("/api/neuron/live/audit");
}
