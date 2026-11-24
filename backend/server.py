"""
Meridian cyt — lean FastAPI server (build terkurasi & disederhanakan)
=====================================================================

Versi sederhana dari server 38-route di repo Test: hanya layer yang lolos
filter akurasi, di-wiring dengan pola STATELESS (neuron & memory state
disimpan client/localStorage dan dikirim balik di tiap body request — aman
untuk Vercel serverless ephemeral).

Routes (14):
  GET  /api/health                     status + cryptorank stats
  GET  /api/markets                    snapshot universe 24h (query: limit)
  GET  /api/search?q=                  cari pair USDT seluruh Binance
  GET  /api/screen-v2/spec             metadata rumus v2 (7 fix)
  GET  /api/screen-v2/{symbol}         screening v2 + regime BTC + unlock gate
  GET  /api/cryptorank/plan            tier plan / credits / endpoints (free)
  GET  /api/cryptorank/unlocks         unlock market-wide 30d (Pro, cache 6h)
  GET  /api/cryptorank/stats           usage/credit/cache stats
  GET  /api/tokenomics/{symbol}        identitas + supply + vesting (CR v2)
  GET  /api/fp/{symbol}                metrics fokker-planck (pStable/pTailCrash)
  POST /api/neuron/predict             prediksi neuron + catat episode
  POST /api/neuron/episode/close       tutup episode + belajar online RMSProp
  POST /api/neuron/refit               usulan refit (TIDAK auto-pasang)
  POST /api/neuron/validate            weight-lab gate Brier/AUC/precision

Jalankan lokal: uvicorn backend.server:app --port 8000
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import (
    cryptorank,
    cryptorank_vesting,
    fokker_planck,
    market_data,
    neuron_logistic,
    screening_v2,
    weight_lab,
)
from backend.gates import VERDICT_META, apply_unlock_gate
from backend.neuron_core import Neuron, build_dendrites
from backend.neuron_memory import NeuronMemory

load_dotenv()

FRONTEND_BUILD = _fb = None  # placeholder diisi di bawah agar import aman
from pathlib import Path  # noqa: E402
FRONTEND_BUILD = Path(__file__).resolve().parent.parent / "frontend" / "build"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _app.state.http = httpx.AsyncClient()
    try:
        yield
    finally:
        await _app.state.http.aclose()


# Serverless-safe: Vercel cold start tidak menjamin lifespan jalan, jadi setiap
# route punya fallback client yang dibuat malas.
_HTTP_CLIENT: Optional[httpx.AsyncClient] = None


def _http_client() -> httpx.AsyncClient:
    global _HTTP_CLIENT
    client = getattr(app.state, "http", None) if "app" in globals() else None
    if client is not None:
        return client
    if _HTTP_CLIENT is None:
        _HTTP_CLIENT = httpx.AsyncClient(follow_redirects=True)
    return _HTTP_CLIENT


app = FastAPI(title="Meridian cyt — filtered & simplified", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _preferred_source() -> Optional[str]:
    src = os.getenv("SCREEN_SOURCE", "auto").strip().lower()
    return src if src in {"live", "seed"} else None


def _clean_sym(symbol: str) -> str:
    sym = symbol.upper().strip()
    if not sym.isalnum() or len(sym) > 20:
        raise HTTPException(status_code=400, detail="Invalid symbol.")
    return sym


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _btc_regime(client: httpx.AsyncClient) -> float:
    """Regime fitur v2: sat(return 30d BTC). Gagal -> 0.0 netral."""
    try:
        payload = await market_data.fetch_symbol_klines(client, "BTCUSDT", 40)
        closes = [c["close"] for c in payload.get("candles") or []]
        if len(closes) >= 31 and closes[-31] > 0:
            r = closes[-1] / closes[-31] - 1.0
            return r / (1.0 + abs(r))
    except Exception:  # noqa: BLE001 — regime gagal = netral, bukan error
        pass
    return 0.0


async def _unlock_dendrite(client: httpx.AsyncClient, symbol: str) -> Optional[float]:
    """Dendrite unlockGate [-1,+1]: unlock besar mendekat -> negatif.
    0% -> +0.2 (aman), 1% -> -0.33, 3% -> -1.0 (linear dari 1% ke 3%)."""
    try:
        unlock_map = await cryptorank.unlocks_by_symbol(client)
        block = cryptorank.unlock_block(symbol, unlock_map)
        pct = (block or {}).get("percentOfMcap")
        if pct is None:
            return None
        pct = max(0.0, float(pct))
        if pct <= 0.5:
            return 0.2
        return -min(1.0, (pct - 0.5) / 2.5)
    except Exception:  # noqa: BLE001 — unlock feed gagal = dendrite netral
        return None


async def _screen_v2_result(client: httpx.AsyncClient, symbol: str, with_context: bool = True) -> dict[str, Any]:
    """Candle -> screening v2 (+ regime BTC) -> cryptorank context -> unlock gate."""
    payload = await market_data.fetch_symbol_klines(client, symbol, 120)
    if payload.get("exists") is False:
        raise HTTPException(status_code=404, detail=f"{symbol} tidak terdaftar sebagai pair USDT di Binance.")
    if payload.get("unavailable"):
        raise HTTPException(status_code=503, detail="Bursa tidak bisa dihubungi dari server ini — coba lagi sebentar.")

    result = screening_v2.compute_features_v2(payload.get("candles") or [], regime=await _btc_regime(client))
    result["symbol"] = symbol
    result["sources"] = {"market": payload.get("source"), "klines": payload.get("source"),
                         "live": bool(payload.get("live"))}
    if result.get("ok"):
        meta = VERDICT_META.get(result["verdict"], VERDICT_META["NEUTRAL"])
        result["verdictLabel"] = meta["label"]
        result["verdictTone"] = meta["tone"]

    if with_context:
        try:
            cr_map = await cryptorank.symbol_map(client)
            result["cryptorank"] = cryptorank.block_for(symbol, cr_map)
        except Exception:  # noqa: BLE001
            result["cryptorank"] = None
        try:
            unlock_map = await cryptorank.unlocks_by_symbol(client)
            unlock = cryptorank.unlock_block(symbol, unlock_map)
            result["unlock"] = unlock
            if unlock and apply_unlock_gate(result, unlock,
                                            cryptorank.UNLOCK_WATCH_PCT, cryptorank.UNLOCK_AVOID_PCT):
                result["unlockGateApplied"] = True
        except Exception:  # noqa: BLE001
            result["unlock"] = None
    return result


# ---------------------------------------------------------------------------
# Market & screener
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "service": "meridian-cyt",
        "version": "1.0.0",
        "build": "filtered-simplified",
        "cryptorank": cryptorank.stats(),
    }


@app.get("/api/markets")
async def markets(limit: int = Query(40, ge=1, le=100)):
    client = _http_client()
    return await market_data.fetch_universe(client, limit=limit)


@app.get("/api/search")
async def search(q: str = Query("", max_length=20)):
    probe = (q or "").strip()
    if not probe:
        return {"query": q, "matches": [], "universeSize": 0}
    client = _http_client()
    try:
        found = await market_data.search_binance_symbols(client, probe)
    except Exception as exc:  # noqa: BLE001 — search must never 500
        return {"query": q, "matches": [], "universeSize": 0, "error": str(exc)}
    return {"ok": True, **found}


@app.get("/api/screen-v2/spec")
async def screen_v2_spec():
    return screening_v2.formula_spec_v2()


@app.get("/api/screen-v2/{symbol}")
async def screen_v2(symbol: str):
    sym = _clean_sym(symbol)
    client = _http_client()
    return await _screen_v2_result(client, sym)


# ---------------------------------------------------------------------------
# CryptoRank context
# ---------------------------------------------------------------------------

@app.get("/api/cryptorank/plan")
async def cryptorank_plan():
    return await cryptorank.plan_status(_http_client())


@app.get("/api/cryptorank/unlocks")
async def cryptorank_unlocks(days_ahead: int = Query(30, ge=1, le=365)):
    client = _http_client()
    result = await cryptorank.upcoming_unlocks(client, days_ahead=days_ahead, min_percent_mcap=0.5)
    if not result.get("ok"):
        raise HTTPException(status_code=503, detail=result)
    return result


@app.get("/api/cryptorank/stats")
async def cryptorank_stats():
    return cryptorank.stats()


@app.get("/api/tokenomics/{symbol}")
async def tokenomics(symbol: str):
    """Layer tokenomics CR v2: identitas + supply + vesting unlock/locked/alokasi.
    Tanpa fallback palsu — gagal = jujur {available: false, reason}."""
    sym = _clean_sym(symbol)
    return await cryptorank_vesting.fetch_tokenomics_bundle(_http_client(), sym)


# ---------------------------------------------------------------------------
# Fokker-Planck metrics (dendrite fp untuk neuron)
# ---------------------------------------------------------------------------

@app.get("/api/fp/{symbol}")
async def fp_metrics(symbol: str, horizonDays: float = Query(7.0, ge=1.0, le=30.0)):
    sym = _clean_sym(symbol)
    client = _http_client()
    payload = await market_data.fetch_symbol_klines(client, sym, 120)
    if payload.get("exists") is False:
        raise HTTPException(status_code=404, detail=f"{sym} tidak terdaftar sebagai pair USDT di Binance.")
    res = fokker_planck.analyze_candles_fp(payload.get("candles") or [], horizon_days=horizonDays)
    if not res.get("ok"):
        raise HTTPException(status_code=422, detail=res.get("reason", "Data FP tidak cukup."))
    res["symbol"] = sym
    res["source"] = payload.get("source")
    return res


# ---------------------------------------------------------------------------
# Neuron suite (stateless — state client di body, server balas state terbaru)
# ---------------------------------------------------------------------------

class NeuronPredictRequest(BaseModel):
    symbol: Optional[str] = Field(None, description="mis. BTCUSDT — dipakai bila dendrites kosong")
    dendrites: Optional[dict[str, float]] = None
    fpState: Optional[dict[str, Any]] = Field(None, description="opsional: {ok, metrics:{pStable,pTailCrash}} dari /api/fp/{symbol}")
    neuronState: Optional[dict[str, Any]] = None
    memoryState: Optional[dict[str, Any]] = None


class NeuronCloseRequest(BaseModel):
    episode: dict[str, Any]
    realizedReturn: float
    neuronState: Optional[dict[str, Any]] = None
    memoryState: Optional[dict[str, Any]] = None


class NeuronRefitRequest(BaseModel):
    memoryState: dict[str, Any]
    neuronState: Optional[dict[str, Any]] = None


class NeuronValidateRequest(BaseModel):
    memoryState: dict[str, Any]
    neuronState: Optional[dict[str, Any]] = None
    candidateWeights: Optional[dict[str, float]] = None
    baselineWeights: Optional[dict[str, float]] = None


class NeuronStatsRequest(BaseModel):
    memoryState: Optional[dict[str, Any]] = None


@app.post("/api/neuron/predict")
async def neuron_predict(req: NeuronPredictRequest):
    """Prediksi neuron + catat episode. Prioritas dendrites client > screen
    live dari symbol > dendrite netral. State dikembalikan untuk disimpan."""
    neuron = Neuron.from_dict(req.neuronState)
    memory = NeuronMemory.from_dict(req.memoryState)

    screen, fp_used = None, None
    client = _http_client()
    dendrites = req.dendrites
    unlock_d = None
    if not dendrites and req.symbol:
        sym = _clean_sym(req.symbol)
        screen = await _screen_v2_result(client, sym)
        if req.fpState and req.fpState.get("ok"):
            fp_used = req.fpState
        else:
            try:
                fp_payload = await market_data.fetch_symbol_klines(client, sym, 120)
                fp_used = fokker_planck.analyze_candles_fp(fp_payload.get("candles") or [])
            except Exception:  # noqa: BLE001 — fp gagal = dendrite fp netral
                fp_used = None
        unlock_d = await _unlock_dendrite(client, sym)
        dendrites = build_dendrites(screen=screen, fp=fp_used, unlock=unlock_d)
    dendrites = dendrites or {}

    pred = neuron.predict(dendrites)
    ep = memory.record_episode(req.symbol or "?", dendrites, pred["y"], pred["verdict"])
    return {
        "ok": True,
        "prediction": pred,
        "episode": ep,
        "trust": memory.pattern_trust(dendrites),
        "screen": screen,
        "fpUsed": bool(fp_used and fp_used.get("ok")),
        "unlockDendrite": unlock_d,
        "neuronState": neuron.to_dict(),
        "memoryState": memory.to_dict(),
    }


@app.post("/api/neuron/episode/close")
async def neuron_episode_close(req: NeuronCloseRequest):
    """Tutup episode + belajar online (RMSProp + surprise gate)."""
    ep_in = req.episode or {}
    if not ep_in.get("id"):
        raise HTTPException(status_code=400, detail="body wajib: {episode: {id, dendrites, ...}, realizedReturn}")
    memory = NeuronMemory.from_dict(req.memoryState)
    try:
        ep = memory.close_episode(str(ep_in["id"]), float(req.realizedReturn))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    learn, neuron_state = None, None
    if req.neuronState is not None and ep_in.get("dendrites"):
        neuron = Neuron.from_dict(req.neuronState)
        learn = neuron.update(ep_in["dendrites"], float(req.realizedReturn))
        neuron_state = neuron.to_dict()

    return {
        "ok": True, "episode": ep, "learning": learn,
        "stats": memory.stats(),
        "neuronState": neuron_state,
        "memoryState": memory.to_dict(),
    }


@app.post("/api/neuron/refit")
async def neuron_refit(req: NeuronRefitRequest):
    """Guru offline: refit dari episode CLOSED. Hasil = USULAN, bukan pemasangan."""
    memory = NeuronMemory.from_dict(req.memoryState)
    neuron = Neuron.from_dict(req.neuronState)
    proposal = neuron_logistic.propose(neuron.weights, memory.closed_episodes())
    return {"ok": True, "proposal": proposal}


@app.post("/api/neuron/validate")
async def neuron_validate(req: NeuronValidateRequest):
    """Weight-lab gate: mutlak (Brier/AUC/precision Wilson) + relatif vs baseline.
    NB: `episodes` adalah ATRIBUT list di NeuronMemory (bukan method) —
    weight_lab._build_data menyaring sendiri episode CLOSED yang layak."""
    memory = NeuronMemory.from_dict(req.memoryState)
    candidate = req.candidateWeights or Neuron.from_dict(req.neuronState).weights
    result = weight_lab.evaluate(candidate, memory.episodes, baseline_weights=req.baselineWeights)
    return {"ok": True, "evaluation": result}


@app.post("/api/neuron/stats")
async def neuron_stats(req: NeuronStatsRequest):
    memory = NeuronMemory.from_dict(req.memoryState)
    return {"ok": True, "stats": memory.stats(), "trustedPatterns": memory.trusted_patterns()}


# ---------------------------------------------------------------------------
# Static frontend (opsional — kalau frontend/build ada, dilayani di /)
# ---------------------------------------------------------------------------

if FRONTEND_BUILD.is_dir():
    _assets = FRONTEND_BUILD / "static"
    if _assets.is_dir():
        app.mount("/static", StaticFiles(directory=str(_assets)), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        candidate = (FRONTEND_BUILD / full_path).resolve()
        if full_path and candidate.is_file() and str(candidate).startswith(str(FRONTEND_BUILD.resolve())):
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_BUILD / "index.html"))
